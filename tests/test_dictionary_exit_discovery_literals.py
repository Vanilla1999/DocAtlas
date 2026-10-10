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


@pytest.mark.parametrize("segment", ["docs", "documentation", "reference", "api", "guide"])
def test_path_subject_does_not_boost_candidate(segment):
    urls = [f"https://docs.example/{segment}/z", "https://docs.example/a"]
    result = discovery._dedupe_and_rank([_candidate(url) for url in urls])
    assert [item.url for item in result] == sorted(urls)
    assert {item.url for item in result} == set(urls)


def test_strategy_provenance_and_content_survive_deduplication():
    url = "https://docs.example/api/entity"
    preferred = discovery.DiscoveredUrl(url, discovery.DiscoveryStrategy.LLMS_TXT, "raw")
    result = discovery._dedupe_and_rank([
        _candidate(url + "/#anchor"), _candidate("https://docs.example/a"), preferred,
    ])
    assert len(result) == 2
    assert result[0] is preferred
    assert result[0].content == "raw"
    assert result[0].strategy == discovery.DiscoveryStrategy.LLMS_TXT


@pytest.mark.parametrize("word", ["and", "are", "for", "from", "how", "the", "this", "use", "what", "when", "where", "which", "with"])
def test_query_words_are_literal_terms_not_stopwords(word):
    unrelated = _candidate("https://docs.example/alpha")
    literal = _candidate(f"https://docs.example/{word}")
    result = discovery._rank_urls_for_query([unrelated, literal], word)
    assert result == [literal, unrelated]
    assert discovery._rank_urls_for_query([unrelated, literal], "unknown") == [unrelated, literal]


@pytest.mark.parametrize("word", ["what", "when", "where", "which", "with", "should", "using", "implemented"])
def test_dartdoc_query_words_are_literal_terms(word):
    urls = ["https://docs.example/Alpha-class.html", f"https://docs.example/{word}-class.html"]
    assert discovery._rank_dartdoc_urls_for_query(urls, word) == urls[::-1]


def test_dartdoc_filename_identity_is_structural_not_topical():
    urls = [
        "https://docs.example/guide.html",
        "https://docs.example/guide-class.html/fake.html",
        "https://docs.example/Alpha-class.html",
    ]
    assert discovery._rank_dartdoc_urls_for_query(urls, "unknown") == [urls[2], *urls[:2]]


@pytest.mark.parametrize("package,root", [
    ("riverpod", "https://riverpod.dev/"),
    ("flutter_riverpod", "https://riverpod.dev/"),
    ("hooks_riverpod", "https://riverpod.dev/"),
    ("flutter_bloc", "https://bloclibrary.dev/"),
    ("bloc", "https://bloclibrary.dev/"),
    ("hydrated_bloc", "https://bloclibrary.dev/"),
])
def test_registered_roots_survive_without_inferred_topic_seeds(package, root):
    api = f"https://pub.dev/documentation/{package}/2.4.0/"
    resolution = resolve_dart_official_docs(package, version="2.4.0")
    assert resolution.official_docs_urls == sorted([root, api])
    assert resolution.pubdev_docs_url == api
    assert resolution.docs_strategy == "mixed"
    assert has_official_docs(package)
    assert get_seed_urls_for_package(package, "2.4.0", max_urls=1) == sorted([root, api])[:1]
    assert resolve_dart_official_docs(package, "2.4.0", include_pubdev=False).official_docs_urls == [root]


def test_framework_topic_seed_is_removed_without_replacement_root():
    result = resolve_dart_official_docs("go_router", "14.0.0")
    assert not result.official_docs_available
    assert not has_official_docs("go_router")
    assert result.official_docs_urls == [
        "https://pub.dev/documentation/go_router/14.0.0/",
        "https://pub.dev/packages/go_router",
    ]
    assert all("flutter.dev" not in url for url in result.official_docs_urls)


def test_explicit_api_templates_and_package_pages_are_not_topic_tables():
    for package, sources in DART_PACKAGE_OFFICIAL_DOCS.items():
        result = resolve_dart_official_docs(package, "1.2.3")
        assert result.pubdev_docs_url == sources.pubdev_api.format(version="1.2.3")
        assert set(result.official_docs_urls) == set(sources.official_guides) | {
            result.pubdev_docs_url,
            *([sources.package_page] if sources.package_page else []),
        }
    unknown = resolve_dart_official_docs("unknown_package", "1.2.3")
    assert unknown.official_docs_urls == ["https://pub.dev/documentation/unknown_package/1.2.3/"]
    assert resolve_dart_official_docs("unknown_package", include_pubdev=False).official_docs_urls == []


@pytest.mark.parametrize("package", ["flutter-riverpod", "flutter riverpod", "../riverpod", "riverpod/other", ""])
def test_nonliteral_package_alias_does_not_open_another_source(package):
    with pytest.raises(ValueError, match="literal Dart package"):
        resolve_dart_official_docs(package)
    assert discovery_candidates_for(package, "dart") == []


@pytest.mark.parametrize("ecosystem", ["pub", "flutter", "unknown"])
def test_ecosystem_identities_do_not_collapse_to_dart(ecosystem):
    assert canonical_dart_ecosystem(ecosystem) == ecosystem
    assert discovery_candidates_for("riverpod", ecosystem) == []


def test_literal_identity_spelling_and_candidate_copies():
    assert normalize_package_name(" Riverpod ") == "riverpod"
    assert canonical_dart_ecosystem(" DART ") == "dart"
    assert canonical_dart_ecosystem(None) is None
    result = discovery_candidates_for(" RIVERPOD ", " DART ")
    assert [item["docs_url"] for item in result] == sorted([
        "https://riverpod.dev/", "https://pub.dev/documentation/riverpod/latest/",
    ])
    assert all("preferred" not in item["why"] and "fallback" not in item["why"] for item in result)
    result[0]["docs_url"] = "https://evil.example/"
    assert all(item["docs_url"] != "https://evil.example/" for item in discovery_candidates_for("riverpod", None))
    assert discovery_candidates_for("FastAPI", "python")[0]["docs_url"] == "https://fastapi.tiangolo.com/"
    assert discovery_candidates_for("mcp", "python")[0]["docs_url"] == "https://github.com/modelcontextprotocol/python-sdk"


def test_diagnostics_preserve_snapshot_and_non_authority_fields():
    result = build_dart_diagnostics(
        package="riverpod", version="2.4.0", root_url="https://riverpod.dev/",
        pages_discovered=2, pages_extracted=0, chunks_created=0, used_official_docs=True,
    )
    assert result["version"] == "2.4.0"
    assert result["root_url"] == "https://riverpod.dev/"
    assert result["reason_code"] == "dartdoc_no_extractable_content"
    assert result["docs_strategy"] == "mixed"
    assert "mutation_authorized" not in result


def test_actual_dart_resolver_caller_preserves_root_and_version_provenance(tmp_path):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import LibraryDocsService

    registry = LibraryRegistry(tmp_path / "docs.sqlite3")
    service = LibraryDocsService(config=DocmancerConfig(), registry=registry)
    info = service.resolve_library("riverpod", ecosystem="dart", version="2.4.0")
    record = registry.get(info.library_id, source_type="web")
    assert record.docs_url == "https://riverpod.dev/"
    assert record.ecosystem == "dart"
    assert record.target_spec["seed_urls"] == ["https://pub.dev/documentation/riverpod/2.4.0/"]
    assert set(record.target_spec["allowed_domains"]) == {"riverpod.dev", "pub.dev"}
    assert record.target_spec["max_pages"] == 100
    assert record.requested_version == "2.4.0"
    # Registry currently echoes the requested version; that is not an exact
    # binding for the unversioned root (the explicit flag remains negative).
    assert record.resolved_version == "2.4.0"
    assert record.docs_snapshot_exact is False
    assert record.target_spec["dart_docs"]["version_binding"] == "unversioned_official_guide"


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


@pytest.mark.parametrize("ecosystem", ["pub", "flutter"])
def test_removed_ecosystem_alias_does_not_expand_caller_target(tmp_path, ecosystem):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import LibraryDocsService

    registry = LibraryRegistry(tmp_path / "docs.sqlite3")
    service = LibraryDocsService(config=DocmancerConfig(), registry=registry)
    # Nonowned curated fallback still exists. Its current riverpod target is a
    # strict subset of the original explicit roots, not a new replacement scope.
    info = service.resolve_library("riverpod", ecosystem=ecosystem)
    record = registry.get(info.library_id, source_type=info.source_type)
    assert record.docs_url == "https://riverpod.dev/"
    assert record.target_spec["seed_urls"] == []
    assert record.target_spec["allowed_domains"] == ["riverpod.dev"]
    assert not record.docs_snapshot_exact


def test_bounded_discover_urls_ranks_only_original_candidates(monkeypatch):
    base = "https://docs.example/scope"
    seeds = [base + "/explicit"]
    monkeypatch.setattr(discovery, "_try_dartdoc_index_with_diagnostics", lambda *a, **k: (None, {}))
    monkeypatch.setattr(discovery, "_try_llms_txt", lambda *a: [
        _candidate(base + "/docs/z", discovery.DiscoveryStrategy.LLMS_TXT),
        _candidate(base + "/a", discovery.DiscoveryStrategy.LLMS_TXT),
    ])
    for name in ("_try_robots_sitemap", "_try_sitemap_xml", "_try_platform_sitemap", "_try_nav_crawl", "_try_nav_fallback"):
        monkeypatch.setattr(discovery, name, lambda *a: None)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404))) as client:
        result = discovery.discover_urls(base, client, query="unknown", seed_urls=seeds, max_pages=2)
    assert [item.url for item in result.urls] == [base + "/a", base + "/docs/z"]
    assert result.diagnostics["seed_pages"] == 1
    assert result.diagnostics["strategies"]["llms.txt"] == 2
    assert seeds == [base + "/explicit"]


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


def test_security_errors_are_not_converted_to_discovery_permission():
    def respond(request):
        raise DocsFetchSecurityError("out_of_scope", str(request.url), phase="fetch")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DocsFetchSecurityError):
            discovery.discover_urls("https://docs.example/scope", client, force_strategy="llms.txt")


@pytest.mark.parametrize("path", ["/scope/ru/entity", "/scope/blog/entity", "/scope/changelog/entity", "/scope-other/entity", "/other/entity"])
def test_blocked_exclusion_contract_is_not_broadened(path):
    assert not is_docs_url("https://docs.example" + path, "https://docs.example/scope")
    assert is_docs_url("https://docs.example/scope/entity", "https://docs.example/scope")
