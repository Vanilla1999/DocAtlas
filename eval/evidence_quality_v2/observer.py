"""Test-only extended collector around the existing same-call observer.

Use only with public/synthetic fixtures. It never modifies public payloads,
repeats retrieval, or installs a public debug parameter. Stage boundary names are
literal: the service's selected query window mixes caps/budget/lifecycle, so a
loss inside that boundary is not automatically called a relevance rejection.
"""
from __future__ import annotations
from copy import deepcopy
from unittest.mock import patch
from typing import Any

from eval.evidence_quality_v2.trace import bounded_completeness, source_span


def observe_call(service: Any, arguments: dict) -> tuple[dict, dict]:
    import scripts.run_project_docs_self_host_gate as gate
    from docmancer.docs.application import _project_docs_service_part03 as project
    from docmancer.docs.application import docs_context_projection as projection
    from docmancer.docs.interfaces.mcp import context_tools

    stages: dict[str, list] = {key: [] for key in (
        "retrieved_candidates", "query_window", "rankings", "qualified_fragments", "expansions", "projector_inputs", "projector_outputs")}
    app = getattr(service, "unified_context", service)
    projector_fn = context_tools.project_docs_context
    diagnostics_fn = project._retrieval_stage_diagnostics
    query_fn = service.project_docs.query_project_docs
    rank_fn = projection._facet_aware_candidates
    fragments_fn = projection._qualified_fragments
    expand_fn = projection._expand_selected_snippets

    def capture_projector(*, retrieval, **kwargs):
        # This is the actual prepared projector input after MCP normalization,
        # not a reconstruction from the earlier application dataclass.
        stages["projector_inputs"].append(deepcopy(retrieval))
        payload, snapshot = projector_fn(retrieval=retrieval, **kwargs)
        stages["projector_outputs"].append({"payload":deepcopy(payload),"snapshot":deepcopy(snapshot)})
        return payload, snapshot

    def capture_diagnostics(plan, candidates):
        # The real function is still called exactly once, with unchanged inputs.
        result = diagnostics_fn(plan, candidates)
        spans = [source_span(value) for value in candidates]
        outcomes_total = sum(sum(isinstance(value, dict) for value in ((c.metadata or {}).get("retrieval_query_matches") or {}).values()) for c in candidates)
        stages["retrieved_candidates"].append({"complete": True, "sources": spans,
            "candidate_count": len(candidates), "qualification_outcome_count": outcomes_total,
            "bounded_candidates": bounded_completeness(len(result["retrieved_candidates"]), len(candidates)),
            "bounded_outcomes": bounded_completeness(len(result["qualification_outcomes"]), outcomes_total),
            "planned_query_ids": [lookup.query_id for lookup in plan.queries]})
        return result

    def capture_query(*args, **kwargs):
        result = query_fn(*args, **kwargs)
        stages["query_window"].append({"complete": True, "sources": [source_span(row) for row in result],
                                      "transition": "lifecycle+deduplication+candidate_cap+token_budget"})
        return result

    def capture_rank(candidates, **kwargs):
        inputs = deepcopy(candidates)
        result = rank_fn(candidates, **kwargs)
        stages["rankings"].append({"complete": True, "before": [source_span(row) for row in inputs],
                                  "after": [source_span(row) for row in result]})
        return result

    def capture_fragments(source, **kwargs):
        before = deepcopy(source)
        result = fragments_fn(source, **kwargs)
        stages["qualified_fragments"].append({"complete": True, "before": source_span(before),
            "after": [source_span(row) for row in result]})
        return result

    def capture_expand(sources, **kwargs):
        before = deepcopy(sources)
        result = expand_fn(sources, **kwargs)
        stages["expansions"].append({"complete": True, "before": [source_span(row) for row in before],
                                    "after": [source_span(row) for row in result]})
        return result

    with (patch.object(context_tools, "project_docs_context", capture_projector),
          patch.object(project, "_retrieval_stage_diagnostics", capture_diagnostics),
          patch.object(service.project_docs, "query_project_docs", capture_query),
          patch.object(projection, "_facet_aware_candidates", capture_rank),
          patch.object(projection, "_qualified_fragments", capture_fragments),
          patch.object(projection, "_expand_selected_snippets", capture_expand)):
        observed, snapshot = gate._call_with_snapshot(arguments, service)
    payload = dict(observed or {})
    bounded = payload.pop("diagnostics", {})
    record = {"schema_version": "evidence-quality-same-call-v2", "stages": stages,
              "bounded_diagnostics": bounded, "snapshot": snapshot,
              "final": {"complete": True, "sources": deepcopy(payload.get("sources") or [])},
              "observer_counts": bounded.get("observer_counts", {}),
              "unobserved_transitions": ["query_window: distinguish lifecycle, cap and budget only with additional evidence"]}
    return payload, record
