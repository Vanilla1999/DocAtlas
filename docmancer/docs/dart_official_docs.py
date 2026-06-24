"""Official documentation resolvers for Dart/Flutter packages.

Many Dart/Flutter packages have official guide-style documentation sites
that provide better content for coding agents than bare pub.dev API reference.

This module provides a registry of known packages with official docs,
and resolvers that return seed URLs for comprehensive ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass


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


# Package-specific official docs seed URLs.
# Ordered by priority: guides first, then API reference.
DART_PACKAGE_OFFICIAL_DOCS: dict[str, list[str]] = {
    "riverpod": [
        "https://riverpod.dev/",
        "https://riverpod.dev/docs/introduction/getting_started",
        "https://riverpod.dev/docs/concepts/providers",
        "https://riverpod.dev/docs/concepts/reading",
        "https://riverpod.dev/docs/concepts/modifiers/auto_dispose",
        "https://riverpod.dev/docs/concepts/modifiers/family",
        "https://riverpod.dev/docs/essentials/first_request",
        "https://pub.dev/documentation/riverpod/latest/",
    ],
    "flutter_riverpod": [
        "https://riverpod.dev/",
        "https://riverpod.dev/docs/introduction/getting_started",
        "https://riverpod.dev/docs/concepts/providers",
        "https://riverpod.dev/docs/concepts/reading",
        "https://pub.dev/documentation/flutter_riverpod/latest/",
    ],
    "hooks_riverpod": [
        "https://riverpod.dev/",
        "https://riverpod.dev/docs/introduction/getting_started",
        "https://pub.dev/documentation/hooks_riverpod/latest/",
    ],
    "flutter_bloc": [
        "https://bloclibrary.dev/",
        "https://bloclibrary.dev/getting-started/",
        "https://bloclibrary.dev/flutter-bloc-concepts/",
        "https://bloclibrary.dev/architecture/",
        "https://bloclibrary.dev/tutorials/flutter-counter/",
        "https://pub.dev/documentation/flutter_bloc/latest/",
    ],
    "bloc": [
        "https://bloclibrary.dev/",
        "https://bloclibrary.dev/bloc-concepts/",
        "https://pub.dev/documentation/bloc/latest/",
    ],
    "hydrated_bloc": [
        "https://bloclibrary.dev/",
        "https://pub.dev/documentation/hydrated_bloc/latest/",
    ],
    "go_router": [
        "https://pub.dev/documentation/go_router/latest/",
        "https://pub.dev/packages/go_router",
        "https://docs.flutter.dev/ui/navigation",
    ],
    "provider": [
        "https://pub.dev/documentation/provider/latest/",
        "https://pub.dev/packages/provider",
    ],
    "dio": [
        "https://pub.dev/documentation/dio/latest/",
        "https://pub.dev/packages/dio",
    ],
    "freezed": [
        "https://pub.dev/documentation/freezed/latest/",
        "https://pub.dev/packages/freezed",
    ],
    "json_serializable": [
        "https://pub.dev/documentation/json_serializable/latest/",
        "https://pub.dev/packages/json_serializable",
    ],
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
    
    official_urls = DART_PACKAGE_OFFICIAL_DOCS.get(normalized, [])
    
    if official_urls:
        # Official docs available
        urls = list(official_urls)
        if include_pubdev and pubdev_url not in urls:
            urls.append(pubdev_url)
        
        return DartDocsResolution(
            package=normalized,
            official_docs_available=True,
            official_docs_urls=urls,
            pubdev_docs_url=pubdev_url,
            docs_strategy="official_docs" if official_urls else "mixed",
            confidence="high",
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
    return normalized in DART_PACKAGE_OFFICIAL_DOCS
