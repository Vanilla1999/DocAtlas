"""Bounded retrieval-only projection for free-form project documentation queries."""

from __future__ import annotations

from typing import Any

from docmancer.docs.application.context_selection import (
    context_selection_decision,
    merge_query_matches,
    qualified_query_ids,
)
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS,
    INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    MAX_DOCS_SOURCES,
    _docs_source,
    _refresh_estimate,
    _snapshot_entry,
    estimate_projection_tokens,
    project_insufficient,
)


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Project trusted retrieval as context without claiming answer support."""

    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, int] = {}
    per_path: dict[str, int] = {}
    for original in retrieval.get("context_pack") or ():
        if not isinstance(original, dict):
            continue
        if str(original.get("source_class") or "") != "project_doc":
            continue
        if str(original.get("lifecycle_status") or "active") != "active":
            continue
        if str(original.get("freshness") or "current") != "current":
            continue
        if str(original.get("index_freshness") or "synchronized") != "synchronized":
            continue
        if original.get("risk_flags"):
            continue
        project_identity = str(original.get("project_identity") or "").strip()
        if not project_identity:
            continue
        if not qualified_query_ids((original,)):
            continue
        normalized = _docs_source(original)
        if normalized is None or len(normalized["snippet"]) < 40:
            continue
        path = normalized["path_or_url"]
        if per_path.get(path, 0) >= 2:
            continue
        normalized["snippet"] = normalized["snippet"][:1_200].rstrip()
        normalized.update({
            "project_identity": project_identity,
            "line_start": original.get("line_start"),
            "line_end": original.get("line_end"),
            "authority": str(original.get("authority") or "supporting"),
            "scope": str(original.get("doc_scope") or "project"),
            "retrieval_query_ids": list(original.get("retrieval_query_ids") or ()),
            "retrieval_query_matches": dict(original.get("retrieval_query_matches") or {}),
        })
        evidence_id = normalized["evidence_id"]
        if evidence_id in seen_ids:
            existing_index = seen_ids[evidence_id]
            merged_matches = merge_query_matches(
                sources[existing_index].get("retrieval_query_matches"),
                normalized.get("retrieval_query_matches"),
            )
            merged_query_ids = [
                key for key, value in merged_matches.items() if value.get("qualified") is True
            ]
            candidate_sources = [dict(source) for source in sources]
            candidate_sources[existing_index]["retrieval_query_ids"] = merged_query_ids
            candidate_sources[existing_index]["retrieval_query_matches"] = merged_matches
            query_plan = retrieval.get("documentation_query_plan") or {}
            candidate_decision = context_selection_decision(
                candidate_sources, query_plan.get("query_ids") or (),
            )
            if estimate_projection_tokens(
                _payload(candidate_sources, decision=candidate_decision)
            ) <= max_tokens:
                sources = candidate_sources
            continue
        candidate_sources = [*sources, normalized]
        query_plan = retrieval.get("documentation_query_plan") or {}
        candidate_decision = context_selection_decision(
            candidate_sources, query_plan.get("query_ids") or (),
        )
        candidate_payload = _payload(candidate_sources, decision=candidate_decision)
        if estimate_projection_tokens(candidate_payload) > max_tokens:
            continue
        sources = candidate_sources
        snapshot[evidence_id] = _snapshot_entry(original, normalized)
        seen_ids[evidence_id] = len(sources) - 1
        per_path[path] = per_path.get(path, 0) + 1
        if len(sources) >= MAX_DOCS_SOURCES:
            break

    if not sources:
        return project_insufficient(
            kind="docs_context",
            missing=["No safe, current, project-scoped documentation context was retrieved."],
            recommended_next_action=None,
            max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
        ), {}
    query_plan = retrieval.get("documentation_query_plan") or {}
    decision = context_selection_decision(sources, query_plan.get("query_ids") or ())
    return _payload(sources, decision=decision), snapshot


def _payload(sources: list[dict[str, Any]], *, decision: Any = None) -> dict[str, Any]:
    payload = {
        "status": "ok",
        "kind": "docs_context",
        "context_available": True,
        "answer_supported": False,
        "answer_available": False,
        "support_status": "retrieval_only",
        "query_coverage": decision.query_coverage if decision else "partial",
        "covered_query_ids": list(decision.covered_query_ids) if decision else [],
        "missing_query_ids": list(decision.missing_query_ids) if decision else [],
        "sources": sources,
        "edit_ready": False,
        "investigation_allowed": True,
        "safe_to_answer": False,
        "safe_to_answer_from_sources": True,
        "required_next_step": "answer_from_returned_context",
        "agent_instruction": (
            "Answer only claims directly grounded in the returned sources, cite their paths, "
            "and do not claim that the context is complete. Never use this retrieval-only "
            "result to authorize an edit."
        ),
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    return payload
