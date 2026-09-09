from __future__ import annotations

from tests.docs.test_project_doc_ranking import fake_chunk

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


Q13 = "Where is the public Docs MCP server implemented in this repository?"
Q02 = "What are the three public tools exposed by the DocAtlas Docs MCP server?"


def test_implementation_location_relation_outranks_generic_tool_symbol_mentions():
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
        question=Q13,
        intent=classify_project_query_intent(Q13),
        limit=2,
    )

    assert ranked[0].path == "docs/PROJECT_MAP.md"


def test_public_tool_inventory_still_prefers_the_docs_mcp_guide():
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
        question=Q02,
        intent=classify_project_query_intent(Q02),
        limit=2,
    )

    assert ranked[0].path == "docs/mcp-docs-server.md"
