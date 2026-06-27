from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.execution import build_tool_policy


def test_repo_only_strict_offline_invalidates_network_use(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([{"tool_name": "Bash", "arguments": {"command": "curl https://pub.dev"}}]), encoding="utf-8")

    audit = audit_trajectory("repo_only_strict_offline", trajectory)

    assert not audit.clean
    assert audit.network_attempts > 0


def test_repo_only_web_audited_records_network_use(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([{"tool_name": "Bash", "arguments": {"command": "curl https://pub.dev"}}]), encoding="utf-8")

    audit = audit_trajectory("repo_only_web_audited", trajectory)

    assert audit.clean
    assert audit.network_attempts > 0


def test_repo_only_web_audited_has_no_docatlas_or_context7_mcp(tmp_path: Path):
    policy_path, mcp_path = build_tool_policy("repo_only_web_audited", tmp_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert json.loads(mcp_path.read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert policy["allow_web"] is True
    assert policy["allow_docatlas"] is False
    assert policy["allow_context7"] is False


def test_policy_audit_does_not_count_domain_word_browser_as_web_tool(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([{"tool_name": "Edit", "arguments": {"changes": ["browser/scan preflight"]}}]), encoding="utf-8")

    audit = audit_trajectory("repo_only_strict_offline", trajectory)

    assert audit.clean
    assert audit.web_calls == 0
