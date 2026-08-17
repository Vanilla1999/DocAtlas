"""WebFetcher implementation shard 1."""
from __future__ import annotations

from .shared import *  # noqa: F401,F403


class _WebFetcherPart01:
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
        deadline_at: float | None = None,
        fetch_policy: DocsFetchPolicy | None = None,
        allowed_domains: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        max_response_bytes: int = 8 * 1024 * 1024,
        max_decoded_text_bytes: int = 16 * 1024 * 1024,
        max_redirects: int = 5,
        connect_timeout: float = 10.0,
        max_total_seconds: float = 120.0,
        use_env_proxy: bool = False,
        proxy_url: str | None = None,
        source_manifest: dict | None = None,
        max_fetched_document_bytes: int = 64 * 1024 * 1024,
        query: str | None = None,
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
        self._deadline_at = deadline_at
        self._fetch_policy = fetch_policy or DocsFetchPolicy(
            allowed_hosts=tuple(allowed_domains or ()),
            path_prefixes=tuple(path_prefixes or ()),
        )
        self._max_response_bytes = max_response_bytes
        self._max_decoded_text_bytes = max_decoded_text_bytes
        self._max_redirects = max_redirects
        self._connect_timeout = connect_timeout
        self._max_total_seconds = max_total_seconds
        self._use_env_proxy = use_env_proxy
        self._proxy_url = proxy_url
        self._source_manifest = (
            normalize_resolved_github_manifest(source_manifest) if source_manifest is not None else None
        )
        self._max_fetched_document_bytes = max_fetched_document_bytes
        self._query = query
        self.last_discovery_diagnostics: dict | None = None
        self.last_page_ledger: list[dict] = []
        self._ledger_lock = threading.Lock()

    def _emit_progress(self, event: dict) -> None:
        if not self._progress_callback:
            return
        try:
            self._progress_callback(event)
        except Exception:
            logger.debug("progress callback failed", exc_info=True)

    def _client_kwargs(self) -> dict:
        return {
            "timeout": httpx.Timeout(
                connect=self._connect_timeout,
                read=self._timeout,
                write=self._timeout,
                pool=self._connect_timeout,
            ),
            "follow_redirects": False,
            "headers": {"User-Agent": _DEFAULT_USER_AGENT},
            "trust_env": self._use_env_proxy,
            **({"proxy": self._proxy_url} if self._proxy_url else {}),
        }

    def _new_client(self, policy: DocsFetchPolicy | None = None) -> DocsHttpClient:
        try:
            raw_client = httpx.Client(**self._client_kwargs())
        except ImportError:
            if not self._proxy_url and not self._use_env_proxy:
                raise
            raise DocsFetchSecurityError(
                "proxy_configuration_error", "<configured-proxy>", phase="configuring", retryable=False
            ) from None
        return DocsHttpClient(
            raw_client,
            policy or self._fetch_policy,
            max_redirects=self._max_redirects,
            max_response_bytes=self._max_response_bytes,
            max_decoded_text_bytes=self._max_decoded_text_bytes,
            max_total_seconds=self._max_total_seconds,
            deadline_at=self._deadline_at,
            pin_resolved_ips=not (self._proxy_url or self._use_env_proxy),
        )

    def _policy_for(self, url: str) -> DocsFetchPolicy:
        if self._fetch_policy.allowed_hosts:
            return self._fetch_policy
        hosts = {
            parsed.hostname.rstrip(".").lower()
            for candidate in [url, *self._seed_urls]
            if (parsed := urlparse(candidate)).hostname
        }
        return replace(self._fetch_policy, allowed_hosts=tuple(sorted(hosts)))

    def fetch(self, url: str) -> list[Document]:
        """Fetch documentation from a URL using the generic pipeline.

        Args:
            url: Root URL of the documentation site.

        Returns:
            List of Document objects with extracted content and rich metadata.

        Raises:
            ValueError: If no documentation pages could be discovered or fetched.
        """
        self.last_fetch_failure: DocsFetchSecurityError | None = None
        self.last_page_ledger = []
        policy = self._policy_for(url)
        base_url = url.rstrip("/")
        public_base_url = redact_url(base_url)
        if self._source_manifest is not None:
            try:
                self._raise_if_cancelled()
                policy.validate_url(url)
            except (DocsFetchSecurityError, RuntimeError) as exc:
                reason = exc.category if isinstance(exc, DocsFetchSecurityError) else "cancelled"
                self._record_page(
                    requested_url=base_url, discovered_url=base_url, canonical_url=base_url,
                    redirect_url=None, fetch_url=None, fetcher="github-manifest",
                    outcome="failed", reason_code=reason, bytes=0, chunks=0, elapsed_ms=0,
                )
                self.last_discovery_diagnostics = self._with_page_ledger(
                    {"complete": False, "reason_code": reason}
                )
                raise
            return self._fetch_github_manifest(base_url)
        self._raise_if_cancelled()
        policy.validate_url(url)

        with self._new_client(policy) as client:
            if self._github_blob_raw_url(base_url):
                page = self._fetch_page(
                    DiscoveredUrl(url=base_url, strategy=DiscoveryStrategy.SEED_URLS),
                    base_url,
                    Platform.GENERIC,
                    robots=None,
                    rate_limiter=RateLimiter(delay=0.0),
                    redirect_tracker=RedirectTracker(),
                    redirect_lock=threading.Lock(),
                )
                if page is None:
                    raise ValueError(f"GitHub documentation page {public_base_url!r} had no usable content.")
                self.last_discovery_diagnostics = self._with_page_ledger({"discovery_strategy": "github-blob"})
                return [page.document]
            if self._is_direct_text_url(base_url):
                document = self._fetch_direct_text_page(base_url, client)
                self.last_discovery_diagnostics = self._with_page_ledger({"discovery_strategy": "direct-url"})
                return [document]
            if self._is_direct_dartdoc_url(base_url):
                page = self._fetch_dartdoc_direct_page(base_url, base_url, client, Platform.GENERIC)
                if page is None:
                    raise ValueError(
                        f"Dartdoc page {public_base_url!r} had no extractable article content. "
                        "Try concrete class/library seed URLs or browser=true."
                    )
                self.last_discovery_diagnostics = self._with_page_ledger({"discovery_strategy": "dartdoc-direct"})
                return [page.document]

            # Step 1: Fetch homepage and detect platform
            platform, root_html, root_headers = self._fetch_and_detect(base_url, client)
            self._raise_if_cancelled()
            logger.info("Detected platform: %s", platform.value)

            # Step 2: Set up robots.txt checker
            robots = None
            robots_url = urljoin(f"{base_url}/", "/robots.txt")
            if self._respect_robots and policy.allows_scope(robots_url):
                robots = RobotsChecker(client)
                crawl_delay = robots.get_crawl_delay(base_url)
                if crawl_delay:
                    self._delay = max(self._delay, crawl_delay)

            # Step 3: Discover page URLs
            self._emit_progress({"phase": "discovering", "message": f"Discovering URLs from {public_base_url}", "url": public_base_url})
            discovery_result = discover_urls(
                base_url=base_url,
                client=client,
                platform=platform,
                robots=robots,
                max_pages=self._max_pages,
                force_strategy=self._strategy,
                seed_urls=self._seed_urls,
                root_html=root_html,
                query=self._query,
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
                    f"Could not discover any documentation pages at {public_base_url!r}. "
                    f"No /llms-full.txt, /llms.txt, sitemap, or navigable links found.{hint}"
                )
            self._emit_progress(
                {
                    "phase": "discovering",
                    "message": f"Discovered {len(discovered)} URLs",
                    "url": public_base_url,
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
                documents = self._build_llms_full_documents(discovered[0], platform)
                content = discovered[0].content or ""
                self._record_page(
                    requested_url=discovered[0].url,
                    discovered_url=discovered[0].url,
                    canonical_url=discovered[0].url,
                    redirect_url=None,
                    fetch_url=discovered[0].url,
                    fetcher="llms-full.txt",
                    outcome="usable",
                    reason_code="ok",
                    bytes=len(content.encode("utf-8")),
                    chunks=0,
                    elapsed_ms=0,
                )
                self.last_discovery_diagnostics = self._with_page_ledger(self.last_discovery_diagnostics or {})
                return documents

            # Step 5: Fetch and extract each page
            documents = self._fetch_pages(discovered, base_url, client, platform, robots)
            self.last_discovery_diagnostics = self._with_page_ledger(self.last_discovery_diagnostics or {})
            return documents

    def _fetch_github_manifest(self, base_url: str) -> list[Document]:
        manifest = self._source_manifest
        assert manifest is not None
        rows = manifest["documents"]
        if manifest.get("complete") is not True:
            reason = "github_manifest_incomplete"
            self._record_page(
                requested_url=base_url, discovered_url=base_url, canonical_url=base_url,
                redirect_url=None, fetch_url=None, fetcher="github-manifest",
                outcome="failed", reason_code=reason, bytes=0, chunks=0, elapsed_ms=0,
            )
            self.last_discovery_diagnostics = self._with_page_ledger(
                {"complete": False, "reason_code": reason}
            )
            raise ValueError("github_manifest_incomplete")
        if base_url not in {row["blob_url"] for row in rows} and not (
            not rows and canonical_github_blob_scope_url(base_url, manifest["discovery"])
        ):
            reason = "github_manifest_seed_mismatch"
            self._record_page(
                requested_url=base_url, discovered_url=base_url, canonical_url=base_url,
                redirect_url=None, fetch_url=None, fetcher="github-manifest",
                outcome="failed", reason_code=reason, bytes=0, chunks=0, elapsed_ms=0,
            )
            self.last_discovery_diagnostics = self._with_page_ledger(
                {"complete": False, "reason_code": reason}
            )
            raise ValueError("github_manifest_seed_mismatch")
        if len(rows) > self._max_pages:
            reason = "max_pages"
            self._record_page(
                requested_url=base_url, discovered_url=base_url, canonical_url=base_url,
                redirect_url=None, fetch_url=None, fetcher="github-manifest",
                outcome="failed", reason_code=reason, bytes=0, chunks=0, elapsed_ms=0,
            )
            self.last_discovery_diagnostics = self._with_page_ledger(
                {"complete": False, "reason_code": reason}
            )
            raise ValueError("github manifest fetch incomplete: max_pages")
        raw_paths = tuple(urlparse(row["raw_url"]).path for row in rows)
        policy = replace(
            self._fetch_policy,
            allowed_hosts=("raw.githubusercontent.com",),
            path_prefixes=raw_paths,
        )
        documents: list[Document] = []
        total_bytes = 0
        operation_started = time.monotonic()

        def bounded_reason() -> str | None:
            if self._cancellation_callback and self._cancellation_callback():
                return "cancelled"
            if time.monotonic() - operation_started >= self._max_total_seconds:
                return "deadline_exceeded"
            return None

        with self._new_client(policy) as client:
            for row in rows:
                raw_url = row["raw_url"]
                blob_url = row["blob_url"]
                started = time.monotonic()
                reason = "ok"
                try:
                    reason = bounded_reason() or "ok"
                    if reason != "ok":
                        raise ValueError(reason)
                    response = client.get(raw_url)
                    reason = bounded_reason() or "ok"
                    if reason != "ok":
                        raise ValueError(reason)
                    if response.status_code != 200:
                        reason = "not_found" if response.status_code == 404 else "http_failure"
                        raise ValueError(reason)
                    raw = bytes(response.content)
                    total_bytes += len(raw)
                    if total_bytes > self._max_fetched_document_bytes:
                        reason = "max_fetched_document_bytes"
                        raise ValueError(reason)
                    if len(raw) != row["size"]:
                        reason = "document_size_mismatch"
                        raise ValueError(reason)
                    git_sha = hashlib.sha1(
                        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
                    ).hexdigest()
                    if git_sha != row["git_blob_sha"]:
                        reason = "git_blob_mismatch"
                        raise ValueError(reason)
                    content_sha256 = hashlib.sha256(raw).hexdigest()
                    content = raw.decode("utf-8")
                    reason = bounded_reason() or "ok"
                    if reason != "ok":
                        raise ValueError(reason)
                except UnicodeDecodeError:
                    reason = "invalid_utf8"
                    self._record_page(
                        requested_url=blob_url, discovered_url=blob_url, canonical_url=blob_url,
                        redirect_url=None, fetch_url=raw_url, fetcher="github-manifest",
                        outcome="failed", reason_code=reason, bytes=0, chunks=0,
                        elapsed_ms=int((time.monotonic() - started) * 1000),
                    )
                    self.last_discovery_diagnostics = self._with_page_ledger(
                        {"complete": False, "reason_code": reason}
                    )
                    raise ValueError(f"github manifest fetch incomplete: {reason}") from None
                except Exception as exc:
                    if isinstance(exc, DocsFetchSecurityError):
                        reason = exc.category
                    elif reason == "ok":
                        reason = "network_transport_error"
                    self._record_page(
                        requested_url=blob_url, discovered_url=blob_url, canonical_url=blob_url,
                        redirect_url=None, fetch_url=raw_url, fetcher="github-manifest",
                        outcome="failed", reason_code=reason, bytes=0, chunks=0,
                        elapsed_ms=int((time.monotonic() - started) * 1000),
                    )
                    self.last_discovery_diagnostics = self._with_page_ledger(
                        {"complete": False, "reason_code": reason}
                    )
                    raise ValueError(f"github manifest fetch incomplete: {reason}") from exc
                document = Document(
                    source=blob_url,
                    content=content,
                    metadata={
                        "format": "markdown", "fetch_method": "github-manifest",
                        "docset_root": blob_url, "platform": Platform.GENERIC.value,
                        "canonical_url": blob_url, "content_hash": content_sha256,
                        "content_sha256": content_sha256, "git_blob_sha": git_sha,
                        "word_count": len(content.split()), "title": None,
                        "description": None, "section_path": [], "lang": "en",
                        "http_status": response.status_code,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "requested_url": blob_url, "fetch_url": raw_url,
                        "resolved_commit_sha": manifest["discovery"]["resolved_commit_sha"],
                    },
                )
                documents.append(document)
                self._record_page(
                    requested_url=blob_url, discovered_url=blob_url, canonical_url=blob_url,
                    redirect_url=None, fetch_url=raw_url, fetcher="github-manifest",
                    outcome="usable", reason_code="ok", bytes=len(raw), chunks=0,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
        self.last_discovery_diagnostics = self._with_page_ledger(
            {"complete": True, "reason_code": "ok", "discovery_strategy": "github-manifest"}
        )
        return documents

    def _with_page_ledger(self, diagnostics: dict) -> dict:
        ledger = list(self.last_page_ledger)
        failed = [item for item in ledger if item.get("outcome") in {"failed", "skipped"}]
        return {
            **diagnostics,
            "page_ledger": ledger,
            "page_failure_count": len(failed),
            "page_failure_summary": [
                {"url": item.get("discovered_url"), "reason_code": item.get("reason_code")}
                for item in failed[:20]
            ],
        }

    def _record_page(self, **values) -> None:
        safe = {
            **values,
            "requested_url": redact_url(str(values.get("requested_url") or "")),
            "discovered_url": redact_url(str(values.get("discovered_url") or "")),
            "canonical_url": redact_url(str(values.get("canonical_url") or "")) or None,
            "redirect_url": redact_url(str(values.get("redirect_url") or "")) or None,
            "fetch_url": redact_url(str(values.get("fetch_url") or "")) or None,
        }
        with self._ledger_lock:
            self.last_page_ledger.append(safe)

    @staticmethod
    def _github_blob_raw_url(url: str) -> str | None:
        return _github_blob_raw_url(url)

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
        started = time.monotonic()
        try:
            resp = client.get(url)
        except DocsFetchSecurityError as exc:
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=url, fetcher="direct-url", outcome="failed", reason_code=exc.category,
                bytes=0, chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except httpx.RequestError:
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=url, fetcher="direct-url", outcome="failed", reason_code="network_transport_error",
                bytes=0, chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise ValueError(f"Could not fetch documentation page {redact_url(url)!r}: transport_error") from None

        if resp.status_code != 200:
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=url, fetcher="direct-url", outcome="failed",
                reason_code="not_found" if resp.status_code == 404 else "http_failure",
                bytes=len(resp.content), chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise DocsFetchSecurityError(
                "not_found" if resp.status_code == 404 else "http_failure",
                redact_url(url),
                phase="fetching",
                retryable=resp.status_code in {408, 429} or resp.status_code >= 500,
                status_code=resp.status_code,
            )
        if not resp.text.strip():
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=url, fetcher="direct-url", outcome="failed", reason_code="empty_response",
                bytes=0, chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise ValueError(f"Could not fetch documentation page {redact_url(url)!r}: empty response")
        if looks_like_html(resp.text):
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=url, fetcher="direct-url", outcome="failed", reason_code="unexpected_html",
                bytes=len(resp.content), chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise ValueError(f"Could not fetch documentation page {redact_url(url)!r}: response appears to be HTML")

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
        document = Document(
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
        self._record_page(
            requested_url=url, discovered_url=url, canonical_url=final_url, redirect_url=final_url if final_url != url else None,
            fetch_url=url, fetcher="direct-url", outcome="usable", reason_code="ok",
            bytes=len(content.encode("utf-8")), chunks=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
        return document

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
        except httpx.RequestError:
            logger.warning("Failed to fetch homepage %s: transport_error", redact_url(base_url))
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
        terminal_failure: DocsFetchSecurityError | None = None
        try:
            deduplicator.reset()
            while pending:
                self._raise_if_cancelled()
                done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done:
                    completed_fetches = getattr(self, "_completed_fetches", 0) + 1
                    self._completed_fetches = completed_fetches
                    try:
                        page = future.result()
                    except DocsFetchSecurityError as exc:
                        terminal_failure = terminal_failure or exc
                        page = None
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
                        logger.debug("Skipped %s (duplicate final URL)", redact_url(page.document.source))
                        continue
                    if page.document.source != page.final_url and deduplicator.is_url_duplicate(page.document.source):
                        logger.debug("Skipped %s (duplicate canonical URL)", redact_url(page.document.source))
                        continue
                    if deduplicator.is_content_duplicate(page.document.content):
                        logger.debug("Skipped %s (duplicate content)", redact_url(page.document.source))
                        continue
                    documents.append(page.document)
                    logger.info("Fetched %s (%d words)", redact_url(page.document.source), len(page.document.content.split()))
                    self._emit_progress(
                        {
                            "phase": "fetching",
                            "message": f"Fetched {completed_fetches}/{len(unique_discovered)} pages",
                            "url": redact_url(page.document.source),
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
            if terminal_failure is not None:
                raise terminal_failure
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

        self.last_fetch_failure = terminal_failure
        return documents
