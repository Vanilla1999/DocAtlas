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


def test_known_riverpod_auto_registers_without_discovery_candidates(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("DOCMANCER_HOME", str(home))

    def fail_network(*args, **kwargs):
        raise AssertionError("network must not be used by resolver-only auto-registration")

    monkeypatch.setattr(httpx.Client, "request", fail_network)

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "registry.db")
    service = LibraryDocsService(config=config, registry=LibraryRegistry(config.index.db_path))

    info = service.resolve_library("riverpod", ecosystem="dart")

    assert info.library_id == "dart:riverpod@latest:web"
    assert info.candidates == []
    record = service.registry.get(info.library_id, source_type="web")
    assert record is not None
    assert record.docs_url == "https://riverpod.dev/"
    assert record.target_spec is not None
    assert record.target_spec["seed_urls"]
    index_path = Path(service._index_config_for(record).index.db_path).resolve()
    assert str(home.resolve()) in str(index_path)
    assert not str(index_path).startswith(str((Path.home() / ".docmancer").resolve()))


def test_known_riverpod_fake_refresh_and_query_uses_isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("DOCMANCER_HOME", str(home))

    def fail_network(*args, **kwargs):
        raise AssertionError("network must not be used by fake Riverpod refresh")

    monkeypatch.setattr(httpx.Client, "request", fail_network)

    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "registry.db")
    documents = [
        Document(
            source="https://riverpod.dev/docs/concepts2/providers",
            content="# Providers\n\nRiverpod providers expose deterministic state.",
            metadata={"format": "markdown", "docset_root": "https://riverpod.dev", "title": "Providers"},
        )
    ]

    class FakeFetcher:
        last_discovery_diagnostics = {"discovery_strategy": "fake", "seed_pages": 1}

        def fetch(self, url):
            return documents

    def agent_factory(**kwargs):
        agent = DocmancerAgent(config=kwargs["config"])
        original_add = agent.add

        def add(url, recreate=False, **add_kwargs):
            add_kwargs["fetcher"] = FakeFetcher()
            return original_add(url, recreate=recreate, **add_kwargs)

        agent.add = add
        return agent

    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )
    info = service.resolve_library("riverpod", ecosystem="dart")
    record = service.registry.get(info.library_id, source_type="web")
    assert record is not None
    index_path = Path(service._index_config_for(record).index.db_path).resolve()

    refreshed = service.refresh_docs(info.library_id, source_type="web", force=True)
    result = service.get_docs("riverpod", ecosystem="dart", topic="deterministic state")

    assert refreshed.status == "updated"
    assert result.status == "success"
    assert result.results
    assert str(home.resolve()) in str(index_path)
    assert index_path.exists()
    assert not str(index_path).startswith(str((Path.home() / ".docmancer").resolve()))


def test_discovery_candidates_include_next_action(tmp_path):
    result = _service(tmp_path).get_docs("mcp", ecosystem="python", topic="server")

    assert result.next_actions == [{"type": "get_library_docs", "tool": "get_library_docs", "arguments_patch": {"docs_url": "https://github.com/modelcontextprotocol/python-sdk", "ecosystem": "python"}}]
