"""URL discovery chain for documentation sites.

Runs an ordered list of discovery strategies to find all documentation
page URLs. Short-circuits on the first strategy that returns results.

Strategy order:
1. /llms-full.txt  -- highest quality, entire docs in one file
2. /llms.txt       -- index of individual page URLs
3. robots.txt Sitemap: directives
4. /sitemap.xml    -- standard sitemap location
5. Platform-specific sitemap paths
6. Nav crawl       -- BFS of <nav> link hrefs

Fallback:
If sitemap strategies return fewer than MIN_DOC_PAGES usable URLs, a
nav-crawl fallback with higher depth runs automatically. seed_urls from
configuration are merged into the candidate URL set.
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from docmancer.connectors.fetchers.pipeline.detection import Platform
from docmancer.connectors.fetchers.pipeline.filtering import is_docs_url, normalize_url
from docmancer.connectors.fetchers.pipeline.robots import RobotsChecker
from docmancer.connectors.fetchers.pipeline.sitemap import parse_sitemap
from docmancer.core.html_utils import looks_like_html
from docmancer.connectors.fetchers.pipeline.extraction import discover_dartdoc_candidate_links, is_dartdoc_html

logger = logging.getLogger(__name__)

# Module-level counter for locale-skipped URLs during discovery.
# Reset in discover_urls(); read to surface locale_skipped_count in diagnostics.
_LOCALE_SKIP_COUNTER: list[int] = [0]

# Minimum content length for llms-full.txt to be considered valid.
_LLMS_FULL_MIN_CHARS = 1000

# Minimum number of docs pages expected from sitemap strategies before
# triggering the nav-crawl fallback. ReadTheDocs often exposes only the
# homepage in their sitemap; this threshold ensures a fallback attempt.
MIN_DOC_PAGES = 5


class DiscoveryStrategy(str, Enum):
    """Available URL discovery strategies."""
    LLMS_FULL_TXT = "llms-full.txt"
    LLMS_TXT = "llms.txt"
    ROBOTS_SITEMAP = "robots-sitemap"
    SITEMAP_XML = "sitemap.xml"
    PLATFORM_SITEMAP = "platform-sitemap"
    NAV_CRAWL = "nav-crawl"
    NAV_FALLBACK = "nav-fallback"
    SEED_URLS = "seed_urls"


class DiscoveredUrl:
    """A URL found by a discovery strategy, with metadata."""
    __slots__ = ("url", "strategy", "content")

    def __init__(self, url: str, strategy: DiscoveryStrategy, content: str | None = None):
        self.url = url
        self.strategy = strategy
        self.content = content  # Only set for llms-full.txt (contains the full doc)


@dataclass
class DiscoveryResult:
    """Container for discovery results and strategy diagnostics."""
    urls: list[DiscoveredUrl] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def discover_urls(
    base_url: str,
    client: httpx.Client,
    platform: Platform = Platform.GENERIC,
    robots: RobotsChecker | None = None,
    max_pages: int = 500,
    force_strategy: str | None = None,
    seed_urls: list[str] | None = None,
) -> DiscoveryResult:
    """Run discovery strategies in order and return found URLs.

    Short-circuits on llms-full.txt. Otherwise merges results from
    llms.txt, sitemap strategies, seed_urls, and nav-crawl.

    When sitemap strategies return fewer than MIN_DOC_PAGES usable URLs,
    a nav-fallback with higher depth runs automatically.

    Args:
        base_url: Root URL of the documentation site.
        client: httpx.Client for making requests.
        platform: Detected platform (for platform-specific hints).
        robots: Optional RobotsChecker instance.
        max_pages: Maximum number of URLs to return.
        force_strategy: If set, only run this specific strategy.
        seed_urls: Explicit page URLs to include (from config/docs.yaml).

    Returns:
        DiscoveryResult with urls and diagnostics.
    """
    strategies = [
        (DiscoveryStrategy.LLMS_FULL_TXT, lambda u, c, p, r, m: _try_llms_full_txt(u, c, p, r)),
        (DiscoveryStrategy.LLMS_TXT, lambda u, c, p, r, m: _try_llms_txt(u, c, p, r)),
        (DiscoveryStrategy.ROBOTS_SITEMAP, lambda u, c, p, r, m: _try_robots_sitemap(u, c, r, m)),
        (DiscoveryStrategy.SITEMAP_XML, _try_sitemap_xml),
        (DiscoveryStrategy.PLATFORM_SITEMAP, _try_platform_sitemap),
        (DiscoveryStrategy.NAV_CRAWL, _try_nav_crawl),
    ]

    if force_strategy:
        for strategy_enum, strategy_fn in strategies:
            if strategy_enum.value != force_strategy:
                continue
            try:
                result = strategy_fn(base_url, client, platform, robots, max_pages) or []
                return DiscoveryResult(urls=result[:max_pages])
            except Exception as exc:
                logger.debug("Discovery strategy %s failed: %s", strategy_enum.value, exc)
                return DiscoveryResult()

    _LOCALE_SKIP_COUNTER[0] = 0

    llms_full = _try_llms_full_txt(base_url, client, platform, robots)
    if llms_full:
        logger.info("Discovery: %s found %d URL(s)", DiscoveryStrategy.LLMS_FULL_TXT.value, len(llms_full))
        return DiscoveryResult(urls=llms_full)

    all_results: list[DiscoveredUrl] = []
    strategy_counts: dict[str, int] = {}
    nav_crawl_ran = False
    sitemap_total = 0
    for strategy_enum, strategy_fn in strategies[1:]:
        try:
            results = strategy_fn(base_url, client, platform, robots, max_pages)
            if results:
                strategy_counts[strategy_enum.value] = len(results)
                all_results.extend(results)
                if strategy_enum in (DiscoveryStrategy.ROBOTS_SITEMAP, DiscoveryStrategy.SITEMAP_XML, DiscoveryStrategy.PLATFORM_SITEMAP):
                    sitemap_total += len(results)
                if strategy_enum == DiscoveryStrategy.NAV_CRAWL:
                    nav_crawl_ran = True
        except Exception as exc:
            logger.debug("Discovery strategy %s failed: %s", strategy_enum.value, exc)

    # ---------------------------------------------------------------
    # Nav-fallback: when sitemap coverage is too low, run a deeper
    # nav crawl to try to discover more pages (common for ReadTheDocs).
    # ---------------------------------------------------------------
    fallback_reason = None
    fallback_results: list[DiscoveredUrl] = []
    if all_results and sitemap_total < MIN_DOC_PAGES and not nav_crawl_ran:
        fallback_results = _try_nav_fallback(base_url, client, platform, robots, max_pages) or []
        if fallback_results:
            fallback_reason = "low_sitemap_coverage"
            strategy_counts[DiscoveryStrategy.NAV_FALLBACK.value] = len(fallback_results)
            all_results.extend(fallback_results)
    elif sitemap_total < MIN_DOC_PAGES and nav_crawl_ran:
        # Nav-crawl ran but sitemap was sparse; this is primarily a
        # ReadTheDocs docset — log it for diagnostics.
        fallback_reason = "low_sitemap_coverage_nav_crawl_used"

    # ---------------------------------------------------------------
    # Seed URLs: merge explicit page URLs as an additional source.
    # ---------------------------------------------------------------
    seed_pages = 0
    if seed_urls:
        seed_discovered = []
        for seed in seed_urls:
            seed_discovered.append(DiscoveredUrl(url=seed, strategy=DiscoveryStrategy.SEED_URLS))
        if seed_discovered:
            strategy_counts[DiscoveryStrategy.SEED_URLS.value] = len(seed_discovered)
            seed_pages = len(seed_discovered)
            all_results.extend(seed_discovered)

    if all_results:
        ranked = _dedupe_and_rank(all_results)
        logger.info("Discovery candidates by strategy: %s", strategy_counts)
        discovery_strategy = _compute_discovery_strategy_label(
            strategy_counts, fallback_reason, bool(seed_urls),
        )
        return DiscoveryResult(
            urls=ranked[:max_pages],
            diagnostics={
                "strategies": dict(strategy_counts),
                "discovery_strategy": discovery_strategy,
                "fallback_reason": fallback_reason,
                "sitemap_pages": sitemap_total,
                "seed_pages": seed_pages,
                "fallback_pages": len(fallback_results),
                "locale_skipped_count": _LOCALE_SKIP_COUNTER[0],
            },
        )

    dartdoc = _try_dartdoc_index(base_url, client, max_pages)
    if dartdoc:
        logger.info("Discovery: dartdoc-index found %d URL(s)", len(dartdoc))
        return DiscoveryResult(
            urls=dartdoc[:max_pages],
            diagnostics={
                "strategies": {"dartdoc-index": len(dartdoc)},
                "discovery_strategy": "dartdoc-index",
                "fallback_reason": None,
                "sitemap_pages": 0,
                "seed_pages": 0,
                "fallback_pages": 0,
                "locale_skipped_count": _LOCALE_SKIP_COUNTER[0],
            },
        )

    logger.warning("No discovery strategy found URLs for %s", base_url)
    return DiscoveryResult(
        diagnostics={
            "strategies": {},
            "discovery_strategy": "none",
            "fallback_reason": "no_discovery",
            "sitemap_pages": 0,
            "seed_pages": 0,
            "fallback_pages": 0,
            "locale_skipped_count": _LOCALE_SKIP_COUNTER[0],
        },
    )


def _compute_discovery_strategy_label(
    strategy_counts: dict[str, int],
    fallback_reason: str | None,
    has_seed_urls: bool,
) -> str:
    parts = []
    for s in ("llms.txt", "robots-sitemap", "sitemap.xml", "platform-sitemap"):
        if strategy_counts.get(s, 0) > 0:
            parts.append("sitemap")
            break
    if fallback_reason and strategy_counts.get("nav-fallback", 0) > 0:
        parts.append("nav_fallback")
    elif strategy_counts.get("nav-crawl", 0) > 0:
        parts.append("nav_crawl")
    if has_seed_urls:
        parts.append("seed_urls")
    if not parts:
        return "none"
    return "+".join(parts)


def _try_dartdoc_index(base_url: str, client: httpx.Client, max_pages: int = 500) -> list[DiscoveredUrl] | None:
    try:
        resp = client.get(base_url)
    except httpx.RequestError:
        return None
    if resp.status_code != 200 or not is_dartdoc_html(resp.text, url=base_url):
        return None
    links = discover_dartdoc_candidate_links(resp.text, base_url)
    links.extend(_discover_dartdoc_index_json(base_url, client, max_pages=max_pages))
    if not links:
        return None
    return [DiscoveredUrl(url=url, strategy=DiscoveryStrategy.NAV_CRAWL) for url in links[:max_pages]]


def _discover_dartdoc_index_json(base_url: str, client: httpx.Client, max_pages: int = 500) -> list[str]:
    """Discover Dartdoc entity pages from static index.json navigation data."""
    index_url = f"{base_url.rstrip('/')}/index.json"
    try:
        resp = client.get(index_url)
    except httpx.RequestError:
        return []
    if resp.status_code != 200 or not resp.text.strip():
        return []
    try:
        payload = json.loads(resp.text)
    except json.JSONDecodeError:
        return []

    seen: set[str] = set()
    links: list[str] = []

    def add(value: str) -> None:
        href = value.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            return
        lowered = href.lower()
        if not any(token in lowered for token in ("-class.html", "-library.html", "-mixin.html", "-enum.html", "-extension.html", "-typedef.html", "-function.html")):
            return
        url = normalize_url(urljoin(base_url, href))
        if url in seen:
            return
        seen.add(url)
        links.append(url)

    def visit(value: Any) -> None:
        if len(links) >= max_pages:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"href", "url", "link", "path"} and isinstance(item, str):
                    add(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return links


def _dedupe_and_rank(results: list[DiscoveredUrl]) -> list[DiscoveredUrl]:
    by_url: dict[str, DiscoveredUrl] = {}
    for result in results:
        key = normalize_url(result.url)
        existing = by_url.get(key)
        if existing is None or _strategy_rank(result.strategy) < _strategy_rank(existing.strategy):
            by_url[key] = result
    return sorted(by_url.values(), key=lambda item: (_strategy_rank(item.strategy), _path_rank(item.url), item.url))


def _strategy_rank(strategy: DiscoveryStrategy) -> int:
    return {
        DiscoveryStrategy.LLMS_TXT: 0,
        DiscoveryStrategy.ROBOTS_SITEMAP: 1,
        DiscoveryStrategy.SITEMAP_XML: 2,
        DiscoveryStrategy.PLATFORM_SITEMAP: 3,
        DiscoveryStrategy.NAV_CRAWL: 4,
        DiscoveryStrategy.NAV_FALLBACK: 5,
        DiscoveryStrategy.SEED_URLS: 6,
    }.get(strategy, 10)


def _path_rank(url: str) -> int:
    path = urlparse(url).path.lower()
    if any(part in path for part in ("/docs", "/documentation", "/reference", "/api", "/guide")):
        return 0
    return 1


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _is_valid_text_response(resp: httpx.Response) -> bool:
    """Check that the response is plain text, not an HTML error page."""
    content_type = resp.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        return False
    if looks_like_html(resp.text):
        return False
    return True


def _try_llms_full_txt(
    base_url: str, client: httpx.Client, platform: Platform, robots: RobotsChecker | None,
) -> list[DiscoveredUrl] | None:
    """Try fetching /llms-full.txt (entire docs in one file)."""
    url = f"{base_url}/llms-full.txt"
    try:
        resp = client.get(url)
    except httpx.RequestError:
        return None

    if resp.status_code != 200 or not resp.text.strip():
        return None
    if not _is_valid_text_response(resp):
        return None
    if len(resp.text) < _LLMS_FULL_MIN_CHARS:
        return None

    # llms-full.txt is the content itself, not a list of URLs
    return [DiscoveredUrl(url=url, strategy=DiscoveryStrategy.LLMS_FULL_TXT, content=resp.text)]


def _try_llms_txt(
    base_url: str, client: httpx.Client, platform: Platform, robots: RobotsChecker | None,
) -> list[DiscoveredUrl] | None:
    """Try fetching /llms.txt (index of page URLs)."""
    url = f"{base_url}/llms.txt"
    try:
        resp = client.get(url)
    except httpx.RequestError:
        return None

    if resp.status_code != 200 or not resp.text.strip():
        return None
    if not _is_valid_text_response(resp):
        return None

    urls = _parse_llms_txt(resp.text, base_url)
    if not urls:
        return None

    return [DiscoveredUrl(url=u, strategy=DiscoveryStrategy.LLMS_TXT) for u in urls]


def _parse_llms_txt(content: str, base_url: str) -> list[str]:
    """Extract URLs from llms.txt index format.

    Handles bare URLs, markdown links [Title](url), and relative URLs.
    """
    urls = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Markdown link: [Title](url)
        match = re.search(r'\(([^)]+)\)', line)
        if match:
            candidate = match.group(1)
            if candidate.startswith(("http://", "https://", "/")):
                urls.append(_resolve(candidate, base_url))
                continue
        # Bare URL
        if line.startswith(("http://", "https://")):
            urls.append(line.split()[0])
        elif line.startswith("/"):
            urls.append(_resolve(line.split()[0], base_url))
    return urls


def _resolve(url: str, base_url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


def _try_robots_sitemap(
    base_url: str, client: httpx.Client, robots: RobotsChecker | None,
    max_pages: int = 500,
) -> list[DiscoveredUrl] | None:
    """Use Sitemap: directives from robots.txt."""
    if robots is None:
        return None

    sitemap_urls = robots.get_sitemaps(base_url)
    if not sitemap_urls:
        return None

    all_urls = []
    for sitemap_url in sitemap_urls:
        remaining = max_pages - len(all_urls)
        if remaining <= 0:
            break
        entries = parse_sitemap(sitemap_url, client, max_entries=remaining, scope_base_url=base_url)
        for entry in entries:
            if entry["url"] and is_docs_url(entry["url"], base_url, locale_skip_counter=_LOCALE_SKIP_COUNTER):
                all_urls.append(
                    DiscoveredUrl(url=entry["url"], strategy=DiscoveryStrategy.ROBOTS_SITEMAP)
                )
                if len(all_urls) >= max_pages:
                    break

    return all_urls if all_urls else None


def _try_sitemap_xml(
    base_url: str,
    client: httpx.Client,
    platform: Platform | None = None,
    robots: RobotsChecker | None = None,
    max_pages: int = 500,
) -> list[DiscoveredUrl] | None:
    """Try the standard /sitemap.xml location."""
    for path in ["/sitemap.xml", "/sitemap_index.xml"]:
        sitemap_url = f"{base_url}{path}"
        entries = parse_sitemap(sitemap_url, client, max_entries=max_pages, scope_base_url=base_url)
        if entries:
            results = []
            for entry in entries:
                if entry["url"] and is_docs_url(entry["url"], base_url, locale_skip_counter=_LOCALE_SKIP_COUNTER):
                    results.append(
                        DiscoveredUrl(url=entry["url"], strategy=DiscoveryStrategy.SITEMAP_XML)
                    )
                    if len(results) >= max_pages:
                        break
            if results:
                return results
    return None


def _try_platform_sitemap(
    base_url: str,
    client: httpx.Client,
    platform: Platform,
    robots: RobotsChecker | None,
    max_pages: int = 500,
) -> list[DiscoveredUrl] | None:
    """Try platform-specific sitemap paths."""
    platform_paths: dict[Platform, list[str]] = {
        Platform.MKDOCS: ["/sitemap.xml.gz", "/sitemap.xml"],
        Platform.SPHINX: ["/sitemap.xml"],
        Platform.READTHEDOCS: ["/sitemap.xml"],
        Platform.DOCUSAURUS: ["/sitemap.xml"],
        Platform.VITEPRESS: ["/sitemap.xml"],
    }
    paths = platform_paths.get(platform, [])
    for path in paths:
        sitemap_url = f"{base_url}{path}"
        entries = parse_sitemap(sitemap_url, client, max_entries=max_pages, scope_base_url=base_url)
        if entries:
            results = [
                DiscoveredUrl(url=e["url"], strategy=DiscoveryStrategy.PLATFORM_SITEMAP)
                for e in entries[:max_pages]
                if e["url"] and is_docs_url(e["url"], base_url, locale_skip_counter=_LOCALE_SKIP_COUNTER)
            ]
            if results:
                return results
    return None


def _try_nav_crawl(
    base_url: str,
    client: httpx.Client,
    platform: Platform | None = None,
    robots: RobotsChecker | None = None,
    max_pages: int = 500,
) -> list[DiscoveredUrl] | None:
    """BFS crawl of navigation links from the homepage.

    Fetches the homepage, extracts links from <nav> elements and
    common navigation selectors, then follows those links one level deep.
    """
    seen = {normalize_url(base_url)}
    found: list[str] = []
    queue = deque([(base_url, 0)])
    max_depth = 2

    while queue and len(found) < max_pages:
        page_url, depth = queue.popleft()
        if robots and not robots.can_fetch(page_url):
            continue
        try:
            resp = client.get(page_url)
            if resp.status_code != 200:
                continue
        except httpx.RequestError:
            continue

        links = _extract_nav_links(resp.text, page_url, base_url)
        for link_url in links:
            if link_url in seen:
                continue
            seen.add(link_url)
            found.append(link_url)
            if len(found) >= max_pages:
                break
            if depth < max_depth:
                queue.append((link_url, depth + 1))

    if not found:
        return None

    return [DiscoveredUrl(url=u, strategy=DiscoveryStrategy.NAV_CRAWL) for u in found]


def _try_nav_fallback(
    base_url: str,
    client: httpx.Client,
    platform: Platform | None = None,
    robots: RobotsChecker | None = None,
    max_pages: int = 500,
) -> list[DiscoveredUrl] | None:
    """Aggressive nav crawl fallback for low-sitemap docs sites.

    Uses higher depth (3), more selectors, and always falls back to
    all page links if nav/container selectors find too few.
    """
    seen = {normalize_url(base_url)}
    found: list[str] = []
    queue = deque([(base_url, 0)])
    max_depth = 3

    while queue and len(found) < max_pages:
        page_url, depth = queue.popleft()
        if robots and not robots.can_fetch(page_url):
            continue
        try:
            resp = client.get(page_url)
            if resp.status_code != 200:
                continue
        except httpx.RequestError:
            continue

        links = _extract_nav_links(resp.text, page_url, base_url, fallback_mode=True)
        for link_url in links:
            if link_url in seen:
                continue
            seen.add(link_url)
            found.append(link_url)
            if len(found) >= max_pages:
                break
            if depth < max_depth:
                queue.append((link_url, depth + 1))

    if not found:
        return None

    return [DiscoveredUrl(url=u, strategy=DiscoveryStrategy.NAV_FALLBACK) for u in found]


def _extract_nav_links(html: str, page_url: str, base_url: str, fallback_mode: bool = False) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    nav_selectors = ["nav a", ".sidebar a", "[role='navigation'] a", ".toc a", ".menu a"]

    seen = set()
    nav_links = []
    for selector in nav_selectors:
        for link in soup.select(selector):
            _append_link(link.get("href"), page_url, base_url, seen, nav_links)

    threshold = 10 if fallback_mode else 5

    if len(nav_links) < threshold:
        for selector in ["main a", "article a", ".section a", ".content a", ".bd-main a", ".document a"]:
            for link in soup.select(selector):
                _append_link(link.get("href"), page_url, base_url, seen, nav_links)

    if len(nav_links) < threshold:
        for link in soup.find_all("a", href=True):
            _append_link(link.get("href"), page_url, base_url, seen, nav_links)

    return nav_links


def _append_link(
    href: str | None,
    page_url: str,
    base_url: str,
    seen: set[str],
    output: list[str],
) -> None:
    if not href:
        return
    full_url = normalize_url(_resolve(href, page_url))
    if full_url not in seen and is_docs_url(full_url, base_url, locale_skip_counter=_LOCALE_SKIP_COUNTER):
        seen.add(full_url)
        output.append(full_url)
