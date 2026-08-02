from __future__ import annotations

import httpx
import pytest

from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, normalize_pub_dartdoc_target
from docmancer.docs.fetch_policy import DocsFetchSecurityError
from docmancer.docs.models import DocsTarget
from docmancer.docs.registry import LibraryRecord


def render_docs_url(template: str, library: str, version: str) -> str:
    return template.format(library=library, version=version)


def test_target_service_dict_to_target_preserves_warnings_and_defaults():
    target = DocsTargetService.target_from_dict({"library": "go_router", "warnings": ["warn"]})

    assert target == DocsTarget(library="go_router", version="latest", source_type="api", max_pages=200, warnings=["warn"])


def test_target_service_target_to_spec_includes_resolved_urls():
    target = DocsTarget(library="go_router", version="14.8.1", seed_urls=["https://pub.dev/documentation/go_router/14.8.1/"], allowed_domains=["pub.dev"])

    spec = DocsTargetService.target_to_spec(target, ["https://pub.dev/documentation/go_router/14.8.1/"])

    assert spec["version"] == "14.8.1"
    assert spec["resolved_urls"] == ["https://pub.dev/documentation/go_router/14.8.1/"]


def test_target_service_record_urls_prefers_record_spec_resolved_urls():
    record = LibraryRecord(
        library_id="pub/go_router/14/api",
        source_id="source",
        canonical_id="pub/go_router/14/api",
        name="go_router",
        normalized_name="go-router",
        ecosystem="pub",
        version="14",
        source_type="api",
        docs_url=None,
        docs_url_template=None,
        aliases=[],
        status="available",
        added_at="now",
        last_checked_at=None,
        last_refreshed_at=None,
        last_error=None,
        target_spec={"resolved_urls": ["https://pub.dev/documentation/go_router/14/"]},
    )

    assert DocsTargetService(render_docs_url).record_urls(record) == ["https://pub.dev/documentation/go_router/14/"]


def test_target_service_rejects_remote_urls_without_allowed_domains():
    urls, error = DocsTargetService(render_docs_url).target_urls(DocsTarget(library="flutter", docs_url="https://api.flutter.dev/"))

    assert urls == []
    assert error == "allowed_domains is required for remote docs targets"


def test_pub_dartdoc_discovery_finds_class_pages():
    html = '<a href="go_router/ShellRoute-class.html">ShellRoute</a><a href="go_router/GoRouter-class.html">GoRouter</a>'
    urls = discover_pub_dartdoc_seed_urls("go_router", "17.2.3", html, "https://pub.dev/documentation/go_router/17.2.3/")
    assert urls == [
        "https://pub.dev/documentation/go_router/17.2.3/go_router/ShellRoute-class.html",
        "https://pub.dev/documentation/go_router/17.2.3/go_router/GoRouter-class.html",
    ]


def test_pub_dartdoc_discovery_finds_supported_entity_pages_and_libraries():
    html = """
    <a href="pkg/Foo-mixin.html">Foo</a>
    <a href="pkg/Bar-enum.html">Bar</a>
    <a href="pkg/Baz-extension.html">Baz</a>
    <a href="pkg/Qux-typedef.html">Qux</a>
    <a href="pkg/doThing-function.html">doThing</a>
    <a href="pkg/value-constant.html">value</a>
    <a href="pkg/prop-property.html">prop</a>
    <a href="pkg/">pkg</a>
    """
    urls = discover_pub_dartdoc_seed_urls("sample", "1.0.0", html, "https://pub.dev/documentation/sample/1.0.0/")
    assert urls[-1] == "https://pub.dev/documentation/sample/1.0.0/pkg/"
    assert len(urls) == 8


def test_pub_dartdoc_discovery_empty_returns_no_seeds():
    assert discover_pub_dartdoc_seed_urls("pkg", "1.0.0", "<html></html>", "https://pub.dev/documentation/pkg/1.0.0/") == []


def test_dartdoc_root_page_entity_discovery_fetches_library_pages():
    root = '<a href="sample/">sample</a>'
    pages = {
        "https://pub.dev/documentation/sample/1.0.0/sample/": '<a href="Foo-class.html">Foo</a><a href="doThing-function.html">doThing</a>',
    }

    urls = discover_pub_dartdoc_seed_urls(
        "sample",
        "1.0.0",
        root,
        "https://pub.dev/documentation/sample/1.0.0/",
        fetch_url=pages.get,
    )

    assert urls[:2] == [
        "https://pub.dev/documentation/sample/1.0.0/sample/Foo-class.html",
        "https://pub.dev/documentation/sample/1.0.0/sample/doThing-function.html",
    ]


def test_dartdoc_no_article_content_fallback_uses_json_sidebar():
    root = "<html><body>No extractable article content</body></html>"
    pages = {
        "https://pub.dev/documentation/sample/1.0.0/categories.json": '{"categories":[{"href":"sample/Foo-class.html"}]}',
        "https://pub.dev/documentation/sample/1.0.0/sidebar.json": '{"items":[{"url":"sample/doThing-function.html"}]}',
    }

    urls = discover_pub_dartdoc_seed_urls(
        "sample",
        "1.0.0",
        root,
        "https://pub.dev/documentation/sample/1.0.0/",
        fetch_url=pages.get,
    )

    assert urls == [
        "https://pub.dev/documentation/sample/1.0.0/sample/Foo-class.html",
        "https://pub.dev/documentation/sample/1.0.0/sample/doThing-function.html",
    ]


def test_pub_dartdoc_discovery_dedupes_and_stays_inside_prefix():
    html = """
    <a href="pkg/Foo-class.html">Foo</a>
    <a href="pkg/Foo-class.html#x">Foo again</a>
    <a href="https://pub.dev/documentation/other/1.0.0/other/Other-class.html">Other</a>
    <a href="https://example.com/pkg/Foo-class.html">External</a>
    """
    urls = discover_pub_dartdoc_seed_urls("pkg", "1.0.0", html, "https://pub.dev/documentation/pkg/1.0.0/")
    assert urls == ["https://pub.dev/documentation/pkg/1.0.0/pkg/Foo-class.html"]


def test_normalize_pub_dartdoc_target_infers_defaults():
    target = normalize_pub_dartdoc_target(DocsTarget(library="go_router", ecosystem="pub", version="17.2.3"))
    assert target.doc_format == "dartdoc"
    assert target.allowed_domains == ["pub.dev"]
    assert target.path_prefixes == ["/documentation/go_router/17.2.3/"]
    assert target.max_pages == 500


def test_normalize_pub_dartdoc_target_preserves_explicit_max_pages():
    target = normalize_pub_dartdoc_target(DocsTarget(library="go_router", ecosystem="pub", version="17.2.3", max_pages=75))

    assert target.max_pages == 75


def test_pub_dartdoc_discovery_propagates_security_rejection(monkeypatch):
    def reject(*_args, **_kwargs):
        raise DocsFetchSecurityError(
            "private_network_blocked",
            "https://pub.dev/documentation/pkg/1.0.0/",
        )

    monkeypatch.setattr("docmancer.docs.application.docs_target_service.DocsHttpClient.get", reject)
    target = DocsTarget(
        library="pkg",
        ecosystem="pub",
        version="1.0.0",
        source_type="api",
        allowed_domains=["pub.dev"],
        path_prefixes=["/documentation/pkg/1.0.0"],
    )

    with pytest.raises(DocsFetchSecurityError, match="private_network_blocked"):
        DocsTargetService(render_docs_url).discover_pub_dartdoc_target(target, [])


def test_inspect_docs_target_returns_bounded_navigation_metadata_without_discovery(monkeypatch):
    class FakeTransport:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<title>Sample API</title><base href='../api/'>"
                    "<a href='widgets/'>Widgets</a>"
                    "<a href='https://outside.example/Other-class.html'>Other</a>"
                ),
                request=request,
            )

    monkeypatch.setattr("docmancer.docs.application.docs_target_service.DocsHttpClient", FakeTransport)
    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", lambda **_kwargs: object())
    service = DocsTargetService(render_docs_url)
    monkeypatch.setattr(
        service,
        "discover_pub_dartdoc_target",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("inspection must not discover")),
    )

    result = service.inspect_docs_target({
        "library": "sample",
        "docs_url": "https://docs.example/docs/index.html",
        "allowed_domains": ["docs.example"],
        "path_prefixes": ["/docs/"],
    })

    assert result.status == "ok"
    assert result.observations == {
        "pages_requested": 1,
        "pages_inspected": 1,
        "link_candidates": 2,
        "outside_scope_candidates": 1,
        "content_trust": "untrusted_navigation_metadata",
        "instruction_trust": "untrusted_data",
        "navigation_metadata_is_actionable": False,
        "scope_expanded": False,
        "indexed": False,
    }
    page = result.pages[0]
    assert page["base_within_scope"] is False
    assert page["resolved_base_url"] == "https://docs.example/api/"
    assert page["link_candidates"][0] == {
        "url": "https://docs.example/docs/widgets/",
        "kind": "directory",
        "within_scope": True,
    }
    assert result.decision_options[1]["id"] == "request_scope_expansion"
    assert result.manifest_proposal["version"] == 2
    proposal = result.manifest_proposal["targets"][0]
    assert proposal["source"]["url"] == "https://docs.example/docs/index.html"
    assert proposal["scope"]["path_prefixes"] == ["/docs/"]
    assert result.manifest_proposal["requires_confirmation"] is True
    assert result.evidence_report["decision"] == "confirm"
    assert result.evidence_report["authority"]["status"] == "unconfirmed"


def test_inspect_docs_target_rejects_manifests_and_caps_pages_before_fetch(monkeypatch):
    fetched = []

    class FakeTransport:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, url):
            fetched.append(url)
            request = httpx.Request("GET", url)
            return httpx.Response(200, headers={"content-type": "text/html"}, text="<title>Docs</title>", request=request)

    monkeypatch.setattr("docmancer.docs.application.docs_target_service.DocsHttpClient", FakeTransport)
    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", lambda **_kwargs: object())
    service = DocsTargetService(render_docs_url)
    rejected = service.inspect_docs_target({
        "library": "sample",
        "docs_url": "https://docs.example/docs/",
        "allowed_domains": ["docs.example"],
        "source_manifest": {"schema_version": 2},
    })
    result = service.inspect_docs_target({
        "library": "sample",
        "seed_urls": [f"https://docs.example/docs/{index}" for index in range(10)],
        "allowed_domains": ["docs.example"],
        "path_prefixes": ["/docs/"],
    }, max_pages=99)

    assert rejected.reason_code == "source_manifest_not_supported"
    assert len(fetched) == 5
    assert result.target["max_pages"] == 5


def test_inspect_docs_target_does_not_expose_raw_base_href(monkeypatch):
    class FakeTransport:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<base href="https://user:secret@docs.example/docs/?token=hidden">',
                request=request,
            )

    monkeypatch.setattr("docmancer.docs.application.docs_target_service.DocsHttpClient", FakeTransport)
    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", lambda **_kwargs: object())
    result = DocsTargetService(render_docs_url).inspect_docs_target({
        "library": "sample",
        "docs_url": "https://docs.example/docs/",
        "allowed_domains": ["docs.example"],
        "path_prefixes": ["/docs/"],
    })

    page = result.pages[0]
    assert "base_href" not in page
    assert page["resolved_base_url"] == "https://docs.example/docs/"
    assert "secret" not in str(page)
    assert "hidden" not in str(page)


def test_inspect_docs_target_rejects_multiple_explicit_hosts_before_fetch(monkeypatch):
    monkeypatch.setattr(
        "docmancer.docs.application.docs_target_service.httpx.Client",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("transport must not be created")),
    )
    result = DocsTargetService(render_docs_url).inspect_docs_target({
        "library": "sample",
        "seed_urls": ["https://docs.example/api/", "https://api.example/reference/"],
        "allowed_domains": ["docs.example", "api.example"],
    })

    assert result.status == "failed"
    assert result.reason_code == "multiple_hosts_not_supported"
