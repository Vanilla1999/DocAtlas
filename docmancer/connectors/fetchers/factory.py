from __future__ import annotations

from urllib.parse import urlparse


def detect_fetcher_provider(url: str, provider: str | None = None) -> str:
    """Return the concrete fetcher provider for a URL."""
    if provider and provider != "auto":
        return provider.lower()

    if urlparse(url).netloc.lower() == "github.com":
        return "github"
    return "web"


def build_fetcher(
    url: str,
    provider: str | None = None,
    *,
    timeout: float = 30.0,
    max_pages: int = 500,
    strategy: str | None = None,
    browser: bool = False,
    respect_robots: bool = True,
    delay: float = 0.5,
    workers: int = 8,
    doc_format: str | None = None,
    seed_urls: list[str] | None = None,
    allowed_domains: list[str] | None = None,
    path_prefixes: list[str] | None = None,
    max_redirects: int = 5,
    connect_timeout: float = 10.0,
    max_total_seconds: float = 120.0,
    use_env_proxy: bool = False,
    proxy_url: str | None = None,
    max_response_bytes: int = 8 * 1024 * 1024,
    max_decoded_text_bytes: int = 16 * 1024 * 1024,
    progress_callback=None,
    cancellation_callback=None,
):
    """Build the fetcher shared by the CLI and registry pipeline."""
    concrete = detect_fetcher_provider(url, provider)
    if concrete not in {"web", "gitbook", "mintlify", "github", "crawl4ai", "auto"}:
        raise ValueError(f"Unsupported fetch provider: {concrete}")

    from docmancer.connectors.fetchers.web import WebFetcher

    return WebFetcher(
        timeout=timeout,
        max_pages=max_pages,
        strategy=strategy,
        browser=browser,
        respect_robots=respect_robots,
        delay=delay,
        workers=workers,
        doc_format=doc_format,
        seed_urls=seed_urls,
        allowed_domains=allowed_domains,
        path_prefixes=path_prefixes,
        max_redirects=max_redirects,
        connect_timeout=connect_timeout,
        max_total_seconds=max_total_seconds,
        use_env_proxy=use_env_proxy,
        proxy_url=proxy_url,
        max_response_bytes=max_response_bytes,
        max_decoded_text_bytes=max_decoded_text_bytes,
        progress_callback=progress_callback,
        cancellation_callback=cancellation_callback,
    )
