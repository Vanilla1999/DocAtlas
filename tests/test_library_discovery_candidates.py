from __future__ import annotations

from pathlib import Path

import httpx

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService


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


def test_discovery_candidates_include_next_action(tmp_path):
    result = _service(tmp_path).get_docs("mcp", ecosystem="python", topic="server")

    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert result.next_actions[0]["requires_confirmation"] is True
    assert result.next_actions[1] == {
        "type": "get_library_docs",
        "tool": "get_library_docs",
        "requires_confirmation": True,
        "reason": "Use the first discovered candidate only after user confirmation.",
        "arguments_patch": {"docs_url": "https://github.com/modelcontextprotocol/python-sdk", "ecosystem": "python"},
    }
    assert result.next_actions[2] == {
        "type": "discover_library_docs",
        "tool": "prepare_docs",
        "requires_confirmation": True,
        "reason": "Query bounded package-registry metadata when the user cannot provide an authoritative docs_url.",
        "arguments_patch": {
            "action": "discover_library_docs",
            "library": "mcp",
            "ecosystem": "python",
            "version": None,
        },
    }
