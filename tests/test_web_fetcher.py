"""Tests for the WebFetcher end-to-end pipeline."""

from __future__ import annotations

from contextlib import nullcontext

import ipaddress
import hashlib
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import httpx
import pytest

from docmancer.connectors.fetchers.web import WebFetcher
from docmancer.connectors.fetchers.pipeline.detection import Platform
from docmancer.connectors.fetchers.pipeline.discovery import DiscoveredUrl, DiscoveryStrategy, discover_urls
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest


def _mock_response(text: str, status: int = 200, content_type: str = "text/html") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"content-type": content_type}
    return resp


def test_identical_retry_uses_fresh_client_and_recovers_in_same_process():
    url = "https://example.com/llms.txt"
    request = httpx.Request("GET", url)
    offline = MagicMock()
    offline.get.side_effect = httpx.ConnectError("offline", request=request)
    online = MagicMock()
    online.get.return_value = _mock_response(
        "# Guide\n\nRecovered documentation content.",
        content_type="text/plain",
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),))

    with patch(
        "docmancer.connectors.fetchers.web.httpx.Client",
        side_effect=[offline, online],
    ) as client_factory:
        fetcher = WebFetcher(fetch_policy=policy)
        with pytest.raises(DocsFetchSecurityError) as first:
            fetcher.fetch(url)
        documents = fetcher.fetch(url)

    assert first.value.category == "network_unreachable"
    assert len(documents) == 1
    assert documents[0].source == url
    assert client_factory.call_count == 2


HOMEPAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta name="generator" content="Docusaurus v3.0">
<title>Example Docs</title></head>
<body>
<nav><a href="/docs/intro">Intro</a><a href="/docs/guide">Guide</a></nav>
<main><h1>Welcome</h1><p>Documentation home.</p></main>
</body></html>"""

PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Introduction</title>
<meta name="description" content="Getting started guide">
<link rel="canonical" href="https://example.com/docs/intro">
</head>
<body>
<main>
<h1>Introduction</h1>
<p>Welcome to the getting started guide. This document will walk you through
the basic setup and configuration of the platform. Follow the steps below
to get up and running quickly with all the essential features.</p>
<h2>Prerequisites</h2>
<p>You need Python 3.11 or later installed on your system.</p>
<pre><code class="language-bash">pip install example-lib</code></pre>
</main>
</body></html>"""

DARTDOC_ROOT_HTML = """<!DOCTYPE html>
<html><body>
<nav><a href="/flutter/widgets/SizedBox-class.html">SizedBox</a></nav>
<main><h1>Flutter API</h1><p>Loading...</p></main>
</body></html>"""

DARTDOC_SIZED_BOX_HTML = """<!DOCTYPE html>
<html><body>
<nav><a>Navigation</a></nav>
<main id="dartdoc-main-content">
<h1>SizedBox class</h1>
<p>A box with a specified size.</p>
<h2>Constructors</h2>
<dl><dt><code>SizedBox({double? width, double? height})</code></dt><dd>Creates a fixed size box.</dd></dl>
<h2>Properties</h2><dl><dt><code>width</code></dt><dd>The requested width.</dd></dl>
</main>
</body></html>"""

DARTDOC_EMPTY_HTML = """<!DOCTYPE html><html><body><nav><a href="/a">A</a></nav><main></main></body></html>"""

LLMS_FULL_CONTENT = "# Full Documentation\n\n" + ("This is comprehensive documentation content. " * 100)


@pytest.fixture(autouse=True)
def _public_docs_dns(monkeypatch):
    monkeypatch.setattr(
        "docmancer.docs.fetch_policy.resolve_host",
        lambda _host: (ipaddress.ip_address("93.184.216.34"),),
    )


def _make_mock_client(get_side_effect):
    """Create a mock httpx.Client that works as a context manager."""
    client = MagicMock()
    client.get.side_effect = get_side_effect
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


def test_web_fetcher_honors_cancellation_before_network_access():
    fetcher = WebFetcher(cancellation_callback=lambda: True)

    with patch("httpx.Client") as client, pytest.raises(RuntimeError, match="cancelled"):
        fetcher.fetch("https://example.com/docs/")
    client.assert_not_called()


def test_web_fetcher_rejects_url_userinfo_before_network_access():
    fetcher = WebFetcher()

    with patch("docmancer.connectors.fetchers.web.httpx.Client") as client:
        with pytest.raises(ValueError, match="userinfo_not_allowed"):
            fetcher.fetch("https://user:secret@example.com/docs")

    client.assert_not_called()


def test_web_fetcher_rejects_unsupported_scheme_before_network_access():
    fetcher = WebFetcher()

    with patch("docmancer.connectors.fetchers.web.httpx.Client") as client:
        with pytest.raises(ValueError, match="unsupported_scheme"):
            fetcher.fetch("file:///etc/passwd")

    client.assert_not_called()


def test_default_policy_scope_allows_only_target_and_declared_seed_hosts():
    fetcher = WebFetcher(
        seed_urls=["https://seed.example.org/docs/start"],
        fetch_policy=DocsFetchPolicy(
            resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),)
        ),
    )

    scoped = fetcher._policy_for("https://example.com/docs")

    scoped.validate_url("https://example.com/docs/guide")
    scoped.validate_url("https://seed.example.org/docs/start")
    with pytest.raises(DocsFetchSecurityError, match="host_not_allowed"):
        scoped.validate_url("https://evil.test/docs")
    assert fetcher._fetch_policy.allowed_hosts == ()


def test_github_blob_raw_fetch_keeps_canonical_docset_root():
    blob_url = "https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/coroutines-basics.md"
    raw_url = "https://raw.githubusercontent.com/Kotlin/kotlinx.coroutines/1.8.1/docs/topics/coroutines-basics.md"
    fetcher = WebFetcher(
        delay=0.0,
        fetch_policy=DocsFetchPolicy(
            resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
            allowed_hosts=("github.com", "raw.githubusercontent.com"),
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == "raw.githubusercontent.com"
        assert request.url.path == "/Kotlin/kotlinx.coroutines/1.8.1/docs/topics/coroutines-basics.md"
        return httpx.Response(200, request=request, text="# Coroutines\n\nUse `launch` for concurrent work.")

    real_client = httpx.Client

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler))

    with real_client(transport=httpx.MockTransport(handler)) as discovery_client:
        with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=client_factory):
            documents = fetcher._fetch_pages(
                [DiscoveredUrl(blob_url, DiscoveryStrategy.SEED_URLS)],
                blob_url,
                client=discovery_client,
                platform=Platform.GENERIC,
                robots=None,
            )

    assert len(documents) == 1
    assert documents[0].source == blob_url
    assert documents[0].metadata["fetch_url"] == raw_url
    assert documents[0].metadata["docset_root"] == blob_url


def _manifest_for(raw: bytes, *, blob_sha=None):
    commit = "1" * 40
    sha = blob_sha or hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "Kotlin", "repository": "repo",
                      "requested_ref": "v1", "resolved_commit_sha": commit, "directory": "docs"},
        "documents": [{"path": "docs/guide.md", "git_blob_sha": sha, "size": len(raw)}],
        "complete": True, "truncated": False,
    })


def test_manifest_fetch_reconstructs_raw_url_and_verifies_blob_and_sha256():
    raw = b"# Guide\n\nImmutable documentation."
    manifest = _manifest_for(raw)
    requested = []

    def handler(request):
        requested.append(request.headers["host"] + request.url.path)
        return httpx.Response(200, request=request, content=raw, headers={"content-type": "text/plain"})

    real_client = httpx.Client
    with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler))):
        fetcher = WebFetcher(source_manifest=manifest, delay=0, fetch_policy=DocsFetchPolicy(
            resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),), allowed_hosts=("github.com",)
        ))
        docs = fetcher.fetch(manifest["documents"][0]["blob_url"])
    assert requested == ["raw.githubusercontent.com" + urlparse(manifest["documents"][0]["raw_url"]).path]
    assert docs[0].source == manifest["documents"][0]["blob_url"]
    assert docs[0].metadata["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert docs[0].metadata["git_blob_sha"] == manifest["documents"][0]["git_blob_sha"]


@pytest.mark.parametrize("document_count", [0, 2])
def test_manifest_operation_fetches_each_member_once_and_empty_manifest_fetches_none(
    document_count,
):
    payloads = {
        f"docs/guide-{index}.md": f"# Guide {index}\n".encode()
        for index in range(document_count)
    }
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "Kotlin",
            "repository": "repo",
            "requested_ref": "v1",
            "resolved_commit_sha": "1" * 40,
            "directory": "docs",
        },
        "documents": [
            {
                "path": path,
                "git_blob_sha": hashlib.sha1(
                    b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
                ).hexdigest(),
                "size": len(raw),
            }
            for path, raw in reversed(payloads.items())
        ],
        "complete": True,
        "truncated": False,
    })
    requested: list[str] = []

    def handler(request):
        requested.append(request.url.path)
        path = next(path for path in payloads if request.url.path.endswith("/" + path))
        return httpx.Response(
            200,
            request=request,
            content=payloads[path],
            headers={"content-type": "text/plain"},
        )

    real_client = httpx.Client
    with patch(
        "docmancer.connectors.fetchers.web.httpx.Client",
        side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler)),
    ):
        fetcher = WebFetcher(
            source_manifest=manifest,
            fetch_policy=DocsFetchPolicy(
                resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
                allowed_hosts=("github.com",),
            ),
        )
        seed = (
            manifest["documents"][0]["blob_url"]
            if document_count
            else "https://github.com/Kotlin/repo/blob/v1/docs/approved.md"
        )
        documents = fetcher.fetch(seed)

    assert len(requested) == document_count
    assert len(documents) == document_count
    assert fetcher.last_discovery_diagnostics is not None
    assert fetcher.last_discovery_diagnostics["complete"] is True


def test_manifest_blob_mismatch_fails_closed_and_records_reason():
    manifest = _manifest_for(b"expected")
    real_client = httpx.Client

    def handler(request):
        return httpx.Response(200, request=request, content=b"tampered", headers={"content-type": "text/plain"})

    with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler))):
        fetcher = WebFetcher(source_manifest=manifest, fetch_policy=DocsFetchPolicy(
            resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),), allowed_hosts=("github.com",)
        ))
        with pytest.raises(ValueError, match="git_blob_mismatch"):
            fetcher.fetch(manifest["documents"][0]["blob_url"])
    assert fetcher.last_discovery_diagnostics is not None
    assert fetcher.last_discovery_diagnostics["complete"] is False
    assert fetcher.last_discovery_diagnostics["reason_code"] == "git_blob_mismatch"


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("incomplete", "github_manifest_incomplete"),
        ("max_pages", "max_pages"),
        ("invalid_utf8", "invalid_utf8"),
    ],
)
def test_manifest_early_and_decode_failures_record_failed_page_evidence(failure, reason):
    raw = b"\xff" if failure == "invalid_utf8" else b"# Guide\n"
    manifest = _manifest_for(raw)
    if failure == "incomplete":
        manifest["complete"] = False
        manifest["reason_code"] = "listing_failed"
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return httpx.Response(
            200,
            request=request,
            content=raw,
            headers={"content-type": "text/plain"},
        )

    real_client = httpx.Client
    with patch(
        "docmancer.connectors.fetchers.web.httpx.Client",
        side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler)),
    ):
        fetcher = WebFetcher(
            source_manifest=manifest,
            max_pages=0 if failure == "max_pages" else 100,
            fetch_policy=DocsFetchPolicy(
                resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
                allowed_hosts=("github.com",),
            ),
        )
        with pytest.raises(ValueError, match=reason):
            fetcher.fetch(manifest["documents"][0]["blob_url"])

    assert len(requested) == (1 if failure == "invalid_utf8" else 0)
    diagnostics = fetcher.last_discovery_diagnostics
    assert diagnostics is not None
    assert diagnostics["complete"] is False
    assert diagnostics["reason_code"] == reason
    assert diagnostics["page_failure_count"] == 1
    assert fetcher.last_page_ledger[0]["outcome"] == "failed"
    assert fetcher.last_page_ledger[0]["reason_code"] == reason


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("cancelled", "cancelled"),
        ("seed_mismatch", "github_manifest_seed_mismatch"),
        ("transport", "network_transport_error"),
    ],
)
def test_manifest_entry_and_transport_failures_record_failed_page_evidence(failure, reason):
    raw = b"# Guide\n"
    manifest = _manifest_for(raw)
    seed = (
        "https://github.com/Kotlin/repo/blob/v1/docs/other.md"
        if failure == "seed_mismatch"
        else manifest["documents"][0]["blob_url"]
    )
    real_client = httpx.Client

    def handler(_request):
        if failure == "transport":
            raise RuntimeError("connection lost")
        return httpx.Response(200, content=raw, headers={"content-type": "text/plain"})

    with patch(
        "docmancer.connectors.fetchers.web.httpx.Client",
        side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler)),
    ):
        fetcher = WebFetcher(
            source_manifest=manifest,
            cancellation_callback=(lambda: True) if failure == "cancelled" else None,
            fetch_policy=DocsFetchPolicy(
                resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
                allowed_hosts=("github.com",),
            ),
        )
        with pytest.raises((RuntimeError, ValueError), match=reason):
            fetcher.fetch(seed)

    diagnostics = fetcher.last_discovery_diagnostics
    assert diagnostics is not None
    assert diagnostics["complete"] is False
    assert diagnostics["reason_code"] == reason
    assert diagnostics["page_failure_count"] == 1
    assert fetcher.last_page_ledger[0]["reason_code"] == reason


def test_manifest_fetcher_rejects_complete_and_truncated_contract():
    manifest = _manifest_for(b"ok")
    manifest["truncated"] = True
    with pytest.raises(ValueError, match="complete.*truncated|truncated.*complete"):
        WebFetcher(source_manifest=manifest)


@pytest.mark.parametrize(("cancelled", "ticks", "reason"), [
    ([False, False, True], None, "cancelled"),
    (None, [0.0, 0.0, 0.0, 2.0], "deadline_exceeded"),
])
def test_manifest_fetch_rejects_content_when_cancelled_or_expired_after_transport_return(
    cancelled, ticks, reason,
):
    raw = b"# must not be indexed"
    manifest = _manifest_for(raw)
    callback = (lambda: cancelled.pop(0)) if cancelled is not None else None
    real_client = httpx.Client

    def handler(request):
        return httpx.Response(200, request=request, content=raw, headers={"content-type": "text/plain"})

    client_patch = patch(
        "docmancer.connectors.fetchers.web.httpx.Client",
        side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler)),
    )
    clock_values = list(ticks or [])
    clock_patch = (
        patch(
            "docmancer.connectors.fetchers.web.time.monotonic",
            side_effect=lambda: clock_values.pop(0) if clock_values else 2.0,
        )
        if ticks is not None else nullcontext()
    )
    with client_patch, clock_patch:
        fetcher = WebFetcher(
            source_manifest=manifest,
            cancellation_callback=callback,
            max_total_seconds=1.0,
            fetch_policy=DocsFetchPolicy(
                resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
                allowed_hosts=("github.com",),
            ),
        )
        with pytest.raises(ValueError, match=reason):
            fetcher.fetch(manifest["documents"][0]["blob_url"])

    assert fetcher.last_discovery_diagnostics["complete"] is False
    assert fetcher.last_discovery_diagnostics["reason_code"] == reason
    assert not any(row["outcome"] == "usable" for row in fetcher.last_page_ledger)


class TestWebFetcherLlmsFull:
    def test_llms_full_txt_success(self):
        """When llms-full.txt is available, return it directly."""

        def mock_get(url, **kwargs):
            if "llms-full.txt" in url:
                return _mock_response(LLMS_FULL_CONTENT, content_type="text/plain")
            if "robots.txt" in url:
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            return _mock_response(HOMEPAGE_HTML)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=100)
            docs = fetcher.fetch("https://example.com/docs")

        assert len(docs) == 1
        assert docs[0].metadata["fetch_method"] == "llms-full.txt"
        assert docs[0].metadata["format"] == "markdown"
        assert "content_hash" in docs[0].metadata


class TestWebFetcherDirectText:
    def test_direct_markdown_url_fetches_single_page(self):
        """Exact markdown URLs should not run site-wide discovery."""

        page = "# Process MOTO payments\n\nUse Acme Terminal to process MOTO payments."

        def mock_get(url, **kwargs):
            assert url == "https://docs.example.com/terminal/moto.md"
            return _mock_response(page, content_type="text/plain")

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=100)
            docs = fetcher.fetch("https://docs.example.com/terminal/moto.md")

        assert len(docs) == 1
        assert docs[0].source == "https://docs.example.com/terminal/moto.md"
        assert docs[0].content == page
        assert docs[0].metadata["fetch_method"] == "direct-url"
        assert docs[0].metadata["format"] == "markdown"


class TestWebFetcherNavCrawl:
    def test_nav_crawl_fetches_pages(self):
        """When no llms.txt or sitemap, fall back to nav crawl."""

        def mock_get(url, **kwargs):
            if "llms-full.txt" in url or ("llms.txt" in url and "full" not in url):
                return _mock_response("", status=404, content_type="text/plain")
            if "robots.txt" in url:
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if "sitemap" in url:
                return _mock_response("", status=404)
            if "/docs/intro" in url:
                return _mock_response(PAGE_HTML)
            if "/docs/guide" in url:
                return _mock_response(PAGE_HTML.replace("Introduction", "Guide"))
            # Homepage
            return _mock_response(HOMEPAGE_HTML)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
                fetcher = WebFetcher(max_pages=100, delay=0.0)
                docs = fetcher.fetch("https://example.com/docs")

        assert len(docs) >= 1
        for doc in docs:
            assert "platform" in doc.metadata
            assert "content_hash" in doc.metadata
            assert "word_count" in doc.metadata
            assert "fetched_at" in doc.metadata

    def test_page_source_uses_in_scope_canonical_url(self):
        page_html = PAGE_HTML.replace(
            'href="https://example.com/docs/intro"',
            'href="https://example.com/docs/intro/"',
        )

        def mock_get(url, **kwargs):
            if "llms-full.txt" in url or ("llms.txt" in url and "full" not in url):
                return _mock_response("", status=404, content_type="text/plain")
            if "robots.txt" in url:
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if "sitemap" in url:
                return _mock_response("", status=404)
            if "/docs/intro" in url:
                return _mock_response(page_html)
            return _mock_response(HOMEPAGE_HTML.replace('/docs/guide', '/blog/post'))

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, delay=0.0)
            docs = fetcher.fetch("https://example.com/docs")

        assert len(docs) == 1
        assert docs[0].source == "https://example.com/docs/intro"
        assert docs[0].metadata["canonical_url"] == "https://example.com/docs/intro"

    def test_duplicate_canonical_pages_are_deduplicated(self):
        page_a = PAGE_HTML.replace(
            'href="https://example.com/docs/intro"',
            'href="https://example.com/docs/canonical"',
        )
        page_b = page_a.replace("Introduction", "Introduction Copy")

        def mock_get(url, **kwargs):
            if "llms-full.txt" in url or ("llms.txt" in url and "full" not in url):
                return _mock_response("", status=404, content_type="text/plain")
            if "robots.txt" in url:
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if "sitemap" in url:
                return _mock_response("", status=404)
            if "/docs/intro" in url:
                return _mock_response(page_a)
            if "/docs/guide" in url:
                return _mock_response(page_b)
            return _mock_response(HOMEPAGE_HTML)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, delay=0.0)
            docs = fetcher.fetch("https://example.com/docs")

        assert [doc.source for doc in docs].count("https://example.com/docs/canonical") == 1


class TestWebFetcherErrors:
    def test_no_pages_raises_error(self):
        """Should raise ValueError when no pages are discovered."""

        def mock_get(url, **kwargs):
            return _mock_response("", status=404, content_type="text/plain")

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
                fetcher = WebFetcher()
                with pytest.raises(ValueError, match="Could not discover"):
                    fetcher.fetch("https://example.com/docs")


class TestWebFetcherProtocol:
    def test_default_client_ignores_ambient_proxy_environment(self):
        fetcher = WebFetcher()

        assert fetcher._client_kwargs()["trust_env"] is False

    def test_implements_fetcher_protocol(self):
        """WebFetcher should satisfy the Fetcher protocol."""
        from docmancer.connectors.fetchers.base import Fetcher
        fetcher = WebFetcher()
        assert isinstance(fetcher, Fetcher)

    def test_constructor_defaults(self):
        fetcher = WebFetcher()
        assert fetcher._max_pages == 500
        assert fetcher._browser is False
        assert fetcher._strategy is None
        assert fetcher._respect_robots is True

    def test_constructor_custom(self):
        fetcher = WebFetcher(max_pages=100, strategy="llms-full.txt", browser=True, workers=6)
        assert fetcher._max_pages == 100
        assert fetcher._strategy == "llms-full.txt"
        assert fetcher._browser is True
        assert fetcher._workers == 6


class TestDiscovery:
    def test_discovery_merges_llms_sitemap_and_nav(self):
        sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/docs/from-sitemap</loc></url>
</urlset>"""

        def mock_get(url, **kwargs):
            if url.endswith("/llms-full.txt"):
                return _mock_response("", status=404, content_type="text/plain")
            if url.endswith("/llms.txt"):
                return _mock_response("[LLMS](https://example.com/docs/from-llms)", content_type="text/plain")
            if url.endswith("/sitemap.xml"):
                return _mock_response(sitemap, content_type="application/xml")
            if url.endswith("/sitemap_index.xml"):
                return _mock_response("", status=404)
            return _mock_response('<nav><a href="/docs/from-nav">Nav</a></nav>')

        client = MagicMock(spec=httpx.Client)
        client.get.side_effect = mock_get

        result = discover_urls("https://example.com/docs", client, Platform.GENERIC, max_pages=10)
        discovered = result.urls

        urls = {item.url for item in discovered}
        assert "https://example.com/docs/from-llms" in urls
        assert "https://example.com/docs/from-sitemap" in urls
        assert "https://example.com/docs/from-nav" in urls

    def test_nav_crawl_follows_links_bounded_bfs(self):
        def mock_get(url, **kwargs):
            if url.endswith("/llms-full.txt") or url.endswith("/llms.txt") or "sitemap" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if url == "https://example.com/docs":
                return _mock_response('<nav><a href="/docs/a">A</a></nav>')
            if url == "https://example.com/docs/a":
                return _mock_response('<nav><a href="/docs/b">B</a></nav>')
            return _mock_response("<main><h1>B</h1></main>")

        client = MagicMock(spec=httpx.Client)
        client.get.side_effect = mock_get

        result = discover_urls("https://example.com/docs", client, Platform.GENERIC, max_pages=10)
        discovered = result.urls

        assert [item.strategy for item in discovered] == [DiscoveryStrategy.NAV_CRAWL, DiscoveryStrategy.NAV_CRAWL]
        assert [item.url for item in discovered] == ["https://example.com/docs/a", "https://example.com/docs/b"]

    def test_cross_domain_seed_url_gets_own_docset_root(self):
        pubdev_html = """<!DOCTYPE html><html><head><title>Provider API</title></head><body>
        <main><h1>Provider API</h1><p>Riverpod Provider API reference with enough documentation words to extract.</p></main>
        </body></html>"""

        def mock_get(url, **kwargs):
            if url.endswith("llms-full.txt") or url.endswith("llms.txt") or "sitemap" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if url.endswith("robots.txt"):
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if url == "https://riverpod.dev/":
                return _mock_response('<main><h1>Riverpod</h1><p>Official guide page with meaningful content.</p></main>')
            if url == "https://pub.dev/documentation/riverpod/latest/riverpod/Provider-class.html":
                return _mock_response(pubdev_html)
            return _mock_response("", status=404)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(
                max_pages=10,
                browser=False,
                delay=0.0,
                seed_urls=["https://pub.dev/documentation/riverpod/latest/riverpod/Provider-class.html"],
            )
            docs = fetcher.fetch("https://riverpod.dev/")

        pubdev = next(doc for doc in docs if doc.source.startswith("https://pub.dev/"))
        assert pubdev.metadata["fetch_method"] == DiscoveryStrategy.SEED_URLS.value
        assert pubdev.metadata["docset_root"] == "https://pub.dev/documentation/riverpod/latest"


class TestWebFetcherDartdoc:
    def test_direct_dartdoc_class_page_without_browser(self):
        def mock_get(url, **kwargs):
            assert url == "https://api.flutter.dev/flutter/widgets/SizedBox-class.html"
            return _mock_response(DARTDOC_SIZED_BOX_HTML)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, browser=False, doc_format="dartdoc")
            docs = fetcher.fetch("https://api.flutter.dev/flutter/widgets/SizedBox-class.html")

        assert len(docs) == 1
        assert "SizedBox class" in docs[0].content
        assert "Constructors" in docs[0].content
        assert "width" in docs[0].content
        assert fetcher._browser is False

    def test_dartdoc_root_empty_does_not_fail_when_seed_page_succeeds(self):
        def mock_get(url, **kwargs):
            if url.endswith("llms-full.txt") or url.endswith("llms.txt") or "sitemap" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if url.endswith("robots.txt"):
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if url == "https://api.flutter.dev":
                return _mock_response(DARTDOC_ROOT_HTML)
            if url == "https://api.flutter.dev/flutter/widgets/SizedBox-class.html":
                return _mock_response(DARTDOC_SIZED_BOX_HTML)
            return _mock_response("", status=404)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, browser=False, doc_format="dartdoc", delay=0.0)
            docs = fetcher.fetch("https://api.flutter.dev")

        assert len(docs) == 1
        assert docs[0].source == "https://api.flutter.dev/flutter/widgets/SizedBox-class.html"
        assert "SizedBox class" in docs[0].content

    def test_dartdoc_all_empty_reports_structured_failure(self):
        def mock_get(url, **kwargs):
            if url.endswith("llms-full.txt") or url.endswith("llms.txt") or "sitemap" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if url.endswith("robots.txt"):
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if url == "https://pub.dev/documentation/empty/latest":
                return _mock_response('<nav><a href="/documentation/empty/latest/empty/Empty-class.html">Empty</a></nav>')
            if url.endswith("Empty-class.html"):
                return _mock_response(DARTDOC_EMPTY_HTML)
            return _mock_response("", status=404)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, browser=False, doc_format="dartdoc", delay=0.0)
            with pytest.raises(ValueError, match="Dartdoc extraction found no usable documentation content"):
                fetcher.fetch("https://pub.dev/documentation/empty/latest")

    def test_dartdoc_index_json_discovers_api_pages_when_html_shell_has_no_links(self):
        root = '<html><head><script src="static-assets/main.dart.js"></script></head><body><main>Flutter API</main></body></html>'
        index_json = '{"items":[{"href":"/flutter/widgets/StatefulWidget-class.html"}]}'

        def mock_get(url, **kwargs):
            if url.endswith("llms-full.txt") or url.endswith("llms.txt") or "sitemap" in url:
                return _mock_response("", status=404, content_type="text/plain")
            if url.endswith("robots.txt"):
                return _mock_response("User-agent: *\nAllow: /", content_type="text/plain")
            if url == "https://api.flutter.dev":
                return _mock_response(root)
            if url == "https://api.flutter.dev/index.json":
                return _mock_response(index_json, content_type="application/json")
            if url == "https://api.flutter.dev/flutter/widgets/StatefulWidget-class.html":
                return _mock_response(DARTDOC_SIZED_BOX_HTML.replace("SizedBox", "StatefulWidget"))
            return _mock_response("", status=404)

        mock_client = _make_mock_client(mock_get)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", return_value=mock_client):
            fetcher = WebFetcher(max_pages=10, browser=False, doc_format="dartdoc", delay=0.0)
            docs = fetcher.fetch("https://api.flutter.dev")

        assert len(docs) == 1
        assert docs[0].source == "https://api.flutter.dev/flutter/widgets/StatefulWidget-class.html"
        assert "StatefulWidget class" in docs[0].content
