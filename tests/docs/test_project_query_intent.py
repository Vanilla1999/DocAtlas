from __future__ import annotations

import pytest

from docmancer.docs.domain.project_query_intent import classify_project_query_intent


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is the architecture of docmancer?", "architecture"),
        ("How is the project structured?", "architecture"),
        ("How does ingestion work?", "ingestion_how_to"),
        ("How are documents indexed and retrieved?", "ingestion_internals"),
        ("How does the docs MCP server work?", "docs_mcp"),
        ("How do MCP Packs work?", "packs_mcp"),
        ("What changed recently in ingestion?", "release_history"),
        ("Why are my docs stale?", "troubleshooting"),
        ("How does the MCP server work?", "mcp_disambiguation"),
    ],
)
def test_classify_project_query_intent(question, expected):
    assert classify_project_query_intent(question).name == expected


@pytest.mark.parametrize(
    "question",
    [
        "How do I use this package?",
        "How do package docs work?",
        "How do I use a pub package with project docs?",
        "How does packaging work?",
        "How does webpack integrate with this project?",
    ],
)
def test_package_terms_do_not_trigger_packs_mcp(question):
    intent = classify_project_query_intent(question)
    assert intent.name != "packs_mcp"
    assert intent.wants_packs_mcp is False


@pytest.mark.parametrize(
    "question",
    [
        "How do MCP Packs work?",
        "How do action packs work?",
        "How do I install-pack open-meteo?",
        "How does the MCP packs runtime expose API actions?",
    ],
)
def test_explicit_mcp_packs_terms_trigger_packs_mcp(question):
    intent = classify_project_query_intent(question)
    assert intent.wants_packs_mcp is True


def test_package_with_docs_mcp_is_docs_mcp_not_disambiguation():
    intent = classify_project_query_intent("How do I use this package with docs MCP?")
    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_packs_mcp is False


def test_documentation_files_do_not_imply_code_symbol_evidence():
    intent = classify_project_query_intent(
        "Which docs files must stay under the 1000-line release limit?"
    )
    assert intent.name == "release_history"
    assert intent.wants_code_symbols is False


@pytest.mark.parametrize(
    "question",
    [
        "Which source files implement the MCP server?",
        "Where is the MCP server implemented?",
        "Which implementation file defines ProjectContextService?",
    ],
)
def test_explicit_source_identity_questions_require_code_symbol_evidence(question):
    assert classify_project_query_intent(question).wants_code_symbols is True


def test_named_product_purpose_question_avoids_architecture_and_incident_routes():
    intent = classify_project_query_intent(
        "What is DocAtlas, and what core problem is it designed to solve for coding agents?"
    )
    assert intent.name == "product_overview"
    assert intent.wants_architecture is False
    assert intent.wants_troubleshooting is False


def test_docs_mcp_sequence_question_uses_docs_mcp_route():
    intent = classify_project_query_intent(
        "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?"
    )
    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_packs_mcp is False


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
    intent = classify_project_query_intent(
        'What does prepare_docs(action="sync_project_docs") do to new, changed, stale, and deleted project documentation?'
    )
    assert intent.name == "docs_mcp"
    assert intent.wants_docs_mcp is True
    assert intent.wants_release_history is False


@pytest.mark.parametrize(
    "question",
    [
        "What does fail-closed behavior mean in the DocAtlas documentation workflow?",
        "What is the difference between docs_answer, docs_context, patch_context, and insufficient_evidence?",
    ],
)
def test_concept_definition_or_contrast_does_not_become_troubleshooting(question: str):
    assert classify_project_query_intent(question).wants_troubleshooting is False


def test_real_incident_with_public_tool_keeps_troubleshooting_signal():
    intent = classify_project_query_intent(
        "get_docs_context returned insufficient_evidence unexpectedly; how do I troubleshoot it?"
    )
    assert intent.name == "docs_mcp"
    assert intent.wants_troubleshooting is True
