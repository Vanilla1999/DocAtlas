"""Private bounded diagnostics for project-document retrieval stages."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from docmancer.docs.domain.documentation_query_plan import DocumentationQueryPlan

_INTERNAL_DIAGNOSTIC_LIMIT = 32


def _diagnostic_candidate_id(chunk: Any) -> dict[str, str]:
    metadata = chunk.metadata or {}
    return {
        key: value
        for key, value in {
            "stable_chunk_id": str(metadata.get("stable_chunk_id") or ""),
            "document_id": str(metadata.get("document_id") or chunk.source or ""),
            "parent_logical_id": str(metadata.get("parent_logical_id") or ""),
        }.items()
        if value
    }


def _observed_fields(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    """Copy existing diagnostic values; never recompute an admission decision."""
    return {key: deepcopy(value[key]) for key in keys if key in value} if isinstance(value, dict) else {}


def _observed_candidate(chunk: Any) -> dict[str, Any]:
    metadata = chunk.metadata or {}
    evidence = metadata.get("_reference_evidence") or {}
    root = metadata.get("_reference_root_plan") or {}
    references = root.get("references") if isinstance(root, dict) else None
    references = references if isinstance(references, (list, tuple)) else ()
    body = getattr(chunk, "text", None)
    return {
        "window_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest() if isinstance(body, str) else None,
        "window_characters": len(body) if isinstance(body, str) else None,
        # This belongs to the acquired candidate. A merged lookup candidate's
        # store trace must not be interpreted as another query's BM25 receipt.
        "candidate_lexical_match": _observed_fields(metadata.get("lexical_match"), (
            "mode", "query_terms", "matched_terms", "exact_terms", "missing_exact_terms",
            "query_term_count", "matched_term_count", "match_ratio", "bm25_cost",
            "lexical_score", "field_matches",
        )),
        "source_reference": _observed_fields(evidence, (
            "source", "member_binding", "char_start", "char_end",
        )),
        "root_catalog_complete": root.get("catalog_complete") if isinstance(root, dict) else None,
        "root_reference_count": len(references),
        "root_references": [
            {**_observed_fields(ref, ("role", "state", "reason")),
             "mention": _observed_fields(ref.get("mention"), (
                 "text", "syntax_role", "explicit", "start", "end",
             ))}
            for ref in references[:_INTERNAL_DIAGNOSTIC_LIMIT] if isinstance(ref, dict)
        ],
    }


def _retrieval_stage_diagnostics(
    plan: DocumentationQueryPlan, candidates: list[Any],
) -> dict[str, Any]:
    rows = []
    outcomes = []
    for chunk in candidates[:_INTERNAL_DIAGNOSTIC_LIMIT]:
        identity = _diagnostic_candidate_id(chunk)
        if identity:
            rows.append(identity)
        observed = _observed_candidate(chunk)
        matches = (chunk.metadata or {}).get("retrieval_query_matches") or {}
        for query_id, trace in matches.items():
            if not isinstance(trace, dict):
                continue
            outcomes.append({
                **identity,
                "query_id": str(query_id),
                "outcome": (
                    "qualified" if trace.get("qualified") is True else
                    "rejected" if trace.get("qualified") is False else
                    "unclassified"
                ),
                "reason": str(trace.get("qualification_reason") or trace.get("reason_code") or trace.get("reason") or "unclassified")[:120],
                "observed_candidate": observed,
                "observed_qualification": _observed_fields(trace, (
                    "query_text", "query_origin", "relation", "reference_body_query",
                    "query_terms", "exact_terms", "bound_subjects", "retrieval_anchors",
                    "matched_terms", "body_matched_terms", "matched_term_count", "match_ratio",
                    "missing_exact_terms", "missing_parent_exact_terms",
                    "heading_context_used", "table_context_used", "reference_visible_span",
                    "lexical_score", "qualification_route", "admission_only", "context_only",
                )),
                "literal_context_admission": deepcopy(trace.get("literal_context_admission")),
            })
            if len(outcomes) >= _INTERNAL_DIAGNOSTIC_LIMIT:
                break
        if len(outcomes) >= _INTERNAL_DIAGNOSTIC_LIMIT:
            break
    return {
        "planned_query_ids": [
            str(item.query_id) for item in plan.queries[:_INTERNAL_DIAGNOSTIC_LIMIT]
        ],
        "retrieved_candidates": rows,
        "qualification_outcomes": outcomes,
    }
