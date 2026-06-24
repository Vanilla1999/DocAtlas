"""Integration tests for Dart/Flutter pub.dev and official docs ingestion."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from docmancer.docs.dart_official_docs import (
    resolve_dart_official_docs,
    get_seed_urls_for_package,
    has_official_docs,
    normalize_package_name,
)


class TestDartOfficialDocsResolver:
    """Test official docs resolver for Dart/Flutter packages."""

    def test_normalize_package_name(self):
        """Package names should be normalized to lowercase with underscores."""
        assert normalize_package_name("flutter_bloc") == "flutter_bloc"
        assert normalize_package_name("Flutter_Bloc") == "flutter_bloc"
        assert normalize_package_name("flutter-bloc") == "flutter_bloc"
        assert normalize_package_name("RIVERPOD") == "riverpod"

    def test_riverpod_has_official_docs(self):
        """Riverpod should resolve to official docs at riverpod.dev."""
        resolution = resolve_dart_official_docs("riverpod")
        
        assert resolution.official_docs_available is True
        assert resolution.package == "riverpod"
        assert resolution.docs_strategy == "official_docs"
        assert resolution.confidence == "high"
        assert "riverpod.dev" in resolution.official_docs_urls[0]
        assert "pub.dev/documentation/riverpod" in resolution.pubdev_docs_url

    def test_flutter_bloc_has_official_docs(self):
        """flutter_bloc should resolve to official docs at bloclibrary.dev."""
        resolution = resolve_dart_official_docs("flutter_bloc")
        
        assert resolution.official_docs_available is True
        assert resolution.package == "flutter_bloc"
        assert resolution.docs_strategy == "official_docs"
        assert "bloclibrary.dev" in resolution.official_docs_urls[0]
        assert "pub.dev/documentation/flutter_bloc" in resolution.pubdev_docs_url

    def test_unknown_package_falls_back_to_pubdev(self):
        """Unknown packages should fall back to pub.dev API reference."""
        resolution = resolve_dart_official_docs("unknown_package_xyz")
        
        assert resolution.official_docs_available is False
        assert resolution.package == "unknown_package_xyz"
        assert resolution.docs_strategy == "pubdev_only"
        assert resolution.confidence == "medium"
        assert resolution.official_docs_urls == [resolution.pubdev_docs_url]
        assert "pub.dev/documentation/unknown_package_xyz" in resolution.pubdev_docs_url

    def test_get_seed_urls_returns_list(self):
        """get_seed_urls_for_package should return URL list."""
        urls = get_seed_urls_for_package("riverpod")
        
        assert isinstance(urls, list)
        assert len(urls) > 0
        assert "riverpod.dev" in urls[0]

    def test_get_seed_urls_respects_max_urls(self):
        """get_seed_urls_for_package should respect max_urls limit."""
        urls = get_seed_urls_for_package("riverpod", max_urls=3)
        
        assert len(urls) == 3

    def test_has_official_docs_check(self):
        """has_official_docs should return True for known packages."""
        assert has_official_docs("riverpod") is True
        assert has_official_docs("flutter_bloc") is True
        assert has_official_docs("unknown_xyz") is False


class TestDartdocPubDevIngestion:
    """Test pub.dev Dartdoc ingestion behavior."""

    def test_pubdev_dartdoc_root_discovers_library_pages(self, tmp_path):
        """pub.dev root page should trigger library page discovery."""
        from docmancer.connectors.fetchers.pipeline.extraction import discover_dartdoc_candidate_links
        
        # Mock pub.dev root HTML with library links
        root_html = """
        <html><body class="dartdoc">
        <a href="riverpod/riverpod-library.html">riverpod library</a>
        <a href="riverpod/Provider-class.html">Provider class</a>
        <a href="riverpod/Ref-class.html">Ref class</a>
        </body></html>
        """
        
        links = discover_dartdoc_candidate_links(
            root_html,
            "https://pub.dev/documentation/riverpod/latest/"
        )
        
        # Should discover library and class pages
        assert len(links) >= 2
        assert any("riverpod-library.html" in link for link in links)
        assert any("Provider-class.html" in link for link in links)

    def test_dartdoc_extraction_handles_empty_root(self):
        """Dartdoc root page with no content should not crash extraction."""
        from docmancer.connectors.fetchers.pipeline.extraction import extract_dartdoc_content
        
        # Empty navigation shell
        root_html = """
        <html><body class="dartdoc">
        <nav>Navigation</nav>
        <div id="dartdoc-sidebar-left">Sidebar</div>
        </body></html>
        """
        
        content = extract_dartdoc_content(
            root_html,
            url="https://pub.dev/documentation/flutter_bloc/latest/"
        )
        
        # Should return link list or empty, not crash
        assert isinstance(content, str)
        # May be empty or contain discovered links

    def test_dartdoc_class_page_extracts_content(self):
        """Dartdoc class pages should extract main documentation content."""
        from docmancer.connectors.fetchers.pipeline.extraction import extract_dartdoc_content
        
        class_html = """
        <html><body class="dartdoc">
        <div class="dartdoc-main-content">
        <h1>Provider class</h1>
        <section class="desc">
        <p>A Provider is a widget that exposes a value to its descendants.</p>
        <p>Use Provider to inject dependencies.</p>
        </section>
        </div>
        </body></html>
        """
        
        content = extract_dartdoc_content(
            class_html,
            url="https://pub.dev/documentation/riverpod/latest/riverpod/Provider-class.html"
        )
        
        assert "Provider class" in content
        assert "exposes a value" in content
        assert len(content.split()) >= 10  # Substantial content

    def test_pub_package_does_not_return_python_docs(self):
        """Querying pub package should not return Python/project docs."""
        # This test verifies source isolation
        # Will be implemented when service integration is complete
        pytest.skip("Service integration test - implement after wiring official docs resolver")


class TestOfficialDocsFallback:
    """Test that official docs are preferred over pub.dev API."""

    def test_flutter_bloc_official_docs_preferred(self):
        """flutter_bloc should prioritize bloclibrary.dev over pub.dev."""
        resolution = resolve_dart_official_docs("flutter_bloc")
        
        urls = resolution.official_docs_urls
        # First URLs should be official docs, pub.dev comes later
        assert any("bloclibrary.dev" in url for url in urls[:3])
        assert "pub.dev" in urls[-1]

    def test_riverpod_official_docs_preferred(self):
        """riverpod should prioritize riverpod.dev over pub.dev."""
        resolution = resolve_dart_official_docs("riverpod")
        
        urls = resolution.official_docs_urls
        assert any("riverpod.dev" in url for url in urls[:3])
        assert "pub.dev" in urls[-1]


class TestDartdocDiagnostics:
    """Test Dart-specific diagnostics and reason codes."""

    def test_dartdoc_no_extractable_content_reports_reason(self):
        """Empty Dartdoc pages should report precise reason code."""
        # Will be implemented when diagnostics are added
        pytest.skip("Diagnostics not yet implemented - TODO for PR4")

    def test_official_docs_used_diagnostic(self):
        """When official docs used, diagnostic should indicate source."""
        pytest.skip("Diagnostics not yet implemented - TODO for PR4")


class TestEndToEndDartIngestion:
    """End-to-end tests with mocked network calls."""

    def test_flutter_bloc_preindex_query_end_to_end_mocked(self, tmp_path):
        """flutter_bloc preindex and query should work with mocked official docs."""
        pytest.skip("Full end-to-end test - implement after service wiring")

    def test_riverpod_preindex_query_end_to_end_mocked(self, tmp_path):
        """riverpod preindex and query should work with mocked official docs."""
        pytest.skip("Full end-to-end test - implement after service wiring")
