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


_MANIFEST_PATH = Path(__file__).with_name("curated_sources.json")


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

    def render(self, version: str | None) -> str | None:
        if self.version_rule == "exact" and not version:
            return None
        value = version or "latest"
        return self.docs_url.format(library=self.library, version=value)

    @property
    def exact_snapshot(self) -> bool:
        return self.version_rule == "exact"


def _ecosystem_aliases(ecosystem: str | None) -> set[str]:
    value = (ecosystem or "").strip().lower()
    if value in {"javascript", "typescript", "node", "npm"}:
        return {"npm"}
    if value in {"flutter", "dart", "pub"}:
        return {"dart"}
    return {value}


@lru_cache(maxsize=1)
def curated_sources() -> tuple[CuratedSource, ...]:
    data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("curated source manifest schema_version must be 1")
    entries: list[CuratedSource] = []
    for raw in data.get("sources") or []:
        docs_url = str(raw["docs_url"])
        allowed_domains = tuple(str(value) for value in raw.get("allowed_domains") or [])
        if not allowed_domains or not urlparse(docs_url.format(library="x", version="1")).hostname:
            raise ValueError(f"invalid curated source entry: {raw.get('library')}")
        entries.append(CuratedSource(
            library=str(raw["library"]).casefold(),
            ecosystem=str(raw["ecosystem"]).casefold(),
            version_rule=str(raw.get("version_rule") or "unversioned"),
            docs_url=docs_url,
            allowed_domains=allowed_domains,
            preferred_seeds=tuple(str(value) for value in raw.get("preferred_seeds") or []),
            extraction_format=str(raw.get("extraction_format") or "html"),
            max_pages=int(raw.get("max_pages") or 24),
        ))
    return tuple(entries)


def curated_source_for(library: str, ecosystem: str | None, version: str | None) -> CuratedSource | None:
    normalized_library = library.strip().casefold()
    aliases = _ecosystem_aliases(ecosystem)
    for source in curated_sources():
        if source.library == normalized_library and source.ecosystem in aliases and source.render(version):
            return source
    return None


def curated_target_spec(source: CuratedSource, *, version: str | None) -> dict[str, Any] | None:
    docs_url = source.render(version)
    if not docs_url:
        return None
    seeds = [seed.format(library=source.library, version=version or "latest") for seed in source.preferred_seeds]
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
