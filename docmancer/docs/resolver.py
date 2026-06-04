from __future__ import annotations

import re


def normalize_library_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "-", value.strip().lower())
    return normalized.strip("-")


def normalize_lookup_key(value: str) -> str:
    return normalize_library_name(value).replace("-", "_")


def normalize_version(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def canonical_library_id(
    library: str,
    ecosystem: str | None = None,
    version: str | None = None,
    source_type: str | None = None,
) -> str:
    name = normalize_library_name(library)
    normalized_version = normalize_version(version)
    normalized_ecosystem = normalize_library_name(ecosystem) if ecosystem else None
    normalized_source_type = normalize_library_name(source_type or "api")
    if normalized_ecosystem:
        version_part = f"@{normalized_version}" if normalized_version else ""
        return f"{normalized_ecosystem}:{name}{version_part}:{normalized_source_type}"
    if normalized_version:
        return f"{name}@{normalized_version}"
    return name


def source_identity_id(
    library: str,
    ecosystem: str | None = None,
    source_type: str | None = None,
) -> str:
    return canonical_library_id(library, ecosystem, None, source_type)


def source_id_from_canonical_id(canonical_id: str) -> str:
    if ":" in canonical_id:
        prefix, remainder = canonical_id.split(":", 1)
        if ":" in remainder:
            name_version, source_type = remainder.rsplit(":", 1)
            name = name_version.split("@", 1)[0]
            return f"{prefix}:{name}:{source_type}"
    return canonical_id.split("@", 1)[0]


def docs_url_resolved(docs_url: str | None, docs_url_template: str | None, library: str, version: str | None) -> str | None:
    if docs_url:
        return docs_url
    normalized_version = normalize_version(version)
    if docs_url_template and normalized_version:
        return docs_url_template.format(library=library, version=normalized_version)
    return None


def docs_snapshot_is_exact(version: str | None, docs_url: str | None) -> bool:
    normalized_version = normalize_version(version)
    if not normalized_version:
        return False
    if normalized_version in {"latest", "stable", "main", "master", "beta", "next"}:
        return False
    if docs_url is None:
        return False
    lowered_url = docs_url.lower()
    if any(marker in lowered_url for marker in ("/latest", "/stable", "/main", "/master", "/beta", "/next")):
        return False
    return normalized_version in lowered_url


def legacy_library_id(library: str, version: str | None = None) -> str:
    name = normalize_library_name(library)
    normalized_version = normalize_version(version)
    if normalized_version:
        return f"{name}@{normalized_version}"
    return name
