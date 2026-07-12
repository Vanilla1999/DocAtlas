from __future__ import annotations

import ipaddress
from unittest.mock import patch
import time

import httpx

from docmancer.agent import DocmancerAgent
from docmancer.connectors.fetchers.pipeline.detection import Platform
from docmancer.connectors.fetchers.pipeline.discovery import DiscoveredUrl, DiscoveryStrategy
from docmancer.connectors.fetchers.web import WebFetcher
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.fetch_policy import DocsFetchPolicy
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


class KotlinPartialFixtureFetcher:
    def __init__(self) -> None:
        self.last_discovery_diagnostics = {}
        self.last_fetch_failure = None

    def fetch(self, url: str):
        fetcher = WebFetcher(
            max_pages=4,
            workers=2,
            delay=0.0,
            fetch_policy=DocsFetchPolicy(
                resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
                allowed_hosts=("docs.example.test", "github.com", "raw.githubusercontent.com"),
            ),
        )
        discovered = [
            DiscoveredUrl("https://docs.example.test/good", DiscoveryStrategy.NAV_CRAWL),
            DiscoveredUrl("https://docs.example.test/broken", DiscoveryStrategy.NAV_CRAWL),
            DiscoveredUrl("https://outside.example.test/escape", DiscoveryStrategy.NAV_CRAWL),
            DiscoveredUrl(
                "https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/coroutines-basics.md",
                DiscoveryStrategy.SEED_URLS,
            ),
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            requested = str(request.url)
            host = request.headers.get("host", "")
            if host == "docs.example.test" and request.url.path == "/good":
                return httpx.Response(
                    200,
                    request=request,
                    text=(
                        "<html><head><link rel='canonical' href='/good'/></head><body><main>"
                        "<h1>Kotlin coroutine builders</h1><p>Use launch for concurrent work.</p>"
                        "<pre><code>runBlocking { launch { println(\"ready\") } }</code></pre>"
                        "</main></body></html>"
                    ),
                )
            if host == "docs.example.test" and request.url.path == "/broken":
                return httpx.Response(503, request=request, text="temporarily unavailable")
            if host == "raw.githubusercontent.com" and request.url.path.startswith("/Kotlin/kotlinx.coroutines/1.8.1/"):
                return httpx.Response(
                    200,
                    request=request,
                    text="# Async\n\n```kotlin\nval result = async { 42 }\nprintln(result.await())\n```",
                )
            raise AssertionError(f"unexpected network request: {requested}")

        real_client = httpx.Client
        client_factory = lambda **kwargs: real_client(transport=httpx.MockTransport(handler))
        with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=client_factory):
            documents = fetcher._fetch_pages(
                discovered,
                "https://docs.example.test",
                client=object(),
                platform=Platform.GENERIC,
                robots=None,
            )
        self.last_discovery_diagnostics = fetcher._with_page_ledger(
            {"discovery_strategy": "task14-offline-fixture", "seed_pages": 1}
        )
        self.last_page_ledger = fetcher.last_page_ledger
        self.last_fetch_failure = fetcher.last_fetch_failure
        return documents


def test_kotlin_good_broken_cross_domain_and_github_fixture_is_queryable_partial(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "registry.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    agent = DocmancerAgent(config=config)
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        job_tracker=DocsJobTracker(),
    )
    fixture_fetcher = KotlinPartialFixtureFetcher()
    monkeypatch.setattr(
        "docmancer.connectors.fetchers.factory.build_fetcher",
        lambda *args, **kwargs: fixture_fetcher,
    )

    prepared = service.prefetch_docs(
        "kotlinx.coroutines",
        ecosystem="kotlin",
        versions=["1.8.1"],
        docs_url="https://docs.example.test",
        force_refresh=True,
    )

    assert prepared.status == "partial"
    assert prepared.pages_failed == 2
    assert prepared.pages_indexed >= 2
    assert prepared.preindex is not None
    ledger = prepared.preindex["page_ledger"]
    assert {item["reason_code"] for item in ledger} >= {"ok", "http_failure", "cross_domain_skipped"}
    assert all(item["chunks"] > 0 for item in ledger if item["outcome"] == "usable")
    github = next(item for item in ledger if item["fetcher"] == "github-raw")
    assert github["discovered_url"].startswith("https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/")
    assert github["fetch_url"].startswith("https://raw.githubusercontent.com/Kotlin/kotlinx.coroutines/1.8.1/")

    result = service.get_docs(
        "kotlinx.coroutines",
        ecosystem="kotlin",
        version="1.8.1",
        topic="coroutines launch async example with code",
    )
    combined = "\n".join(item.content for item in result.results)
    assert result.results
    assert "launch" in combined or ("async" in combined and "await" in combined)


def test_kotlin_partial_fixture_surfaces_failed_page_summary_in_job_status(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "registry.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )
    fixture_fetcher = KotlinPartialFixtureFetcher()
    monkeypatch.setattr(
        "docmancer.connectors.fetchers.factory.build_fetcher",
        lambda *args, **kwargs: fixture_fetcher,
    )

    started = time.monotonic()
    job = service.prefetch_docs(
        "kotlinx.coroutines",
        ecosystem="kotlin",
        versions=["1.8.1"],
        docs_url="https://docs.example.test",
        force_refresh=True,
        async_=True,
    )
    assert time.monotonic() - started < 1.0
    assert job.job_id

    for _ in range(200):
        status = service.get_docs_job_status(job.job_id)
        if status and status.status in {"partial", "failed", "succeeded"}:
            break
        time.sleep(0.01)

    assert status is not None
    assert status.status == "partial"
    assert status.failed_pages == 2
    assert {item["reason_code"] for item in status.page_failure_summary} == {
        "http_failure", "cross_domain_skipped"
    }
