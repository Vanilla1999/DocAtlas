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
