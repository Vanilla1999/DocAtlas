"""Selection accounting for retrieval-only documentation context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ContextSelectionDecision:
    selected_evidence_ids: tuple[str, ...]
    covered_query_ids: tuple[str, ...]
    missing_query_ids: tuple[str, ...]

    @property
    def query_coverage(self) -> str:
        return "full" if self.covered_query_ids and not self.missing_query_ids else "partial"


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
            candidate_key = (
                bool(trace.get("qualified")), float(trace.get("lexical_score") or 0.0),
            )
            current_key = (
                bool((current or {}).get("qualified")), float((current or {}).get("lexical_score") or 0.0),
            )
            if current is None or candidate_key > current_key:
                merged[str(query_id)] = trace
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
    "ContextSelectionDecision",
    "context_selection_decision",
    "merge_query_matches",
    "qualified_query_ids",
    "validate_context_selection_payload",
]
