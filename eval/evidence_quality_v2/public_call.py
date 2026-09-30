"""Existing same-call observer, separated from eager self-host gold imports.

Observer moved from run_project_docs_self_host_gate, with an explicit dispatch
injection to preserve that script's existing test seam. Neither entry point
performs another retrieval.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
from unittest.mock import patch

from docmancer.docs.service import LibraryDocsService
from docmancer.docs.application import docs_context_projection
from docmancer.docs.application.model_visible_projection import DOCS_CONTEXT_SOURCE_FIELDS
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.mcp.docs_server import call_docs_tool_payload


def _call_with_snapshot(arguments: dict, service: LibraryDocsService, *, dispatch=None) -> tuple[dict | None, dict]:
    """Observe the public call without replaying retrieval or changing its result."""
    raw_results: list[object] = []
    qualified_sources: list[dict] = []
    snapshots: list[dict] = []
    diagnostics: list[dict] = []
    component_bindings: list[dict] = []
    app = getattr(service, "unified_context", service)
    retrieve = app.get_docs_context
    select = docs_context_projection.context_selection_decision
    validate = context_tools.validate_model_visible_projection
    coverage = docs_context_projection.component_coverage_decision

    def capture_coverage(contract, assignments, sources, **kwargs):
        contract, assignments, sources = tuple(contract), tuple(assignments), tuple(sources)
        decision = coverage(contract, assignments, sources, **kwargs)
        component_bindings.clear()
        for source in sources:
            original = source.get("_qualification_candidate") or {}
            source_ids = {original.get(key) for key in ("stable_id", "stable_chunk_id", "evidence_id") if original.get(key)}
            local_assignments = tuple(item for item in assignments if item.get("evidence_id") in source_ids)
            local = coverage(contract, local_assignments, (source,), **kwargs)
            for component_id in local.covered_component_ids:
                component_bindings.append({
                    "component_id": component_id,
                    "evidence_id": source.get("evidence_id"),
                    "path_or_url": source.get("path_or_url"),
                    "snippet_sha256": hashlib.sha256(str(source.get("snippet") or "").encode()).hexdigest(),
                    "runtime_evidence_ids": list(local.evidence_ids),
                })
        return decision

    def capture_result(*args, **kwargs):
        result = retrieve(*args, **kwargs)
        raw_results.append(result)
        return result

    def capture_selection(sources, requested_query_ids):
        sources = list(sources)
        decision = select(sources, requested_query_ids)
        qualified_sources[:] = deepcopy(sources)
        return decision

    def capture_validation(payload, *, snapshot, **kwargs):
        snapshots.append(deepcopy(snapshot))
        return validate(payload, snapshot=snapshot, **kwargs)

    service._same_call_diagnostics_observer = lambda value: diagnostics.append(deepcopy(value))
    try:
        with (
        patch.object(app, "get_docs_context", capture_result),
        patch.object(docs_context_projection, "context_selection_decision", capture_selection),
        patch.object(context_tools, "validate_model_visible_projection", capture_validation),
        patch.object(docs_context_projection, "component_coverage_decision", capture_coverage),
        ):
            payload = (dispatch or call_docs_tool_payload)("get_docs_context", arguments, service)
    finally:
        del service._same_call_diagnostics_observer
    if isinstance(payload, dict) and diagnostics:
        diagnostics[-1]["component_evidence_bindings"] = component_bindings
        diagnostics[-1]["observer_counts"] = {"retrieval_calls": len(raw_results), "validation_calls": len(snapshots)}
        payload = {**payload, "diagnostics": diagnostics[-1]}
    if len(raw_results) != 1 or len(snapshots) != 1:
        return payload, {}
    snapshot = snapshots[0]
    for bound in snapshot.values():
        bound.pop("qualification", None)
    for source in qualified_sources:
        bound = snapshot.get(str(source.get("evidence_id") or ""))
        public_source = {
            key: value for key, value in source.items()
            if key in DOCS_CONTEXT_SOURCE_FIELDS
        }
        # Optional locators are attached after selection, without altering its
        # evidence. Bind qualification to the exact evidence-bearing fields;
        # _coverage_attribution still checks the whole final source (URI included).
        projected_evidence = {
            key: value for key, value in (bound or {}).get("projected_source", {}).items()
            if key != "source_uri"
        }
        if bound and public_source == projected_evidence:
            bound["qualification"] = source
    return payload, snapshot


