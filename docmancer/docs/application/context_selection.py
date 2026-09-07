"""Selection accounting for retrieval-only documentation context."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from typing import Any, Iterable, Mapping

from docmancer.docs.domain.answer_units import _subject_present, best_local_proof, extract_answer_units
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows
from docmancer.docs.domain.context_windows import source_local_span
from docmancer.docs.domain.project_answer_contract import ProofObligation


def component_obligations(contract: Iterable[Mapping[str, Any]]) -> tuple[ProofObligation, ...]:
    """Decode only semantic obligations supplied by the mandatory query contract."""
    obligations = []
    names = {field.name for field in fields(ProofObligation)}
    for item in contract:
        if not isinstance(item, Mapping) or item.get("mandatory") is False:
            continue
        values = {key: value for key, value in item.items() if key in names}
        values.update(obligation_id=item.get("component_id"), kind=item.get("obligation_kind"))
        if not values.get("obligation_id") or not values.get("kind") or not values.get("subject"):
            continue
        try:
            obligations.append(ProofObligation(**values))
        except (TypeError, ValueError):
            continue
    return tuple(obligations)


def component_witnesses(
    source: Mapping[str, Any], obligations: Iterable[ProofObligation],
) -> dict[str, str]:
    """Recompute local semantic witnesses, without creating query attribution."""
    if not obligations:
        return {}
    original = source.get("_qualification_candidate", source)
    identity = original.get("project_identity")
    expected = source.get("_expected_project_identity")
    if (
        original.get("source_class") != "project_doc" or not identity
        or (expected and identity != expected) or original.get("stale")
        or original.get("freshness", "current") != "current"
        or original.get("index_freshness", "synchronized") != "synchronized"
        or original.get("risk_flags") or original.get("instruction_risk_flags")
        or not lifecycle_allows(original, source.get("_lifecycle_intent", "current"))
    ):
        return {}
    text = next((value for value in (
        source.get("snippet"), source.get("content"), source.get("display_text"),
    ) if isinstance(value, str)), "")
    # Hidden headings, rescue tags, and prior assignments are not semantic proof.
    visible_source = {
        "path": source.get("path_or_url", source.get("path")),
        "heading_path": source.get("section", source.get("heading_path")),
        "authority": source.get("authority"), "project_identity": identity,
        "lifecycle_status": original.get("lifecycle_status"),
    }
    units = extract_answer_units(text, include_soft_wrapped_prose=True)
    # Inventory recognition cannot borrow its owner from metadata or a generic
    # public-tool fallback. A heading alone is never an answer proposition.
    return {
        obligation.obligation_id: match[0].text
        for obligation in obligations
        if (match := best_local_proof(obligation, tuple(
            unit for unit in units
            if unit.proposition and (
                obligation.kind != "inventory"
                or _subject_present(obligation, unit.text)
            )
        ), source=visible_source)) is not None
    }


@dataclass(frozen=True, slots=True)
class ContextSelectionDecision:
    selected_evidence_ids: tuple[str, ...]
    covered_query_ids: tuple[str, ...]
    missing_query_ids: tuple[str, ...]

    @property
    def query_coverage(self) -> str:
        return "full" if self.covered_query_ids and not self.missing_query_ids else "partial"


@dataclass(frozen=True, slots=True)
class ComponentCoverageDecision:
    mandatory_component_ids: tuple[str, ...]
    covered_component_ids: tuple[str, ...]
    missing_component_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    unresolved_residue: tuple[str, ...]
    status: str

    def as_payload(self) -> dict[str, object]:
        return {
            "mandatory_component_ids": list(self.mandatory_component_ids),
            "covered_component_ids": list(self.covered_component_ids),
            "missing_component_ids": list(self.missing_component_ids),
            "evidence_ids": list(self.evidence_ids),
            "unresolved_residue": list(self.unresolved_residue),
            "status": self.status,
            "recognized_component_status": (
                "full" if self.mandatory_component_ids and not self.missing_component_ids
                else "partial" if self.covered_component_ids else "unavailable"
            ),
        }


def component_coverage_decision(
    component_contract: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
    visible_sources: Iterable[Mapping[str, Any]],
    *, unresolved_residue: Iterable[str] = (), component_scope_complete: bool = True,
) -> ComponentCoverageDecision:
    """Account only for canonical witnesses that survived final projection."""
    component_contract = tuple(component_contract)
    visible_sources = tuple(visible_sources)
    assignments = tuple(assignments)
    obligations = component_obligations(component_contract)
    semantic_ids = {
        str(item.get("component_id") or "") for item in component_contract
        if item.get("obligation_kind")
    }
    mandatory = tuple(dict.fromkeys(
        str(item.get("component_id") or "") for item in component_contract
        if str(item.get("component_id") or "")
    ))
    evidence_by_component: dict[str, str] = {}
    for source in visible_sources:
        original = source.get("_qualification_candidate", source)
        for assignment in visible_assignments(original, source, assignments):
            component_id = str(assignment.get("requirement_id") or "")
            if component_id in mandatory and component_id not in semantic_ids:
                evidence_by_component[component_id] = str(assignment.get("evidence_id") or "")
    for source in visible_sources:
        if not source.get("evidence_id"):
            continue
        for component_id in component_witnesses(source, obligations):
            evidence_by_component[component_id] = str(source.get("evidence_id") or "")
    covered = tuple(value for value in mandatory if value in evidence_by_component)
    missing = tuple(value for value in mandatory if value not in evidence_by_component)
    residue = tuple(dict.fromkeys(str(value) for value in unresolved_residue if str(value)))
    if not component_scope_complete:
        residue = (*residue, "unverified_original_component_scope")
    status = "full" if mandatory and not missing and not residue else "partial" if covered else "unavailable"
    return ComponentCoverageDecision(
        mandatory, covered, missing,
        tuple(dict.fromkeys(evidence_by_component[value] for value in covered)),
        residue, status,
    )


def context_selection_decision(
    sources: Iterable[Mapping[str, Any]], requested_query_ids: Iterable[str],
) -> ContextSelectionDecision:
    selected = tuple(str(source.get("evidence_id") or "") for source in sources)
    covered_set = qualified_query_ids(sources)
    requested = tuple(dict.fromkeys(str(value) for value in requested_query_ids if value))
    return ContextSelectionDecision(
        selected_evidence_ids=selected,
        covered_query_ids=tuple(value for value in requested if value in covered_set),
        missing_query_ids=tuple(value for value in requested if value not in covered_set),
    )


def select_context_candidates(priority_groups: Iterable[Iterable[Iterable[Any]]]) -> list[Any]:
    """Give each query lane one opportunity before taking second candidates."""
    lanes = [list(lane) for group in priority_groups for lane in group if lane]
    selected: list[Any] = []
    while any(lanes):
        for lane in lanes:
            if lane:
                selected.append(lane.pop(0))
    return selected


def visible_assignments(
    original: Mapping[str, Any], projected: Mapping[str, Any],
    assignments: Iterable[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Retain assignment identity after verifying its source-local occurrence.

    Equal hashes identify equal text, not interchangeable sources, offsets or
    requirements. Coverage must consume these verified assignments, not hashes.
    """
    if not isinstance(original, Mapping):
        return ()
    source_ids = {
        str(original.get(key) or "") for key in ("stable_id", "stable_chunk_id", "evidence_id")
        if original.get(key)
    }
    raw_text = next((value for value in (
        original.get("code"), original.get("snippet"), original.get("content"),
        original.get("display_text"),
    ) if isinstance(value, str) and value), "")
    visible_text = str(projected.get("snippet") or "")
    visible_span = source_local_span(
        raw_text, visible_text, source_line_start=original.get("line_start"),
        line_start=projected.get("line_start"), line_end=projected.get("line_end"),
    )
    if visible_span is None:
        return ()
    source_start = original.get("char_start")
    visible: list[Mapping[str, Any]] = []
    for assignment in assignments:
        if not isinstance(assignment, Mapping) or str(assignment.get("evidence_id") or "") not in source_ids:
            continue
        digest = str(assignment.get("projected_content_hash") or "")
        start, end = assignment.get("unit_char_start"), assignment.get("unit_char_end")
        if start is None and end is None:
            start, end = assignment.get("char_start"), assignment.get("char_end")
            if source_start is not None:
                if any(type(value) is not int for value in (source_start, start, end)):
                    continue
                start, end = start - source_start, end - source_start
        if digest and type(start) is int and type(end) is int and 0 <= start < end <= len(raw_text):
            witness = raw_text[start:end]
            if (visible_span[0] <= start < end <= visible_span[1]
                    and hashlib.sha256(witness.encode("utf-8")).hexdigest() == digest):
                visible.append(assignment)
    return tuple(visible)


def visible_assignment_hashes(
    original: Mapping[str, Any], projected: Mapping[str, Any],
    assignments: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Diagnostic text fingerprints; never use these to recover requirement IDs."""
    return tuple(dict.fromkeys(
        str(item["projected_content_hash"])
        for item in visible_assignments(original, projected, assignments)
    ))


def bind_visible_assignments(
    original: Mapping[str, Any], projected: Mapping[str, Any],
    assignments: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind a projected variant to exactly the canonical assignments it retains."""
    verified = visible_assignments(original, projected, assignments)
    return {
        **projected,
        "_visible_assignment_hashes": list(dict.fromkeys(
            str(item["projected_content_hash"]) for item in verified
        )),
        "_assigned_requirement_ids": list(dict.fromkeys(
            str(item["requirement_id"]) for item in verified if item.get("requirement_id")
        )),
    }


def qualified_query_ids(sources: Iterable[Mapping[str, Any]]) -> set[str]:
    qualified: set[str] = set()
    for source in sources:
        matches = source.get("retrieval_query_matches") or {}
        qualified.update(
            str(query_id)
            for query_id, trace in matches.items()
            if isinstance(trace, Mapping) and trace.get("qualified") is True
        )
    return qualified


def merge_query_matches(*values: Any) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        for query_id, raw_trace in value.items():
            if not isinstance(raw_trace, Mapping):
                continue
            trace = dict(raw_trace)
            current = merged.get(str(query_id))
            trace_kind = str(trace.get("coverage_kind") or "direct")
            current_kind = str((current or {}).get("coverage_kind") or "direct")
            candidate_key = (
                bool(trace.get("qualified")), trace_kind == "direct",
                float(trace.get("lexical_score") or 0.0),
            )
            current_key = (
                bool((current or {}).get("qualified")), current_kind == "direct",
                float((current or {}).get("lexical_score") or 0.0),
            )
            if current is None or candidate_key > current_key:
                merged[str(query_id)] = trace
            selected = merged[str(query_id)]
            selected["coverage_kinds"] = list(dict.fromkeys(
                kind
                for item in (selected, trace, current)
                if item and item.get("qualified") is True
                for kind in (item.get("coverage_kinds") or (item.get("coverage_kind") or "direct",))
            ))
            derived_from = tuple(dict.fromkeys(
                source_id
                for item in (selected, trace, current)
                if item and item.get("qualified") is True
                for source_id in (
                    *(item.get("derived_from_query_ids") or ()),
                    *([item["derived_from_query_id"]] if item.get("derived_from_query_id") else []),
                )
            ))
            if derived_from:
                selected["derived_from_query_ids"] = list(derived_from)
    return merged


def validate_context_selection_payload(
    payload: Mapping[str, Any], sources: Iterable[Mapping[str, Any]],
    *, snapshot: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[str]:
    coverage = payload.get("query_coverage")
    covered = payload.get("covered_query_ids")
    missing = payload.get("missing_query_ids")
    missing_facets = payload.get("missing_facets")
    facets = payload.get("facets")
    if (
        coverage not in {"full", "partial"}
        or not isinstance(covered, list)
        or not isinstance(missing, list)
        or set(covered).intersection(missing)
        or (coverage == "full") != bool(covered and not missing)
        or not isinstance(missing_facets, list)
        or not isinstance(facets, list)
        or any(
            item.get("status") not in {"covered", "missing", "retrieval_only"}
            or not str(item.get("id") or "").strip()
            or not str(item.get("question") or "").strip()
            or not isinstance(item.get("evidence_ids"), list)
            for item in facets if isinstance(item, Mapping)
        )
        or any(not isinstance(item, Mapping) for item in facets)
        or [item for item in facets if item.get("status") == "missing"] != missing_facets
        or payload.get("coverage_policy") != "retrieval_attribution_only"
        or payload.get("retrieval_coverage") != coverage
        or payload.get("facet_coverage") not in {"none", "partial", "full", "unverified"}
    ):
        return ["docs_context query coverage is inconsistent"]
    evidence_ids = {
        str(source.get("evidence_id") or "") for source in sources
        if str(source.get("evidence_id") or "")
    }
    if any(
        not set(str(value) for value in item.get("evidence_ids") or ()).issubset(evidence_ids)
        for item in facets if isinstance(item, Mapping)
    ):
        return ["docs_context facet evidence requires a visible source"]
    if snapshot is not None:
        for item in facets:
            if not isinstance(item, Mapping) or item.get("status") != "covered":
                continue
            requirement_id = str(item.get("requirement_id") or "")
            if not requirement_id or any(
                requirement_id not in set(
                    ((snapshot.get(str(evidence_id)) or {}).get("source") or {}).get(
                        "_assigned_requirement_ids"
                    ) or ()
                )
                for evidence_id in item.get("evidence_ids") or ()
            ):
                return ["docs_context covered facet requires its canonical assigned witness"]
    return []


__all__ = [
    "ComponentCoverageDecision",
    "ContextSelectionDecision",
    "component_coverage_decision",
    "component_obligations",
    "component_witnesses",
    "context_selection_decision",
    "merge_query_matches",
    "qualified_query_ids",
    "select_context_candidates",
    "visible_assignment_hashes",
    "visible_assignments",
    "bind_visible_assignments",
    "validate_context_selection_payload",
]
