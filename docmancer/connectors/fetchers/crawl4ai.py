"""Deprecated browser lane: finite secure HTTP adapter only.

Browser extraction remains unavailable until every request can enforce the same
finite selection, DNS/private-address, redirect, robots and budget policy.
"""
from __future__ import annotations

from docmancer.core.models import Document


class Crawl4AIFetcher:
    def __init__(
        self, timeout: float = 30.0, max_pages: int = 500,
        use_fit_markdown: bool = True, respect_robots: bool = True,
        delay: float = 0.5, workers: int = 4,
        exact_urls: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        robots_urls: list[str] | None = None,
    ) -> None:
        from docmancer.connectors.fetchers.web import WebFetcher

        self._fetcher = WebFetcher(
            timeout=timeout, max_pages=max_pages, respect_robots=respect_robots,
            delay=delay, workers=workers, exact_urls=exact_urls,
            allowed_domains=allowed_domains, path_prefixes=path_prefixes,
            robots_urls=robots_urls,
        )

    def fetch(self, url: str) -> list[Document]:
        documents = self._fetcher.fetch(url)
        self.last_discovery_diagnostics = self._fetcher.last_discovery_diagnostics
        self.last_page_ledger = self._fetcher.last_page_ledger
        return documents
