from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from eval.task_level.execution import evaluate_agent_patch
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
