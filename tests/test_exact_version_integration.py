"""Integration tests for exact-version wired into library docs service."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from docmancer.docs.exact_version import VersionedDocsResolution
from docmancer.docs.models import DocsResult


class TestExactVersionServiceIntegration:
    """Test that exact-version resolver is properly integrated into get_library_docs."""

    def test_get_library_docs_exact_version_unsupported_does_not_query_latest(self, tmp_path):
        """When exact version is unsupported, should not return latest docs."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        # Request exact version for FastAPI (known to be unsupported)
        result = service.get_docs(
            library="fastapi",
            ecosystem="python",
            version="0.115.0",
            topic="How to use Depends?"
        )
        
        # Should return explicit unsupported status
        assert result.status == "exact_version_not_supported"
        assert len(result.results) == 0  # No latest chunks
        assert result.diagnostics.get("exact_version") is not None
        
        exact_version = result.diagnostics["exact_version"]
        assert exact_version["expected"] == "0.115.0"
        assert exact_version["used"] is None
        assert exact_version["match"] is None
        assert exact_version["fallback"] is False
        assert exact_version["status"] == "exact_version_not_supported"
        assert exact_version["reason_code"] == "versioned_docs_unavailable"
        assert exact_version["fallback_available"] is True
        assert "fastapi.tiangolo.com" in exact_version["fallback_docs_url"]

    def test_exact_version_response_fields_present_in_docs_result(self, tmp_path):
        """Exact-version diagnostics should be present in DocsResult."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        result = service.get_docs(
            library="click",
            ecosystem="python",
            version="8.1.7"
        )
        
        # Check exact-version fields exist
        assert hasattr(result, "diagnostics")
        assert isinstance(result.diagnostics, dict)
        exact_version = result.diagnostics.get("exact_version")
        assert exact_version is not None
        
        # Verify structure
        assert "expected" in exact_version
        assert "used" in exact_version
        assert "match" in exact_version
        assert "status" in exact_version
        assert "fallback" in exact_version
        assert "reason_code" in exact_version

    def test_existing_latest_library_docs_queries_unchanged(self, tmp_path):
        """Normal latest queries should not trigger exact-version logic."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        # Query without version (should use latest flow)
        result = service.get_docs(
            library="fastapi",
            ecosystem="python",
            topic="HTTP exception"
        )
        
        # Should not have exact-version error status
        assert result.status != "exact_version_not_supported"
        # May be needs_input or other status, but not exact-version-specific

    def test_exact_version_with_latest_keyword_skips_exact_version_logic(self, tmp_path):
        """Explicitly passing version='latest' should skip exact-version checks."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        result = service.get_docs(
            library="fastapi",
            ecosystem="python",
            version="latest"
        )
        
        # Should not trigger exact-version unsupported
        assert result.status != "exact_version_not_supported"

    def test_pydantic_exact_version_returns_structured_unsupported(self, tmp_path):
        """Pydantic exact version should return structured unsupported."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        result = service.get_docs(
            library="pydantic",
            ecosystem="python",
            version="2.10.0"
        )
        
        assert result.status == "exact_version_not_supported"
        exact_version = result.diagnostics.get("exact_version")
        assert exact_version is not None
        assert exact_version["reason_code"] == "patch_version_docs_unavailable"
        assert "docs.pydantic.dev" in exact_version["fallback_docs_url"]

    def test_non_python_ecosystem_skips_exact_version_resolver(self, tmp_path):
        """Non-Python ecosystems should not trigger Python exact-version resolver."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        result = service.get_docs(
            library="riverpod",
            ecosystem="flutter",
            version="2.6.1"
        )
        
        # Should not use Python exact-version logic
        # May return needs_input or other status, but not Python-specific exact-version
        if result.status == "exact_version_not_supported":
            # If it does have exact-version logic, should not be Python-specific
            exact_version = result.diagnostics.get("exact_version")
            # Should not have Python-specific fallback URLs
            if exact_version and exact_version.get("fallback_docs_url"):
                assert "python" not in exact_version["fallback_docs_url"].lower()
                assert "pypi" not in exact_version["fallback_docs_url"].lower()


    def test_registered_latest_does_not_satisfy_exact_version_request(self, tmp_path):
        """When latest is registered, exact-version request must not silently use latest."""
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        from datetime import datetime, timezone
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        now = datetime.now(timezone.utc).isoformat()
        
        # Register latest FastAPI with docs_url
        service.registry.upsert(
            library="fastapi",
            ecosystem="python",
            version=None,  # latest
            docs_url="https://fastapi.tiangolo.com/",
            source_type="web",
            now=now,
        )
        
        # Request exact version (different from latest)
        result = service.get_docs(
            library="fastapi",
            ecosystem="python",
            version="0.115.0",  # Specific version
            topic="How to use Depends?"
        )
        
        # Must NOT silently return latest docs
        # Should either:
        # 1. Return exact_version_not_supported (preferred)
        # 2. Return empty_index with exact_version diagnostics
        # 3. Return needs_input
        # But MUST NOT return success with latest chunks
        
        if result.status == "success":
            # If status is success, exact_version diagnostics must show no match
            exact_version = result.diagnostics.get("exact_version")
            if exact_version:
                assert exact_version["expected"] == "0.115.0"
                assert exact_version.get("match") is not True  # Not exact match
                # If latest was used, fallback must be True
                if exact_version.get("used") is None or exact_version.get("used") != "0.115.0":
                    assert exact_version.get("fallback") is True
        else:
            # Preferred: explicit unsupported or needs_input
            assert result.status in ("exact_version_not_supported", "needs_input", "empty_index")
            
            # If exact_version diagnostics present, verify correctness
            exact_version = result.diagnostics.get("exact_version")
            if exact_version:
                assert exact_version["expected"] == "0.115.0"
                assert exact_version.get("used") is None or exact_version.get("used") != "0.115.0"
                assert exact_version.get("match") is not True
                assert exact_version.get("fallback") is False


class TestExactVersionSupportedPath:
    """Test the supported exact-version path (when docs are available)."""

    def test_explicit_docs_url_exact_version_flow_does_not_return_unsupported(self, tmp_path):
        """When explicit docs_url is provided with version, should not return unsupported.
        
        Note: This test uses explicit docs_url, so the resolver is not actually called.
        TODO: Add true resolver-supported path test that calls resolver without docs_url.
        """
        from docmancer.core.config import DocmancerConfig
        from docmancer.docs.service import LibraryDocsService
        
        config = DocmancerConfig()
        config.index.db_path = str(tmp_path / "test.db")
        service = LibraryDocsService(config=config)
        
        # When explicit docs_url is provided, exact-version resolver is not called
        result = service.get_docs(
            library="mocklib",
            ecosystem="python",
            version="1.2.3",
            docs_url="https://docs.example.com/1.2.3/"
        )
        
        # Should not return exact_version_not_supported when explicit URL provided
        # (may return needs_input or empty_index if not indexed)
        assert result.status != "exact_version_not_supported"


class TestCanonicalIDSeparation:
    """Test that versioned and latest use separate canonical IDs and indexes."""

    def test_versioned_and_latest_canonical_ids_differ(self):
        """Versioned and latest should have different canonical IDs."""
        from docmancer.docs.resolver import canonical_library_id
        
        latest_id = canonical_library_id("fastapi", "python", None, "web")
        versioned_id = canonical_library_id("fastapi", "python", "0.115.0", "web")
        
        assert latest_id != versioned_id
        assert "@0.115.0" in versioned_id
        assert "@" not in latest_id or ":" in latest_id  # Ecosystem format

    def test_registry_stores_versioned_and_latest_separately(self, tmp_path):
        """Registry should store versioned and latest as separate records."""
        from docmancer.docs.registry import LibraryRegistry
        from datetime import datetime, timezone
        
        registry = LibraryRegistry(tmp_path / "test.db")
        now = datetime.now(timezone.utc).isoformat()
        
        # Register latest
        latest_record = registry.upsert(
            library="testlib",
            ecosystem="python",
            version=None,
            docs_url="https://example.com/latest/",
            source_type="web",
            now=now,
        )
        
        # Register versioned
        versioned_record = registry.upsert(
            library="testlib",
            ecosystem="python",
            version="1.0.0",
            docs_url="https://example.com/1.0.0/",
            source_type="web",
            now=now,
        )
        
        # Should have different library_ids
        assert latest_record.library_id != versioned_record.library_id
        assert latest_record.canonical_id != versioned_record.canonical_id
        
        # Lookup should not cross-contaminate
        latest_lookup = registry.get("testlib", "python", None, "web")
        versioned_lookup = registry.get("testlib", "python", "1.0.0", "web")
        
        assert latest_lookup.library_id == latest_record.library_id
        assert versioned_lookup.library_id == versioned_record.library_id
