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
from docmancer.connectors.fetchers.pipeline.extraction import extract_content
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest


def _mock_response(text: str, status: int = 200, content_type: str = "text/html") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"content-type": content_type}
    return resp








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
    pass

class TestWebFetcherDirectText:
    pass

class TestWebFetcherNavCrawl:
    pass

class TestWebFetcherErrors:
    pass



class TestDiscovery:
    pass

class TestWebFetcherDartdoc:
    def test_direct_dartdoc_class_page_without_browser(self):
        selected = "https://api.flutter.dev/flutter/widgets/SizedBox-class.html"
        robots = "https://api.flutter.dev/robots.txt"
        calls = []
        policy = DocsFetchPolicy(
            allowed_hosts=("api.flutter.dev",),
            path_prefixes=("/flutter/widgets/SizedBox-class.html", "/robots.txt"),
            resolver=lambda _host: (ipaddress.ip_address("93.184.216.34"),),
        )

        def respond(request):
            # Exercise the ordinary pinned transport, entirely inside MockTransport.
            assert request.url.host == "93.184.216.34"
            url = f"{request.url.scheme}://{request.headers['host']}{request.url.raw_path.decode('ascii')}"
            calls.append(url)
            if url == robots:
                return httpx.Response(200, text="User-agent: *\nAllow: /\n",
                                      headers={"content-type": "text/plain"}, request=request)
            assert url == "https://api.flutter.dev/flutter/widgets/SizedBox-class.html"
            return httpx.Response(200, text=DARTDOC_SIZED_BOX_HTML,
                                  headers={"content-type": "text/html"}, request=request)

        client_type = httpx.Client

        def fixture_client(**kwargs):
            return client_type(transport=httpx.MockTransport(respond), **kwargs)

        with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=fixture_client):
            fetcher = WebFetcher(
                max_pages=10, browser=False, doc_format="dartdoc", fetch_policy=policy,
                exact_urls=[selected], robots_urls=[robots],
            )
            docs = fetcher.fetch("https://api.flutter.dev/flutter/widgets/SizedBox-class.html")
            assert calls == [robots, selected]
            with pytest.raises(ValueError, match="finite_member_seed_mismatch"):
                fetcher.fetch(selected + "?unselected=1")
            with pytest.raises(ValueError, match="explicit_robots_member_required"):
                WebFetcher(
                    max_pages=10, browser=False, doc_format="dartdoc", fetch_policy=policy,
                    exact_urls=[selected],
                ).fetch(selected)
            assert calls == [robots, selected]

        assert len(docs) == 1
        assert "SizedBox class" in docs[0].content
        assert "Constructors" in docs[0].content
        assert "width" in docs[0].content
        assert fetcher._browser is False
        assert docs[0].source == selected
        assert fetcher._respect_robots is True
