from __future__ import annotations

from pathlib import Path

import pytest

from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult, ProjectMetadata


pytestmark = pytest.mark.integration


def write_live_quality_fixture(root: Path) -> None:
    """Create a tiny fixture project for future live Context7-vs-DocAtlas evals.

    Run with:
        pytest tests/docs/test_project_context_live_quality.py -m integration
    """
    (root / "wiki").mkdir()
    (root / "docs").mkdir()
    (root / "README.md").write_text(
        """# DocAtlas

DocAtlas is a local, version-aware docs runtime.

## Documentation MCP server

Run `doc-atlas mcp docs-serve`.

Tools include `get_project_context`, `get_project_docs`, `get_library_docs`.
""",
        encoding="utf-8",
    )
    (root / "CONTRIBUTING.md").write_text(
        """# Contributing

## Project structure

The codebase has `docmancer/core`, `docmancer/connectors`, `docmancer/cli`, and tests.
""",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        """# Changelog

## Added

- ingestion workers and embed_queue_size.
- MCP server improvements.
""",
        encoding="utf-8",
    )
    (root / "wiki" / "Architecture.md").write_text(
        """# Architecture

## Project Docs pipeline

Docs are discovered, hashed, chunked, indexed, and queried.

## Indexing

Documents are normalized into sections, stored in SQLite FTS, embedded, and retrieved with hybrid search.

## Docs MCP runtime

The docs MCP server exposes documentation lookup tools.
""",
        encoding="utf-8",
    )
    (root / "wiki" / "MCP-Packs.md").write_text(
        """# MCP Packs

MCP Packs are the action runtime layer.

Run `doc-atlas mcp packs-serve` for packs.
""",
        encoding="utf-8",
    )
    (root / "docs" / "mcp-docs-server.md").write_text(
        """# Docs MCP Server

The docs MCP server runs with `doc-atlas mcp docs-serve`.

It exposes `get_project_context`, `get_project_docs`, and `get_library_docs`.
""",
        encoding="utf-8",
    )


class FixtureProjectContextFacade:
    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return ProjectMetadata(project_path=project_path)

    def get_project_docs(self, project_path: str, question: str, **kwargs):
        root = Path(project_path)
        chunks = [
            self._chunk(root, "README.md", "README > Documentation MCP server", 0.82),
            self._chunk(root, "CONTRIBUTING.md", "Contributing > Project structure", 0.42),
            self._chunk(root, "CHANGELOG.md", "Changelog > Added", 0.99),
            self._chunk(root, "wiki/Architecture.md", "Architecture > Project Docs pipeline", 0.90),
            self._chunk(root, "wiki/Architecture.md", "Architecture > Indexing", 0.89),
            self._chunk(root, "wiki/Architecture.md", "Architecture > Docs MCP runtime", 0.78),
            self._chunk(root, "wiki/MCP-Packs.md", "MCP Packs", 0.84),
            self._chunk(root, "docs/mcp-docs-server.md", "Docs MCP server", 0.75),
        ]
        return ProjectDocsResult(project_path=project_path, query=question, results=chunks)

    def get_docs(self, *args, **kwargs):  # pragma: no cover - project-only fixture path
        raise AssertionError("dependency docs are not used by this integration skeleton")

    @staticmethod
    def _chunk(root: Path, path: str, heading_path: str, score: float) -> ProjectDocsChunk:
        content = (root / path).read_text(encoding="utf-8")
        return ProjectDocsChunk(
            title=heading_path.split(">")[-1].strip(),
            content=content,
            source=str(root / path),
            url=None,
            path=path,
            heading_path=heading_path,
            metadata={"score": score},
        )


def test_live_project_context_architecture_prefers_readme_architecture_contributing(tmp_path):
    write_live_quality_fixture(tmp_path)

    result = ProjectContextService(FixtureProjectContextFacade()).get_project_context(
        str(tmp_path),
        "What is the architecture and project structure?",
        mode="project-only",
        limit=6,
    )
    paths = [item["source"]["path"] for item in result.context_pack]

    assert "README.md" in paths
    assert "wiki/Architecture.md" in paths
    assert "CONTRIBUTING.md" in paths
    assert "CHANGELOG.md" not in paths[:4]


def test_live_project_context_docs_mcp_includes_specific_docs_source(tmp_path):
    write_live_quality_fixture(tmp_path)

    result = ProjectContextService(FixtureProjectContextFacade()).get_project_context(
        str(tmp_path),
        "How does the docs MCP server work?",
        mode="project-only",
        limit=4,
    )
    paths = [item["source"]["path"] for item in result.context_pack]

    assert "docs/mcp-docs-server.md" in paths
    assert paths[0] != "wiki/MCP-Packs.md"
