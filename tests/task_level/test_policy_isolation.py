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
    _, mcp_path = build_tool_policy("docatlas_tool_optional", tmp_path)
    config = json.loads(mcp_path.read_text(encoding="utf-8"))

    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]
    assert config["mcpServers"]["docmancer-docs"]["command"] == "uv"


def test_deprecated_docatlas_snippet_first_alias_still_has_mcp(tmp_path: Path):
    _, mcp_path = build_tool_policy("docatlas_snippet_first", tmp_path)
    config = json.loads(mcp_path.read_text(encoding="utf-8"))

    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]


def test_docatlas_recommended_has_mcp_without_required_policy(tmp_path: Path):
    policy_path, mcp_path = build_tool_policy("docatlas_tool_recommended", tmp_path)
    config = json.loads(mcp_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]
    assert policy["recommend_docatlas_before_edit"] is True
    assert policy["require_docatlas_call_before_edit"] is False


def test_docatlas_recommended_does_not_require_call(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([
        {"sequence": 1, "tool_name": "Edit", "arguments": {"changes": ["src/app.py"]}},
    ]), encoding="utf-8")

    audit = audit_trajectory("docatlas_tool_recommended", trajectory)

    assert audit.clean
    assert audit.docatlas_calls == 0


def test_policy_violation_invalidates_run(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([{"tool_name": "Bash", "arguments": {"command": "curl https://fastapi.tiangolo.com/"}}]), encoding="utf-8")

    audit = audit_trajectory("repo_only", trajectory)

    assert not audit.clean
    assert audit.network_shell_calls > 0


def test_required_docatlas_call_must_precede_edit(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([
        {"sequence": 1, "tool_name": "Edit", "arguments": {"changes": ["src/app.py"]}},
        {"sequence": 2, "tool_name": "get_docs_context", "arguments": {"server": "docmancer-docs", "tool": "get_docs_context"}},
    ]), encoding="utf-8")

    audit = audit_trajectory("docatlas_tool_required_once", trajectory)

    assert not audit.clean
    assert "required_docatlas_call_missing" in audit.violations


def test_required_docatlas_call_before_edit_is_clean(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([
        {"sequence": 1, "tool_name": "get_docs_context", "arguments": {"server": "docmancer-docs", "tool": "get_docs_context"}},
        {"sequence": 2, "tool_name": "Edit", "arguments": {"changes": ["src/app.py"]}},
    ]), encoding="utf-8")

    audit = audit_trajectory("docatlas_tool_required_once", trajectory)

    assert audit.clean
    assert audit.docatlas_calls == 1
    assert audit.first_docatlas_call_before_first_edit is True


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


def test_patch_constraints_workflow_has_only_docatlas_mcp(tmp_path: Path):
    policy_path, mcp_path = build_tool_policy("docatlas_patch_constraints_workflow", tmp_path)
    config = json.loads(mcp_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]
    assert policy["allow_docatlas"] is True
    assert policy["inject_patch_constraints"] is False
    assert policy["recommend_docatlas_before_edit"] is True


def test_patch_constraints_workflow_rejects_context7_and_web(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([
        {"sequence": 1, "tool_name": "context7.query-docs", "arguments": {}},
        {"sequence": 2, "tool_name": "WebFetch", "arguments": {"url": "https://example.com"}},
    ]), encoding="utf-8")

    audit = audit_trajectory("docatlas_patch_constraints_workflow", trajectory)

    assert not audit.clean
    assert "docatlas condition used Context7 tools" in audit.violations
    assert "docatlas condition used web or network shell tools" in audit.violations
