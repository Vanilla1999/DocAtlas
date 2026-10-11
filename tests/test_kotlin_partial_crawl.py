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


