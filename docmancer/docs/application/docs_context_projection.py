"""Source-native documentation projection with final provenance checks."""
from __future__ import annotations

from typing import Any

from .context_query_probes import authoritative_queries, independent_query_probes, literal_query_probe
from .context_selection import merge_query_matches
from .experimental_context_finalization import (
    capture_experimental_context, project_native_rank_context, recheck_experimental_context,
)
from .projection_decision_trace import ProjectionFlowTrace
from .source_continuation import attach_source_continuation_locators
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.original_body_discovery import experimental_context_max_tokens


def _requalify_visible_source(source: dict[str, Any], *, query_text: dict[str, str]) -> dict[str, Any]:
    visible_text = "\n".join(str(source.get(key) or "") for key in ("path_or_url", "section", "snippet"))
    matches: dict[str, dict[str, Any]] = {}
    planned = authoritative_queries(source.get("_independent_query_plan") or {})
    incoming = independent_query_probes(source, source.get("_independent_query_plan") or {})
    for query_id, query in planned.items():
        if query_text.get(query_id) != query["text"]:
            continue
        trace = incoming.get(query_id) or {}
        qualification = qualify_evidence(
            literal_query_probe(query), query_id=str(query_id), visible_text=visible_text,
            evidence_text=str(source.get("snippet") or ""), catalog_role=str(source.get("catalog_role") or ""),
            candidate={**source.get("_qualification_candidate", {}), **source},
            expected_project_identity=source.get("_expected_project_identity"),
            lifecycle_intent=source.get("_lifecycle_intent", "current"), authoritative_query=query,
        )
        qualified_trace = dict(qualification.trace)
        if query_id == "query-original" and (
            trace.get("admission_only") or trace.get("query_text") != query["text"]
            or trace.get("query_origin") != "original" or trace.get("relation") != "direct"
            or trace.get("public_parent_query_id") or trace.get("derived_from_query_id")
            or trace.get("derived_from_query_ids")
        ):
            qualified_trace["admission_only"] = True
        matches = merge_query_matches(matches, {str(query_id): qualified_trace})
    return {**source, "retrieval_query_matches": matches,
            "retrieval_query_ids": [key for key, trace in matches.items() if trace.get("qualified") is True]}


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int | None = None,
    selection_diagnostics: dict[str, Any] | None = None, _allow_context_hints: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cap = experimental_context_max_tokens()
    packet_max = min(max_tokens, cap) if max_tokens is not None and cap is not None else cap or max_tokens
    payload, snapshot = project_native_rank_context(
        retrieval=retrieval, max_tokens=packet_max,
        selection_diagnostics=selection_diagnostics, _allow_context_hints=_allow_context_hints,
    )
    flow = ProjectionFlowTrace(retrieval)
    flow.boundary("core.output", payload, snapshot)
    capture_experimental_context(retrieval, payload, snapshot)
    root = str(retrieval.get("_source_continuation_project_root") or "")
    if root:
        attach_source_continuation_locators(payload, snapshot, root=root, max_tokens=packet_max)
    flow.boundary("decoration.output", payload, snapshot)
    return recheck_experimental_context(payload, snapshot, retrieval, restore_native=False)
