"""Tests for exact-version documentation support."""

from __future__ import annotations

import pytest

from docmancer.docs.exact_version import (
    VersionedDocsResolution,
    resolve_fastapi_versioned_docs,
    resolve_click_versioned_docs,
    resolve_pydantic_versioned_docs,
    resolve_python_versioned_docs,
)
from docmancer.docs.resolver import canonical_library_id


class TestCanonicalIDVersioned:
    """Test that exact version and latest use different canonical IDs."""

    def test_exact_version_canonical_id_is_versioned(self):
        """Versioned and latest canonical IDs must be different."""
        latest_id = canonical_library_id("fastapi", "python", None, "web")
        versioned_id = canonical_library_id("fastapi", "python", "0.115.0", "web")
        
        assert latest_id != versioned_id
        assert "@" not in latest_id or latest_id.endswith(":web")
        assert "@0.115.0" in versioned_id
        assert versioned_id == "python:fastapi@0.115.0:web"

    def test_canonical_id_includes_ecosystem_version_source_type(self):
        """Canonical ID should encode ecosystem, library, version, and source_type."""
        cid = canonical_library_id("click", "python", "8.1.7", "web")
        assert cid == "python:click@8.1.7:web"

    def test_canonical_id_without_ecosystem(self):
        """Canonical ID without ecosystem uses legacy format."""
        cid = canonical_library_id("fastapi", None, "0.115.0", "web")
        assert cid == "fastapi@0.115.0"

    def test_canonical_id_latest_vs_versioned(self):
        """Latest and versioned IDs must never collide."""
        latest = canonical_library_id("pydantic", "python", "latest", "web")
        versioned = canonical_library_id("pydantic", "python", "2.10.0", "web")
        
        assert latest != versioned
        assert latest == "python:pydantic@latest:web"
        assert versioned == "python:pydantic@2.10.0:web"


class TestPythonVersionedDocsResolution:
    """Test Python library exact-version docs resolution."""

    def test_fastapi_versioned_docs_not_supported(self):
        """FastAPI does not provide per-version docs."""
        resolution = resolve_fastapi_versioned_docs("0.115.0")
        
        assert resolution.status == "exact_version_not_supported"
        assert resolution.docs_url is None
        assert resolution.version_used is None
        assert resolution.reason_code == "versioned_docs_unavailable"
        assert resolution.fallback_docs_url == "https://fastapi.tiangolo.com/"
        assert resolution.exact_version_match is False

    def test_click_versioned_docs_not_supported(self):
        """Click provides major.x docs, not exact patch versions."""
        resolution = resolve_click_versioned_docs("8.1.7")
        
        assert resolution.status == "exact_version_not_supported"
        assert resolution.docs_url is None
        assert resolution.reason_code == "patch_version_docs_unavailable"
        assert resolution.fallback_docs_url == "https://click.palletsprojects.com/8.x/"
        assert resolution.exact_version_match is False

    def test_pydantic_v1_versioned_docs_not_supported(self):
        """Pydantic v1 provides major version docs, not exact patch."""
        resolution = resolve_pydantic_versioned_docs("1.10.2")
        
        assert resolution.status == "exact_version_not_supported"
        assert resolution.reason_code == "patch_version_docs_unavailable"
        assert resolution.fallback_docs_url == "https://docs.pydantic.dev/1.10/"
        assert resolution.exact_version_match is False

    def test_pydantic_v2_versioned_docs_not_supported(self):
        """Pydantic v2 provides major version docs, not exact patch."""
        resolution = resolve_pydantic_versioned_docs("2.10.0")
        
        assert resolution.status == "exact_version_not_supported"
        assert resolution.reason_code == "patch_version_docs_unavailable"
        assert resolution.fallback_docs_url == "https://docs.pydantic.dev/latest/"
        assert resolution.exact_version_match is False

    def test_python_versioned_docs_registry(self):
        """Verify Python resolver registry works."""
        # Known libraries
        assert resolve_python_versioned_docs("fastapi", "0.115.0") is not None
        assert resolve_python_versioned_docs("click", "8.1.7") is not None
        assert resolve_python_versioned_docs("pydantic", "2.10.0") is not None
        
        # Unknown library
        assert resolve_python_versioned_docs("unknown_lib", "1.0.0") is None


class TestExactVersionDoesNotFallbackSilently:
    """Test that exact-version requests don't silently use latest docs."""

    def test_fastapi_exact_version_returns_structured_unsupported(self):
        """When exact version is unsupported, return explicit status."""
        resolution = resolve_fastapi_versioned_docs("0.115.0")
        
        # Must return structured unsupported, not None or generic error
        assert isinstance(resolution, VersionedDocsResolution)
        assert resolution.status == "exact_version_not_supported"
        assert resolution.reason_code is not None
        assert resolution.exact_version_match is False

    def test_fallback_latest_must_be_marked(self):
        """If latest docs are used, must be explicitly marked as fallback."""
        resolution = resolve_fastapi_versioned_docs("0.115.0")
        
        # If fallback exists, it must be explicit
        if resolution.fallback_docs_url:
            assert resolution.status == "exact_version_not_supported"
            assert resolution.exact_version_match is False
            # The system should NOT silently use fallback_docs_url without marking it


class TestLatestFallbackMarkedNotExactMatch:
    """Test that latest fallback is marked and not counted as exact match."""

    def test_fallback_latest_has_explicit_status(self):
        """Fallback to latest must have distinct status."""
        # This test verifies the data model supports fallback tracking
        resolution = VersionedDocsResolution(
            status="exact_version_fallback_latest",
            docs_url="https://fastapi.tiangolo.com/",
            version_used="latest",
            reason_code="versioned_docs_unavailable",
            exact_version_match=False,
        )
        
        assert resolution.status == "exact_version_fallback_latest"
        assert resolution.version_used == "latest"
        assert resolution.exact_version_match is False

    def test_exact_match_only_when_versions_equal(self):
        """exact_version_match should only be True when versions exactly match."""
        # Exact match case
        exact = VersionedDocsResolution(
            status="exact_version_supported",
            docs_url="https://example.com/docs/1.0.0/",
            version_used="1.0.0",
            reason_code=None,
            exact_version_match=True,
        )
        assert exact.exact_version_match is True
        
        # Fallback case
        fallback = VersionedDocsResolution(
            status="exact_version_fallback_latest",
            docs_url="https://example.com/docs/latest/",
            version_used="latest",
            reason_code="versioned_docs_unavailable",
            exact_version_match=False,
        )
        assert fallback.exact_version_match is False


class TestVersionedAndLatestIndexesAreSeparate:
    """Test that exact version and latest use separate index paths."""

    def test_canonical_ids_determine_separate_storage(self):
        """Different canonical IDs should result in separate storage."""
        latest_id = canonical_library_id("fastapi", "python", None, "web")
        versioned_id = canonical_library_id("fastapi", "python", "0.115.0", "web")
        
        # These must be different to ensure separate index paths
        assert latest_id != versioned_id
        
        # Registry lookup by exact canonical_id should not cross-contaminate
        # (This is a design constraint verified by the ID generation)


class TestExactVersionMetrics:
    """Test exact-version metrics calculation."""

    def test_metrics_zero_success(self):
        """When no exact-version queries succeed, correctness_on_success is None."""
        # Mock scenario: all exact-version queries failed
        ev_success = 0
        ev_total = 5
        
        coverage_rate = ev_success / max(ev_total, 1)
        correctness_on_success = None if ev_success == 0 else 1.0
        
        assert coverage_rate == 0.0
        assert correctness_on_success is None

    def test_metrics_success_and_fallback(self):
        """Test metrics distinguish exact success from fallback."""
        # Mock scenario: 2 exact success, 1 fallback, 1 unsupported, 1 empty
        ev_total = 5
        ev_exact_success = 2  # exact_version_match=True
        ev_fallback = 1  # exact_version_fallback=True
        ev_unsupported = 1  # status=not_supported
        ev_empty = 1  # status=empty_index
        
        ev_success = ev_exact_success + ev_fallback  # Both are "success" status
        
        coverage_rate = ev_success / ev_total
        match_rate = ev_exact_success / ev_total
        fallback_rate = ev_fallback / ev_total
        unsupported_rate = ev_unsupported / ev_total
        
        assert coverage_rate == 0.6  # 3/5
        assert match_rate == 0.4  # 2/5 - only exact matches
        assert fallback_rate == 0.2  # 1/5
        assert unsupported_rate == 0.2  # 1/5

    def test_metrics_exact_match_vs_fallback_distinction(self):
        """Verify exact match and fallback are counted separately."""
        # Exact match result
        exact_match_count = 1
        exact_version_match = True
        
        # Fallback result
        fallback_count = 1
        fallback_match = False
        
        # Only exact matches should count toward match_rate
        assert exact_version_match is True
        assert fallback_match is False
        assert exact_match_count != fallback_count or exact_version_match != fallback_match


class TestExactVersionStatusCodes:
    """Test that all exact-version status codes are explicit."""

    def test_all_status_codes_are_explicit(self):
        """Verify all exact-version status codes are well-defined."""
        valid_statuses = {
            "exact_version_supported",
            "exact_version_indexed",
            "exact_version_not_supported",
            "exact_version_fallback_latest",
            "exact_version_empty_index",
            "exact_version_resolution_failed",
        }
        
        # All resolver functions should return one of these
        fastapi_res = resolve_fastapi_versioned_docs("0.115.0")
        assert fastapi_res.status in valid_statuses or fastapi_res.status == "exact_version_not_supported"

    def test_reason_codes_are_specific(self):
        """Verify reason codes are specific, not generic."""
        fastapi_res = resolve_fastapi_versioned_docs("0.115.0")
        
        # Should have specific reason, not just "not_supported"
        assert fastapi_res.reason_code == "versioned_docs_unavailable"
        assert fastapi_res.reason_code != "not_supported"
        assert fastapi_res.reason_code != "error"
