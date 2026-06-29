from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.conditions import CONDITIONS, DEFAULT_CONDITIONS
from eval.task_level.execution import count_jsonl_records, execute_pilot, run_artifact_integrity, serialize_run_results_jsonl, write_run_progress
from eval.task_level.report import bootstrap_delta_ci, write_report
from eval.task_level.runner import load_tasks, run_smoke
from eval.task_level.runners.base import RunnerCapabilities
from eval.task_level.schemas import TASKS_PATH


def test_manifest_has_required_pilot_shape():
    tasks = load_tasks(TASKS_PATH)

    assert len(tasks) == 18
    assert sum(1 for task in tasks if task.suite == "comparable") == 5
    assert sum(1 for task in tasks if task.suite == "differentiation") == 13
    assert {task.task_type for task in tasks} == {"curated", "real"}


def test_conditions_encode_tool_isolation():
    assert not CONDITIONS["repo_only"].tool_policy.allow_docatlas
    assert not CONDITIONS["repo_only"].tool_policy.allow_context7
    assert not CONDITIONS["repo_only_strict_offline"].tool_policy.allow_docatlas
    assert not CONDITIONS["repo_only_strict_offline"].tool_policy.allow_web
    assert CONDITIONS["repo_only_web_audited"].tool_policy.allow_web
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


class FailingRunner:
    runner_id = "failing"

    def verify(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            runner_id="failing",
            version="test",
            structured_trajectory=False,
            patch_capture=False,
            tool_isolation=False,
            mcp_isolation=False,
            shell_network_isolation=False,
            token_usage=False,
            independent_process=False,
            verified=False,
        )

    def run(self, request):
        raise NotImplementedError("runner unavailable in test")


def test_execute_pilot_records_runner_blocked_rows(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("eval.task_level.execution.RESULTS_ROOT", tmp_path)
    task = next(task for task in load_tasks(TASKS_PATH) if task.task_id == "decisive_docmancer_vector_timeout_fallback_001")

    results = execute_pilot(
        [task],
        ["repo_only_strict_offline"],
        repeats=1,
        run_id="runner_blocked",
        runner=FailingRunner(),
        model="test",
        timeout_seconds=1,
        prompt_template="Issue:\n{issue_text}",
    )

    assert len(results) == 1
    result = results[0]
    assert result["status"] == "runner_unavailable"
    assert result["resolved"] is False
    assert result["constraint_violations_after_patch"] == 0
    assert (tmp_path / "runner_blocked" / "runs.jsonl").exists()
    run_dir = tmp_path / "runner_blocked" / task.task_id / "repo_only_strict_offline" / "repeat_0"
    assert json.loads((run_dir / "changed_files.json").read_text(encoding="utf-8")) == []
    assert (run_dir / "patch.diff").read_text(encoding="utf-8") == ""
    assert json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))["constraint_validation"]["violated"] == 0


def test_report_summarizes_runner_unavailable_failures(tmp_path: Path):
    report = write_report(
        tmp_path,
        metadata={"environment": {}, "executive_result": "test"},
        results=[{
            "task_id": "t",
            "condition_id": "repo_only_strict_offline",
            "repeat": 0,
            "status": "runner_unavailable",
            "resolved": False,
            "public_tests_passed": False,
            "hidden_tests_passed": False,
            "policy_clean": False,
            "metrics": {},
            "docatlas": {},
            "contract": {},
            "actionability": {},
        }],
    )

    text = report.read_text(encoding="utf-8")
    assert "1 run(s) did not produce patches" in text
