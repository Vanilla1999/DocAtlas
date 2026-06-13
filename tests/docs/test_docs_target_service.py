from __future__ import annotations

from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, normalize_pub_dartdoc_target
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
