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
