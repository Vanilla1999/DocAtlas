from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.analysis.cost_accuracy import (
    NormalizedRun,
    compute_condition_metrics,
    compute_context_utilization,
    compute_paired_deltas,
    detect_policy_positive_cases,
    parse_run_directory,
    summarize_cost_accuracy,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    *,
    run_id: str = "pilot_001",
    task_id: str = "task_a",
    condition_id: str = "repo_only_strict_offline",
    repeat: int = 0,
    resolved: bool = False,
    hidden: bool = False,
    policy_clean: bool = True,
    network_attempts: int = 0,
    input_tokens=None,
    output_tokens=None,
    wall_time_seconds=None,
    docatlas_calls: int = 0,
    context_used: bool = False,
    checklist_used: bool = False,
    forbidden_changes: list[str] | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "condition_id": condition_id,
        "repeat": repeat,
        "status": "completed",
        "resolved": resolved,
        "public_tests_passed": True,
        "hidden_tests_passed": hidden,
        "policy_clean": policy_clean,
        "policy": {"network_attempts": network_attempts},
        "metrics": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "wall_time_seconds": wall_time_seconds,
            "agent_docatlas_calls": docatlas_calls,
            "harness_docatlas_calls": 0,
        },
        "docatlas": {
            "agent_calls": docatlas_calls,
            "harness_calls": 0,
            "context_used": context_used,
            "fallback_used": False,
            "docatlas_retrieval_status": "success" if context_used else None,
            "vector_indexing_timed_out": False,
        },
        "actionability": {"action_checklist_used": checklist_used},
        "contract": {
            "behavioral_contract_score": 1.0 if resolved else 0.0,
            "project_convention_score": 0.5,
            "version_contract_score": None,
            "generated_file_contract_score": None,
        },
        "forbidden_changes": forbidden_changes or [],
    }


def test_cost_accuracy_parser_handles_missing_tokens(tmp_path: Path):
    run_dir = tmp_path / "pilot_missing_tokens_001"
    run_dir.mkdir()
    _write_jsonl(run_dir / "runs.jsonl", [_row(input_tokens=None, output_tokens=None)])

    parsed = parse_run_directory(run_dir)

    assert parsed.artifact_integrity_warning is None
    assert parsed.records[0].input_tokens is None
    assert parsed.records[0].output_tokens is None
    assert parsed.records[0].total_tokens is None


def test_cost_accuracy_parser_rejects_inconsistent_artifacts(tmp_path: Path):
    run_dir = tmp_path / "pilot_inconsistent_001"
    run_dir.mkdir()
    _write_jsonl(run_dir / "runs.jsonl", [_row()])
    (run_dir / "status.json").write_text(json.dumps({"artifact_integrity": {"runs_jsonl_records": 2}}), encoding="utf-8")

    parsed = parse_run_directory(run_dir)

    assert parsed.artifact_integrity_warning == "runs_jsonl_record_count_mismatch"


def test_paired_delta_uses_same_task_and_repeat():
    records = [
        NormalizedRun(run_id="pilot_a", run_family="pilot", task_id="task_a", condition_id="repo_only_strict_offline", repeat=0, resolved=False, hidden_tests=False, policy_clean=True, input_tokens=100, output_tokens=10, total_tokens=110, wall_time_seconds=10),
        NormalizedRun(run_id="pilot_a", run_family="pilot", task_id="task_a", condition_id="docatlas_tool_recommended", repeat=0, resolved=True, hidden_tests=True, policy_clean=True, input_tokens=200, output_tokens=20, total_tokens=220, wall_time_seconds=15),
        NormalizedRun(run_id="pilot_a", run_family="pilot", task_id="task_a", condition_id="docatlas_tool_recommended", repeat=1, resolved=True, hidden_tests=True, policy_clean=True, input_tokens=999, output_tokens=1, total_tokens=1000, wall_time_seconds=1),
    ]

    deltas = compute_paired_deltas(records)

    pair = deltas["docatlas_tool_recommended - repo_only_strict_offline"]
    assert pair["pairs"] == 1
    assert pair["resolved_delta_mean"] == 1.0
    assert pair["total_token_delta_median"] == 110


def test_tokens_per_resolved_handles_zero_denominator():
    metrics = compute_condition_metrics([NormalizedRun(run_id="r", run_family="pilot", task_id="t", condition_id="repo_only_strict_offline", repeat=0, total_tokens=100, resolved=False)])

    assert metrics["repo_only_strict_offline"]["tokens_per_resolved_task"] is None
    assert metrics["repo_only_strict_offline"]["tokens_per_policy_clean_resolved_task"] is None


def test_condition_metrics_separate_smoke_from_accepted():
    records = [
        NormalizedRun(run_id="r", run_family="pilot", task_id="accepted", condition_id="repo_only_strict_offline", repeat=0, task_role="accepted", resolved=True, hidden_tests=True),
        NormalizedRun(run_id="r", run_family="pilot", task_id="smoke", condition_id="repo_only_strict_offline", repeat=0, task_role="smoke", resolved=False, hidden_tests=False),
    ]

    accepted = compute_condition_metrics(records, task_role_filter={"accepted"})
    smoke = compute_condition_metrics(records, task_role_filter={"smoke", "rejected_too_easy"})

    assert accepted["repo_only_strict_offline"]["runs"] == 1
    assert accepted["repo_only_strict_offline"]["resolved_rate"] == 1.0
    assert smoke["repo_only_strict_offline"]["runs"] == 1
    assert smoke["repo_only_strict_offline"]["resolved_rate"] == 0.0


def test_policy_positive_detects_repo_only_network_violation():
    records = [
        NormalizedRun(run_id="p", run_family="pilot", task_id="task_a", condition_id="repo_only_strict_offline", repeat=0, resolved=True, policy_clean=False, network_attempts=1),
        NormalizedRun(run_id="p", run_family="pilot", task_id="task_a", condition_id="docatlas_tool_recommended", repeat=0, resolved=True, policy_clean=True, network_attempts=0),
    ]

    cases = detect_policy_positive_cases(records)

    assert cases[0]["policy_interpretation"] == "DocAtlas solved policy-clean where repo_only violated no-web policy"


def test_context_utilization_rates_ignore_non_docatlas_conditions():
    records = [
        NormalizedRun(run_id="p", run_family="pilot", task_id="task_a", condition_id="repo_only_strict_offline", repeat=0, context_used=True),
        NormalizedRun(run_id="p", run_family="pilot", task_id="task_a", condition_id="docatlas_tool_recommended", repeat=0, agent_docatlas_calls=2, context_used=True, resolved=True),
    ]

    rates = compute_context_utilization(records)

    assert "repo_only_strict_offline" not in rates
    assert rates["docatlas_tool_recommended"]["docatlas_call_rate"] == 1.0
    assert rates["docatlas_tool_recommended"]["context_used_rate"] == 1.0


def test_cost_accuracy_summary_has_verdict():
    summary = summarize_cost_accuracy(
        condition_metrics={
            "repo_only_strict_offline": {"resolved_rate": 0.0, "policy_clean_resolved_rate": 0.0, "median_total_tokens": 100, "median_wall_time_seconds": 10},
            "docatlas_tool_recommended": {"resolved_rate": 0.0, "policy_clean_resolved_rate": 0.0, "median_total_tokens": 200, "median_wall_time_seconds": 20},
        },
        paired_deltas={},
        context_utilization={},
    )

    assert summary["verdict"] in {
        "EFFICIENT_POSITIVE",
        "QUALITY_POSITIVE_COSTLY",
        "POLICY_POSITIVE",
        "COST_ONLY_POSITIVE",
        "NO_MEASURABLE_GAIN",
        "INCONCLUSIVE",
    }


def test_injected_context_tokens_are_reported_when_available(tmp_path: Path):
    run_dir = tmp_path / "pilot_context_tokens_001"
    run_dir.mkdir()
    row = _row(condition_id="docatlas_context_injected", context_used=True)
    row["metrics"]["injected_context_tokens"] = 321
    _write_jsonl(run_dir / "runs.jsonl", [row])

    parsed = parse_run_directory(run_dir)
    metrics = compute_condition_metrics(parsed.records)

    assert parsed.records[0].injected_context_tokens == 321
    assert metrics["docatlas_context_injected"]["median_injected_context_tokens"] == 321


def test_checklist_tokens_are_reported_when_available(tmp_path: Path):
    run_dir = tmp_path / "pilot_checklist_tokens_001"
    run_dir.mkdir()
    row = _row(condition_id="docatlas_action_checklist_injected", checklist_used=True)
    row["actionability"]["checklist_tokens"] = 77
    _write_jsonl(run_dir / "runs.jsonl", [row])

    parsed = parse_run_directory(run_dir)
    metrics = compute_condition_metrics(parsed.records)

    assert parsed.records[0].checklist_tokens == 77
    assert metrics["docatlas_action_checklist_injected"]["median_checklist_tokens"] == 77


def test_fallback_success_is_not_counted_as_vector_success(tmp_path: Path):
    run_dir = tmp_path / "pilot_fallback_001"
    run_dir.mkdir()
    row = _row(condition_id="docatlas_context_injected", context_used=True)
    row["docatlas"].update({
        "fallback_used": True,
        "fallback_source": "visible_fixture_project_docs",
        "docatlas_retrieval_status": "fallback_local_project_context",
        "docatlas_fallback_success": True,
    })
    _write_jsonl(run_dir / "runs.jsonl", [row])

    rates = compute_context_utilization(parse_run_directory(run_dir).records)

    assert rates["docatlas_context_injected"]["retrieval_success_rate"] == 0.0
    assert rates["docatlas_context_injected"]["fallback_success_rate"] == 1.0


def test_workflow_success_separated_from_retrieval_success(tmp_path: Path):
    run_dir = tmp_path / "pilot_workflow_001"
    run_dir.mkdir()
    row = _row(condition_id="docatlas_context_injected", context_used=False, resolved=True, policy_clean=True)
    row["docatlas"].update({"docatlas_retrieval_status": "success", "docatlas_tool_success": True})
    _write_jsonl(run_dir / "runs.jsonl", [row])

    records = parse_run_directory(run_dir).records
    rates = compute_context_utilization(records)
    metrics = compute_condition_metrics(records)

    assert rates["docatlas_context_injected"]["retrieval_success_rate"] == 1.0
    assert rates["docatlas_context_injected"]["workflow_success_rate"] == 0.0
    assert metrics["docatlas_context_injected"]["workflow_success_rate"] == 1.0


def test_constraint_packet_tokens_in_condition_metrics():
    metrics = compute_condition_metrics([
        NormalizedRun(
            run_id="r",
            run_family="pilot",
            task_id="t",
            condition_id="docatlas_patch_constraints_injected",
            repeat=0,
            constraint_packet_tokens=456,
        )
    ])

    assert metrics["docatlas_patch_constraints_injected"]["median_constraint_packet_tokens"] == 456
