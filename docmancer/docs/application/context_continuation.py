"""Snapshot binding and visible accounting for checked-context portions.

The digest detects a changed question, checked pool or host configuration.
It grants no access and replaces none of the live source checks. Only stable
selection inputs are bound: diagnostic timings and observer state are excluded.
"""
from __future__ import annotations

import hashlib
import json


# Original-source fields that affect grouping, pruning, qualification or scope.
# The projected row also binds its exact text, coordinates and public provenance.
_SOURCE_BINDINGS = (
    "project_identity", "source_class", "source_type", "doc_scope", "module_path",
    "authority", "version_binding", "version", "requested_version", "generation_id",
    "docs_snapshot_exact", "project_doc_catalog_entry_hash", "project_doc_content_hash",
    "_source_snapshot_sha256", "_source_catalog_hash", "retrieval_query_matches",
    "_reference_plans", "_reference_root_plan",
)
_REFERENCE_BINDINGS = (
    "source", "member_binding", "project_doc_content_hash", "char_start", "char_end", "text",
)


def continuation_fingerprint(
    payload: dict, snapshot: dict, retrieval: dict, *, policy: str, settings: dict,
    limit: int, max_source_references: int | None, request_binding: dict | None = None,
) -> str:
    """Bind the complete ordered pool, including rows that pruning may remove."""
    bindings = []
    for row in payload.get("sources") or ():
        source = snapshot[row["evidence_id"]]["source"]
        reference = source.get("_reference_evidence") or {}
        bindings.append({
            "row": row,
            "source": {key: source[key] for key in _SOURCE_BINDINGS if key in source},
            # The checked source/content hashes bind the full document; do not
            # repeatedly serialize its raw text for every checked window.
            "reference": {key: reference[key] for key in _REFERENCE_BINDINGS if key in reference},
        })
    material = {
        "format": "docatlas.context-portions.v1", "policy": policy,
        # Explicit request scope/targets matter even when they happen to yield
        # the same checked rows. The caller omits portion and its token here.
        "request": request_binding,
        "queries": retrieval.get("documentation_query_plan") or {},
        "project_identity": retrieval.get("project_identity"),
        "upstream": {key: payload.get(key) for key in (
            "status", "covered_query_ids", "missing_query_ids",
        )},
        "checked_pool": bindings, "settings": settings,
        "max_tokens": limit, "max_source_references": max_source_references,
    }
    body = json.dumps(material, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def continuation_metadata(portion: int, token: str, candidates: int, selected: int) -> dict:
    """Count unreturned checked candidates, without promising useful evidence.

    A no-progress page is terminal even when unselectable candidates remain.
    The client still decides whether another call is needed for its question.
    """
    remaining = max(0, candidates - selected)
    return {
        "portion": portion,
        "next_portion": portion + 1 if selected and remaining else None,
        "remaining_rows": remaining,
        "continuation_token": token,
    }
