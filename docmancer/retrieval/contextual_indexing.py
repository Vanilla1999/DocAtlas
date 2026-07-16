"""Deterministic, source-owned context for FTS and embedding inputs."""
from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from docmancer.core.structured_chunking import estimate_utf8_tokens
from docmancer.retrieval.contracts import (
    ContextConfig,
    ContextField,
    ContextPrefix,
    canonical_hash,
)


_AUTHORITIES = {
    "official",
    "project_owned",
    "verified",
    "community",
    "stale",
    "unknown",
    "legal",
    "generated",
    "mirror",
    "external_generic",
    "project_rule",
}
_SYMBOL_PATTERNS = (
    re.compile(r"(?<![\w.-])--[a-zA-Z][a-zA-Z0-9-]{1,118}"),
    re.compile(r"\b[A-Z][A-Z0-9_]{2,119}\b"),
    re.compile(r"\b[A-Za-z_]\w*(?:::[A-Za-z_]\w*)+\b"),
    re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b"),
    re.compile(r"(?<![\w/])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"),
    re.compile(r"\b[A-Za-z_]\w{2,119}(?=\s*\()"),
)
_PLAIN_WORD = re.compile(r"^[A-Za-z][a-z]{2,}$")
_FIELD_LABELS = {
    # "Canonical" is a user search term in policy questions. Emitting it as
    # a label for every source creates false-positive lexical matches.
    "canonical_location": "Location",
}


def _field_label(name: str) -> str:
    return _FIELD_LABELS.get(name, name.replace("_", " ").title())


def _single_line(value: Any, *, limit: int = 480) -> str:
    return " ".join(str(value or "").split())[:limit]


def _canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    host = parsed.hostname.casefold()
    try:
        port = parsed.port
    except ValueError:
        return ""
    if port and not (
        (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = "/" + posixpath.normpath(parsed.path or "/").lstrip("/")
    return urlunsplit((parsed.scheme.casefold(), host, path, "", ""))


def _canonical_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return ""
    # Never expose a drive, home, temporary directory, or repository root.
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith("/"):
        normalized = PurePosixPath(normalized).name
    normalized = posixpath.normpath(normalized).lstrip("./")
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        return ""
    return normalized[:480]


def extract_symbol_aliases(
    display_text: str,
    *,
    max_aliases: int = 16,
    max_alias_bytes: int = 512,
) -> tuple[str, ...]:
    aliases: list[str] = []
    seen: set[str] = set()
    used_bytes = 0
    for pattern in _SYMBOL_PATTERNS:
        for match in pattern.finditer(display_text):
            alias = match.group(0)[:120]
            if _PLAIN_WORD.fullmatch(alias):
                continue
            key = alias.casefold()
            encoded = len(alias.encode("utf-8"))
            if key in seen or used_bytes + encoded > max_alias_bytes:
                continue
            aliases.append(alias)
            seen.add(key)
            used_bytes += encoded
            if len(aliases) >= max_aliases:
                return tuple(aliases)
    return tuple(aliases)


def _field_candidates(
    metadata: Mapping[str, Any],
    *,
    heading_path: tuple[str, ...],
    display_text: str,
) -> list[ContextField]:
    fields: list[ContextField] = []

    def add(name: str, value: Any, provenance: str, priority: int) -> None:
        normalized = _single_line(value)
        if normalized:
            fields.append(ContextField(name, normalized, provenance, priority))

    add("document_title", metadata.get("title") or metadata.get("document_title"), "source.metadata.title", 10)

    raw_url = str(metadata.get("canonical_url") or metadata.get("source_url") or "")
    location = _canonical_url(raw_url)
    location_provenance = "source.metadata.canonical_url"
    if not location:
        raw_path = str(metadata.get("project_doc_path") or metadata.get("source_path") or "")
        location = _canonical_relative_path(raw_path)
        location_provenance = "source.metadata.relative_path"
    add("canonical_location", location, location_provenance, 20)

    if heading_path:
        add("heading_path", " > ".join(_single_line(item, limit=160) for item in heading_path), "source.markdown.heading_path", 30)
    add("library", metadata.get("library") or metadata.get("library_name") or metadata.get("library_id"), "source.metadata.library", 40)
    resolved_version = metadata.get("resolved_version")
    if resolved_version and str(resolved_version).casefold() != "latest":
        add("resolved_version", resolved_version, "source.metadata.resolved_version", 50)
    add("version_family", metadata.get("version_family"), "source.metadata.version_family", 60)
    add("project_module", metadata.get("module_name") or metadata.get("module_id"), "source.metadata.project_module", 70)
    add("project_scope", metadata.get("doc_scope"), "source.metadata.doc_scope", 80)
    add("source_class", metadata.get("source_class"), "source.metadata.source_class", 90)

    authority = str(
        metadata.get("authority")
        or metadata.get("project_doc_authority")
        or "unknown"
    ).casefold().replace("-", "_")
    if authority not in _AUTHORITIES:
        authority = "unknown"
    if authority != "unknown":
        add("authority", authority, "source.metadata.authority", 100)

    aliases = extract_symbol_aliases(display_text)
    if aliases:
        add("symbol_aliases", ", ".join(aliases), "source.display_text.symbol_extractor", 110)

    source_class = str(metadata.get("source_class") or "")
    project_docs = metadata.get("project_docs")
    project_owned = (
        project_docs is True
        or project_docs == 1
        or (isinstance(project_docs, str) and project_docs.strip().casefold() in {"1", "true", "yes", "on"})
    ) or source_class in {
        "project_file",
        "project_doc",
    }
    if project_owned:
        add(
            "catalog_description",
            metadata.get("project_doc_description"),
            "project.catalog.description",
            120,
        )
    return fields


def normalized_filter_metadata(metadata: Mapping[str, Any]) -> dict[str, str | int | None]:
    """Return the small, typed metadata surface allowed in retrieval filters."""
    authority = str(
        metadata.get("authority") or metadata.get("project_doc_authority") or "unknown"
    ).casefold().replace("-", "_")
    if authority not in _AUTHORITIES:
        authority = "unknown"
    resolved_version = _single_line(metadata.get("resolved_version"))
    if resolved_version.casefold() == "latest":
        resolved_version = ""
    exact = metadata.get("docs_snapshot_exact")
    if exact is None:
        exact_value: int | None = None
    elif isinstance(exact, bool):
        exact_value = int(exact)
    elif isinstance(exact, int) and exact in {0, 1}:
        exact_value = exact
    elif isinstance(exact, str) and exact.strip().casefold() in {"true", "false", "1", "0"}:
        exact_value = int(exact.strip().casefold() in {"true", "1"})
    else:
        exact_value = None
    return {
        "library_id": _single_line(metadata.get("library_id")),
        "resolved_version": resolved_version,
        "version_family": _single_line(metadata.get("version_family")),
        "project_identity": _single_line(metadata.get("project_identity")),
        # Retrieval isolation needs the exact resolved project root. It is a
        # typed filter value, not model-visible context; source-relative paths
        # are represented separately by canonical_location/project_doc_path.
        "project_path": _single_line(metadata.get("project_path")) or _canonical_relative_path(str(
            metadata.get("project_doc_path") or metadata.get("source_path") or ""
        )),
        "module_id": _single_line(metadata.get("module_id") or metadata.get("module_name")),
        "doc_scope": _single_line(metadata.get("doc_scope")),
        "source_class": _single_line(metadata.get("source_class")),
        "authority": authority,
        "docs_snapshot_exact": exact_value,
    }


def build_context_prefix(
    metadata: Mapping[str, Any],
    *,
    heading_path: tuple[str, ...],
    display_text: str,
    config: ContextConfig | None = None,
    available_tokens: int | None = None,
) -> ContextPrefix:
    config = config or ContextConfig()
    max_tokens = config.max_prefix_tokens
    if available_tokens is not None:
        max_tokens = min(max_tokens, max(0, int(available_tokens)))
    selected: list[ContextField] = []
    truncated = False
    for field in sorted(
        _field_candidates(metadata, heading_path=heading_path, display_text=display_text),
        key=lambda item: (item.priority, item.name),
    ):
        if field.name not in config.allowed_fields:
            continue
        candidate = [*selected, field]
        candidate_text = "\n".join(
            f"{_field_label(item.name)}: {item.normalized_value}"
            for item in candidate
        )
        if (
            len(candidate_text.encode("utf-8")) > config.max_prefix_bytes
            or estimate_utf8_tokens(candidate_text) > max_tokens
        ):
            truncated = True
            continue
        selected.append(field)

    text = "\n".join(
        f"{_field_label(field.name)}: {field.normalized_value}"
        for field in selected
    )
    content_hash = canonical_hash([field.manifest_entry() for field in selected])
    return ContextPrefix(
        text=text,
        fields=tuple(selected),
        schema_version=config.schema_version,
        config_hash=config.config_hash,
        content_hash=content_hash,
        token_estimate=estimate_utf8_tokens(text) if text else 0,
        truncated=truncated,
    )


def embedding_input(prefix: ContextPrefix, retrieval_body: str) -> str:
    return f"{prefix.text}\n\n{retrieval_body}" if prefix.text else retrieval_body


__all__ = [
    "build_context_prefix",
    "embedding_input",
    "extract_symbol_aliases",
    "normalized_filter_metadata",
]
