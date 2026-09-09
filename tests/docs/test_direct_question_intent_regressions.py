from __future__ import annotations

import pytest

from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


Q01 = "What is DocAtlas, and what core problem is it designed to solve for coding agents?"
Q03 = "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?"
Q14 = 'What does prepare_docs(action="sync_project_docs") do to new, changed, stale, and deleted project documentation?'


def _alias_ids(question: str) -> set[str]:
    return {alias.intent_id for alias in build_project_retrieval_aliases(question)}


def test_product_purpose_question_is_not_architecture_or_incident_routing():
    intent = classify_project_query_intent(Q01)

    assert intent.name == "product_overview"
    assert intent.wants_architecture is False
    assert intent.wants_troubleshooting is False
    assert _alias_ids(Q01) == {"product_overview"}


def test_docs_mcp_sequence_question_is_not_product_purpose_or_surface_disambiguation():
    intent = classify_project_query_intent(Q03)
    aliases = _alias_ids(Q03)

    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_packs_mcp is False
    assert "docs_mcp_workflow" in aliases
    assert "product_overview" not in aliases


@pytest.mark.parametrize(
    "question",
    [
        "When should an agent use get_docs_context?",
        "When is an agent allowed to call prepare_docs?",
        "What kinds of requests should use docs_status, and when must it not be used?",
    ],
)
def test_current_public_docs_mcp_tool_names_route_to_docs_mcp(question: str):
    intent = classify_project_query_intent(question)

    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_packs_mcp is False


def test_project_docs_sync_lifecycle_question_is_not_release_history():
    intent = classify_project_query_intent(Q14)

    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_release_history is False
    assert "project_docs_sync" in _alias_ids(Q14)


@pytest.mark.parametrize(
    "question",
    [
        "What does fail-closed behavior mean in the DocAtlas documentation workflow?",
        "What is the difference between docs_answer, docs_context, patch_context, and insufficient_evidence?",
    ],
)
def test_concept_definition_or_contrast_is_not_troubleshooting_alias(question: str):
    assert "troubleshooting" not in _alias_ids(question)


def test_real_release_history_question_stays_release_history():
    intent = classify_project_query_intent("What changed recently in ingestion?")
    assert intent.name == "release_history"
    assert intent.wants_release_history is True


def test_real_incident_question_stays_troubleshooting():
    question = "get_docs_context returned insufficient_evidence unexpectedly; how do I troubleshoot it?"
    intent = classify_project_query_intent(question)

    assert intent.name == "docs_mcp"
    assert intent.wants_troubleshooting is True
    assert "troubleshooting" in _alias_ids(question)
