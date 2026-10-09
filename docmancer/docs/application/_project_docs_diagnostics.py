"""Private bounded diagnostics for project-document retrieval stages."""
from __future__ import annotations

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


def _retrieval_stage_diagnostics(
    plan: DocumentationQueryPlan, candidates: list[Any],
) -> dict[str, Any]:
    rows = []
    outcomes = []
    for chunk in candidates[:_INTERNAL_DIAGNOSTIC_LIMIT]:
        identity = _diagnostic_candidate_id(chunk)
        if identity:
            rows.append(identity)
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
