"""Host scope planning stays explicit and never widens a caller-selected scope."""
from __future__ import annotations

from importlib.resources import files

from docmancer.cli.commands import _get_template_content
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts


def test_public_agent_contract_exposes_bounded_scope_planning():
    workflow = public_agent_contract()["workflow"]
    scope = workflow["scope_planning"]

    assert scope["explicit_scope_is_authoritative"] is True
    assert scope["repo_level_policy_scope"] == "project"
    assert scope["known_module_scope"] == "module"
    assert scope["cross_module_scope"] == "all"
    assert scope["module_path_implies_scope"] == "module"
    assert scope["all_requires_no_module_filter"] is True
    assert scope["mixed_module_and_project_prefer_two_calls"] is True
    assert scope["never_widen_project_to_all"] is True


def test_public_tool_and_agent_template_explain_scope_without_hidden_widening():
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    description = tools["get_docs_context"]["description"]
    schema_scope = tools["get_docs_context"]["inputSchema"]["properties"]["scope"]

    assert 'scope="project"' in description
    assert 'scope="module"' in description
    assert 'scope="all"' in description
    assert "repo-level docs only" in schema_scope["description"]
    assert "repo-level plus modules" in schema_scope["description"]

    canonical = files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8")
    rendered = _get_template_content("agent_contract.md")
    for text in (canonical, rendered):
        assert 'scope="project"' in text
        assert 'scope="module"' in text
        assert 'scope="all"' in text
        assert "never widen" in text.lower()
