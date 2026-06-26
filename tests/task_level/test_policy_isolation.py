from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.execution import build_tool_policy, fresh_run_environment


def test_repo_only_has_no_mcp_config(tmp_path: Path):
    _, mcp_path = build_tool_policy("repo_only", tmp_path)

    assert mcp_path is not None
    assert json.loads(mcp_path.read_text(encoding="utf-8")) == {"mcpServers": {}}


def test_docatlas_condition_has_only_docatlas_mcp(tmp_path: Path):
    _, mcp_path = build_tool_policy("docatlas_snippet_first", tmp_path)
    config = json.loads(mcp_path.read_text(encoding="utf-8"))

    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]


def test_policy_violation_invalidates_run(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([{"tool_name": "Bash", "arguments": {"command": "curl https://fastapi.tiangolo.com/"}}]), encoding="utf-8")

    audit = audit_trajectory("repo_only", trajectory)

    assert not audit.clean
    assert audit.network_shell_calls > 0


def test_each_run_uses_fresh_home(tmp_path: Path):
    env_a = fresh_run_environment(tmp_path / "a")
    env_b = fresh_run_environment(tmp_path / "b")

    assert env_a["HOME"] != env_b["HOME"]
    assert Path(env_a["HOME"]).exists()


def test_each_run_uses_fresh_docmancer_home(tmp_path: Path):
    env_a = fresh_run_environment(tmp_path / "a")
    env_b = fresh_run_environment(tmp_path / "b")

    assert env_a["DOCMANCER_HOME"] != env_b["DOCMANCER_HOME"]
    assert Path(env_a["DOCMANCER_HOME"]).exists()
