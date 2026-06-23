"""Exact-version documentation resolution for Python libraries.

This module provides minimal exact-version support for Python packages
where reliable versioned docs URLs can be constructed or known to be unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class VersionedDocsResolution:
    """Result of attempting to resolve exact-version docs for a library."""
    
    status: Literal[
        "exact_version_supported",
        "exact_version_not_supported", 
        "exact_version_fallback_latest"
    ]
    """Resolution status."""
    
    docs_url: str | None
    """Resolved docs URL (may be versioned or latest fallback)."""
    
    version_used: str | None
    """Actual version used (may differ from requested if fallback)."""
    
    reason_code: str | None
    """Machine-readable reason for the resolution result."""
    
    fallback_docs_url: str | None = None
    """Alternative latest docs URL if versioned docs unavailable."""
    
    exact_version_match: bool = False
    """True only if version_used exactly matches the requested version."""


def resolve_fastapi_versioned_docs(version: str) -> VersionedDocsResolution:
    """Resolve FastAPI exact-version docs.
    
    FastAPI official docs at https://fastapi.tiangolo.com/ do not provide
    per-version documentation snapshots. Only latest/stable docs are available.
    """
    return VersionedDocsResolution(
        status="exact_version_not_supported",
        docs_url=None,
        version_used=None,
        reason_code="versioned_docs_unavailable",
        fallback_docs_url="https://fastapi.tiangolo.com/",
        exact_version_match=False,
    )


def resolve_click_versioned_docs(version: str) -> VersionedDocsResolution:
    """Resolve Click exact-version docs.
    
    Click/Pallets docs at https://click.palletsprojects.com/ provide some
    version-specific documentation, but not granular per-patch-version docs.
    Major version docs are available (e.g., /8.x/).
    """
    # Extract major.minor version
    parts = version.split(".")
    if len(parts) >= 2:
        major_minor = f"{parts[0]}.{parts[1]}"
        # Click docs use major.x pattern
        versioned_url = f"https://click.palletsprojects.com/{parts[0]}.x/"
        return VersionedDocsResolution(
            status="exact_version_not_supported",
            docs_url=None,
            version_used=None,
            reason_code="patch_version_docs_unavailable",
            fallback_docs_url=versioned_url,
            exact_version_match=False,
        )
    
    return VersionedDocsResolution(
        status="exact_version_not_supported",
        docs_url=None,
        version_used=None,
        reason_code="versioned_docs_unavailable",
        fallback_docs_url="https://click.palletsprojects.com/",
        exact_version_match=False,
    )


def resolve_pydantic_versioned_docs(version: str) -> VersionedDocsResolution:
    """Resolve Pydantic exact-version docs.
    
    Pydantic provides major-version docs:
    - v1 docs: https://docs.pydantic.dev/1.10/
    - v2 docs: https://docs.pydantic.dev/latest/ or https://docs.pydantic.dev/2.0/
    
    Exact patch-level versions are not available, but we can map to major version docs.
    """
    parts = version.split(".")
    if not parts:
        return VersionedDocsResolution(
            status="exact_version_not_supported",
            docs_url=None,
            version_used=None,
            reason_code="version_parse_failed",
            fallback_docs_url="https://docs.pydantic.dev/latest/",
            exact_version_match=False,
        )
    
    major = parts[0]
    
    if major == "1":
        # Pydantic v1 docs
        return VersionedDocsResolution(
            status="exact_version_not_supported",
            docs_url=None,
            version_used=None,
            reason_code="patch_version_docs_unavailable",
            fallback_docs_url="https://docs.pydantic.dev/1.10/",
            exact_version_match=False,
        )
    elif major == "2":
        # Pydantic v2 docs
        return VersionedDocsResolution(
            status="exact_version_not_supported",
            docs_url=None,
            version_used=None,
            reason_code="patch_version_docs_unavailable",
            fallback_docs_url="https://docs.pydantic.dev/latest/",
            exact_version_match=False,
        )
    
    return VersionedDocsResolution(
        status="exact_version_not_supported",
        docs_url=None,
        version_used=None,
        reason_code="versioned_docs_unavailable",
        fallback_docs_url="https://docs.pydantic.dev/latest/",
        exact_version_match=False,
    )


# Registry of Python package-specific resolvers
PYTHON_VERSIONED_DOCS_RESOLVERS = {
    "fastapi": resolve_fastapi_versioned_docs,
    "click": resolve_click_versioned_docs,
    "pydantic": resolve_pydantic_versioned_docs,
}


def resolve_python_versioned_docs(library: str, version: str) -> VersionedDocsResolution | None:
    """Resolve exact-version docs for a Python library.
    
    Args:
        library: Normalized library name
        version: Requested version string
        
    Returns:
        VersionedDocsResolution if library is known, None otherwise
    """
    resolver = PYTHON_VERSIONED_DOCS_RESOLVERS.get(library)
    if resolver:
        return resolver(version)
    return None
