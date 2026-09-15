"""Query planning must not substitute a convenient task for the user's task."""
from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.patch_request_plan import build_patch_request_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def _project(question: str, text: str):
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements).as_payload()
    diagnostics = {}
    payload, _ = project_docs_context(retrieval={
        "documentation_query_plan": plan,
        "context_pack": [{
            "stable_id": "source", "source_class": "project_doc", "path": "docs/api.md",
            "project_identity": "project:test", "content": text,
            "authority": "source_of_truth", "lifecycle_status": "active",
        }],
    }, selection_diagnostics=diagnostics)
    return plan, payload, diagnostics


@pytest.mark.parametrize("tool", ["get_docs_context", "lookup_context", "read_evidence"])
@pytest.mark.parametrize("verb", ["сделать", "предпринять"])
def test_next_action_does_not_become_implementation(tool, verb):
    question = f"Что должен {verb} агент, если {tool} вернул недостаточно данных?"
    contract = build_project_answer_contract(question)
    assert not any(row.relation == "implementation" for row in contract.proof_obligations)
    assert contract.unresolved_parts
    assert not contract.component_scope_complete
    assert not build_patch_request_plan(question).mutation_targets
    _, payload, _ = _project(question, f"The implementation of {tool} is in the adapter. {tool} retrieves evidence.")
    assert payload["context_quality"]["status"] != "checked"
    assert payload["answer_supported"] is False and payload["edit_ready"] is False


@pytest.mark.parametrize("tail", [
    "if the cache contains an unknown tenant",
    "unless the reader has refreshed its credentials",
    "without discarding an incomplete result",
    "only when the source is unavailable",
    "after an interrupted request",
    "under an unknown operating mode",
])
def test_legacy_subject_match_cannot_consume_an_unmodelled_condition(tail):
    question = f"What does lookup_context do {tail}?"
    plan, payload, _ = _project(question, "lookup_context retrieves documentation from the local index.")
    assert plan["unresolved_parts"]
    assert not plan["component_scope_complete"]
    assert payload["context_quality"]["status"] != "checked"
    assert plan["original_question"] == question


def test_english_next_action_preserves_unverified_scope():
    question = "What should the agent do next if lookup_context returns insufficient evidence?"
    plan, payload, _ = _project(question, "lookup_context retrieves documentation from the local index.")
    assert not plan["component_scope_complete"]
    assert plan["unresolved_parts"]
    assert payload["context_quality"]["status"] != "checked"


def test_closed_command_still_checked_through_real_requirements_and_projection():
    plan, payload, diagnostics = _project(
        "Which command starts the Docs MCP server?",
        "Start the local stdio server with `doc-atlas mcp docs-serve`.",
    )
    assert plan["component_scope_complete"] and not plan["unresolved_parts"]
    assert diagnostics["component_coverage"]["status"] == "full"
    assert payload["context_quality"]["status"] == "checked"
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800


def test_explicit_implementation_remains_owned_by_patch_request_plan():
    plan = build_patch_request_plan("Implement lookup_context")
    assert plan.operation == "modify"
    assert [target.value for target in plan.mutation_targets] == ["lookup_context"]
    contract = build_project_answer_contract("Implement lookup_context")
    assert any(row.relation == "implementation" for row in contract.proof_obligations)


@pytest.mark.parametrize('tool', ['get_docs_context', 'lookup_context'])
def test_contract_and_lifecycle_keywords_do_not_prove_whole_question(tool):
    question = f'In offline mode, will {tool} fetch missing documentation from the network, or must missing evidence require an explicit lifecycle action?'
    plan, payload, _ = _project(question,
        f'{tool} retrieves documentation. The {tool} lifecycle uses prepare, inspect, and retry steps.')
    assert not plan['component_scope_complete']
    assert plan['unresolved_parts']
    assert payload['context_quality']['status'] != 'checked'


def test_definition_of_file_is_not_the_default_setting_requested_in_that_file():
    question = 'What is the default cache budget in app.settings?'
    plan, payload, _ = _project(question, 'app.settings is the application configuration file.')
    assert not plan['component_scope_complete']
    assert plan['unresolved_parts']
    assert payload['context_quality']['status'] != 'checked'


def test_closed_numbered_public_inventory_remains_checked():
    question = 'Which three public tools does the Docs MCP server expose?'
    plan, payload, diagnostics = _project(question,
        'The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, and `docs_status`.')
    assert plan['component_scope_complete']
    assert not plan['unresolved_parts']
    assert payload['context_quality']['status'] == 'checked'


@pytest.mark.parametrize("question", [
    "Where is the DocAtlas execution roadmap?",
    "How many connection retries does SocketPolicy allow?",
])
def test_existing_closed_location_and_quantified_frames_keep_complete_scope(question):
    contract = build_project_answer_contract(question)
    assert contract.component_scope_complete
    assert not contract.unresolved_parts
    for tail in [" if the source is missing", " after an unknown operation"]:
        qualified = build_project_answer_contract(question.rstrip("?") + tail + "?")
        assert not qualified.component_scope_complete
        assert qualified.unresolved_parts


def test_unreviewed_legacy_contract_does_not_by_itself_forbid_safe_context_reads():
    from docmancer.docs.domain.project_retrieval_intent import project_retrieval_disposition
    question = "Does guide.md prove the source ownership contract?"
    contract = build_project_answer_contract(question)
    assert not contract.component_scope_complete
    assert project_retrieval_disposition(question) == "broad_context"
