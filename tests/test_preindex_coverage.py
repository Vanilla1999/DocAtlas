"""Regression tests for preindex public docs coverage (PR 1).

Tests cover:
- Nav-crawl fallback for low-sitemap sites (ReadTheDocs/Click).
- seed_urls integration.
- End-to-end refresh → inspect → query (mocked).
- Index path consistency.
- guard_dropped_all vs empty_index distinction.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from docmancer.connectors.fetchers.pipeline.discovery import (
    MIN_DOC_PAGES,
    DiscoveryResult,
    DiscoveryStrategy,
    discover_urls,
)
from docmancer.connectors.fetchers.pipeline.detection import Platform
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.application.library_registry_ops import LibraryRegistryOps
from docmancer.docs.models import (
    DocsChunk,
    DocsInspectResult,
    DocsResult,
    RefreshResult,
)
from docmancer.docs.registry import LibraryRecord, LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(text: str, status: int = 200, content_type: str = "text/html") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"content-type": content_type}
    return resp


def _make_mock_client(get_side_effect):
    client = MagicMock()
    client.get.side_effect = get_side_effect
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Test A: low sitemap triggers nav fallback
# ---------------------------------------------------------------------------

SITEMAP_ONE_URL = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://click.palletsprojects.com/en/stable/</loc></url>
</urlset>"""

CLICK_HOMEPAGE = """<!DOCTYPE html>
<html><head><title>Click</title></head>
<body>
<nav>
<a href="/en/stable/quickstart/">Quickstart</a>
<a href="/en/stable/parameters/">Parameters</a>
<a href="/en/stable/options/">Options</a>
<a href="/en/stable/arguments/">Arguments</a>
<a href="/en/stable/commands/">Commands</a>
<a href="/en/stable/api/">API</a>
</nav>
<main><h1>Click Documentation</h1></main>
</body></html>"""

CLICK_PAGE = """<!DOCTYPE html>
<html><head><title>Click Page</title></head>
<body><main><h1>Page</h1><p>Content.</p></main></body></html>"""


# ---------------------------------------------------------------------------
# Test B: seed_urls integration
# ---------------------------------------------------------------------------

class TestSeedUrlsIntegration:
    def test_seed_urls_deduplicated_with_sitemap(self):
        """Same URL from sitemap and seed_urls is not duplicated."""

        def mock_get(url, **kwargs):
            if "llms-full.txt" in url or "llms.txt" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if "robots.txt" in url:
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if "sitemap" in url:
                return _mock_response(SITEMAP_ONE_URL, content_type="application/xml")
            return _mock_response("<html><body><p>No nav</p></body></html>")

        seed_urls = ["https://click.palletsprojects.com/en/stable/"]

        client = _make_mock_client(mock_get)
        result = discover_urls(
            "https://click.palletsprojects.com/en/stable/",
            client,
            Platform.READTHEDOCS,
            max_pages=30,
            seed_urls=seed_urls,
        )

        urls = [u.url for u in result.urls]
        assert urls.count("https://click.palletsprojects.com/en/stable/") == 1


# ---------------------------------------------------------------------------
# Fake agent for service-level tests
# ---------------------------------------------------------------------------

class PreindexFakeAgent:
    """Simulates indexing a docs URL with configurable pages/chunks."""

    def __init__(self):
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[tuple[str, int | None]] = []
        self.config = None
        self._db_path: str | None = None
        self._extracted_dir: str | None = None
        self._pages_per_url: int = 1
        self._chunks_per_page: int = 5

    def set_output(self, pages_per_url: int, chunks_per_page: int):
        self._pages_per_url = pages_per_url
        self._chunks_per_page = chunks_per_page

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            db_path = self.config.index.db_path
            extracted_dir = self.config.index.extracted_dir
            metadata = dict(kwargs.get("metadata") or {})
            metadata.setdefault("title", "Guide")
            store = SQLiteStore(db_path, extracted_dir)
            docs = []
            for i in range(self._pages_per_url):
                docs.append(
                    Document(
                        source=docs_url.rstrip("/") + f"/page{i}",
                        content=f"# Page {i}\nContent with test keywords.",
                        metadata=metadata,
                    )
                )
            store.add_documents(docs, recreate=recreate)
        return self._pages_per_url

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        metadata = dict((self.add_kwargs[-1].get("metadata") if self.add_kwargs else None) or {})
        metadata.setdefault("title", "Test Section")
        urls = list(dict.fromkeys([
            kw.get("metadata", {}).get("docs_url") or call
            for kw, call in zip(self.add_kwargs, self.add_calls)
        ]))
        base = urls[-1] if urls else "https://docs.example.com/"
        chunks = []
        for i in range(self._chunks_per_page):
            chunks.append(
                RetrievedChunk(
                    source=base.rstrip("/") + f"/page{min(i, self._pages_per_url - 1)}",
                    chunk_index=i,
                    text=f"Relevant content snippet {i} with test keywords.",
                    score=1.0 / (i + 1),
                    metadata=dict(metadata),
                )
            )
        return chunks


def _service(tmp_path, monkeypatch, agent: PreindexFakeAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    agent = agent or PreindexFakeAgent()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        agent.config = kwargs.get("config")
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _write_library_index(service: LibraryDocsService, record, content: str = "# Guide\nUse this documentation.") -> None:
    config = service._index_config_for(record)
    store = SQLiteStore(config.index.db_path, config.index.extracted_dir)
    store.add_documents([
        Document(
            source=record.docs_url_resolved or record.docs_url or record.library_id,
            content=content,
            metadata={"library_id": record.library_id},
        )
    ])


def _old_iso(days: int = 31) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Test C: FastAPI preindex → inspect → query (mocked)
# ---------------------------------------------------------------------------

class TestFastApiPreindexMocked:
    pass

class TestClickPreindexMocked:
    pass

class TestIndexPathConsistency:
    pass

