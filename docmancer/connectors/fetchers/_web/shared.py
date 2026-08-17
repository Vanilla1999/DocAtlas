"""Generic web fetcher for any documentation site.

Implements the full ingestion pipeline:
1. Fetch homepage and detect platform
2. Run discovery chain to find all doc page URLs
3. Filter, normalize, and deduplicate URLs
4. Fetch each page with rate limiting and robots.txt compliance
5. Extract content with trafilatura + markdownify
6. Deduplicate content and build Document objects
"""

from __future__ import annotations

import logging
import time
import threading
import hashlib
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from docmancer.connectors.fetchers.pipeline.detection import Platform, detect_platform
from docmancer.connectors.fetchers.pipeline.discovery import (
    DiscoveredUrl,
    DiscoveryStrategy,
    discover_urls,
)
from docmancer.connectors.fetchers.pipeline.extraction import (
    discover_dartdoc_candidate_links,
    extract_content,
    extract_metadata,
    extract_section_path,
    is_dartdoc_html,
)
from docmancer.connectors.fetchers.pipeline.filtering import (
    ContentDeduplicator,
    infer_docset_root,
    is_docs_url,
    normalize_url,
    resolve_url,
)
from docmancer.connectors.fetchers.pipeline.rate_limit import RateLimiter
from docmancer.connectors.fetchers.pipeline.redirect import RedirectTracker
from docmancer.connectors.fetchers.pipeline.robots import RobotsChecker
from docmancer.core.html_utils import looks_like_html
from docmancer.core.models import Document
from docmancer.docs.dartdoc import DARTDOC_ENTITY_SUFFIXES
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError, redact_url
from docmancer.docs.fetch_transport import DocsHttpClient
from docmancer.docs.github_source_manifest import (
    canonical_github_blob_scope_url,
    normalize_resolved_github_manifest,
)

logger = logging.getLogger(__name__)

# Default HTTP client settings.
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_USER_AGENT = "docmancer/1.0 (+https://github.com/docmancer/docmancer)"
_DIRECT_TEXT_SUFFIXES = {".md", ".txt"}
_DIRECT_DARTDOC_SUFFIXES = DARTDOC_ENTITY_SUFFIXES


def _github_blob_raw_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "blob":
        return None
    owner, repo, _, ref = parts[:4]
    file_path = "/".join(parts[4:])
    if not owner or not repo or not ref or not file_path or any(part in {".", ".."} for part in parts):
        return None
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_path}"


def _source_docset_root(final_url: str, base_url: str) -> str:
    normalized_base = normalize_url(base_url)
    normalized_final = normalize_url(final_url)
    base_host = urlparse(base_url).hostname
    final = urlparse(final_url)
    if base_host == final.hostname:
        return normalized_base
    if _github_blob_raw_url(normalized_base) == normalized_final:
        return normalized_base
    parts = [part for part in final.path.split("/") if part]
    if final.hostname == "pub.dev" and len(parts) >= 3 and parts[0] == "documentation":
        return normalize_url(f"{final.scheme}://{final.netloc}/{'/'.join(parts[:3])}")
    return infer_docset_root(final_url) or final_url


@dataclass(slots=True)
class _FetchedPage:
    document: Document
    final_url: str

__all__ = [name for name in globals() if not name.startswith('__')]
