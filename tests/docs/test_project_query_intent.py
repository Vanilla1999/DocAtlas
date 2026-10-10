from __future__ import annotations

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from tests.docs.test_project_doc_ranking import fake_chunk


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
