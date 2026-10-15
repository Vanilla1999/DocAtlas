from __future__ import annotations

import hashlib
import json
import signal
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval.task_level.execution import (
    TASK33C_REQUIRED_TARGET_PATHS,
    _bounded_direct_projection_errors,
    _estimate_tokens,
    _host_evidence_categories,
    build_bounded_direct_packet,
    capture_task33_host_evidence,
    evaluate_agent_patch,
    prepare_docatlas,
    trajectory_evidence_metrics,
    trajectory_tool_output_metrics,
)
from eval.task_level.fixtures.builder import materialize_fixture
from eval.task_level.isolated_delivery import IsolatedDeliveryError
from eval.task_level.runner import load_tasks, run_smoke
from eval.task_level.runners.base import AgentRunOutput
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)




def _runner_output(tmp_path: Path, *, input_tokens: int | None = 100) -> AgentRunOutput:
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
        input_tokens=input_tokens,
        output_tokens=20,
        model="mock",
        runner_version="mock",
        token_usage={"cached_input_tokens": 60, "reasoning_tokens": 5, "completed_turn_events": 2},
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
    assert result["metrics"]["cached_input_tokens"] == 60
    assert result["metrics"]["uncached_input_tokens"] == 40
    assert result["metrics"]["reasoning_tokens"] == 5
    assert result["metrics"]["completed_turn_events"] == 2
    assert result["token_attribution"]["system_total_tokens"] == 120


def test_current_index_setup_tokens_are_not_charged_to_agent_budget(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    out = tmp_path / "pilot" / task.task_id / "docatlas_snippet_first" / "repeat_0"
    out.mkdir(parents=True)
    materialize_fixture(task, workspace)
    (out / "docatlas_preparation.json").write_text(json.dumps({
        "status": "already_current",
        "index_revision": "current-index",
        "provider_input_tokens": 99_999,
        "provider_output_tokens": 99_999,
        "wall_time_seconds": 0.1,
    }))
    runner_output = _runner_output(out)

    result = evaluate_agent_patch(
        task,
        workspace,
        out,
        "docatlas_snippet_first",
        runner_output.trajectory_path,
        runner_output,
    )

    assert result["metrics"]["input_tokens"] == 100
    assert result["budget"]["measured_input_tokens"] == 100
    assert result["budget"]["indexing_provider_tokens_included"] is False
    assert result["token_attribution"]["indexing"] == {
        "status": "already_current",
        "provider_input_tokens": 99_999,
        "provider_output_tokens": 99_999,
        "included_in_parent_budget": False,
    }


def test_missing_provider_usage_does_not_claim_provider_reported_token_basis(
    tmp_path: Path,
):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    out = tmp_path / "pilot" / task.task_id / "repo_only" / "repeat_0"
    out.mkdir(parents=True)
    materialize_fixture(task, workspace)
    runner_output = _runner_output(out, input_tokens=None)

    result = evaluate_agent_patch(
        task,
        workspace,
        out,
        "repo_only",
        runner_output.trajectory_path,
        runner_output,
    )

    assert result["budget"]["measured_input_tokens"] is None
    assert result["budget"]["input_token_basis"] is None








def test_each_run_uses_fresh_workspace(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    a = tmp_path / "a"
    b = tmp_path / "b"

    materialize_fixture(task, a)
    materialize_fixture(task, b)

    assert a != b
    assert (a / ".git").exists()
    assert (b / ".git").exists()




