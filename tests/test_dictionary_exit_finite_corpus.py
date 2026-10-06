from __future__ import annotations

import hashlib
import ipaddress
from unittest.mock import MagicMock

import httpx
import pytest

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.connectors.fetchers.web import WebFetcher
from docmancer.connectors.fetchers.github import GitHubFetcher
from docmancer.connectors.fetchers.crawl4ai import Crawl4AIFetcher
from docmancer.connectors.fetchers.pipeline.discovery import discover_urls, DiscoveryStrategy
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.fetch_transport import DocsHttpClient
from docmancer.docs.finite_membership import exact_url, finite_members
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest

ROOT = "https://example.com/docs"
ROBOTS = "https://example.com/robots.txt"


@pytest.fixture
def offline_http(monkeypatch):
    calls = []
    responses = {}
    monkeypatch.setattr("docmancer.docs.fetch_policy.resolve_host", lambda host: (ipaddress.ip_address("93.184.216.34"),))

    def handler(request):
        url = str(request.url)
        calls.append(url)
        value = responses.get(url, "# Exact document\n\nSelected source content.")
        if isinstance(value, tuple):
            return httpx.Response(value[0], headers={"location": value[1]}, request=request)
        return httpx.Response(200, content=value, headers={"content-type": "text/plain"}, request=request)

    def client(fetcher, policy=None):
        return DocsHttpClient(
            httpx.Client(transport=httpx.MockTransport(handler)), policy or fetcher._fetch_policy,
            pin_resolved_ips=False, max_redirects=fetcher._max_redirects,
            max_response_bytes=fetcher._max_response_bytes,
            max_decoded_text_bytes=fetcher._max_decoded_text_bytes,
            max_total_seconds=fetcher._max_total_seconds, deadline_at=fetcher._deadline_at,
        )

    monkeypatch.setattr(WebFetcher, "_new_client", client)
    responses[ROBOTS] = "User-agent: *\nAllow: /\nSitemap: https://evil.test/map.xml"
    return calls, responses


def _agent():
    agent = DocmancerAgent.__new__(DocmancerAgent)
    agent.config = DocmancerConfig()
    agent._store = MagicMock()
    agent.store.delete_docset_sources_except.return_value = 0
    agent.documents = []
    agent.ingest_documents = lambda documents, **kwargs: agent.documents.extend(documents) or len(documents)
    return agent


@pytest.mark.parametrize("path", ["ru/page", "blog/page", "changelog", "pricing", "settings", "print.html", "old/legacy.md", "Widget-class.html", "llms-full.txt"])
def test_agent_exact_selection_keeps_locale_topic_and_early_returns_bounded(path, offline_http):
    calls, responses = offline_http
    url = ROOT + "/" + path + "?source=v1&ref=v2&from=guide&utm_source=explicit"
    agent = _agent()
    assert agent.add(url, exact_urls=[url], robots_urls=[ROBOTS], allowed_domains=["example.com"], path_prefixes=["/"], with_vectors=False) == 1
    assert calls == [ROBOTS, url]
    assert agent.documents[0].source == url
    assert agent.last_discovery_diagnostics["discovery_strategy"] == "finite-explicit"


@pytest.mark.parametrize("strategy", [None, "llms-full.txt", "llms.txt", "sitemap.xml", "nav-crawl", "platform-sitemap", "unknown"])
def test_discovery_never_probes_and_seed_collision_cannot_replace_member(strategy):
    client = MagicMock()
    urls = [ROOT, ROOT, ROOT + "/ru/a"]
    result = discover_urls(ROOT, client, seed_urls=urls, force_strategy=strategy, root_html='<a href="https://evil.test/a">extra</a>', query="topic")
    assert [item.url for item in result.urls] == [ROOT, ROOT + "/ru/a"]
    assert all(item.strategy == DiscoveryStrategy.SEED_URLS and item.content is None for item in result.urls)
    client.get.assert_not_called()


@pytest.mark.parametrize("members", [None, [], (), "https://example.com/docs"])
def test_unknown_or_empty_set_never_fetches(members, offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError, match="explicit_members_required"):
        WebFetcher(exact_urls=members).fetch(ROOT)
    assert calls == []


@pytest.mark.parametrize("url", ["https://evil.test/docs", "https://example.com/docs-other", "https://example.com/docs?source=other", "http://example.com/docs", ROOT + "/ru/extra"])
def test_unselected_seed_never_fetches(url, offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError, match="seed_mismatch"):
        WebFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS]).fetch(url)
    assert calls == []


@pytest.mark.parametrize("extra", ["https://evil.test/docs", "https://example.com/docs-other"])
def test_invalid_set_preflight_does_not_fetch_any_member(extra, offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError, match="outside_transport_scope"):
        WebFetcher(exact_urls=[ROOT, extra], allowed_domains=["example.com"], path_prefixes=["/docs"], respect_robots=False).fetch(ROOT)
    assert calls == []


@pytest.mark.parametrize("location", ["https://evil.test/docs", "/docs-other", "/docs?source=v2", "/docs/ru/extra", "http://127.0.0.1/admin"])
def test_redirect_cannot_dispatch_to_unselected_member(location, offline_http):
    calls, responses = offline_http
    responses[ROOT] = (302, location)
    with pytest.raises(DocsFetchSecurityError, match="url_not_selected"):
        WebFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS], delay=0).fetch(ROOT)
    assert calls == [ROBOTS, ROOT]


def test_selected_redirect_still_enforces_private_network(offline_http, monkeypatch):
    calls, responses = offline_http
    private = "https://private.example.com/docs"
    monkeypatch.setattr("docmancer.docs.fetch_policy.resolve_host", lambda host: (ipaddress.ip_address("127.0.0.1" if host.startswith("private") else "93.184.216.34"),))
    with pytest.raises(DocsFetchSecurityError, match="private_network_blocked"):
        WebFetcher(exact_urls=[ROOT, private], allowed_domains=["example.com"], respect_robots=False).fetch(ROOT)
    assert calls == []


def test_canonical_cannot_relabel_to_unselected_query(offline_http, monkeypatch):
    calls, responses = offline_http
    responses[ROOT] = '<html><body><article>Selected content</article></body></html>'
    monkeypatch.setattr("docmancer.connectors.fetchers.web.extract_content", lambda *a, **k: "Selected content")
    monkeypatch.setattr("docmancer.connectors.fetchers.web.extract_metadata", lambda *a, **k: {"canonical_url": ROOT + "?ref=other"})
    with pytest.raises(ValueError, match="canonical_url_not_selected"):
        WebFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS], delay=0).fetch(ROOT)
    assert calls == [ROBOTS, ROOT]


def test_robots_must_be_explicit_and_cannot_promote_scope(offline_http):
    calls, responses = offline_http
    with pytest.raises(ValueError, match="explicit_robots_member_required"):
        WebFetcher(exact_urls=[ROOT]).fetch(ROOT)
    with pytest.raises(ValueError, match="outside_transport_scope"):
        WebFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS], path_prefixes=["/docs"]).fetch(ROOT)
    assert calls == []
    responses[ROBOTS] = "User-agent: *\nDisallow: /docs"
    assert WebFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS], delay=0).fetch(ROOT) == []
    assert calls == [ROBOTS]


def test_aggregate_requires_explicit_whole_document_and_never_expands_links(offline_http):
    calls, responses = offline_http
    aggregate = "https://example.com/llms-full.txt"
    responses[aggregate] = "# Whole document\n[More](https://evil.test/extra)"
    fetcher = WebFetcher(exact_urls=[aggregate], robots_urls=[ROBOTS], delay=0)
    docs = fetcher.fetch(aggregate)
    assert len(docs) == 1 and docs[0].source == aggregate
    assert calls == [ROBOTS, aggregate]


@pytest.mark.parametrize("lane", ["github", "crawl4ai", "injected"])
def test_direct_legacy_lanes_fail_closed_without_contract(lane, offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError):
        if lane == "github":
            GitHubFetcher(file_patterns=["**/*.md"]).fetch("https://github.com/o/r/tree/main")
        elif lane == "crawl4ai":
            Crawl4AIFetcher().fetch(ROOT)
        else:
            _agent().add(ROOT, fetcher=MagicMock())
    assert calls == []


def test_crawl4ai_valid_contract_uses_secure_finite_http_not_browser(offline_http):
    calls, _ = offline_http
    docs = Crawl4AIFetcher(exact_urls=[ROOT], robots_urls=[ROBOTS], delay=0).fetch(ROOT)
    assert [doc.source for doc in docs] == [ROOT]
    assert calls == [ROBOTS, ROOT]


@pytest.mark.parametrize("path", ["docs/ru/CHANGELOG.md", "docs/legacy/LICENSE.md"])
def test_immutable_manifest_selected_rows_keep_blob_hash_provenance(path, offline_http):
    calls, responses = offline_http
    raw = b"# Approved immutable member\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "o", "repository": "r", "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs"},
        "documents": [{"path": path, "git_blob_sha": blob, "size": len(raw)}],
        "complete": True, "truncated": False,
    })
    row = manifest["documents"][0]
    responses[row["raw_url"]] = raw
    docs = GitHubFetcher(source_manifest=manifest).fetch(row["blob_url"])
    assert calls == [row["raw_url"]]
    assert docs[0].source == row["blob_url"]
    assert docs[0].metadata["git_blob_sha"] == blob
    assert docs[0].metadata["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert docs[0].metadata["resolved_commit_sha"] == "1" * 40


@pytest.mark.parametrize("url", ["https://github.com/o/r/blob/main/docs/a.md", "https://github.com/o/r/tree/v2/docs", "https://raw.githubusercontent.com/o/r/main/docs/a.md"])
def test_extra_github_refs_and_unhashed_files_never_fetch(url, offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError, match="github_source_manifest_required"):
        WebFetcher(exact_urls=[url], respect_robots=False).fetch(url)
    assert calls == []


def test_finite_budget_rejects_whole_set_not_silent_truncation(offline_http):
    calls, _ = offline_http
    with pytest.raises(ValueError, match="exceed_max_pages"):
        WebFetcher(exact_urls=[ROOT, ROOT + "/a"], max_pages=1).fetch(ROOT)
    assert calls == []


@pytest.mark.parametrize("url", [ROOT + "/../admin", ROOT + "/%252e%252e/admin", ROOT + "#part", "https://user:secret@example.com/docs", "file:///docs"])
def test_invalid_exact_spelling_is_not_another_member(url):
    with pytest.raises(ValueError, match="invalid_finite_member"):
        exact_url(url)


def test_prefetch_real_agent_path_propagates_exact_urls_and_ceilings(tmp_path, monkeypatch, offline_http):
    from tests._shared_test_docs_service import _service

    calls, responses = offline_http
    agent = _agent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda *a, **k: pytest.fail("implicit package discovery"))
    monkeypatch.setattr(service, "_resolve_github_directory_target", lambda *a, **k: pytest.fail("implicit tree discovery"))
    member = ROOT + "/ru/blog?source=v1"
    result = service.prefetch_docs_targets([{
        "library": "finite-example", "docs_url": member, "seed_urls": [ROBOTS],
        "allowed_domains": ["example.com"], "path_prefixes": ["/"],
    }], force_refresh=True)
    assert member in calls
    assert set(calls) == {ROBOTS, member}
    assert all(doc.source in {ROBOTS, member} for doc in agent.documents)
    assert result.results[0].canonical_id
    calls.clear()
    monkeypatch.setattr(service, "_record_urls", lambda *a, **k: pytest.fail("legacy resolved/discovered cache used"))
    service.refresh_docs("finite-example", force=True)
    assert member in calls
    assert set(calls) == {ROBOTS, member}


def test_prefetch_missing_members_does_not_call_discovery(tmp_path, monkeypatch, offline_http):
    from tests._shared_test_docs_service import _service

    service = _service(tmp_path, monkeypatch, _agent())
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda *a, **k: pytest.fail("implicit package discovery"))
    result = service.prefetch_docs_targets([{"library": "unknown", "allowed_domains": ["example.com"]}])
    assert result.results[0].status == "failed"
    assert offline_http[0] == []


@pytest.mark.parametrize("kind", ["host", "path", "robots_missing", "unresolved_manifest"])
def test_prefetch_rejected_caller_selection_makes_no_http_request(kind, tmp_path, monkeypatch, offline_http):
    from tests._shared_test_docs_service import _service

    service = _service(tmp_path, monkeypatch, _agent())
    target = {"library": "rejected", "docs_url": ROOT, "allowed_domains": ["example.com"], "path_prefixes": ["/"]}
    if kind == "host":
        target["docs_url"] = "https://evil.test/docs"
    elif kind == "path":
        target.update(docs_url="https://example.com/docs-other", path_prefixes=["/docs"])
    elif kind == "unresolved_manifest":
        target["source_manifest"] = {"schema_version": 2, "discovery": {"kind": "github_directory", "owner": "o", "repository": "r", "requested_ref": "main", "directory": "docs"}}
    result = service.prefetch_docs_targets([target], force_refresh=True)
    assert result.results[0].status in {"failed", "partial"}
    assert offline_http[0] == []


@pytest.mark.parametrize("kind", ["bytes", "cancelled", "deadline"])
def test_finite_lane_preserves_operation_budgets(kind, offline_http):
    calls, _ = offline_http
    kwargs = {"exact_urls": [ROOT], "robots_urls": [ROBOTS], "delay": 0}
    if kind == "bytes":
        kwargs["max_fetched_document_bytes"] = 1
    elif kind == "cancelled":
        kwargs["cancellation_callback"] = lambda: True
    else:
        kwargs["deadline_at"] = 0
    with pytest.raises((RuntimeError, DocsFetchSecurityError)):
        WebFetcher(**kwargs).fetch(ROOT)
    assert calls == ([ROBOTS, ROOT] if kind == "bytes" else [])


def test_manifest_redirect_cannot_expand_raw_ref(offline_http):
    calls, responses = offline_http
    raw = b"# A\n"
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "o", "repository": "r", "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs"},
        "documents": [{"path": "docs/a.md", "git_blob_sha": hashlib.sha1(b"blob 4\0" + raw).hexdigest(), "size": len(raw)}],
        "complete": True, "truncated": False,
    })
    row = manifest["documents"][0]
    responses[row["raw_url"]] = (302, row["raw_url"].replace("1" * 40, "2" * 40))
    with pytest.raises(ValueError, match="url_not_selected"):
        GitHubFetcher(source_manifest=manifest).fetch(row["blob_url"])
    assert calls == [row["raw_url"]]


def test_concrete_agent_roots_and_seeds_are_members_not_subtrees(offline_http, monkeypatch):
    calls, responses = offline_http
    seeds = [ROOT + "?ref=v1", ROOT + "?ref=v2"]
    responses[ROOT] = '<html><body><article>Exact root</article><a href="/docs/ru/extra">extra</a><a href="/llms-full.txt">aggregate</a></body></html>'
    monkeypatch.setattr("docmancer.connectors.fetchers.web.extract_content", lambda *a, **k: "Exact root")
    monkeypatch.setattr("docmancer.connectors.fetchers.web.extract_metadata", lambda *a, **k: {})
    monkeypatch.setattr(WebFetcher, "_fetch_and_detect", lambda *a, **k: pytest.fail("implicit landing/discovery"))
    agent = _agent()
    assert agent.add(ROOT, seed_urls=seeds, robots_urls=[ROBOTS], max_pages=3, with_vectors=False) == 3
    assert calls == [ROBOTS, ROOT, *seeds]
    assert [doc.source for doc in agent.documents] == [ROOT, *seeds]


def test_explicit_empty_agent_contract_cannot_fall_back_to_root(offline_http):
    with pytest.raises(ValueError, match="explicit_members_required"):
        _agent().add(ROOT, exact_urls=[], seed_urls=[ROOT], robots_urls=[ROBOTS])
    assert offline_http[0] == []


def test_sdk_fetch_documents_accepts_same_finite_contract(offline_http):
    docs = _agent().fetch_documents(ROOT, exact_urls=[ROOT], robots_urls=[ROBOTS])
    assert [doc.source for doc in docs] == [ROOT]
    assert offline_http[0] == [ROBOTS, ROOT]
