"""Rendered guidance and ToolSpec consistency, not a reader-model benchmark."""
from copy import deepcopy
from importlib.resources import files
import re

import pytest

from docmancer.cli.commands import _get_template_content
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from tests.docs._scope_guidance_contract import (
    advertised_guidance,
    assert_public_context_guidance,
    assert_public_lifecycle_guidance,
)


def _assert_recovery_policy(policy):
    recovery = policy["recovery"]
    assert recovery["after_prepare"] == "retry_original_get_docs_context_unchanged"
    assert recovery["retry_after_prepare_requires"] == "terminal_success"
    assert recovery["after_prepare_job_id"] == "poll_docs_status"
    assert recovery["after_prepare_failure"] == "inspect_failure_no_automatic_retry"
    assert recovery["rephrase_auto_execute"] is False
    assert recovery["hard_stop_false_authorizes_edit"] is False
    version = policy["version_binding"]
    assert version["project_query_default"] == "resolve_current_project_version"
    assert version["explicit_version"] == "explicit_exact_or_historical_request"
    assert version["after_lockfile_change"] == "requery_current_project_do_not_reuse_previous_context"
    assert version["cached_previous_version_is_current_evidence"] is False
    assert policy["free_form_lookup"]["preserve_conditions_negation_and_comparison_sides"] is True
    assert policy["prepare_docs"]["allowed_when"] == ["recommended_next_action", "explicit_lifecycle_request"]
    assert policy["prepare_docs"]["speculative"] is False
    assert policy["docs_status"]["allowed_when"] == ["explicit_status_request", "recommended_next_action", "returned_job_id"]
    assert policy["docs_status"]["discovery"] is False


def _assert_preparation_guide(text):
    normalized = " ".join(text.casefold().replace("`", "").split())
    for retained in (
        "only for a returned typed recommended_next_action or an explicit lifecycle request",
        "preserve its exact arguments and project/library/version/source scope",
        "obtain required confirmation and network consent before work",
        'poll a returned job_id using docs_status(action="job", job_id=...)',
        "retry the original concrete get_docs_context question unchanged only after terminal success",
        "running, failed and cancelled jobs are not ready",
        "inspect a failure instead of automatically retrying",
        "never as discovery",
        "for current project dependencies, pass project_path and omit version unless an exact/historical version was explicitly requested",
        "re-query after lockfile changes rather than reusing previous-version context",
    ):
        assert retained in normalized, retained


def _replace_guidance(value, old, new):
    if isinstance(value, list):
        return [_replace_guidance(child, old, new) for child in value]
    if not isinstance(value, dict):
        return value
    return {
        key: re.sub(re.escape(old), new, child, flags=re.IGNORECASE)
        if key == "description" and isinstance(child, str)
        else _replace_guidance(child, old, new)
        for key, child in value.items()
    }


def test_installed_guidance_preserves_question_conditions_and_current_binding():
    text = _get_template_content("skill.md")
    for phrase in ("conditions", "negation", "comparison sides", "lockfile", "omit `version`"):
        assert phrase in text
    assert "only after success, not failure" in text
    assert "job_id" in text
    assert "docatlas-references/prepare.md" in text
    guide = files("docmancer.templates").joinpath("references/prepare.md").read_text(encoding="utf-8")
    _assert_preparation_guide(guide)
    for old, new in (
        ("Running, failed and cancelled jobs are not ready", "Running, failed and cancelled jobs are ready"),
        ("instead of automatically retrying", "and automatically retry"),
        ("omit `version`", "reuse previous version"),
    ):
        assert old in guide
        with pytest.raises(AssertionError):
            _assert_preparation_guide(guide.replace(old, new))


def test_machine_contract_disambiguates_preparation_success_and_version_state():
    policy = public_agent_contract()["workflow"]
    _assert_recovery_policy(policy)
    for section, key, value in (
        ("recovery", "retry_after_prepare_requires", "job_started"),
        ("recovery", "after_prepare", "retry_rephrased_question"),
        ("recovery", "after_prepare_failure", "automatic_retry"),
        ("recovery", "rephrase_auto_execute", True),
        ("recovery", "hard_stop_false_authorizes_edit", True),
        ("version_binding", "cached_previous_version_is_current_evidence", True),
        ("version_binding", "project_query_default", "reuse_previous_version"),
        ("version_binding", "after_lockfile_change", "reuse_previous_context"),
        ("free_form_lookup", "preserve_conditions_negation_and_comparison_sides", False),
        ("prepare_docs", "speculative", True), ("docs_status", "discovery", True),
    ):
        mutated = deepcopy(policy)
        mutated[section][key] = value
        with pytest.raises(AssertionError):
            _assert_recovery_policy(mutated)


def test_advertised_tool_guidance_matches_installed_recovery_and_question_rules():
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    assert_public_context_guidance(tools["get_docs_context"])
    assert_public_lifecycle_guidance(tools)
    properties = tools["get_docs_context"]["inputSchema"]["properties"]
    assert properties["version"]["type"] == ["string", "null"]
    assert "version" not in tools["get_docs_context"]["inputSchema"]["required"]
    for name, old, new in (
        ("get_docs_context", "Current project: omit version", "Current project: pin previous version"),
        ("get_docs_context", "requery after lockfile changes", "reuse context after lockfile changes"),
        ("prepare_docs", "retry unchanged once only after verified success/readiness", "retry after job start"),
        ("prepare_docs", "confirmation and network consent", "network availability"),
        ("docs_status", "no discovery", "allow discovery"),
        ("docs_status", "a returned job_id from prepare_docs", "any guessed job_id"),
    ):
        mutated = deepcopy(tools)
        mutated[name] = _replace_guidance(mutated[name], old, new)
        assert advertised_guidance(mutated[name]) != advertised_guidance(tools[name])
        with pytest.raises(AssertionError):
            assert_public_context_guidance(mutated["get_docs_context"])
            assert_public_lifecycle_guidance(mutated)
