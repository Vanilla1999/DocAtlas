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
) -> str:
    name = normalize_library_name(library)
    normalized_version = normalize_version(version)
    if normalized_version:
        return f"{name}@{normalized_version}"
    if ecosystem:
        return f"{normalize_library_name(ecosystem)}:{name}"
    return name
