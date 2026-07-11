"""Generic web fetcher for any documentation site.

Implements the full ingestion pipeline:
1. Fetch homepage and detect platform
2. Run discovery chain to find all doc page URLs
3. Filter, normalize, and deduplicate URLs
4. Fetch each page with rate limiting and robots.txt compliance
5. Extract content with trafilatura + markdownify
6. Deduplicate content and build Document objects
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from docmancer.connectors.fetchers.pipeline.detection import Platform, detect_platform
from docmancer.connectors.fetchers.pipeline.discovery import (
    DiscoveredUrl,
    DiscoveryResult,
    DiscoveryStrategy,
    discover_urls,
)
from docmancer.connectors.fetchers.pipeline.extraction import (
    discover_dartdoc_candidate_links,
    extract_content,
    extract_metadata,
    extract_section_path,
    is_dartdoc_html,
)
from docmancer.connectors.fetchers.pipeline.filtering import (
    ContentDeduplicator,
    infer_docset_root,
    is_docs_url,
    normalize_url,
    resolve_url,
)
from docmancer.connectors.fetchers.pipeline.rate_limit import RateLimiter
from docmancer.connectors.fetchers.pipeline.redirect import RedirectTracker
from docmancer.connectors.fetchers.pipeline.robots import RobotsChecker
from docmancer.core.html_utils import looks_like_html
from docmancer.core.models import Document
from docmancer.docs.dartdoc import DARTDOC_ENTITY_SUFFIXES
from docmancer.docs.fetch_policy import DocsFetchPolicy

logger = logging.getLogger(__name__)

# Default HTTP client settings.
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_USER_AGENT = "docmancer/1.0 (+https://github.com/docmancer/docmancer)"
_DIRECT_TEXT_SUFFIXES = {".md", ".txt"}
_DIRECT_DARTDOC_SUFFIXES = DARTDOC_ENTITY_SUFFIXES


def _source_docset_root(final_url: str, base_url: str) -> str:
    base_host = urlparse(base_url).hostname
    final = urlparse(final_url)
    if base_host == final.hostname:
        return normalize_url(base_url)
    parts = [part for part in final.path.split("/") if part]
    if final.hostname == "pub.dev" and len(parts) >= 3 and parts[0] == "documentation":
        return normalize_url(f"{final.scheme}://{final.netloc}/{'/'.join(parts[:3])}")
    return infer_docset_root(final_url) or final_url


@dataclass(slots=True)
class _FetchedPage:
    document: Document
    final_url: str


class WebFetcher:
    """Generic documentation fetcher that works with any docs site.

    Implements the Fetcher protocol: ``def fetch(self, url: str) -> list[Document]``.

    Uses platform detection to select the best discovery strategy,
    then fetches and extracts content from discovered pages.

    Args:
        timeout: HTTP request timeout in seconds.
        max_pages: Maximum number of pages to fetch.
        strategy: Force a specific discovery strategy (e.g. "llms-full.txt").
        browser: Enable Playwright browser fallback for JS-heavy sites.
        respect_robots: Whether to respect robots.txt (default True).
        delay: Base delay between requests to same host (seconds).
    """

    def __init__(
        self,
        timeout: float = _DEFAULT_TIMEOUT,
        max_pages: int = 500,
        strategy: str | None = None,
        browser: bool = False,
        respect_robots: bool = True,
        delay: float = 0.5,
        workers: int = 8,
        doc_format: str | None = None,
        seed_urls: list[str] | None = None,
        progress_callback=None,
        cancellation_callback=None,
        fetch_policy: DocsFetchPolicy | None = None,
    ):
        self._timeout = timeout
        self._max_pages = max_pages
        self._strategy = strategy
        self._browser = browser
        self._respect_robots = respect_robots
        self._delay = delay
        self._workers = max(1, workers)
        self._doc_format = doc_format
        self._seed_urls = list(seed_urls or [])
        self._progress_callback = progress_callback
        self._cancellation_callback = cancellation_callback
        self._fetch_policy = fetch_policy or DocsFetchPolicy()
        self.last_discovery_diagnostics: dict | None = None

    def _emit_progress(self, event: dict) -> None:
        if not self._progress_callback:
            return
        try:
            self._progress_callback(event)
        except Exception:
            logger.debug("progress callback failed", exc_info=True)

    def _client_kwargs(self) -> dict:
        return {
            "timeout": self._timeout,
            "follow_redirects": True,
            "headers": {"User-Agent": _DEFAULT_USER_AGENT},
        }

    def fetch(self, url: str) -> list[Document]:
        """Fetch documentation from a URL using the generic pipeline.

        Args:
            url: Root URL of the documentation site.

        Returns:
            List of Document objects with extracted content and rich metadata.

        Raises:
            ValueError: If no documentation pages could be discovered or fetched.
        """
        self._raise_if_cancelled()
        self._fetch_policy.validate_url(url)
        base_url = url.rstrip("/")

        with httpx.Client(**self._client_kwargs()) as client:
            if self._is_direct_text_url(base_url):
                return [self._fetch_direct_text_page(base_url, client)]
            if self._is_direct_dartdoc_url(base_url):
                page = self._fetch_dartdoc_direct_page(base_url, base_url, client, Platform.GENERIC)
                if page is None:
                    raise ValueError(
                        f"Dartdoc page {base_url!r} had no extractable article content. "
                        "Try concrete class/library seed URLs or browser=true."
                    )
                return [page.document]

            # Step 1: Fetch homepage and detect platform
            platform, root_html, root_headers = self._fetch_and_detect(base_url, client)
            self._raise_if_cancelled()
            logger.info("Detected platform: %s", platform.value)

            # Step 2: Set up robots.txt checker
            robots = None
            if self._respect_robots:
                robots = RobotsChecker(client)
                crawl_delay = robots.get_crawl_delay(base_url)
                if crawl_delay:
                    self._delay = max(self._delay, crawl_delay)

            # Step 3: Discover page URLs
            self._emit_progress({"phase": "discovering", "message": f"Discovering URLs from {base_url}", "url": base_url})
            discovery_result = discover_urls(
                base_url=base_url,
                client=client,
                platform=platform,
                robots=robots,
                max_pages=self._max_pages,
                force_strategy=self._strategy,
                seed_urls=self._seed_urls,
            )
            discovered = discovery_result.urls
            self._raise_if_cancelled()
            self.last_discovery_diagnostics = discovery_result.diagnostics

            if not discovered and is_dartdoc_html(root_html, url=base_url):
                candidates = discover_dartdoc_candidate_links(root_html, base_url)
                if candidates:
                    discovered = [DiscoveredUrl(url=item, strategy=DiscoveryStrategy.NAV_CRAWL) for item in candidates[: self._max_pages]]

            if not discovered:
                # Check if the page might be JavaScript-rendered
                body_words = len(root_html.split()) if root_html else 0
                hint = ""
                if body_words < 50:
                    hint = (
                        " The page appears to be JavaScript-rendered (very little content "
                        "in the static HTML). Try: doc-atlas add <url> --browser"
                    )
                raise ValueError(
                    f"Could not discover any documentation pages at {base_url!r}. "
                    f"No /llms-full.txt, /llms.txt, sitemap, or navigable links found.{hint}"
                )
            self._emit_progress(
                {
                    "phase": "discovering",
                    "message": f"Discovered {len(discovered)} URLs",
                    "url": base_url,
                    "discovered_pages": len(discovered),
                    "total_pages": len(discovered),
                }
            )

            # Step 4: Handle llms-full.txt (content already available)
            if (
                len(discovered) == 1
                and discovered
                and discovered[0].strategy == DiscoveryStrategy.LLMS_FULL_TXT
                and discovered[0].content
            ):
                return self._build_llms_full_documents(discovered[0], platform)

            # Step 5: Fetch and extract each page
            return self._fetch_pages(discovered, base_url, client, platform, robots)

    def _raise_if_cancelled(self) -> None:
        if self._cancellation_callback and self._cancellation_callback():
            raise RuntimeError("Documentation fetch cancelled.")

    @staticmethod
    def _is_direct_text_url(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(suffix) for suffix in _DIRECT_TEXT_SUFFIXES)

    def _is_dartdoc_url(self, url: str) -> bool:
        if self._doc_format == "dartdoc":
            return True
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        return host == "api.flutter.dev" or (host == "pub.dev" and path.startswith("/documentation/"))

    def _is_direct_dartdoc_url(self, url: str) -> bool:
        return self._is_dartdoc_url(url) and urlparse(url).path.lower().endswith(_DIRECT_DARTDOC_SUFFIXES)

    def _fetch_direct_text_page(self, url: str, client: httpx.Client) -> Document:
        """Fetch an exact markdown/text docs URL without running site discovery."""
        try:
            resp = client.get(url)
        except httpx.RequestError as exc:
            raise ValueError(f"Could not fetch documentation page {url!r}: {exc}") from exc

        if resp.status_code != 200:
            raise ValueError(f"Could not fetch documentation page {url!r}: status {resp.status_code}")
        if not resp.text.strip():
            raise ValueError(f"Could not fetch documentation page {url!r}: empty response")
        if looks_like_html(resp.text):
            raise ValueError(f"Could not fetch documentation page {url!r}: response appears to be HTML")

        resp_url = getattr(resp, "url", None)
        if isinstance(resp_url, (str, httpx.URL)):
            final_url = normalize_url(str(resp_url))
        else:
            final_url = normalize_url(url)
        content = resp.text
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        content_hash = ContentDeduplicator.content_hash(content)
        suffix = urlparse(final_url).path.lower().rsplit(".", 1)[-1]
        fmt = "markdown" if suffix == "md" else "text"
        return Document(
            source=final_url,
            content=content,
            metadata={
                "fetch_method": "direct-url",
                "format": fmt,
                "docset_root": infer_docset_root(final_url) or final_url,
                "platform": Platform.GENERIC.value,
                "title": None,
                "description": None,
                "lang": None,
                "canonical_url": final_url,
                "section_path": [],
                "content_hash": content_hash,
                "word_count": len(content.split()),
                "fetched_at": fetched_at,
            },
        )

    def _fetch_dartdoc_direct_page(
        self,
        url: str,
        base_url: str,
        client: httpx.Client,
        platform: Platform,
    ) -> _FetchedPage | None:
        return self._fetch_page(
            DiscoveredUrl(url=url, strategy=DiscoveryStrategy.NAV_CRAWL),
            base_url,
            platform,
            robots=None,
            rate_limiter=RateLimiter(delay=0.0),
            redirect_tracker=RedirectTracker(),
            redirect_lock=threading.Lock(),
        )

    def _fetch_and_detect(
        self, base_url: str, client: httpx.Client
    ) -> tuple[Platform, str, dict[str, str]]:
        """Fetch the homepage and detect the platform."""
        try:
            resp = client.get(base_url)
            html = resp.text
            headers = dict(resp.headers)
            platform = detect_platform(html, base_url, headers)
            return platform, html, headers
        except httpx.RequestError as exc:
            logger.warning("Failed to fetch homepage %s: %s", base_url, exc)
            return Platform.GENERIC, "", {}

    def _build_llms_full_documents(
        self, discovered: DiscoveredUrl, platform: Platform
    ) -> list[Document]:
        """Build Document list from llms-full.txt content."""
        content = discovered.content or ""
        return [
            Document(
                source=discovered.url,
                content=content,
                metadata={
                    "format": "markdown",
                    "fetch_method": "llms-full.txt",
                    "docset_root": discovered.url.removesuffix("/llms-full.txt"),
                    "platform": platform.value,
                    "word_count": len(content.split()),
                    "content_hash": ContentDeduplicator.content_hash(content),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        ]

    def _fetch_pages(
        self,
        discovered: list[DiscoveredUrl],
        base_url: str,
        client: httpx.Client,
        platform: Platform,
        robots: RobotsChecker | None,
    ) -> list[Document]:
        """Fetch, extract, and build Documents for a list of discovered URLs."""
        rate_limiter = RateLimiter(delay=self._delay)
        deduplicator = ContentDeduplicator()
        redirect_tracker = RedirectTracker()
        redirect_lock = threading.Lock()
        documents = []
        unique_discovered: list[DiscoveredUrl] = []
        for disc in discovered:
            self._raise_if_cancelled()
            normalized = normalize_url(disc.url)
            if deduplicator.is_url_duplicate(normalized):
                continue
            unique_discovered.append(disc)

        max_workers = min(self._workers, max(1, len(unique_discovered)))
        executor = ThreadPoolExecutor(max_workers=max_workers)
        pending = {
                executor.submit(
                    self._fetch_page,
                    disc,
                    base_url,
                    platform,
                    robots,
                    rate_limiter,
                    redirect_tracker,
                    redirect_lock,
                )
                for disc in unique_discovered
            }
        cancelled = False
        try:
            deduplicator.reset()
            while pending:
                self._raise_if_cancelled()
                done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done:
                    completed_fetches = getattr(self, "_completed_fetches", 0) + 1
                    self._completed_fetches = completed_fetches
                    page = future.result()
                    if page is None:
                        self._emit_progress(
                            {
                                "phase": "fetching",
                                "message": f"Fetched {completed_fetches}/{len(unique_discovered)} pages",
                                "fetched_pages": completed_fetches,
                                "failed_pages": 1,
                                "total_pages": len(unique_discovered),
                            }
                        )
                        continue
                    if deduplicator.is_url_duplicate(page.final_url):
                        logger.debug("Skipped %s (duplicate final URL)", page.document.source)
                        continue
                    if page.document.source != page.final_url and deduplicator.is_url_duplicate(page.document.source):
                        logger.debug("Skipped %s (duplicate canonical URL)", page.document.source)
                        continue
                    if deduplicator.is_content_duplicate(page.document.content):
                        logger.debug("Skipped %s (duplicate content)", page.document.source)
                        continue
                    documents.append(page.document)
                    logger.info("Fetched %s (%d words)", page.document.source, len(page.document.content.split()))
                    self._emit_progress(
                        {
                            "phase": "fetching",
                            "message": f"Fetched {completed_fetches}/{len(unique_discovered)} pages",
                            "url": page.document.source,
                            "fetched_pages": completed_fetches,
                            "total_pages": len(unique_discovered),
                        }
                    )
        except RuntimeError as exc:
            cancelled = "cancelled" in str(exc).lower()
            raise
        finally:
            if cancelled:
                for future in pending:
                    future.cancel()
            executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

        if not documents:
            last_url = unique_discovered[-1].url if unique_discovered else base_url
            if self._is_dartdoc_url(base_url):
                candidate_hint = ""
                if unique_discovered:
                    candidate_hint = f" Candidate doc links tried: {', '.join(item.url for item in unique_discovered[:5])}."
                raise ValueError(
                    f"Extraction failed for {len(unique_discovered)} page(s). Last URL: {last_url}. "
                    "Dartdoc extraction found no usable documentation content."
                    f"{candidate_hint} Try concrete class/library seed URLs or browser=true."
                )
            raise ValueError(
                f"Extraction failed for {len(unique_discovered)} page(s). Last URL: {last_url}. "
                "Try class/library seed URLs or browser=true."
            )

        return documents

    def _fetch_page(
        self,
        disc: DiscoveredUrl,
        base_url: str,
        platform: Platform,
        robots: RobotsChecker | None,
        rate_limiter: RateLimiter,
        redirect_tracker: RedirectTracker,
        redirect_lock: threading.Lock,
    ) -> _FetchedPage | None:
        url = normalize_url(disc.url)
        self._emit_progress({"phase": "fetching", "message": f"Fetching {url}", "url": url})
        is_seed_url = disc.strategy == DiscoveryStrategy.SEED_URLS
        if robots and not robots.can_fetch(url):
            logger.debug("Skipped %s (blocked by robots.txt)", url)
            return None
        if not is_seed_url and not is_docs_url(url, base_url):
            logger.debug("Skipped %s (out of docs scope)", url)
            return None

        with redirect_lock:
            predicted_url = redirect_tracker.predict_final_url(url)
        fetch_url = predicted_url or url

        with httpx.Client(**self._client_kwargs()) as client:
            rate_limiter.wait(fetch_url)
            try:
                resp = client.get(fetch_url)
            except httpx.RequestError as exc:
                logger.warning("Failed to fetch %s: %s", fetch_url, exc)
                self._emit_progress({"phase": "fetching", "message": f"Fetch failed: {url}", "url": url})
                return None

            if resp.status_code == 404 and predicted_url and fetch_url == predicted_url:
                logger.debug("Predicted URL %s returned 404, retrying original %s", predicted_url, url)
                rate_limiter.wait(url)
                try:
                    resp = client.get(url)
                except httpx.RequestError as exc:
                    logger.warning("Failed to fetch %s: %s", url, exc)
                    return None
                fetch_url = url

            if resp.status_code in {429, 503}:
                rate_limiter.record_rate_limit(fetch_url)
                logger.warning("Rate limited on %s (status %d), skipping", fetch_url, resp.status_code)
                return None
            if resp.status_code != 200:
                logger.debug("Skipped %s (status %d)", fetch_url, resp.status_code)
                self._emit_progress({"phase": "fetching", "message": f"Fetch failed with status {resp.status_code}: {url}", "url": url})
                return None

            rate_limiter.reset_backoff(fetch_url)
            resp_url = getattr(resp, "url", None)
            if isinstance(resp_url, (str, httpx.URL)):
                final_url = normalize_url(str(resp_url))
            else:
                final_url = normalize_url(fetch_url)
            if final_url != normalize_url(fetch_url):
                with redirect_lock:
                    redirect_tracker.record_redirect(url, final_url)
            raw_html = resp.text

        if looks_like_html(raw_html):
            doc_format = "dartdoc" if self._is_dartdoc_url(url) or is_dartdoc_html(raw_html, url=final_url) else None
            content = extract_content(raw_html, url=url, doc_format=doc_format)
            meta = extract_metadata(raw_html, url=final_url)
            section_path = extract_section_path(raw_html)
            fmt = "markdown"
        else:
            content = raw_html
            meta = {"title": None, "description": None, "lang": None, "canonical_url": None}
            section_path = []
            fmt = "markdown"

        if not content or not content.strip():
            logger.debug("Skipped %s (empty after extraction)", url)
            return None

        if self._browser and len(content.split()) < 100 and looks_like_html(raw_html):
            browser_content = self._try_browser_fallback(url)
            if browser_content:
                content = browser_content

        content_hash = ContentDeduplicator.content_hash(content)
        canonical = normalize_url(resolve_url(str(meta.get("canonical_url")), final_url)) if meta.get("canonical_url") else url
        source_url = canonical if (is_seed_url or is_docs_url(canonical, base_url)) else url
        docset_root = _source_docset_root(final_url, base_url)
        doc = Document(
            source=source_url,
            content=content,
            metadata={
                "format": fmt,
                "fetch_method": disc.strategy.value,
                "docset_root": docset_root,
                "platform": platform.value,
                "canonical_url": canonical,
                "content_hash": content_hash,
                "word_count": len(content.split()),
                "title": meta.get("title"),
                "description": meta.get("description"),
                "section_path": section_path,
                "lang": meta.get("lang") or "en",
                "http_status": resp.status_code,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return _FetchedPage(document=doc, final_url=final_url)

    def _try_browser_fallback(self, url: str) -> str | None:
        """Attempt to render a page with Playwright and extract content."""
        try:
            from docmancer.connectors.fetchers.pipeline.browser import BrowserRenderer
            renderer = BrowserRenderer()
            html = renderer.render(url)
            if html:
                return extract_content(html, url=url)
        except ImportError:
            logger.debug(
                "Playwright not installed. Install with: pip install docmancer[browser]"
            )
        except Exception as exc:
            logger.debug("Browser fallback failed for %s: %s", url, exc)
        return None
