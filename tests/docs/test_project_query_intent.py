from __future__ import annotations

import pytest

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from tests.docs.test_project_doc_ranking import fake_chunk


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
        ("What is DocAtlas, and what core problem is it designed to solve for coding agents?", "product_overview"),
        ("What is the recommended sequence of MCP tool calls for answering a normal project documentation question?", "docs_mcp"),
        ("When should an agent use get_docs_context?", "docs_mcp"),
        ("When is an agent allowed to call prepare_docs?", "docs_mcp"),
        ("What kinds of requests should use docs_status, and when must it not be used?", "docs_mcp"),
        ('What does prepare_docs(action="sync_project_docs") do to new, changed, stale, and deleted project documentation?', "docs_mcp"),
    ],
)
def test_classify_project_query_intent(question, expected):
    intent = classify_project_query_intent(question)
    assert intent.name == expected
    if question.startswith("What is DocAtlas"):
        assert intent.wants_architecture is False
        assert intent.wants_troubleshooting is False
    if "sync_project_docs" in question:
        assert intent.wants_release_history is False


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

    for concept_question in (
        "What does fail-closed behavior mean in the DocAtlas documentation workflow?",
        "What is the difference between docs_answer, docs_context, patch_context, and insufficient_evidence?",
    ):
        assert classify_project_query_intent(concept_question).wants_troubleshooting is False

    incident = classify_project_query_intent(
        "get_docs_context returned insufficient_evidence unexpectedly; how do I troubleshoot it?"
    )
    assert incident.name == "docs_mcp"
    assert incident.wants_troubleshooting is True


def test_documentation_files_do_not_imply_code_symbol_evidence():
    intent = classify_project_query_intent(
        "Which docs files must stay under the 1000-line release limit?"
    )
    assert intent.name == "release_history"
    assert intent.wants_code_symbols is False

    implementation_question = "Where is the public Docs MCP server implemented in this repository?"
    generic_guide = fake_chunk(
        "docs/mcp-docs-server.md",
        "Public tools",
        0.92,
        "The public tools are `get_docs_context`, `prepare_docs`, and `docs_status`.",
    )
    relation_map = fake_chunk(
        "docs/PROJECT_MAP.md",
        "Runtime areas",
        0.55,
        "| MCP Docs server | `docmancer/mcp/docs_server.py` | Public documentation tools, resources and transport boundary |",
    )
    ranked = rerank_project_doc_chunks(
        [generic_guide, relation_map],
        question=implementation_question,
        intent=classify_project_query_intent(implementation_question),
        limit=2,
    )
    assert ranked[0].path == "docs/PROJECT_MAP.md"

    inventory_question = "What are the three public tools exposed by the DocAtlas Docs MCP server?"
    ranked_inventory = rerank_project_doc_chunks(
        [generic_guide, relation_map],
        question=inventory_question,
        intent=classify_project_query_intent(inventory_question),
        limit=2,
    )
    assert ranked_inventory[0].path == "docs/mcp-docs-server.md"


@pytest.mark.parametrize(
    "question",
    [
        "Which source files implement the MCP server?",
        "Where is the MCP server implemented?",
        "Which implementation file defines ProjectContextService?",
        "Where is the public Docs MCP server implemented in this repository?",
    ],
)
def test_explicit_source_identity_questions_require_code_symbol_evidence(question):
    assert classify_project_query_intent(question).wants_code_symbols is True
