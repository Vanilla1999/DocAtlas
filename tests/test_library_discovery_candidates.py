from __future__ import annotations

from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


def _service(tmp_path):
    config = DocmancerConfig()
    registry = LibraryRegistry(tmp_path / "docs.sqlite3")
    return LibraryDocsService(config=config, registry=registry)


def test_unknown_python_mcp_returns_discovery_candidates_not_dead_end(tmp_path):
    result = _service(tmp_path).get_docs("mcp", ecosystem="python", topic="tools")

    assert result.status == "needs_input"
    assert result.discovery_candidates
    assert result.discovery_candidates[0]["library"] == "mcp"
    assert result.discovery_candidates[0]["docs_url"]


def test_unknown_riverpod_returns_dart_candidates(tmp_path):
    result = _service(tmp_path).get_docs("riverpod", ecosystem="dart", topic="state")

    assert result.discovery_candidates
    assert "pub.dev/documentation/riverpod" in result.discovery_candidates[0]["docs_url"]


def test_discovery_candidates_include_next_action(tmp_path):
    result = _service(tmp_path).get_docs("mcp", ecosystem="python", topic="server")

    assert result.next_actions == ["Retry get_library_docs with docs_url from discovery_candidates[0]."]
