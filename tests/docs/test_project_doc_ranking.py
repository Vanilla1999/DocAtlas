from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks, source_weight_for_intent, source_weight_reason
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


@dataclass
class FakeChunk:
    path: str
    heading_path: str
    score: float
    content: str = "content"
    metadata: dict[str, Any] = field(default_factory=dict)


def fake_chunk(path: str, heading_path: str, score: float, content: str = "content", metadata: dict[str, Any] | None = None) -> FakeChunk:
    return FakeChunk(path=path, heading_path=heading_path, score=score, content=content, metadata=metadata)


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


def test_ingestion_internals_uses_specific_weight_before_architecture_fallback():
    intent = classify_project_query_intent("How are documents indexed and retrieved?")

    architecture_indexing_weight = source_weight_for_intent(
        "wiki/Architecture.md",
        "Architecture > Indexing",
        intent,
    )

    generic_architecture_weight = source_weight_for_intent(
        "wiki/Architecture.md",
        "Architecture > General overview",
        intent,
    )

    assert architecture_indexing_weight >= generic_architecture_weight


def test_ingestion_internals_reason_mentions_indexing_or_retrieval():
    intent = classify_project_query_intent("How are documents indexed and retrieved?")

    reason = source_weight_reason(
        "wiki/Architecture.md",
        "Architecture > Indexing",
        intent,
    ).lower()

    assert "index" in reason or "retriev" in reason or "ingestion" in reason


def test_broad_query_backfill_preserves_source_diversity_when_enough_sources_exist():
    intent = classify_project_query_intent("What is the architecture and project structure?")

    chunks = [
        fake_chunk(path="wiki/Architecture.md", heading_path="A", score=0.99),
        fake_chunk(path="wiki/Architecture.md", heading_path="B", score=0.98),
        fake_chunk(path="wiki/Architecture.md", heading_path="C", score=0.97),
        fake_chunk(path="wiki/Architecture.md", heading_path="D", score=0.96),
        fake_chunk(path="README.md", heading_path="Overview", score=0.70),
        fake_chunk(path="CONTRIBUTING.md", heading_path="Project structure", score=0.60),
        fake_chunk(path="docs/mcp-docs-server.md", heading_path="Docs MCP", score=0.50),
    ]

    ranked = rerank_project_doc_chunks(
        chunks,
        question="What is the architecture and project structure?",
        intent=intent,
        limit=6,
    )

    counts = Counter(c.path for c in ranked)
    assert counts["wiki/Architecture.md"] <= 2


def test_docs_mcp_query_requires_specific_docs_mcp_source_when_available():
    intent = classify_project_query_intent("How does the docs MCP server work?")

    chunks = [
        fake_chunk(path="README.md", heading_path="Documentation MCP server", content="doc-atlas mcp docs-serve", score=0.95),
        fake_chunk(path="wiki/MCP-Packs.md", heading_path="MCP Packs", content="doc-atlas mcp packs-serve", score=0.90),
        fake_chunk(path="docs/mcp-docs-server.md", heading_path="Docs MCP server", content="get_project_context", score=0.50),
    ]

    ranked = rerank_project_doc_chunks(
        chunks,
        question="How does the docs MCP server work?",
        intent=intent,
        limit=3,
    )

    paths = [c.path for c in ranked]
    assert "docs/mcp-docs-server.md" in paths
    assert paths[0] != "wiki/MCP-Packs.md"


def test_ambiguous_mcp_query_includes_specific_docs_and_packs_sources():
    intent = classify_project_query_intent("How does the MCP server work?")

    chunks = [
        fake_chunk(path="README.md", heading_path="Documentation MCP server", content="doc-atlas mcp docs-serve", score=0.95),
        fake_chunk(path="docs/mcp-docs-server.md", heading_path="Docs MCP server", content="get_project_context", score=0.60),
        fake_chunk(path="wiki/MCP-Packs.md", heading_path="MCP Packs", content="doc-atlas mcp packs-serve", score=0.60),
        fake_chunk(path="CHANGELOG.md", heading_path="Added", content="MCP changes", score=0.99),
    ]

    ranked = rerank_project_doc_chunks(
        chunks,
        question="How does the MCP server work?",
        intent=intent,
        limit=4,
    )

    paths = [c.path for c in ranked]
    assert "README.md" in paths
    assert "docs/mcp-docs-server.md" in paths
    assert "wiki/MCP-Packs.md" in paths
    assert "CHANGELOG.md" not in paths[:3]


def test_explicit_dogfood_query_can_promote_artifact_source():
    question = "What did the docatlas dogfood patch-review artifact find about the workflow?"
    intent = classify_project_query_intent(question)
    artifact_path = "docs/research/docatlas-dogfood-v4/nbo/patch-review/review_summary.md"

    ranked = rerank_project_doc_chunks(
        [
            fake_chunk(path="ARCHITECTURE.md", heading_path="Workflow", content="Authoritative workflow overview.", score=0.90),
            fake_chunk(path=artifact_path, heading_path="Dogfood workflow finding", content="Dogfood patch-review artifact finding.", score=0.75),
        ],
        question=question,
        intent=intent,
        limit=2,
    )

    assert ranked[0].path == artifact_path
    assert ranked[0].metadata["project_source"]["source_type"] == "patch_review_artifact"
    assert "dogfood_artifact" in ranked[0].metadata["project_source"]["risk_flags"]


def test_ranking_metadata_attached_when_metadata_is_none():
    intent = classify_project_query_intent("What is the architecture?")

    chunk = fake_chunk(
        path="README.md",
        heading_path="Overview",
        content="overview",
        score=0.9,
        metadata=None,
    )

    ranked = rerank_project_doc_chunks(
        [chunk],
        question="What is the architecture?",
        intent=intent,
        limit=1,
    )

    metadata = getattr(ranked[0], "metadata", None)
    assert isinstance(metadata, dict)
    assert "project_ranking" in metadata


def test_is_specific_docs_mcp_source_matches_docs_server_py():
    from docmancer.docs.domain.project_doc_ranking import is_specific_docs_mcp_source

    class FakeMcpSource:
        def __init__(self, path: str):
            self.path = path
            self.heading_path = ""
            self.content = ""

    assert is_specific_docs_mcp_source(FakeMcpSource("docmancer/mcp/docs_server.py"))
    assert is_specific_docs_mcp_source(FakeMcpSource("docmancer/docs/interfaces/mcp/context_tools.py"))
    assert is_specific_docs_mcp_source(FakeMcpSource("docs/mcp-docs-server.md"))
    assert not is_specific_docs_mcp_source(FakeMcpSource("CHANGELOG.md"))


def test_docs_mcp_weight_boost_docs_server_py():
    intent = classify_project_query_intent("How does the MCP docs server work?")
    assert intent.name == "docs_mcp"

    w = source_weight_for_intent("docmancer/mcp/docs_server.py", None, intent)
    assert w >= 1.7

    w = source_weight_for_intent("docmancer/docs/interfaces/mcp/context_tools.py", None, intent)
    assert w >= 1.7


def test_mcp_disambiguation_boost_interfaces_mcp():
    intent = classify_project_query_intent("What is the MCP server?")
    assert intent.name == "mcp_disambiguation"

    w = source_weight_for_intent("docmancer/mcp/docs_server.py", None, intent)
    assert w >= 1.3

    w = source_weight_for_intent("docmancer/docs/interfaces/mcp/context_tools.py", None, intent)
    assert w >= 1.3
