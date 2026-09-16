"""Rendered guidance and ToolSpec consistency, not a reader-model benchmark."""
from docmancer.cli.commands import _get_template_content
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts


def test_installed_guidance_preserves_question_conditions_and_current_binding():
    text = _get_template_content("skill.md")
    for phrase in ("conditions", "negation", "comparison sides", "lockfile", "omit `version`"):
        assert phrase in text
    assert "only after success, not failure" in text
    assert "job_id" in text


def test_machine_contract_disambiguates_preparation_success_and_version_state():
    policy = public_agent_contract()["workflow"]
    assert policy["recovery"]["retry_after_prepare_requires"] == "terminal_success"
    assert policy["recovery"]["after_prepare_job_id"] == "poll_docs_status"
    assert policy["recovery"]["after_prepare_failure"] == "inspect_failure_no_automatic_retry"
    assert policy["version_binding"]["project_query_default"] == "resolve_current_project_version"
    assert policy["version_binding"]["cached_previous_version_is_current_evidence"] is False
    assert policy["free_form_lookup"]["preserve_conditions_negation_and_comparison_sides"] is True


def test_advertised_tool_guidance_matches_installed_recovery_and_question_rules():
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    lookup = tools["get_docs_context"]["inputSchema"]["properties"]["lookup_queries"]["description"]
    assert "conditions" in lookup and "negation" in lookup
    assert "same question" in lookup.lower()
    assert "only after success" in tools["prepare_docs"]["description"]
    assert "returned job_id" in tools["docs_status"]["description"]
    version = tools["get_docs_context"]["inputSchema"]["properties"]["version"]["description"]
    assert "omit" in version.lower() and "current project" in version.lower()
