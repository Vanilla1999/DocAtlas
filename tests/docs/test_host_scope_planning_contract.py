"""Host scope planning stays explicit and never widens a caller-selected scope."""
from __future__ import annotations

from importlib.resources import files

from docmancer.cli.commands import _get_template_content
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from tests.docs._scope_guidance_contract import assert_public_scope_guidance


def test_public_agent_contract_exposes_bounded_scope_planning():
    workflow = public_agent_contract()["workflow"]
    scope = workflow["scope_planning"]

    assert scope["explicit_scope_is_authoritative"] is True
    assert scope["module_path_implies_scope"] == "module"
    assert scope["all_requires_no_module_filter"] is True
    assert scope["never_widen_project_to_all"] is True
    assert scope["all_is_repository_local"] is True


def test_public_tool_and_agent_template_explain_scope_without_hidden_widening():
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    assert_public_scope_guidance(tools["get_docs_context"])

    canonical = files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8")
    rendered = _get_template_content("agent_contract.md")
    for text in (canonical, rendered):
        assert 'scope="project"' in text
        assert 'scope="module"' in text
        assert 'scope="all"' in text
        assert "never widen" in text.lower()
