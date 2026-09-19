"""Lossless model-facing views for reader-only evaluation.

This module never retrieves, ranks, qualifies, or changes the public MCP
payload.  It only renders a copied subset for controlled reader experiments.
Unsupported/unknown contracts fall back to the original raw JSON rendering.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Literal


VIEW_SCHEMA = "docatlas-reader-view-v1"

_KNOWN_TOP_LEVEL = frozenset({
    "status", "kind", "schema_version",
    "context_status", "context_available", "context_quality",
    "answer_supported", "answer_available", "support_status",
    "answer_policy", "coverage_policy",
    "query_coverage", "retrieval_coverage", "facet_coverage",
    "covered_query_ids", "missing_query_ids", "missing_facets", "facets",
    "sources", "edit_ready", "investigation_allowed", "estimated_tokens",
    "missing", "omitted_counts", "limitations", "recommended_next_action",
    "read_next", "requires_confirmation", "confirmation_reason",
    "operational_status", "disposition", "reason_code",
})

_CONTRACT_FIELDS = (
    "schema_version", "kind", "status",
    "context_status", "context_available", "context_quality",
    "answer_supported", "answer_available", "edit_ready",
    "support_status", "answer_policy", "coverage_policy",
    "query_coverage", "retrieval_coverage", "facet_coverage",
    "covered_query_ids", "missing_query_ids", "missing_facets", "facets",
    "investigation_allowed", "missing", "omitted_counts", "limitations",
    "recommended_next_action", "read_next",
    "requires_confirmation", "confirmation_reason",
    "operational_status", "disposition", "reason_code",
)

_KNOWN_SOURCE_FIELDS = frozenset({
    "evidence_id", "path_or_url", "path", "section", "symbol_or_section",
    "snippet", "version_binding", "authority", "instruction_trust", "scope",
    "line_start", "line_end", "content_sha256", "project_identity",
})

_SOURCE_VIEW_FIELDS = (
    "evidence_id", "path_or_url", "path", "section", "symbol_or_section",
    "line_start", "line_end", "version_binding",
    "authority", "instruction_trust", "scope", "snippet",
)

_HEADER = b"DOCATLAS_READER_VIEW_V1\n"


class UnsupportedReaderView(ValueError):
    """The packet has fields this eval renderer is not allowed to discard."""


def _raw_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def reader_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copied lossless evidence view without inferring any answer."""

    if not isinstance(payload, dict) or payload.get("kind") != "docs_context":
        raise UnsupportedReaderView("only docs_context is supported")
    # The reviewed docs_context contract is unversioned. Do not interpret an
    # explicit future schema using this allowlist, even if its keys look familiar.
    if "schema_version" in payload:
        raise UnsupportedReaderView("explicit schema version is not supported")
    unknown = set(payload) - _KNOWN_TOP_LEVEL
    if unknown:
        raise UnsupportedReaderView(f"unknown top-level fields: {sorted(unknown)}")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise UnsupportedReaderView("sources must be a list")

    projected_sources: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise UnsupportedReaderView("source must be an object")
        if not isinstance(source.get("snippet"), str):
            raise UnsupportedReaderView("source snippet must be a string")
        unknown_source = set(source) - _KNOWN_SOURCE_FIELDS
        if unknown_source:
            raise UnsupportedReaderView(
                f"unknown source fields: {sorted(unknown_source)}"
            )
        projected_sources.append({
            key: deepcopy(source[key])
            for key in _SOURCE_VIEW_FIELDS
            if key in source
        })

    return {
        "schema_version": VIEW_SCHEMA,
        "server_contract": {
            key: deepcopy(payload[key])
            for key in _CONTRACT_FIELDS
            if key in payload
        },
        "sources": projected_sources,
    }


def _render_text(view: dict[str, Any]) -> str:
    contract = json.dumps(
        view["server_contract"], ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    output = bytearray(_HEADER)
    output.extend(f"CONTRACT_BYTES {len(contract)}\n".encode("ascii"))
    output.extend(contract)
    output.extend(b"\n")
    sources = view["sources"]
    output.extend(f"SOURCES {len(sources)}\n".encode("ascii"))
    for source in sources:
        metadata = {key: value for key, value in source.items() if key != "snippet"}
        metadata_bytes = json.dumps(
            metadata, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        snippet_bytes = source["snippet"].encode("utf-8")
        output.extend(f"META_BYTES {len(metadata_bytes)}\n".encode("ascii"))
        output.extend(metadata_bytes)
        output.extend(b"\n")
        output.extend(f"SNIPPET_BYTES {len(snippet_bytes)}\n".encode("ascii"))
        output.extend(snippet_bytes)
        output.extend(b"\n")
    return output.decode("utf-8")


def _read_line(data: bytes, cursor: int) -> tuple[bytes, int]:
    end = data.find(b"\n", cursor)
    if end < 0:
        raise ValueError("truncated reader view")
    return data[cursor:end], end + 1


def _read_framed(data: bytes, cursor: int, prefix: bytes) -> tuple[bytes, int]:
    line, cursor = _read_line(data, cursor)
    if not line.startswith(prefix):
        raise ValueError("invalid reader view frame")
    try:
        size = int(line[len(prefix):])
    except ValueError as exc:
        raise ValueError("invalid reader view frame length") from exc
    if size < 0 or cursor + size > len(data):
        raise ValueError("invalid reader view frame length")
    value = data[cursor:cursor + size]
    cursor += size
    if cursor >= len(data) or data[cursor:cursor + 1] != b"\n":
        raise ValueError("invalid reader view frame boundary")
    return value, cursor + 1


def parse_reader_view_text(value: str) -> dict[str, Any]:
    """Parse the deterministic length-framed text view used by tests/evals."""

    data = value.encode("utf-8")
    if not data.startswith(_HEADER):
        raise ValueError("unsupported reader view header")
    cursor = len(_HEADER)
    contract_bytes, cursor = _read_framed(data, cursor, b"CONTRACT_BYTES ")
    source_line, cursor = _read_line(data, cursor)
    if not source_line.startswith(b"SOURCES "):
        raise ValueError("invalid reader view source count")
    try:
        source_count = int(source_line[len(b"SOURCES "):])
    except ValueError as exc:
        raise ValueError("invalid reader view source count") from exc
    if source_count < 0:
        raise ValueError("invalid reader view source count")

    sources: list[dict[str, Any]] = []
    for _ in range(source_count):
        metadata_bytes, cursor = _read_framed(data, cursor, b"META_BYTES ")
        snippet_bytes, cursor = _read_framed(data, cursor, b"SNIPPET_BYTES ")
        metadata = json.loads(metadata_bytes)
        if not isinstance(metadata, dict):
            raise ValueError("invalid reader view source metadata")
        metadata["snippet"] = snippet_bytes.decode("utf-8")
        sources.append(metadata)
    if cursor != len(data):
        raise ValueError("unexpected trailing reader view data")

    contract = json.loads(contract_bytes)
    if not isinstance(contract, dict):
        raise ValueError("invalid reader view contract")
    return {
        "schema_version": VIEW_SCHEMA,
        "server_contract": contract,
        "sources": sources,
    }


def render_reader_view(
    payload: dict[str, Any], *,
    mode: Literal["raw_json", "view_json", "view_text"],
) -> str:
    """Render one fixed experiment arm; unknown contracts fail open to raw."""

    if mode == "raw_json":
        return _raw_json(payload)
    if mode not in {"view_json", "view_text"}:
        raise ValueError(f"unsupported reader view mode: {mode}")
    try:
        view = reader_view(payload)
    except UnsupportedReaderView:
        return _raw_json(payload)
    if mode == "view_json":
        return json.dumps(view, ensure_ascii=False, separators=(",", ":"))
    return _render_text(view)
