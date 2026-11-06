"""Opt-in same-call diagnostics kept outside the public context handler."""
from __future__ import annotations

import json
import sys
from typing import Any
from uuid import uuid4

from docmancer.docs.application.projection_decision_trace import same_call_projection_observation
from docmancer.docs.application.query_trace import current_request_id, query_trace_enabled
from docmancer.docs.service import LibraryDocsService


def _observe_same_call_diagnostics(
    service: LibraryDocsService, raw: dict[str, Any], projection: dict[str, Any],
    selection_trace: dict[str, Any], *, delivery_blocked: bool = False,
) -> None:
    """Send bounded internals to an in-process observer, never the MCP payload."""
    if not query_trace_enabled():
        return
    observer = getattr(service, "_same_call_diagnostics_observer", None)
    if not callable(observer):
        try:
            observation = same_call_projection_observation(raw, projection, delivery_blocked=delivery_blocked)
            sys.stderr.write(json.dumps({
                "event": "docatlas_query_trace", "request_id": current_request_id() or uuid4().hex,
                "projection_observation": observation,
            }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return
    ingestion = raw.get("ingestion_diagnostics") or {}
    project = ingestion.get("project") if isinstance(ingestion, dict) else {}
    service_trace = (
        project.get("same_call_pipeline") if isinstance(project, dict) else None
    ) or {}
    projection_trace = ((raw.get("retrieval_diagnostics") or {}).get(
        "docs_context_projection"
    ) or {})
    coverage = selection_trace.get("component_coverage")
    outcomes = list(service_trace.get("qualification_outcomes") or ())[:32]
    retrieved = list(service_trace.get("retrieved_candidates") or ())[:32]
    ranked = list(projection_trace.get("ranked_candidate_ids") or ())[:32]
    variants = list(projection_trace.get("considered_variants") or ())[:32]
    final_ids = list(projection_trace.get("final_visible_evidence_ids") or ())[:3]
    diagnostics = {
        "runtime_component_coverage": coverage if isinstance(coverage, dict) else {"status": "unclassified"},
        "stage_status": {
            "planning": "observed" if service_trace.get("planned_query_ids") is not None else "unclassified",
            "retrieval": "observed" if service_trace.get("retrieved_candidates") is not None else "unclassified",
            "qualification": "observed" if service_trace.get("qualification_outcomes") is not None else "unclassified",
            "ranking": "not_reached" if delivery_blocked else "observed" if projection_trace.get("ranked_candidate_ids") is not None else "unclassified",
            "projection": "not_reached" if delivery_blocked else "observed" if projection_trace.get("considered_variants") is not None else "unclassified",
            "coverage": "not_reached" if delivery_blocked else "observed" if isinstance(coverage, dict) else "unclassified",
            "delivery": "blocked_before_projection" if delivery_blocked else "projected",
        },
    }
    if delivery_blocked:
        # Observe the decision already enforced above. The private callback
        # cannot retry retrieval, bypass the veto or alter the public payload.
        decision = raw.get("delivery_decision")
        diagnostics["delivery_decision"] = {
            "deliverable": False,
            "reason_code": str(
                (decision.get("reason_code") if isinstance(decision, dict) else None)
                or projection.get("reason_code") or "unspecified_delivery_veto"
            )[:120],
        }
    if service_trace.get("planned_query_ids") is not None:
        diagnostics["planned_query_ids"] = list(service_trace.get("planned_query_ids") or ())[:32]
    if service_trace.get("retrieved_candidates") is not None:
        diagnostics.update({
            "retrieved_candidates": retrieved,
            "retrieved_candidate_ids": [
                str(item.get("stable_chunk_id") or item.get("document_id") or "")
                for item in retrieved if isinstance(item, dict)
            ],
        })
    if service_trace.get("qualification_outcomes") is not None:
        diagnostics.update({
            "qualification_outcomes": outcomes,
            "qualification_rejections": [
                str(item.get("stable_chunk_id") or item.get("document_id") or "")
                for item in outcomes
                if isinstance(item, dict) and item.get("outcome") == "rejected"
            ],
            "pre_projection_qualified_ids": list(dict.fromkeys(
                str(item.get("stable_chunk_id") or item.get("document_id") or "")
                for item in outcomes
                if isinstance(item, dict) and item.get("outcome") == "qualified"
            ))[:32],
        })
    if projection_trace.get("ranked_candidate_ids") is not None:
        diagnostics["ranked_candidate_ids"] = ranked
    if projection_trace.get("considered_variants") is not None:
        diagnostics.update({
            "selected_candidate_ids": list(dict.fromkeys(
                str(item.get("candidate_id") or "") for item in variants
                if isinstance(item, dict) and item.get("candidate_id")
            ))[:32],
            "considered_variants": variants,
            "projection_rejections": list(projection_trace.get("projection_rejections") or ())[:32],
            "final_visible_evidence_ids": final_ids,
        })
    try:
        diagnostics["projection_observation"] = same_call_projection_observation(
            raw, projection, delivery_blocked=delivery_blocked,
        )
        observer(diagnostics)
    except Exception:
        # Debug observers cannot alter the validated public MCP result.
        return
