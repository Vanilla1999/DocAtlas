"""URL normalization, filtering, and content deduplication.

Provides utilities for:
- Normalizing URLs (trailing slashes, fragments, query params)
- Filtering URLs against blocklist patterns
- Checking if a URL belongs to a docs site's scope
- Deduplicating content via SHA-256 hashing
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlparse, urljoin

from w3lib.url import canonicalize_url

# URL path patterns to exclude (compiled for performance).
_BLOCKLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"/blog(/|$)",
        r"/changelog(/|$)",
        r"/release-notes(/|$)",
        r"/status(/|$)",
        r"/pricing(/|$)",
        r"/login(/|$)",
        r"/signup(/|$)",
        r"/register(/|$)",
        r"/sign-in(/|$)",
        r"/sign-up(/|$)",
        r"/account(/|$)",
        r"/settings(/|$)",
        r"/search(\?|$)",
        r"[?&]print",
        r"/_print(/|$)",
        r"/print\.html",
        r"\.(pdf|zip|tar|gz|png|jpg|jpeg|gif|svg|mp4|mp3|woff|woff2|ttf|eot|ico)$",
    ]
]

# Query parameters to strip (tracking/noise).
_STRIP_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                 "ref", "from", "source", "fbclid", "gclid"}


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison.

    - Lowercases scheme and host
    - Removes fragments
    - Strips tracking query parameters
    - Removes trailing slash (except for root path)
    - Applies w3lib canonicalization

    Args:
        url: The URL to normalize.

    Returns:
        Canonicalized URL string.
    """
    # Strip fragment
    url = url.split("#")[0]

    # Use w3lib for RFC-correct canonicalization
    url = canonicalize_url(url, keep_fragments=False)

    # Strip tracking params
    parsed = urlparse(url)
    if parsed.query:
        params = parsed.query.split("&")
        filtered = [p for p in params if p.split("=")[0] not in _STRIP_PARAMS]
        query = "&".join(filtered)
        url = parsed._replace(query=query).geturl()

    # Remove trailing slash (but keep root "/")
    if url.endswith("/") and urlparse(url).path != "/":
        url = url.rstrip("/")

    return url


_LOCALE_PREFIXES = {
    "ar",
    "bn",
    "de",
    "es",
    "fr",
    "id",
    "it",
    "ja",
    "ko",
    "nl",
    "pl",
    "pt",
    "pt-br",
    "ru",
    "tr",
    "uk",
    "vi",
    "zh-hans",
    "zh-hant",
}


def _is_locale_segment(segment: str) -> bool:
    return segment.lower().replace("_", "-") in _LOCALE_PREFIXES


def _starts_with_parts(parts: list[str], prefix: list[str]) -> bool:
    return len(parts) >= len(prefix) and parts[: len(prefix)] == prefix


def infer_docset_root(url: str) -> str | None:
    """Legacy hook: a URL alone does not establish docset identity or scope.

    Callers retain their exact source URL when explicit docset metadata is absent.
    Neither host labels nor path words authorize a broader corpus root.
    """
    return None


def _infer_scope_path(base_path: str) -> str:
    """Retain the supplied path; never guess a parent section boundary."""
    return base_path.rstrip("/")


def _safe_scope_path(path: str) -> bool:
    """Reject transport spellings that can escape a literal path boundary."""
    decoded = path
    for _ in range(3):
        value = unquote(decoded)
        if value == decoded:
            break
        decoded = value
    else:
        if unquote(decoded) != decoded:
            return False
    return "\\" not in decoded and not any(part in {".", ".."} for part in decoded.split("/"))


def is_docs_url(url: str, base_url: str, locale_skip_counter: list[int] | None = None) -> bool:
    """Check if a URL is within the documentation scope.

    A URL is in scope if:
    - It shares the same domain as the base URL
    - Its path is exactly the supplied base path or a descendant
    - It does not match any blocklist pattern

    No parent root or sibling-page scope is inferred from path vocabulary.

    Args:
        url: The candidate URL to check.
        base_url: The documentation root URL.
        locale_skip_counter: Optional mutable counter (list[1]) incremented
            when a URL is rejected because it uses a locale prefix not
            present in the seed URL.

    Returns:
        True if the URL is in scope.
    """
    try:
        parsed = urlparse(url)
        base_parsed = urlparse(base_url)
    except Exception:
        return False

    # Must be HTTP(S)
    if parsed.scheme not in ("http", "https") or base_parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc or parsed.username is not None or base_parsed.username is not None:
        return False

    # Must share domain
    if parsed.netloc.lower() != base_parsed.netloc.lower():
        return False
    if not _safe_scope_path(parsed.path) or not _safe_scope_path(base_parsed.path):
        return False

    # Exact segment boundary, not a lexical prefix such as /docs-other.
    scope_path = _infer_scope_path(base_parsed.path.rstrip("/"))
    url_path = parsed.path.rstrip("/")
    if scope_path and url_path != scope_path and not url_path.startswith(scope_path + "/"):
        return False

    # Default web/Docusaurus ingest should not pull translated mirrors when
    # the seed is the canonical English root. Users can still opt into a
    # locale by seeding that locale path directly, e.g. /ru/docs.
    url_parts = [part.lower() for part in parsed.path.split("/") if part]
    base_parts = [part.lower() for part in base_parsed.path.split("/") if part]
    base_has_locale = any(_is_locale_segment(part) for part in base_parts)
    scope_parts = [part.lower() for part in scope_path.split("/") if part]
    relative_parts = url_parts[len(scope_parts) :] if scope_parts and _starts_with_parts(url_parts, scope_parts) else url_parts
    if relative_parts and _is_locale_segment(relative_parts[0]) and not base_has_locale:
        if locale_skip_counter is not None:
            locale_skip_counter[0] += 1
        return False

    # Must not match blocklist
    full_url = parsed.path + ("?" + parsed.query if parsed.query else "")
    for pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(full_url):
            return False

    return True


def resolve_url(url: str, base_url: str) -> str:
    """Resolve a potentially relative URL against a base URL.

    Args:
        url: URL to resolve (may be relative).
        base_url: Base URL for resolution.

    Returns:
        Absolute URL string.
    """
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


class ContentDeduplicator:
    """Tracks content hashes to detect and skip duplicate pages.

    Uses SHA-256 of normalized content for comparison.
    Also tracks seen URLs (after normalization) to skip URL-level duplicates.
    """

    def __init__(self) -> None:
        self._content_hashes: set[str] = set()
        self._url_hashes: set[str] = set()

    @staticmethod
    def content_hash(content: str) -> str:
        """Compute SHA-256 hex digest of content."""
        normalized = " ".join(content.split()).strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_content_duplicate(self, content: str) -> bool:
        """Check if content has already been seen. Adds it if not.

        Returns:
            True if the content is a duplicate.
        """
        h = self.content_hash(content)
        if h in self._content_hashes:
            return True
        self._content_hashes.add(h)
        return False

    def is_url_duplicate(self, url: str) -> bool:
        """Check if a normalized URL has already been seen. Adds it if not.

        Returns:
            True if the URL is a duplicate.
        """
        normalized = normalize_url(url)
        if normalized in self._url_hashes:
            return True
        self._url_hashes.add(normalized)
        return False

    def reset(self) -> None:
        """Clear all tracked hashes."""
        self._content_hashes.clear()
        self._url_hashes.clear()
