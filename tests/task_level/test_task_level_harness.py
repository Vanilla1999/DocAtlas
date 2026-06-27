from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.conditions import CONDITIONS, DEFAULT_CONDITIONS
from eval.task_level.execution import count_jsonl_records, run_artifact_integrity, serialize_run_results_jsonl, write_run_progress
from eval.task_level.report import bootstrap_delta_ci
from eval.task_level.runner import load_tasks, run_smoke
from eval.task_level.schemas import TASKS_PATH


def test_manifest_has_required_pilot_shape():
    tasks = load_tasks(TASKS_PATH)

    assert len(tasks) == 9
    assert sum(1 for task in tasks if task.suite == "comparable") == 5
    assert sum(1 for task in tasks if task.suite == "differentiation") == 4
    assert {task.task_type for task in tasks} == {"curated", "real"}


def test_conditions_encode_tool_isolation():
    assert not CONDITIONS["repo_only"].tool_policy.allow_docatlas
    assert not CONDITIONS["repo_only"].tool_policy.allow_context7
    assert CONDITIONS["context7"].tool_policy.allow_context7
    assert not CONDITIONS["context7"].tool_policy.allow_docatlas
    assert CONDITIONS["docatlas_evidence_first"].tool_policy.allow_docatlas
    assert CONDITIONS["docatlas_evidence_first"].tool_policy.docatlas_response_style == "evidence-first"
    assert CONDITIONS["docatlas_snippet_first"].tool_policy.docatlas_response_style == "snippet-first"
    assert CONDITIONS["docatlas_tool_recommended"].tool_policy.recommend_docatlas_before_edit
    assert not CONDITIONS["docatlas_tool_recommended"].tool_policy.require_docatlas_call_before_edit


def test_smoke_results_are_explicitly_not_causal(tmp_path: Path):
    tasks = load_tasks(TASKS_PATH)
    results = run_smoke(tasks, list(DEFAULT_CONDITIONS), repeats=1, run_dir=tmp_path)

    assert results
    assert {result["status"] for result in results} == {"smoke_not_causal"}
    assert not any(result["resolved"] for result in results)


def test_bootstrap_delta_ci_is_paired_and_directional():
    ci = bootstrap_delta_ci([True, True, False, True], [True, False, False, False])
    assert ci is not None
    observed, low, high = ci
    assert observed == 0.5
    assert low <= observed <= high


def _sample_run_result(index: int) -> dict[str, object]:
    return {
        "run_id": "artifact_test",
        "task_id": f"task_{index // 4}",
        "condition_id": f"condition_{index % 4}",
        "repeat": 0,
        "status": "completed",
        "resolved": index % 2 == 0,
        "public_tests_passed": True,
        "hidden_tests_passed": index % 2 == 0,
        "policy_clean": True,
        "metrics": {"wall_time_seconds": float(index)},
        "docatlas": {"agent_calls": 0, "context_used": False},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
    }


def test_run_jsonl_serialization_has_one_physical_line_per_record(tmp_path: Path):
    results = [_sample_run_result(index) for index in range(8)]
    text = serialize_run_results_jsonl(results)

    assert text.endswith("\n")
    assert text.count("\n") == 8

    path = tmp_path / "runs.jsonl"
    path.write_text(text, encoding="utf-8")
    assert count_jsonl_records(path) == 8


def test_write_run_progress_records_artifact_integrity(tmp_path: Path):
    results = [_sample_run_result(index) for index in range(8)]

    write_run_progress(tmp_path, results, total_runs=8, current=None, finished=True)

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "finished"
    assert status["completed_runs"] == 8
    assert status["artifact_integrity"] == {
        "finished": True,
        "in_memory_results": 8,
        "expected_total_runs": 8,
        "ok": True,
        "reason": None,
        "runs_jsonl_records": 8,
    }
    assert count_jsonl_records(tmp_path / "runs.jsonl") == 8


def test_finished_progress_marks_incomplete_artifacts_failed(tmp_path: Path):
    results = [_sample_run_result(index) for index in range(7)]

    write_run_progress(tmp_path, results, total_runs=8, current=None, finished=True)

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "artifact_integrity_failed"
    assert status["artifact_integrity"]["ok"] is False
    assert status["artifact_integrity"]["reason"] == ["finished_before_expected_run_count"]
    assert run_artifact_integrity(tmp_path, in_memory_results=7, total_runs=8, finished=True)["ok"] is False
