"""Optional, generation-bound reuse of canonical Markdown parent sections.

Read functions only issue SELECTs and never parse Markdown or prepare artifacts.
The caller retains source/catalog/request validation and verifies the raw SHA
before passing content to the reader.  A miss permits the caller's old parser
only for that same, independently verified source snapshot.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping

from .structured_chunking import (
    PARENT_PARSER_REVISION,
    ParentSection,
    parent_sections_digest,
    parse_markdown_parents,
)


MANIFEST_SCHEMA_VERSION = 1
_EXPERIMENT_ENV = "DOCATLAS_EXPERIMENT_PREPARED_PARENTS"
_PARENT_COLUMNS = (
    "logical_id, revision_id, source_identity, source_content_hash, "
    "title, level, heading_path_json, heading_levels_json, occurrence, "
    "char_start, char_end, byte_start, byte_end, line_start, line_end"
)
_TEXT_FIELDS = (
    "logical_id", "revision_id", "source_identity", "source_content_hash", "title",
)
_INTEGER_FIELDS = (
    "level", "occurrence", "char_start", "char_end", "byte_start", "byte_end",
    "line_start", "line_end",
)


def prepared_parents_enabled() -> bool:
    """Host-only opt-in; requests and document metadata cannot enable reuse."""
    return os.environ.get(_EXPERIMENT_ENV) == "1"


@dataclass(frozen=True, slots=True)
class PreparedParentManifest:
    generation_id: str
    payload: dict[str, Any] | None
    miss_reason: str | None
    elapsed_ms: float
    bytes_read: int


@dataclass(frozen=True, slots=True)
class PreparedParentRead:
    parents: list[ParentSection] | None
    miss_reason: str | None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def load_prepared_parent_manifest(
    conn: sqlite3.Connection, generation_id: str,
) -> PreparedParentManifest:
    """Read once per context after the caller captures the host opt-in.

    Readers do not reread environment flags during an in-flight request.
    """
    started = perf_counter()
    bytes_read = 0

    def result(payload=None, reason=None):
        return PreparedParentManifest(
            generation_id, payload, reason,
            (perf_counter() - started) * 1000.0, bytes_read,
        )

    try:
        row = conn.execute(
            "SELECT status, validation_json FROM index_generations WHERE generation_id=?",
            (generation_id,),
        ).fetchone()
        if row is None:
            return result(reason="missing_generation")
        # A captured immutable snapshot may become superseded during a request.
        # A not-yet-published candidate is never a query-time source of authority.
        if row["status"] not in {"active", "superseded"}:
            return result(reason="unpublished_generation")
        raw = row["validation_json"]
        if not isinstance(raw, str):
            return result(reason="malformed_validation")
        bytes_read = len(raw.encode("utf-8"))
        validation = json.loads(raw)
        if not isinstance(validation, dict) or validation.get("status") != "PASS":
            return result(reason="unvalidated_generation")
        payload = validation.get("prepared_parents")
        if payload is None:
            return result(reason="missing_manifest")
        if not isinstance(payload, dict) or not isinstance(payload.get("sources"), dict):
            return result(reason="malformed_manifest")
        if (type(payload.get("manifest_schema_version")) is not int
                or payload["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION):
            return result(reason="incompatible_manifest_schema")
        if payload.get("parent_parser_revision") != PARENT_PARSER_REVISION:
            return result(reason="incompatible_parent_revision")
        if payload.get("generation_id") != generation_id:
            return result(reason="manifest_snapshot_mismatch")
        return result(payload=payload)
    except sqlite3.Error:
        return result(reason="manifest_read_error")
    except (TypeError, ValueError, KeyError, IndexError, RecursionError):
        return result(reason="malformed_manifest")


def _hydrate_parent(
    row: Mapping[str, Any], *, content: str,
    source_identity: str, content_sha256: str,
) -> ParentSection:
    """Decode fields; certificate verification supplies canonical completeness."""
    if any(not isinstance(row[name], str) for name in _TEXT_FIELDS):
        raise ValueError("parent text field type")
    if any(type(row[name]) is not int for name in _INTEGER_FIELDS):
        raise ValueError("parent integer field type")
    if (row["source_identity"] != source_identity
            or row["source_content_hash"] != content_sha256):
        raise ValueError("parent source binding")
    start, end = row["char_start"], row["char_end"]
    if not 0 <= start < end <= len(content):
        raise ValueError("parent character bounds")
    if not (0 <= row["byte_start"] < row["byte_end"]
            and 1 <= row["line_start"] <= row["line_end"]
            and 0 <= row["level"] <= 6 and row["occurrence"] >= 1):
        raise ValueError("parent coordinate bounds")
    path = json.loads(row["heading_path_json"])
    levels = json.loads(row["heading_levels_json"])
    if (not isinstance(path, list) or not all(isinstance(item, str) for item in path)
            or not isinstance(levels, list) or len(levels) != len(path)
            or not all(type(item) is int and 1 <= item <= 6 for item in levels)):
        raise ValueError("parent ancestry fields")
    return ParentSection(
        **{name: row[name] for name in (*_TEXT_FIELDS, *_INTEGER_FIELDS)},
        heading_path=tuple(path), heading_levels=tuple(levels),
        display_text=content[start:end],
    )


def read_prepared_parent_sections(
    conn: sqlite3.Connection, *, manifest: PreparedParentManifest,
    generation_id: str, source: str, source_identity: str,
    content: str, content_sha256: str, source_id: int | None,
) -> PreparedParentRead:
    """Return canonical parents or a diagnostic miss, without a Markdown parse.

    ``content_sha256`` must be the caller-verified SHA of ``content`` from this
    captured generation's generation_sources row.  ``source_id`` must be the
    single integer found in the already fetched children for this generation
    and source, never a lookup in the mutable sources table.  No raw hash is
    repeated here; neither this certificate nor source_id authorizes a source.
    The caller captures and guards the host opt-in once per request context.
    """
    started = perf_counter()
    diagnostics: dict[str, Any] = {
        "parent_rows": 0, "parent_selects": 0, "read_ms": 0.0,
        "verification_ms": 0.0,
    }

    def result(parents=None, reason=None):
        return PreparedParentRead(parents, reason, {
            **diagnostics, "elapsed_ms": (perf_counter() - started) * 1000.0,
        })

    if manifest.generation_id != generation_id:
        return result(reason="manifest_snapshot_mismatch")
    if manifest.payload is None:
        return result(reason=manifest.miss_reason or "missing_manifest")
    if type(source_id) is not int:
        return result(reason="missing_or_ambiguous_source_id")
    payload = manifest.payload
    if not isinstance(payload, dict):
        return result(reason="malformed_manifest")
    if (payload.get("generation_id") != generation_id
            or payload.get("parent_parser_revision") != PARENT_PARSER_REVISION
            or type(payload.get("manifest_schema_version")) is not int
            or payload.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION):
        return result(reason="incompatible_manifest")
    try:
        sources = payload.get("sources")
        certificate = sources.get(source) if isinstance(sources, dict) else None
        if certificate is None:
            return result(reason="uncertified_source")
        if not isinstance(certificate, dict):
            return result(reason="malformed_source_certificate")
        if (certificate.get("source_identity") != source_identity
                or certificate.get("content_sha256") != content_sha256):
            return result(reason="source_certificate_binding_mismatch")
        count = certificate.get("parent_count")
        digest = certificate.get("canonical_rows_sha256")
        if (type(count) is not int or count < 0
                or not isinstance(digest, str) or len(digest) != 64):
            return result(reason="malformed_source_certificate")
        read_started = perf_counter()
        diagnostics["parent_selects"] += 1
        try:
            rows = conn.execute(
                f"SELECT {_PARENT_COLUMNS} FROM retrieval_parents "
                "WHERE generation_id=? AND source_id=? AND source=? "
                "ORDER BY char_start, logical_id",
                (generation_id, source_id, source),
            ).fetchall()
        finally:
            diagnostics["read_ms"] = (perf_counter() - read_started) * 1000.0
        diagnostics["parent_rows"] = len(rows)
        if len(rows) != count:
            return result(reason="parent_count_mismatch")
        verification_started = perf_counter()
        try:
            parents = [
                _hydrate_parent(row, content=content, source_identity=source_identity,
                                content_sha256=content_sha256)
                for row in rows
            ]
            actual_digest = parent_sections_digest(parents)
        finally:
            diagnostics["verification_ms"] = (perf_counter() - verification_started) * 1000.0
        if actual_digest != digest:
            return result(reason="parent_digest_mismatch")
        return result(parents=parents)
    except sqlite3.Error:
        return result(reason="parent_read_error")
    except (TypeError, ValueError, KeyError, IndexError, RecursionError):
        return result(reason="malformed_parent_rows")


def certify_prepared_parent_sections(
    conn: sqlite3.Connection, generation_id: str, *,
    canonical_by_source: Mapping[str, list[ParentSection]] | None = None,
) -> dict[str, Any] | None:
    """Build optional certificates during candidate preparation, never on read.

    Supplied canonical results come directly from the writer's chunker. Copied
    sources without those results are parsed here, rather than certified by
    merely hashing old rows. A failure omits that source's certificate; it does
    not add a rejection to the store's existing generation-validation contract.
    The caller owns the transaction and the eventual validation_json write.
    """
    if not prepared_parents_enabled():
        return None
    started = perf_counter()
    sources: dict[str, Any] = {}
    misses: dict[str, str] = {}
    costs: dict[str, Any] = {
        "sources_seen": 0, "writer_results_reused": 0, "canonical_parse_calls": 0,
        "canonical_parse_ms": 0.0,
    }
    try:
        snapshots = conn.execute(
            "SELECT source, source_identity, content, content_hash "
            "FROM generation_sources WHERE generation_id=? ORDER BY source",
            (generation_id,),
        ).fetchall()
        grouped: dict[str, list[Any]] = {}
        for row in conn.execute(
            f"SELECT source, display_text, {_PARENT_COLUMNS} FROM retrieval_parents "
            "WHERE generation_id=? ORDER BY source, char_start, logical_id",
            (generation_id,),
        ):
            grouped.setdefault(row["source"], []).append(row)
        for snapshot in snapshots:
            source = snapshot["source"]
            costs["sources_seen"] += 1
            try:
                content, identity, digest = (
                    snapshot["content"], snapshot["source_identity"], snapshot["content_hash"],
                )
                if not all(isinstance(value, str) for value in (source, content, identity, digest)):
                    misses[str(source)] = "malformed_source_snapshot"
                    continue
                expected = canonical_by_source.get(source) if canonical_by_source is not None else None
                if expected is None:
                    parse_started = perf_counter()
                    costs["canonical_parse_calls"] += 1
                    try:
                        expected = parse_markdown_parents(content, identity)
                    finally:
                        costs["canonical_parse_ms"] += (perf_counter() - parse_started) * 1000.0
                else:
                    costs["writer_results_reused"] += 1
                rows = grouped.get(source, [])
                hydrated = [
                    _hydrate_parent(row, content=content, source_identity=identity,
                                    content_sha256=digest)
                    for row in rows
                ]
                if (hydrated != expected or any(
                    row["display_text"] != parent.display_text
                    for row, parent in zip(rows, hydrated)
                )):
                    misses[source] = "canonical_parent_mismatch"
                    continue
                sources[source] = {
                    "source_identity": identity,
                    "content_sha256": digest,
                    "parent_count": len(expected),
                    "canonical_rows_sha256": parent_sections_digest(expected),
                }
            except (TypeError, ValueError, KeyError, IndexError, RecursionError):
                misses[str(source)] = "malformed_parent_rows"
    except sqlite3.Error:
        costs["read_error"] = True
    costs.update(
        certified_sources=len(sources), missed_sources=len(misses),
        elapsed_ms=(perf_counter() - started) * 1000.0,
    )
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "parent_parser_revision": PARENT_PARSER_REVISION,
        "generation_id": generation_id,
        "sources": sources,
        "misses": misses,
        "certification": costs,
    }
