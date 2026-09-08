"""Retrieval-only context payload and facet attribution projection."""
from __future__ import annotations

from typing import Any

from .context_selection import qualified_query_ids
from .model_visible_projection import _refresh_estimate


def _payload(
    sources: list[dict[str, Any]], *, decision: Any = None,
    query_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_queries = {
        str(item.get("query_id") or ""): item
        for item in (query_plan or {}).get("queries") or ()
        if isinstance(item, dict)
    }
    context_only = bool(query_plan.get("broad_context_only"))
    covered_query_ids = set(decision.covered_query_ids if decision else ())
    assigned_requirement_ids = set(
        str(value) for value in query_plan.get("assigned_requirement_ids") or ()
    )
    facets = []
    for query_id, item in plan_queries.items():
        facet_id = str(item.get("facet_id") or "")
        if not facet_id:
            continue
        retrieved = any(
            query_id in qualified_query_ids((source,)) for source in sources
        )
        requirement_id = str(item.get("requirement_id") or "")
        assigned_evidence_ids = [
            str(source.get("evidence_id") or "")
            for source in sources
            if requirement_id
            and requirement_id in set(source.get("_assigned_requirement_ids") or ())
            and query_id in qualified_query_ids((source,))
        ]
        proved = bool(requirement_id and requirement_id in assigned_requirement_ids and assigned_evidence_ids)
        status = (
            "covered" if retrieved and proved and not context_only else
            "retrieval_only" if retrieved else
            "missing"
        )
        retrieved_evidence_ids = [
            str(source.get("evidence_id") or "")
            for source in sources
            if query_id in qualified_query_ids((source,))
        ]
        evidence_ids = assigned_evidence_ids if status == "covered" else retrieved_evidence_ids
        facets.append({
            "id": facet_id,
            "requirement_id": requirement_id or None,
            "question": str(item.get("text") or query_id),
            "status": status,
            "evidence_ids": evidence_ids,
        })
    grouped_facets: dict[str, dict[str, Any]] = {}
    status_rank = {"missing": 0, "retrieval_only": 1, "covered": 2}
    for facet in facets:
        current = grouped_facets.get(facet["id"])
        if current is None:
            grouped_facets[facet["id"]] = dict(facet)
            continue
        current["evidence_ids"] = list(dict.fromkeys((
            *current["evidence_ids"], *facet["evidence_ids"],
        )))
        if status_rank[facet["status"]] > status_rank[current["status"]]:
            current["status"] = facet["status"]
            current["question"] = facet["question"]
            current["requirement_id"] = facet["requirement_id"]
    facets = list(grouped_facets.values())
    covered_facets = [item for item in facets if item["status"] == "covered"]
    missing_facets = [item for item in facets if item["status"] == "missing"]
    facet_coverage = (
        "unverified" if context_only or not facets else
        "full" if len(covered_facets) == len(facets) else
        "partial" if covered_facets else
        "none"
    )
    public_sources = [
        {
            key: value for key, value in source.items()
            if key not in {
                "retrieval_query_ids", "retrieval_query_matches",
                "_assigned_requirement_ids", "_visible_assignment_hashes", "catalog_role",
                "_qualification_candidate", "_expected_project_identity", "_lifecycle_intent",
            }
        }
        for source in sources
    ]
    payload = {
        "status": "ok",
        "kind": "docs_context",
        "context_status": "ready",
        "context_available": True,
        "answer_supported": False,
        "answer_available": False,
        "support_status": "retrieval_only",
        "answer_policy": "cite_only",
        "coverage_policy": "retrieval_attribution_only",
        "query_coverage": decision.query_coverage if decision else "partial",
        "retrieval_coverage": decision.query_coverage if decision else "partial",
        "facet_coverage": facet_coverage,
        "covered_query_ids": list(decision.covered_query_ids) if decision else [],
        "missing_query_ids": list(decision.missing_query_ids) if decision else [],
        "missing_facets": missing_facets,
        "facets": facets,
        "sources": public_sources,
        "edit_ready": False,
        "investigation_allowed": True,
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    return payload
