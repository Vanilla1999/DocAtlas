"""Bounded discovery: literal URL ranking, identities and fail-closed seed scope."""

from __future__ import annotations

import json

import httpx
import pytest

from docmancer.connectors.fetchers.pipeline import discovery
from docmancer.connectors.fetchers.pipeline.detection import Platform
from docmancer.connectors.fetchers.pipeline.filtering import is_docs_url
from docmancer.docs.dart_official_docs import (
    DART_PACKAGE_OFFICIAL_DOCS,
    build_dart_diagnostics,
    canonical_dart_ecosystem,
    get_seed_urls_for_package,
    has_official_docs,
    normalize_package_name,
    resolve_dart_official_docs,
)
from docmancer.docs.discovery_candidates import discovery_candidates_for
from docmancer.docs.fetch_policy import DocsFetchSecurityError


def _candidate(url, strategy=discovery.DiscoveryStrategy.NAV_CRAWL):
    return discovery.DiscoveredUrl(url, strategy)






















@pytest.mark.parametrize("package", ["riverpod", "flutter_bloc", "go_router"])
def test_actual_explicit_api_caller_retains_package_snapshot_identity(tmp_path, package):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import LibraryDocsService

    registry = LibraryRegistry(tmp_path / "docs.sqlite3")
    service = LibraryDocsService(config=DocmancerConfig(), registry=registry)
    info = service.resolve_library(package, ecosystem="dart", version="2.4.0", source_type="api")
    record = registry.get(info.library_id, source_type="api")
    assert record.docs_url == f"https://pub.dev/documentation/{package}/2.4.0/"
    assert record.target_spec["seed_urls"] == []
    assert record.target_spec["allowed_domains"] == ["pub.dev"]
    assert record.target_spec["max_pages"] == 100
    assert record.requested_version == record.resolved_version == "2.4.0"
    assert record.docs_snapshot_exact is True
    assert record.target_spec["dart_docs"]["version_binding"] == "pubdev_api_snapshot"


def test_dartdoc_index_preserves_host_path_and_page_budget():
    base = "https://docs.example/snapshot/1.2.3/"
    payload = [
        {"href": "https://evil.example/Which-class.html"},
        {"href": "/snapshot/1.2.4/Which-class.html"},
        {"href": "Alpha-class.html"},
        {"href": "Which-class.html"},
    ]
    requests = []

    def respond(request):
        requests.append(str(request.url))
        assert str(request.url) == base + "index.json"
        return httpx.Response(200, text=json.dumps(payload))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        urls, diagnostic = discovery._try_dartdoc_index_with_diagnostics(
            base, client, max_pages=1, query="Which", root_html='<html class="dartdoc"></html>',
        )
    assert [item.url for item in urls] == [base + "Which-class.html"]
    assert diagnostic == {"complete": True, "reason_code": "ok"}
    assert requests == [base + "index.json"]


def test_protocol_locators_and_robots_sitemap_scope_are_preserved():
    base = "https://docs.example/scope"
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if str(request.url) == base + "/llms.txt":
            return httpx.Response(200, text=f"[Entity]({base}/entity)")
        if str(request.url) == base + "/sitemap.xml":
            return httpx.Response(200, text=f'<urlset><url><loc>{base}/entity</loc></url></urlset>')
        if str(request.url) == base + "/llms-full.txt":
            return httpx.Response(200, text="raw " * 400)
        return httpx.Response(404)

    class Robots:
        def get_sitemaps(self, url):
            assert url == base
            return [base + "/sitemap.xml"]

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert discovery._try_llms_txt(base, client, Platform.GENERIC, None)[0].url == base + "/entity"
        assert discovery._try_llms_full_txt(base, client, Platform.GENERIC, None)[0].content == "raw " * 400
        assert discovery._try_robots_sitemap(base, client, Robots(), max_pages=1)[0].url == base + "/entity"
    assert requests == [base + "/llms.txt", base + "/llms-full.txt", base + "/sitemap.xml"]

