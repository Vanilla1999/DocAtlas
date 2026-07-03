from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pytest

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.application.project_context_service import project_context_pack
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult


QUALITY_CASES = [
    {
        "name": "architecture_project_structure",
        "question": "What is the architecture of docmancer? How is the project structured?",
        "must_include_paths": ["wiki/Architecture.md", "CONTRIBUTING.md", "README.md"],
        "must_not_include_top_paths": ["CHANGELOG.md"],
        "max_chunks_per_path": 2,
    },
    {
        "name": "ingestion_how_to",
        "question": "How does ingestion work in docmancer? How are documents indexed and retrieved?",
        "must_include_paths": ["wiki/Architecture.md", "README.md"],
        "must_not_include_top_paths": ["CHANGELOG.md"],
        "required_heading_terms": ["Indexing"],
    },
    {
        "name": "docs_mcp_server",
        "question": "How does the docs MCP server work?",
        "must_include_paths": ["README.md", "docs/mcp-docs-server.md"],
        "must_not_include_top_paths": ["wiki/MCP-Packs.md", "CHANGELOG.md"],
    },
    {
        "name": "packs_mcp",
        "question": "How do MCP Packs work?",
        "must_include_paths": ["wiki/MCP-Packs.md"],
        "allow_paths": ["README.md", "wiki/MCP-Packs.md", "wiki/Architecture.md"],
    },
    {
        "name": "ambiguous_mcp_server",
        "question": "How does the MCP server work?",
        "must_include_paths": ["README.md", "docs/mcp-docs-server.md", "wiki/MCP-Packs.md"],
        "must_not_include_top_paths": ["CHANGELOG.md"],
    },
    {
        "name": "release_history",
        "question": "What changed recently in ingestion config?",
        "must_include_paths": ["CHANGELOG.md"],
        "allow_changelog_top": True,
    },
]


@dataclass
class QualityChunk:
    path: str
    heading_path: str
    score: float


def make_quality_fixture_chunks() -> list[QualityChunk]:
    return [
        QualityChunk("CHANGELOG.md", "Added", 0.99),
        QualityChunk("wiki/Architecture.md", "Architecture > Project Docs pipeline", 0.90),
        QualityChunk("wiki/Architecture.md", "Architecture > Indexing", 0.89),
        QualityChunk("wiki/Architecture.md", "Architecture > Docs MCP runtime", 0.78),
        QualityChunk("wiki/Architecture.md", "Architecture > Packs MCP runtime", 0.76),
        QualityChunk("README.md", "Documentation MCP server", 0.82),
        QualityChunk("README.md", "Quickstart", 0.80),
        QualityChunk("CONTRIBUTING.md", "Project structure", 0.42),
        QualityChunk("wiki/MCP-Packs.md", "MCP Packs", 0.84),
        QualityChunk("docs/mcp-docs-server.md", "Docs MCP server", 0.75),
        QualityChunk("docs/capabilities.md", "Capabilities", 0.50),
    ]


@pytest.mark.parametrize("case", QUALITY_CASES, ids=lambda case: case["name"])
def test_project_doc_ranking_quality_cases(case):
    chunks = make_quality_fixture_chunks()
    intent = classify_project_query_intent(case["question"])
    ranked = rerank_project_doc_chunks(chunks, question=case["question"], intent=intent, limit=8)
    paths = [chunk.path for chunk in ranked]
    top_paths = paths[:4]

    for required in case.get("must_include_paths", []):
        assert required in paths, f"{case['name']} missing {required}; got {paths}"
    for forbidden in case.get("must_not_include_top_paths", []):
        assert forbidden not in top_paths, f"{case['name']} had forbidden top path {forbidden}; got {top_paths}"
    for term in case.get("required_heading_terms", []):
        assert any(term.lower() in chunk.heading_path.lower() for chunk in ranked), f"{case['name']} missing heading term {term}; got {[chunk.heading_path for chunk in ranked]}"

    allowed = case.get("allow_paths")
    if allowed:
        assert set(paths[: len(allowed)]).issubset(set(allowed))
    max_chunks_per_path = case.get("max_chunks_per_path")
    if max_chunks_per_path:
        counts = Counter(paths)
        assert all(count <= max_chunks_per_path for count in counts.values())
    if case.get("allow_changelog_top"):
        assert paths[0] == "CHANGELOG.md"


def test_project_context_acceptance_schema_aliases_and_nested_source_section():
    project_docs = ProjectDocsResult(
        project_path="/repo",
        query="What is the architecture of docmancer?",
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Architecture and project structure",
                source="/repo/wiki/Architecture.md",
                url=None,
                path="wiki/Architecture.md",
                heading_path="Architecture > Project Docs pipeline",
            )
        ],
    )

    trust_contract = build_project_context_trust_contract(project_docs=project_docs, dependency_docs=None, requested_library=None, mode="auto")
    assert trust_contract["sources"].keys() == {"selected", "rejected", "risky"}
    assert "selected_sources" not in trust_contract
    assert "selected" not in trust_contract

    pack = project_context_pack(project_docs=project_docs, dependency_docs=None)
    assert pack[0]["source"]["source_class"] == "project_doc"
    assert pack[0]["source"]["path"] == "wiki/Architecture.md"
    assert pack[0]["section"]["heading_path"] == "Architecture > Project Docs pipeline"
