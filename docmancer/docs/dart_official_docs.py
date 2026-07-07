"""Official documentation resolvers for Dart/Flutter packages.

Many Dart/Flutter packages have official guide-style documentation sites
that provide better content for coding agents than bare pub.dev API reference.

This module provides a registry of known packages with official docs,
and resolvers that return seed URLs for comprehensive ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class DartDocsResolution:
    """Result of resolving official docs for a Dart package."""
    
    package: str
    """Package name (normalized)."""
    
    official_docs_available: bool
    """Whether official docs are available for this package."""
    
    official_docs_urls: list[str]
    """List of official docs URLs (guides, concepts, API reference).
    
    Ordered by priority:
    1. Official guide/concept pages
    2. Official API reference
    3. pub.dev API reference (fallback)
    """
    
    pubdev_docs_url: str
    """pub.dev API reference URL (always available as fallback)."""
    
    docs_strategy: str
    """Strategy used: 'official_docs' | 'pubdev_only' | 'mixed'."""
    
    confidence: str
    """'high' if official docs known, 'medium' if pub.dev only."""


@dataclass(frozen=True)
class DartDocsSources:
    """Structured Dart documentation source set."""

    official_guides: tuple[str, ...]
    pubdev_api: str | None
    package_page: str | None = None


# Package-specific official docs seed URLs.
# Ordered by priority: guides first, then API reference.
DART_PACKAGE_OFFICIAL_DOCS: dict[str, DartDocsSources] = {
    "riverpod": DartDocsSources(
        official_guides=(
            "https://riverpod.dev/",
            "https://riverpod.dev/docs/introduction/getting_started",
            "https://riverpod.dev/docs/concepts2/providers",
            "https://riverpod.dev/docs/concepts2/auto_dispose",
            "https://riverpod.dev/docs/concepts2/family",
            "https://riverpod.dev/docs/essentials/first_request",
        ),
        pubdev_api="https://pub.dev/documentation/riverpod/{version}/",
    ),
    "flutter_riverpod": DartDocsSources(
        official_guides=(
            "https://riverpod.dev/",
            "https://riverpod.dev/docs/introduction/getting_started",
            "https://riverpod.dev/docs/concepts2/providers",
            "https://riverpod.dev/docs/concepts2/auto_dispose",
        ),
        pubdev_api="https://pub.dev/documentation/flutter_riverpod/{version}/",
    ),
    "hooks_riverpod": DartDocsSources(
        official_guides=(
            "https://riverpod.dev/",
            "https://riverpod.dev/docs/introduction/getting_started",
        ),
        pubdev_api="https://pub.dev/documentation/hooks_riverpod/{version}/",
    ),
    "flutter_bloc": DartDocsSources(
        official_guides=(
            "https://bloclibrary.dev/",
            "https://bloclibrary.dev/getting-started/",
            "https://bloclibrary.dev/flutter-bloc-concepts/",
            "https://bloclibrary.dev/architecture/",
            "https://bloclibrary.dev/tutorials/flutter-counter/",
        ),
        pubdev_api="https://pub.dev/documentation/flutter_bloc/{version}/",
    ),
    "bloc": DartDocsSources(
        official_guides=(
            "https://bloclibrary.dev/",
            "https://bloclibrary.dev/bloc-concepts/",
        ),
        pubdev_api="https://pub.dev/documentation/bloc/{version}/",
    ),
    "hydrated_bloc": DartDocsSources(
        official_guides=("https://bloclibrary.dev/",),
        pubdev_api="https://pub.dev/documentation/hydrated_bloc/{version}/",
    ),
    "go_router": DartDocsSources(
        official_guides=("https://docs.flutter.dev/ui/navigation",),
        pubdev_api="https://pub.dev/documentation/go_router/{version}/",
        package_page="https://pub.dev/packages/go_router",
    ),
    "provider": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/provider/{version}/",
        package_page="https://pub.dev/packages/provider",
    ),
    "dio": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/dio/{version}/",
        package_page="https://pub.dev/packages/dio",
    ),
    "freezed": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/freezed/{version}/",
        package_page="https://pub.dev/packages/freezed",
    ),
    "json_serializable": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/json_serializable/{version}/",
        package_page="https://pub.dev/packages/json_serializable",
    ),
    "firebase_auth": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/firebase_auth/{version}/",
        package_page="https://pub.dev/packages/firebase_auth",
    ),
    "firebase_core": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/firebase_core/{version}/",
        package_page="https://pub.dev/packages/firebase_core",
    ),
    "firebase_firestore": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/cloud_firestore/{version}/",
        package_page="https://pub.dev/packages/cloud_firestore",
    ),
    "cloud_firestore": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/cloud_firestore/{version}/",
        package_page="https://pub.dev/packages/cloud_firestore",
    ),
    "shared_preferences": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/shared_preferences/{version}/",
        package_page="https://pub.dev/packages/shared_preferences",
    ),
    "sqflite": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/sqflite/{version}/",
        package_page="https://pub.dev/packages/sqflite",
    ),
    "flutter_secure_storage": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/flutter_secure_storage/{version}/",
        package_page="https://pub.dev/packages/flutter_secure_storage",
    ),
    "get_it": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/get_it/{version}/",
        package_page="https://pub.dev/packages/get_it",
    ),
    "equatable": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/equatable/{version}/",
        package_page="https://pub.dev/packages/equatable",
    ),
    "dartz": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/dartz/{version}/",
        package_page="https://pub.dev/packages/dartz",
    ),
    "retrofit": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/retrofit/{version}/",
        package_page="https://pub.dev/packages/retrofit",
    ),
    "json_annotation": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/json_annotation/{version}/",
        package_page="https://pub.dev/packages/json_annotation",
    ),
    "logger": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/logger/{version}/",
        package_page="https://pub.dev/packages/logger",
    ),
    "flutter_local_notifications": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/flutter_local_notifications/{version}/",
        package_page="https://pub.dev/packages/flutter_local_notifications",
    ),
    "url_launcher": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/url_launcher/{version}/",
        package_page="https://pub.dev/packages/url_launcher",
    ),
    "path_provider": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/path_provider/{version}/",
        package_page="https://pub.dev/packages/path_provider",
    ),
    "http": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/http/{version}/",
        package_page="https://pub.dev/packages/http",
    ),
    "intl": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/intl/{version}/",
        package_page="https://pub.dev/packages/intl",
    ),
    "cached_network_image": DartDocsSources(
        official_guides=(),
        pubdev_api="https://pub.dev/documentation/cached_network_image/{version}/",
        package_page="https://pub.dev/packages/cached_network_image",
    ),
}


def normalize_package_name(package: str) -> str:
    """Normalize package name for lookup.
    
    Args:
        package: Package name (may contain underscores, hyphens, mixed case).
    
    Returns:
        Normalized package name (lowercase, underscores preserved).
    """
    return package.lower().strip().replace("-", "_")


def resolve_dart_official_docs(
    package: str,
    version: str | None = None,
    include_pubdev: bool = True,
) -> DartDocsResolution:
    """Resolve official documentation URLs for a Dart/Flutter package.
    
    Args:
        package: Package name (e.g., "riverpod", "flutter_bloc").
        version: Package version (e.g., "latest", "2.4.0"). Currently unused,
                 but reserved for future version-specific docs resolution.
        include_pubdev: Whether to include pub.dev API reference as fallback.
    
    Returns:
        DartDocsResolution with official docs URLs or pub.dev fallback.
    
    Examples:
        >>> resolution = resolve_dart_official_docs("riverpod")
        >>> resolution.official_docs_available
        True
        >>> resolution.official_docs_urls[0]
        'https://riverpod.dev/'
        
        >>> resolution = resolve_dart_official_docs("unknown_package")
        >>> resolution.official_docs_available
        False
        >>> resolution.docs_strategy
        'pubdev_only'
    """
    normalized = normalize_package_name(package)
    version_normalized = (version or "latest").lower().strip()
    if version_normalized in ("", "*"):
        version_normalized = "latest"
    
    pubdev_url = f"https://pub.dev/documentation/{normalized}/{version_normalized}/"
    
    sources = DART_PACKAGE_OFFICIAL_DOCS.get(normalized)
    
    if sources:
        urls = list(sources.official_guides)
        pubdev_url = sources.pubdev_api.format(version=version_normalized) if sources.pubdev_api else pubdev_url
        if include_pubdev and sources.pubdev_api:
            urls.append(pubdev_url)
        if sources.package_page:
            urls.append(sources.package_page)
        has_guides = bool(sources.official_guides)
        has_pubdev = bool(sources.pubdev_api and include_pubdev)
        if has_guides and has_pubdev:
            strategy = "mixed"
        elif has_guides:
            strategy = "official_docs"
        elif has_pubdev:
            strategy = "pubdev_only"
        else:
            strategy = "unresolved"
        
        return DartDocsResolution(
            package=normalized,
            official_docs_available=has_guides,
            official_docs_urls=urls,
            pubdev_docs_url=pubdev_url,
            docs_strategy=strategy,
            confidence="high" if has_guides else "medium",
        )
    
    # No official docs known, fall back to pub.dev
    return DartDocsResolution(
        package=normalized,
        official_docs_available=False,
        official_docs_urls=[pubdev_url] if include_pubdev else [],
        pubdev_docs_url=pubdev_url,
        docs_strategy="pubdev_only",
        confidence="medium",
    )


def get_seed_urls_for_package(
    package: str,
    version: str | None = None,
    max_urls: int | None = None,
) -> list[str]:
    """Get seed URLs for a Dart/Flutter package.
    
    Convenience wrapper around resolve_dart_official_docs that returns
    just the URL list.
    
    Args:
        package: Package name.
        version: Package version (default: "latest").
        max_urls: Maximum number of URLs to return (default: unlimited).
    
    Returns:
        List of seed URLs (official docs + pub.dev fallback).
    """
    resolution = resolve_dart_official_docs(package, version=version)
    urls = resolution.official_docs_urls
    if max_urls is not None and max_urls > 0:
        urls = urls[:max_urls]
    return urls


def has_official_docs(package: str) -> bool:
    """Check if a package has known official documentation.
    
    Args:
        package: Package name.
    
    Returns:
        True if official docs are registered, False otherwise.
    """
    normalized = normalize_package_name(package)
    sources = DART_PACKAGE_OFFICIAL_DOCS.get(normalized)
    return bool(sources and sources.official_guides)


def allowed_domains_for_urls(urls: list[str]) -> list[str]:
    """Return unique hostnames for a docs target URL set."""
    domains: list[str] = []
    for url in urls:
        hostname = urlparse(url).hostname
        if hostname and hostname not in domains:
            domains.append(hostname)
    return domains


def canonical_dart_ecosystem(ecosystem: str | None) -> str | None:
    """Collapse pub/flutter aliases to the single Dart registry identity."""
    if ecosystem is None:
        return None
    normalized = ecosystem.lower().strip()
    if normalized in {"pub", "flutter", "dart"}:
        return "dart"
    return normalized


def build_dart_diagnostics(
    *,
    package: str,
    version: str | None,
    root_url: str | None,
    pages_discovered: int | None = None,
    pages_extracted: int | None = None,
    chunks_created: int | None = None,
    used_official_docs: bool | None = None,
    reason_code: str | None = None,
    nav_shell_count: int | None = None,
) -> dict[str, object]:
    """Build Dart diagnostics for both success and empty-index paths.

    The ``nav_shell_count`` is the number of dartdoc-pipeline pages whose
    extracted content consisted only of navigation/index links (no real
    documentation body). When every discovered page is nav-shell-only, the
    reason code is set to ``dartdoc_nav_shell_only``, indicating the root
    page is an API index rather than guide-style docs.
    """
    resolution = resolve_dart_official_docs(package, version=version)
    if reason_code is None:
        if pages_discovered == 0:
            reason_code = "dartdoc_root_only"
        elif pages_extracted == 0:
            reason_code = "dartdoc_no_extractable_content"
        elif nav_shell_count is not None and nav_shell_count > 0 and nav_shell_count == (pages_discovered or 0):
            reason_code = "dartdoc_nav_shell_only"
        elif chunks_created == 0:
            reason_code = "dartdoc_ingest_produced_no_chunks"
        else:
            reason_code = "healthy"
    return {
        "attempted": True,
        "package": normalize_package_name(package),
        "version": version or "latest",
        "root_url": root_url,
        "official_available": resolution.official_docs_available,
        "used_official_docs": bool(used_official_docs),
        "docs_strategy": resolution.docs_strategy,
        "pages_discovered": pages_discovered,
        "pages_extracted": pages_extracted,
        "chunks_created": chunks_created,
        "nav_shell_count": nav_shell_count,
        "reason_code": reason_code,
    }
