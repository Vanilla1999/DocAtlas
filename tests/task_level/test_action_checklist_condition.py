from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.conditions import CONDITIONS
from eval.task_level.execution import build_tool_policy, inject_action_checklist
from eval.task_level.schemas import TaskSpec


def test_action_checklist_condition_injects_context_and_checklist(tmp_path: Path):
    policy = CONDITIONS["docatlas_action_checklist_injected"].tool_policy

    assert policy.inject_docatlas_context is True
    assert policy.inject_action_checklist is True
    assert policy.allow_docatlas is True


def test_action_checklist_only_condition_skips_full_context_flag():
    policy = CONDITIONS["docatlas_action_checklist_only"].tool_policy

    assert policy.inject_docatlas_context is False
    assert policy.inject_action_checklist is True


def test_action_checklist_condition_has_docatlas_mcp(tmp_path: Path):
    policy_path, mcp_path = build_tool_policy("docatlas_action_checklist_injected", tmp_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    config = json.loads(mcp_path.read_text(encoding="utf-8"))

    assert policy["inject_action_checklist"] is True
    assert list(config["mcpServers"].keys()) == ["docmancer-docs"]


def test_inject_action_checklist_writes_markdown_and_json(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "src/app").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / "src/app/security.py").write_text("def require_admin():\n    pass\n", encoding="utf-8")
    (workspace / "docs/security.md").write_text("Admin routes use `require_admin`.", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    (output / "docatlas_response.json").write_text(json.dumps({"context_pack": [{"content": "require_admin"}]}), encoding="utf-8")
    task = TaskSpec(
        task_id="mixed_fastapi_project_001",
        task_type="curated",
        suite="differentiation",
        repo="fixture://test",
        base_commit="fixture-base",
        issue_text="Add admin route using require_admin.",
        language="python",
        ecosystem="python",
        dependencies=(),
        setup_command="",
        test_command="pytest",
    )

    result = inject_action_checklist(task, workspace, output)

    assert result["status"] == "success"
    assert (output / "action_checklist.md").exists()
    assert (output / "action_checklist.json").exists()
    assert "require_admin" in (output / "action_checklist.md").read_text(encoding="utf-8")
