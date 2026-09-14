"""Finalized retrieval-only documentation projection with bounded recovery metadata."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import _docs_context_projection_core as _core
from ._docs_context_payload import _payload
from .context_quality import context_quality
from .context_selection import (
    component_coverage_decision,
    component_obligations,
    component_witnesses,
    context_selection_decision,
)
from .model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS,
    INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    _refresh_estimate,
)
from .source_continuation import (
    attach_docs_context_read_next,
    attach_source_continuation_locators,
    docs_context_read_next_cost,
    prepare_docs_context_read_next,
)

# Preserve the established helper surface used by focused production tests.
_expand_selected_snippets = _core._expand_selected_snippets
_facet_aware_candidates = _core._facet_aware_candidates
_focused_line_range = _core._focused_line_range
_focused_snippet = _core._focused_snippet
_qualified_fragments = _core._qualified_fragments
_requalify_visible_source = _core._requalify_visible_source


def _final_sources(snapshot: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for public in payload.get("sources") or ():
        bound = snapshot.get(public.get("evidence_id")) if isinstance(public, dict) else None
        projected = bound.get("projected_source") if isinstance(bound, dict) else None
        if isinstance(projected, dict):
            rows.append(projected)
    return tuple(rows)


def _annotate_budget_omissions(
    retrieval: dict[str, Any], coverage: dict[str, Any], assignments: tuple[Any, ...],
) -> list[dict[str, Any]]:
    missing = {str(value) for value in coverage.get("missing_component_ids") or () if value}
    if not missing:
        return []
    plan = retrieval.get("documentation_query_plan") or {}
    obligations = component_obligations(plan.get("_component_contract") or ())
    expected_identity = retrieval.get("project_identity")
    diagnostics = ((retrieval.get("retrieval_diagnostics") or {}).get("docs_context_projection") or {})
    candidates = tuple(item for item in retrieval.get("context_pack") or () if isinstance(item, dict))
    events: list[dict[str, Any]] = []
    for rejection in diagnostics.get("projection_rejections") or ():
        if not isinstance(rejection, dict) or rejection.get("reason") != "token_budget":
            continue
        candidate_id = str(rejection.get("candidate_id") or "")
        original = next(
            (item for item in candidates if _core._internal_candidate_id(item) == candidate_id), None,
        )
        if original is None:
            continue
        component_ids: set[str] = set()
        source_ids = {
            str(original.get(key) or "")
            for key in ("stable_id", "stable_chunk_id", "evidence_id") if original.get(key)
        }
        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue
            requirement = str(assignment.get("requirement_id") or "")
            if requirement in missing and str(assignment.get("evidence_id") or "") in source_ids:
                component_ids.add(requirement)
        probe = {
            **original,
            "snippet": str(original.get("content") or original.get("snippet") or ""),
            "_qualification_candidate": original,
            "_expected_project_identity": expected_identity,
        }
        component_ids.update(component_witnesses(probe, obligations))
        component_ids &= missing
        if component_ids:
            rejection["component_ids"] = sorted(component_ids)
            events.append({"reason": "token_budget", "component_ids": sorted(component_ids)})
    return events


def _strip_legacy_locators(payload: dict[str, Any], snapshot: dict[str, Any]) -> None:
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            continue
        source.pop("source_uri", None)
        bound = snapshot.get(source.get("evidence_id"))
        if isinstance(bound, dict):
            bound.pop("source_uri", None)
            projected = bound.get("projected_source")
            if isinstance(projected, dict):
                projected.pop("source_uri", None)
    _refresh_estimate(payload)


def _finalize_quality(
    retrieval: dict[str, Any], payload: dict[str, Any], snapshot: dict[str, Any],
) -> None:
    plan = retrieval.get("documentation_query_plan")
    if not isinstance(plan, dict):
        plan = {}
    selection = retrieval.get("selection_decision")
    assignments = tuple(
        item for item in ((selection or {}).get("assignments") or ()) if isinstance(item, dict)
    ) if isinstance(selection, dict) else ()
    final_sources = _final_sources(snapshot, payload)
    coverage = component_coverage_decision(
        plan.get("_component_contract") or (), assignments, final_sources,
        unresolved_residue=plan.get("unresolved_parts") or (),
        component_scope_complete=plan.get("component_scope_complete", True),
    ).as_payload()
    omissions = _annotate_budget_omissions(retrieval, coverage, assignments)
    plan["_component_coverage"] = coverage
    plan["_projection_omissions"] = omissions
    retrieval["documentation_query_plan"] = plan
    payload["context_quality"] = context_quality(
        sources=payload.get("sources") or (), component_coverage=coverage, omissions=omissions,
    )
    payload.setdefault("read_next", [])
    _refresh_estimate(payload)


def _run_core(
    *, retrieval: dict[str, Any], max_tokens: int,
    selection_diagnostics: dict[str, Any] | None, allow_context_hints: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _core.project_docs_context(
        retrieval=retrieval,
        max_tokens=max_tokens,
        selection_diagnostics=selection_diagnostics,
        _allow_context_hints=allow_context_hints,
    )


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
    _allow_context_hints: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Finalize visible evidence, quality and at most one registered recovery target."""
    packet_max = min(DOCS_CONTEXT_MAX_TOKENS, max_tokens)
    payload, snapshot = _run_core(
        retrieval=retrieval, max_tokens=packet_max,
        selection_diagnostics=selection_diagnostics, allow_context_hints=_allow_context_hints,
    )
    _strip_legacy_locators(payload, snapshot)
    _finalize_quality(retrieval, payload, snapshot)

    root = str(retrieval.get("_source_continuation_project_root") or "")
    target: dict[str, Any] | None = None
    target_source: dict[str, Any] | None = None
    if root:
        target, target_source = prepare_docs_context_read_next(payload, snapshot, retrieval, root=root)

    target_budget = (
        min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, packet_max)
        if payload.get("status") == "insufficient_evidence" else packet_max
    )
    if target is not None and target_source is not None:
        if attach_docs_context_read_next(payload, target, max_tokens=target_budget):
            snapshot["__read_next__"] = {"source": deepcopy(target_source)}
        elif payload.get("status") != "insufficient_evidence":
            reserve = docs_context_read_next_cost(payload, target)
            evidence_budget = max(1, packet_max - reserve)
            if evidence_budget < packet_max:
                payload, snapshot = _run_core(
                    retrieval=retrieval, max_tokens=evidence_budget,
                    selection_diagnostics=selection_diagnostics,
                    allow_context_hints=_allow_context_hints,
                )
                _strip_legacy_locators(payload, snapshot)
                _finalize_quality(retrieval, payload, snapshot)
                target, target_source = prepare_docs_context_read_next(
                    payload, snapshot, retrieval, root=root,
                )
                if (
                    target is not None and target_source is not None
                    and attach_docs_context_read_next(payload, target, max_tokens=packet_max)
                ):
                    snapshot["__read_next__"] = {"source": deepcopy(target_source)}
        if target is not None and not payload.get("read_next"):
            quality = payload.get("context_quality") or {}
            reasons = list(quality.get("reasons") or ())
            if "budget_limited" not in reasons and len(reasons) < 2:
                reasons.append("budget_limited")
                quality["reasons"] = reasons
                payload["context_quality"] = quality
                _refresh_estimate(payload)

    if root:
        attach_source_continuation_locators(payload, snapshot, root=root, max_tokens=packet_max)
    return payload, snapshot


__all__ = [
    "project_docs_context", "_expand_selected_snippets", "_facet_aware_candidates",
    "_focused_line_range", "_focused_snippet", "_qualified_fragments",
    "_requalify_visible_source",
]
