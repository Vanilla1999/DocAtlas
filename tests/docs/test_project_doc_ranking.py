from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


@dataclass
class FakeChunk:
    path: str
    heading_path: str
    score: float
    content: str = "content"
    metadata: dict[str, Any] = field(default_factory=dict)


def fake_chunk(path: str, heading_path: str, score: float) -> FakeChunk:
    return FakeChunk(path=path, heading_path=heading_path, score=score)


def test_changelog_demoted_for_how_ingestion_question():
    intent = classify_project_query_intent("How does ingestion work?")
    ranked = rerank_project_doc_chunks(
        [
            fake_chunk("CHANGELOG.md", "Added", 0.99),
            fake_chunk("wiki/Architecture.md", "Architecture > Indexing", 0.80),
            fake_chunk("README.md", "Quickstart lanes", 0.70),
        ],
        question="How does ingestion work?",
        intent=intent,
        limit=3,
    )
    assert ranked[0].path != "CHANGELOG.md"
    assert ranked[-1].path == "CHANGELOG.md"


def test_changelog_boosted_for_release_question():
    intent = classify_project_query_intent("What changed recently in ingestion?")
    ranked = rerank_project_doc_chunks(
        [fake_chunk("CHANGELOG.md", "Added", 0.80), fake_chunk("wiki/Architecture.md", "Indexing", 0.85)],
        question="What changed recently in ingestion?",
        intent=intent,
        limit=2,
    )
    assert ranked[0].path == "CHANGELOG.md"


def test_architecture_project_structure_includes_contributing_when_available():
    intent = classify_project_query_intent("What is the architecture and project structure?")
    ranked = rerank_project_doc_chunks(
        [
            fake_chunk("wiki/Architecture.md", "Architecture > A", 0.99),
            fake_chunk("wiki/Architecture.md", "Architecture > B", 0.98),
            fake_chunk("wiki/Architecture.md", "Architecture > C", 0.97),
            fake_chunk("CONTRIBUTING.md", "Project structure", 0.40),
            fake_chunk("README.md", "What you get", 0.50),
            fake_chunk("CHANGELOG.md", "Added", 0.90),
        ],
        question="What is the architecture and project structure?",
        intent=intent,
        limit=4,
    )
    paths = [chunk.path for chunk in ranked]
    assert "CONTRIBUTING.md" in paths
    assert "README.md" in paths
    assert paths.count("wiki/Architecture.md") <= 2
    assert "CHANGELOG.md" not in paths


def test_docs_mcp_query_demotes_packs():
    intent = classify_project_query_intent("How does the docs MCP server work?")
    ranked = rerank_project_doc_chunks(
        [
            fake_chunk("wiki/MCP-Packs.md", "MCP Packs", 0.95),
            fake_chunk("README.md", "Documentation MCP server", 0.80),
            fake_chunk("docs/mcp-docs-server.md", "Docs MCP server", 0.75),
        ],
        question="How does the docs MCP server work?",
        intent=intent,
        limit=3,
    )
    assert ranked[0].path in {"README.md", "docs/mcp-docs-server.md"}


def test_packs_mcp_query_boosts_packs():
    intent = classify_project_query_intent("How do MCP Packs work?")
    ranked = rerank_project_doc_chunks(
        [fake_chunk("wiki/MCP-Packs.md", "MCP Packs", 0.80), fake_chunk("README.md", "Documentation MCP server", 0.90)],
        question="How do MCP Packs work?",
        intent=intent,
        limit=2,
    )
    assert ranked[0].path == "wiki/MCP-Packs.md"


def test_ambiguous_mcp_query_includes_docs_and_packs_when_available():
    intent = classify_project_query_intent("How does the MCP server work?")
    ranked = rerank_project_doc_chunks(
        [
            fake_chunk("README.md", "Documentation MCP server", 0.80),
            fake_chunk("wiki/MCP-Packs.md", "MCP Packs", 0.80),
            fake_chunk("wiki/Architecture.md", "Docs MCP runtime", 0.75),
        ],
        question="How does the MCP server work?",
        intent=intent,
        limit=3,
    )
    paths = [chunk.path for chunk in ranked]
    assert "README.md" in paths
    assert "wiki/MCP-Packs.md" in paths
