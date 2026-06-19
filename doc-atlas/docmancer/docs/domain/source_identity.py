from __future__ import annotations

from typing import Any, Protocol


class LibraryIdentityInfo(Protocol):
    source_id: str | None
    canonical_id: str | None
    library: str
    ecosystem: str | None
    version: str | None
    source_type: str | None
    docs_url: str | None
    docs_url_template: str | None
    docs_snapshot_exact: bool | None


def docs_identity(info: LibraryIdentityInfo | None, *, docs_url_source: str | None = None) -> dict[str, Any]:
    return {
        "source_id": info.source_id if info else None,
        "canonical_id": info.canonical_id if info else None,
        "library": info.library if info else None,
        "ecosystem": info.ecosystem if info else None,
        "version": info.version if info else None,
        "docs_url": info.docs_url if info else None,
        "docs_url_source": docs_url_source,
        "selected_by": "registry" if docs_url_source == "registry" else None,
        "docs_snapshot_exact": info.docs_snapshot_exact if info else None,
    }


def docs_request(input_args: dict[str, Any], info: LibraryIdentityInfo | None = None) -> dict[str, Any]:
    effective = dict(input_args)
    if info:
        effective.update(
            {
                "library": info.library,
                "ecosystem": info.ecosystem,
                "version": info.version,
                "source_type": info.source_type,
                "docs_url": info.docs_url,
                "docs_url_template": info.docs_url_template,
            }
        )
    return {"input": input_args, "effective": effective}


def docs_exactness(docs_snapshot_exact: bool | None, docs_url: str | None, docs_url_template: str | None) -> str:
    if docs_snapshot_exact:
        return "exact_snapshot"
    if docs_url or docs_url_template:
        return "exact_version_url"
    return "no_docs"
