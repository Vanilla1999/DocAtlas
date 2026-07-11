"""Small, versioned allowlist of official documentation sources.

The manifest deliberately contains locators, not fetched content.  It is used to
avoid arbitrary URL guessing before the existing confirmation-first prefetch
workflow acquires a local snapshot.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error


_MANIFEST_PATH = Path(__file__).with_name("curated_sources.json")
_SUPPORTED_VERSION_RULES = {"exact", "unversioned"}
_VALIDATION_VERSION = "1.0.0"


@dataclass(frozen=True)
class CuratedSource:
    library: str
    ecosystem: str
    version_rule: str
    docs_url: str
    allowed_domains: tuple[str, ...]
    preferred_seeds: tuple[str, ...]
    extraction_format: str
    max_pages: int
    path_prefixes: tuple[str, ...] = ()

    def render(self, version: str | None) -> str | None:
        if self.version_rule == "exact" and not version:
            return None
        value = version or "latest"
        return self.docs_url.format(library=self.library, version=value)

    @property
    def exact_snapshot(self) -> bool:
        return self.version_rule == "exact" and "{version}" in self.docs_url


def _ecosystem_aliases(ecosystem: str | None) -> set[str]:
    value = (ecosystem or "").strip().lower()
    if value in {"javascript", "typescript", "node", "npm"}:
        return {"npm"}
    if value in {"flutter", "dart", "pub"}:
        return {"dart"}
    return {value}


def _validation_error(source: CuratedSource, field: str, detail: str) -> ValueError:
    return ValueError(f"invalid curated source {source.library} field {field}: {detail}")


def _render_url_template(source: CuratedSource, template: str, field: str) -> str:
    try:
        rendered = template.format(library=source.library, version=_VALIDATION_VERSION)
    except (KeyError, ValueError) as exc:
        raise _validation_error(source, field, f"unresolved template: {exc}") from exc
    if "{" in rendered or "}" in rendered:
        raise _validation_error(source, field, "unresolved template placeholder")
    return rendered


def _validate_url(source: CuratedSource, url: str, field: str) -> None:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        raise _validation_error(source, field, "URL userinfo is not allowed")
    security_error = url_security_error(url)
    if security_error:
        raise _validation_error(source, field, security_error)
    if not is_remote_url(url):
        raise _validation_error(source, field, "URL must use http or https")
    if not parsed.hostname:
        raise _validation_error(source, field, "URL host is required")
    domains = list(source.allowed_domains)
    if not domains:
        raise _validation_error(source, field, "allowed_domains is required")
    if not host_allowed(url, domains):
        raise _validation_error(source, field, "URL host is not in allowed_domains")
    if not path_allowed(url, list(source.path_prefixes)):
        raise _validation_error(source, field, "URL path is outside path_prefixes")


def validate_curated_sources(sources: tuple[CuratedSource, ...] | list[CuratedSource] | None = None) -> None:
    """Validate shipped source locators without making network requests."""
    values = curated_sources() if sources is None else tuple(sources)
    seen: set[tuple[str, str]] = set()
    for source in values:
        key = (source.library, source.ecosystem)
        if key in seen:
            raise _validation_error(source, "library", "duplicate library/ecosystem entry")
        seen.add(key)
        if not source.library or not source.ecosystem:
            raise _validation_error(source, "library", "library and ecosystem are required")
        if source.version_rule not in _SUPPORTED_VERSION_RULES:
            raise _validation_error(source, "version_rule", f"unsupported value {source.version_rule!r}")
        if source.version_rule == "exact" and "{version}" not in source.docs_url:
            raise _validation_error(source, "docs_url", "exact source must bind {version}")
        if not source.extraction_format:
            raise _validation_error(source, "extraction_format", "value is required")
        if source.max_pages <= 0:
            raise _validation_error(source, "max_pages", "must be positive")
        _validate_url(source, _render_url_template(source, source.docs_url, "docs_url"), "docs_url")
        for index, seed in enumerate(source.preferred_seeds):
            field = f"preferred_seeds[{index}]"
            _validate_url(source, _render_url_template(source, seed, field), field)


@lru_cache(maxsize=1)
def curated_sources() -> tuple[CuratedSource, ...]:
    data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("curated source manifest schema_version must be 1")
    entries: list[CuratedSource] = []
    for raw in data.get("sources") or []:
        library = str(raw.get("library") or "<unknown>").casefold()
        ecosystem = str(raw.get("ecosystem") or "").casefold()
        docs_url = str(raw.get("docs_url") or "")
        version_rule = str(raw.get("version_rule") or "")
        try:
            max_pages = int(raw.get("max_pages"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid curated source {library} field max_pages: must be an integer") from exc
        entries.append(CuratedSource(
            library=library,
            ecosystem=ecosystem,
            version_rule=version_rule,
            docs_url=docs_url,
            allowed_domains=tuple(str(value) for value in raw.get("allowed_domains") or []),
            preferred_seeds=tuple(str(value) for value in raw.get("preferred_seeds") or []),
            extraction_format=str(raw.get("extraction_format") or ""),
            max_pages=max_pages,
            path_prefixes=tuple(str(value) for value in raw.get("path_prefixes") or []),
        ))
    validate_curated_sources(entries)
    return tuple(entries)


def curated_source_for(library: str, ecosystem: str | None, version: str | None) -> CuratedSource | None:
    normalized_library = library.strip().casefold()
    aliases = _ecosystem_aliases(ecosystem)
    for source in curated_sources():
        if source.library != normalized_library or source.ecosystem not in aliases:
            continue
        # An unversioned/current documentation site cannot satisfy an exact
        # dependency request.  Keep the normal confirmation-first flow instead
        # of silently labelling latest documentation as the requested version.
        if version and not source.exact_snapshot:
            continue
        if source.render(version):
            return source
    return None


def curated_target_spec(source: CuratedSource, *, version: str | None) -> dict[str, Any] | None:
    docs_url = source.render(version)
    if not docs_url:
        return None
    # Manifest seed hints are advisory and historically included mechanically
    # appended, non-existent llms.txt/sitemap.xml paths.  The canonical docs URL
    # is the safe bounded starting point until a seed has been verified.
    seeds: list[str] = []
    return {
        "library": source.library,
        "ecosystem": source.ecosystem,
        "version": version or "latest",
        "source_type": "api",
        "docs_url": docs_url,
        "seed_urls": seeds,
        "allowed_domains": list(source.allowed_domains),
        "max_pages": source.max_pages,
        "doc_format": source.extraction_format,
        "source_manifest": {"schema_version": 1, "version_rule": source.version_rule, "official": True},
    }


def canonical_source_identity(url: str) -> str:
    """Stable cache namespace for one canonical source locator."""
    canonical = url.strip().rstrip("/").casefold()
    return f"source:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
