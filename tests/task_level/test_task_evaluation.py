from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from eval.task_level.execution import evaluate_agent_patch, trajectory_evidence_metrics, trajectory_tool_output_metrics
from eval.task_level.fixtures.builder import materialize_fixture
from eval.task_level.runner import load_tasks, run_smoke
from eval.task_level.runners.base import AgentRunOutput
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)


def _runner_output(tmp_path: Path) -> AgentRunOutput:
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([]), encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    return AgentRunOutput(
        status="completed",
        exit_code=0,
        started_at=now,
        finished_at=now,
        wall_time_seconds=0.1,
        raw_stdout_path=str(tmp_path / "stdout.log"),
        raw_stderr_path=str(tmp_path / "stderr.log"),
        trajectory_path=str(trajectory),
        patch_path=None,
        tool_calls=[],
        input_tokens=None,
        output_tokens=None,
        model="mock",
        runner_version="mock",
        notes=[],
    )


def test_resolved_requires_public_and_hidden_tests(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    out = tmp_path / "pilot" / task.task_id / "repo_only" / "repeat_0"
    out.mkdir(parents=True)
    materialize_fixture(task, workspace)
    (workspace / "src/app/main.py").write_text((workspace / "src/app/main.py").read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")

    result = evaluate_agent_patch(task, workspace, out, "repo_only", _runner_output(out).trajectory_path, _runner_output(out))

    assert not result["resolved"]
    assert result["patch_path"]
    assert result["hidden_tests_passed"] is False
    assert result["budget"]["max_input_tokens"] == task.max_input_tokens
    assert result["budget"]["max_turns_enforced_by_runner"] is False


def test_each_run_uses_fresh_workspace(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    a = tmp_path / "a"
    b = tmp_path / "b"

    materialize_fixture(task, a)
    materialize_fixture(task, b)

    assert a != b
    assert (a / ".git").exists()
    assert (b / ".git").exists()


def test_smoke_results_remain_non_causal(tmp_path: Path):
    tasks = load_tasks(TASKS_PATH)
    results = run_smoke(tasks, ["repo_only", "docatlas_snippet_first"], repeats=1, run_dir=tmp_path)

    assert {result["status"] for result in results} == {"smoke_not_causal"}
    assert not any(result["resolved"] for result in results)


def test_trajectory_evidence_metrics_measure_recall_and_first_observation_rank(tmp_path: Path):
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(json.dumps([
        {"sequence": 1, "arguments": {"command": "read docs/policy.md"}, "result_summary": "policy"},
        {"sequence": 2, "arguments": {"command": "inspect src"}, "result_summary": "PermissionService owns the gate"},
    ]))
    task = SimpleNamespace(expected_symbols=["PermissionService", "MissingSymbol"], expected_project_docs=["docs/policy.md"])

    metrics = trajectory_evidence_metrics(task, trajectory)

    assert metrics == {
        "required_evidence_total": 3,
        "required_evidence_found": 2,
        "required_evidence_recall": 2 / 3,
        "first_required_evidence_rank": 1,
    }


def test_tool_output_metrics_use_measured_chars_and_do_not_alias_recall():
    task = SimpleNamespace(expected_symbols=["PermissionService"], expected_project_docs=[])
    calls = [
        {"tool_name": "get_docs_context", "result_summary": "PermissionService owns the gate", "result_chars": 32},
        {"tool_name": "Bash", "result_summary": "unrelated test output", "result_chars": 20},
    ]

    metrics = trajectory_tool_output_metrics(task, calls)

    assert metrics["tool_output_chars"] == 52
    assert metrics["tool_output_tokens_estimate"] == 13
    assert metrics["docs_context_output_chars"] == 32
    assert metrics["docs_output_evidence_coverage"] == 1.0
    assert metrics["docs_output_evidence_found"] == 1
    assert metrics["useful_context_ratio"] is None
    assert metrics["useful_context_ratio_method"] == "not_measured_without_chunk_usage_attribution"
