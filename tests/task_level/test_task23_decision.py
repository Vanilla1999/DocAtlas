from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eval.task_level.analysis.task23_decision import apply_protocol_amendment, evaluate_predeclared_rule, validate_protocol
from eval.task_level.fixtures.builder import fixture_hash


REQUIRED_CONDITIONS = [
    "repo_only_strict_offline",
    "repo_plus_audited_external_context",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _protocol(*, domains: list[str] | None = None, repeats: int = 3) -> dict:
    return {
        "schema_version": "task23-protocol-1",
        "frozen_before_results": True,
        "tasks": [
            {
                "task_id": f"task_{index}",
                "source_project": domain,
                "domain": domain,
                "fixture_hash": "a" * 64,
                "oracle_sha256": "b" * 64,
                "external_context_sha256": "c" * 64,
            }
            for index, domain in enumerate(domains or ["nbo", "help_chat", "viscanner"], start=1)
        ],
        "conditions": REQUIRED_CONDITIONS,
        "repeats_per_task_condition": repeats,
        "controls": {
            "same_model": True,
            "same_prompt_policy": True,
            "same_context_limits": True,
            "same_attempt_budget": True,
            "same_starting_state": True,
        },
        "decision_rule": {
            "resolved_rate_improvement_min": 0.10,
            "median_total_tokens_increase_max": 0.10,
            "resolved_rate_equivalence_margin": 0.02,
            "median_total_tokens_reduction_min": 0.25,
            "median_latency_increase_max": 0.10,
            "confidence_level": 0.95,
            "fail_closed_on_missing_metrics": True,
        },
    }


def _rows(*, doc_resolved: list[bool], base_resolved: list[bool], doc_tokens: int, base_tokens: int, doc_latency: float, base_latency: float) -> list[dict]:
    rows: list[dict] = []
    for index, (base, doc) in enumerate(zip(base_resolved, doc_resolved, strict=True)):
        task_id = f"task_{index // 3}"
        repeat = index % 3
        rows.extend(
            [
                {"task_id": task_id, "repeat": repeat, "condition_id": "repo_only_strict_offline", "resolved": base, "total_tokens": base_tokens, "wall_time_seconds": base_latency},
                {"task_id": task_id, "repeat": repeat, "condition_id": "docatlas_tool_recommended", "resolved": doc, "total_tokens": doc_tokens, "wall_time_seconds": doc_latency},
            ]
        )
    return rows


def test_protocol_requires_three_independent_domains_four_lanes_and_three_repeats():
    errors = validate_protocol(_protocol(domains=["nbo", "help_chat"], repeats=2))

    assert "at_least_three_independent_domains_required" in errors
    assert "at_least_three_repeats_required" in errors


def test_frozen_protocol_matches_fixture_oracle_and_context_artifacts():
    protocol = json.loads((PROJECT_ROOT / "eval/task_level/task23_protocol.json").read_text())

    assert validate_protocol(protocol) == []
    for task in protocol["tasks"]:
        task_id = task["task_id"]
        assert fixture_hash(PROJECT_ROOT / "eval/task_level/fixtures/templates" / task_id) == task["fixture_hash"]
        for field, path in (
            ("oracle_sha256", PROJECT_ROOT / "eval/task_level/oracles" / f"{task_id}.patch"),
            ("external_context_sha256", PROJECT_ROOT / "eval/task_level/external_context" / f"{task_id}.json"),
        ):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == task[field]


def test_protocol_amendment_replaces_only_screening_rejection_without_changing_rules():
    protocol = _protocol()
    protocol["protocol_id"] = "task23-test"
    amendment = {
        "schema_version": "task23-protocol-amendment-1",
        "base_protocol_id": "task23-test",
        "frozen_before_replacement_results": True,
        "reason": "predeclared_screening_exclusion",
        "excluded_task_id": "task_1",
        "excluded_screening_status": "rejected_too_easy",
        "replacement_task": {
            "task_id": "task_replacement",
            "source_project": "project_replacement",
            "domain": "domain_replacement",
            "fixture_hash": "d" * 64,
            "oracle_sha256": "e" * 64,
            "external_context_sha256": "f" * 64,
        },
        "conditions_unchanged": True,
        "decision_rule_unchanged": True,
    }

    effective = apply_protocol_amendment(protocol, amendment)

    assert [task["task_id"] for task in effective["tasks"]] == ["task_2", "task_3", "task_replacement"]
    assert effective["conditions"] == protocol["conditions"]
    assert effective["decision_rule"] == protocol["decision_rule"]


def test_checked_in_protocol_amendment_matches_replacement_artifacts():
    protocol_path = PROJECT_ROOT / "eval/task_level/task23_protocol.json"
    amendment_path = PROJECT_ROOT / "eval/task_level/task23_protocol_amendment_001.json"
    protocol = json.loads(protocol_path.read_text())
    amendment = json.loads(amendment_path.read_text())

    assert amendment["base_protocol_sha256"] == hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    screening = PROJECT_ROOT / "eval/task_level/task23_screening_001.json"
    assert amendment["screening_results_sha256"] == hashlib.sha256(screening.read_bytes()).hexdigest()

    effective = apply_protocol_amendment(protocol, amendment)
    replacement = amendment["replacement_task"]
    task_id = replacement["task_id"]
    assert fixture_hash(PROJECT_ROOT / "eval/task_level/fixtures/templates" / task_id) == replacement["fixture_hash"]
    assert hashlib.sha256((PROJECT_ROOT / "eval/task_level/oracles" / f"{task_id}.patch").read_bytes()).hexdigest() == replacement["oracle_sha256"]
    assert hashlib.sha256((PROJECT_ROOT / "eval/task_level/external_context" / f"{task_id}.json").read_bytes()).hexdigest() == replacement["external_context_sha256"]
    assert task_id in {task["task_id"] for task in effective["tasks"]}


@pytest.mark.parametrize("field", ["conditions_unchanged", "decision_rule_unchanged", "frozen_before_replacement_results"])
def test_protocol_amendment_fails_closed_when_frozen_rules_can_drift(field: str):
    protocol = _protocol()
    protocol["protocol_id"] = "task23-test"
    amendment = {
        "schema_version": "task23-protocol-amendment-1",
        "base_protocol_id": "task23-test",
        "frozen_before_replacement_results": True,
        "reason": "predeclared_screening_exclusion",
        "excluded_task_id": "task_1",
        "excluded_screening_status": "rejected_too_easy",
        "replacement_task": {
            "task_id": "task_replacement",
            "source_project": "project_replacement",
            "domain": "domain_replacement",
            "fixture_hash": "d" * 64,
            "oracle_sha256": "e" * 64,
            "external_context_sha256": "f" * 64,
        },
        "conditions_unchanged": True,
        "decision_rule_unchanged": True,
    }
    amendment[field] = False

    with pytest.raises(ValueError, match=field):
        apply_protocol_amendment(protocol, amendment)


def test_protocol_rejects_lane_or_control_drift():
    protocol = _protocol()
    protocol["conditions"] = ["repo_only_strict_offline", "docatlas_tool_recommended"]
    protocol["controls"]["same_model"] = False

    errors = validate_protocol(protocol)

    assert "required_condition_matrix_mismatch" in errors
    assert "controlled_comparison_invariant_missing:same_model" in errors


def test_protocol_requires_immutable_fixture_oracle_and_external_context_hashes():
    protocol = _protocol()
    del protocol["tasks"][1]["fixture_hash"]
    protocol["tasks"][2]["oracle_sha256"] = "not-a-sha"

    errors = validate_protocol(protocol)

    assert "immutable_task_artifact_missing:task_2:fixture_hash" in errors
    assert "immutable_task_artifact_missing:task_3:oracle_sha256" in errors


def test_quality_threshold_requires_confidence_interval_to_clear_ten_points():
    rows = _rows(
        base_resolved=[False] * 12,
        doc_resolved=[True] * 12,
        base_tokens=1000,
        doc_tokens=1050,
        base_latency=100,
        doc_latency=105,
    )

    result = evaluate_predeclared_rule(rows, protocol=_protocol())

    assert result["decision"] == "CONTINUE"
    assert result["threshold_met"] == "resolved_rate"
    assert result["uncertainty"]["resolved_rate_delta"]["lower"] >= 0.10


def test_token_efficiency_threshold_accepts_equivalent_success_with_lower_cost():
    resolved = [True, False] * 6
    rows = _rows(
        base_resolved=resolved,
        doc_resolved=resolved,
        base_tokens=1000,
        doc_tokens=700,
        base_latency=100,
        doc_latency=105,
    )

    result = evaluate_predeclared_rule(rows, protocol=_protocol())

    assert result["decision"] == "CONTINUE"
    assert result["threshold_met"] == "token_efficiency"
    assert result["uncertainty"]["token_change_ratio"]["upper"] <= -0.25


def test_decision_fails_closed_when_metrics_or_repeats_are_incomplete():
    rows = _rows(
        base_resolved=[False, False],
        doc_resolved=[True, True],
        base_tokens=1000,
        doc_tokens=900,
        base_latency=100,
        doc_latency=90,
    )
    rows[0]["total_tokens"] = None

    result = evaluate_predeclared_rule(rows, protocol=_protocol())

    assert result["decision"] == "INCONCLUSIVE"
    assert "incomplete_task_repeat_matrix" in result["reasons"]
    assert "missing_total_tokens" in result["reasons"]


def test_token_change_uses_condition_medians_not_mean_of_pair_ratios():
    rows = _rows(
        base_resolved=[False, False, False],
        doc_resolved=[False, False, False],
        base_tokens=100,
        doc_tokens=90,
        base_latency=100,
        doc_latency=100,
    )
    baseline = next(row for row in rows if row["condition_id"] == "repo_only_strict_offline" and row["repeat"] == 2)
    candidate = next(row for row in rows if row["condition_id"] == "docatlas_tool_recommended" and row["repeat"] == 2)
    baseline["total_tokens"] = 1000
    candidate["total_tokens"] = 2000

    result = evaluate_predeclared_rule(rows, protocol=_protocol())

    assert result["uncertainty"]["token_change_ratio"]["estimate"] == -0.10


def test_protocol_rejects_changed_predeclared_numeric_rule():
    protocol = _protocol()
    protocol["decision_rule"]["resolved_rate_improvement_min"] = 0.09

    with pytest.raises(ValueError, match="predeclared_decision_rule_mismatch"):
        evaluate_predeclared_rule([], protocol=protocol)
