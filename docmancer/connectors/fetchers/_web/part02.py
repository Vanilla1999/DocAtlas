"""WebFetcher implementation shard 2."""
from __future__ import annotations

from .shared import *  # noqa: F401,F403


class _WebFetcherPart02:
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
        started = time.monotonic()
        self._raise_if_cancelled()
        url = exact_url(disc.url)
        if not contains(self._fetch_policy.exact_urls or (), url):
            raise ValueError("url_not_selected")
        if self._respect_robots and robots is None:
            raise ValueError("explicit_robots_control_required")
        self._emit_progress({"phase": "fetching", "message": f"Fetching {url}", "url": url})
        is_seed_url = disc.strategy == DiscoveryStrategy.SEED_URLS
        if robots and not robots.can_fetch(url):
            logger.debug("Skipped %s (blocked by robots.txt)", url)
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=None, fetcher="web", outcome="skipped", reason_code="robots_disallowed",
                bytes=0, chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            return None
        if not is_seed_url and not is_docs_url(url, base_url):
            logger.debug("Skipped %s (out of docs scope)", url)
            reason = "cross_domain_skipped" if urlparse(url).hostname != urlparse(base_url).hostname else "path_policy_skipped"
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                fetch_url=None, fetcher="web", outcome="skipped", reason_code=reason,
                bytes=0, chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            return None

        predicted_url = None  # No inferred transport destination.
        github_raw_url = None  # Immutable files use only the hashed manifest lane.
        fetch_url = url

        request_policy = self._fetch_policy
        with self._new_client(request_policy) as client:
            rate_limiter.wait(fetch_url)
            try:
                resp = client.get(fetch_url)
            except DocsFetchSecurityError as exc:
                self._record_page(
                    requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                    fetch_url=fetch_url, fetcher="github-raw" if github_raw_url else "web",
                    outcome="failed", reason_code=exc.category, bytes=0, chunks=0,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
                raise
            except httpx.RequestError as exc:
                logger.warning("Failed to fetch %s: %s", fetch_url, exc)
                self._emit_progress({"phase": "fetching", "message": f"Fetch failed: {url}", "url": url})
                self._record_page(
                    requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                    fetch_url=fetch_url, fetcher="github-raw" if github_raw_url else "web",
                    outcome="failed", reason_code="network_transport_error", bytes=0, chunks=0,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
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
                logger.warning("Rate limited on %s (status %d)", fetch_url, resp.status_code)
            if resp.status_code != 200:
                self._emit_progress({"phase": "fetching", "message": f"Fetch failed with status {resp.status_code}: {url}", "url": url})
                retryable = resp.status_code in {408, 425, 429} or resp.status_code >= 500
                self._record_page(
                    requested_url=url, discovered_url=url, canonical_url=None, redirect_url=None,
                    fetch_url=fetch_url, fetcher="github-raw" if github_raw_url else "web",
                    outcome="failed", reason_code="not_found" if resp.status_code == 404 else "http_failure",
                    bytes=len(resp.content), chunks=0, elapsed_ms=int((time.monotonic() - started) * 1000),
                )
                raise DocsFetchSecurityError(
                    "not_found" if resp.status_code == 404 else "http_failure",
                    redact_url(fetch_url),
                    phase="fetching",
                    retryable=retryable,
                    status_code=resp.status_code,
                )

            rate_limiter.reset_backoff(fetch_url)
            resp_url = getattr(resp, "url", None)
            if isinstance(resp_url, (str, httpx.URL)):
                final_url = exact_url(str(resp_url))
            else:
                final_url = exact_url(fetch_url)
            if not contains(self._fetch_policy.exact_urls or (), final_url):
                raise ValueError("redirect_url_not_selected")
            if final_url != normalize_url(fetch_url):
                with redirect_lock:
                    redirect_tracker.record_redirect(url, final_url)
            raw_html = resp.text
            self._raise_if_cancelled()
            self._finite_total_bytes = getattr(self, "_finite_total_bytes", 0) + len(resp.content)
            if self._finite_total_bytes > self._max_fetched_document_bytes:
                raise DocsFetchSecurityError("max_fetched_document_bytes", redact_url(url))

        if looks_like_html(raw_html):
            doc_format = (
                "dartdoc"
                if self._is_dartdoc_url(url) or is_dartdoc_html(raw_html, url=final_url)
                else self._doc_format
            )
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
            self._record_page(
                requested_url=url, discovered_url=url, canonical_url=None, redirect_url=final_url if final_url != fetch_url else None,
                fetch_url=fetch_url, fetcher="github-raw" if github_raw_url else "web",
                outcome="failed", reason_code="extraction_empty", bytes=len(raw_html.encode("utf-8")), chunks=0,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            return None

        if self._browser and len(content.split()) < 100 and looks_like_html(raw_html):
            browser_content = self._try_browser_fallback(url)
            if browser_content:
                content = browser_content

        content_hash = ContentDeduplicator.content_hash(content)
        canonical = exact_url(resolve_url(str(meta.get("canonical_url")), final_url)) if meta.get("canonical_url") else url
        if not contains(self._fetch_policy.exact_urls or (), canonical):
            raise ValueError("canonical_url_not_selected")
        source_url = canonical
        docset_root = url
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
                "requested_url": redact_url(url),
                "discovered_url": redact_url(url),
                "fetch_url": redact_url(fetch_url),
                "redirect_url": redact_url(final_url) if final_url != fetch_url else None,
            },
        )
        self._record_page(
            requested_url=url,
            discovered_url=url,
            canonical_url=canonical,
            redirect_url=final_url if final_url != fetch_url else None,
            fetch_url=fetch_url,
            fetcher="github-raw" if github_raw_url else "web",
            outcome="usable",
            reason_code="ok",
            bytes=len(raw_html.encode("utf-8")),
            chunks=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
        return _FetchedPage(document=doc, final_url=final_url)

    def _try_browser_fallback(self, url: str) -> str | None:
        """Fail closed until Playwright requests share the Docs network policy."""
        logger.warning(
            "Browser fallback skipped for %s: secure browser network interception is unavailable.",
            redact_url(url),
        )
        return None
