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
) -> list[str]:
    coverage = payload.get("query_coverage")
    covered = payload.get("covered_query_ids")
    missing = payload.get("missing_query_ids")
    if (
        coverage not in {"full", "partial"}
        or not isinstance(covered, list)
        or not isinstance(missing, list)
        or set(covered).intersection(missing)
        or (coverage == "full") != bool(covered and not missing)
    ):
        return ["docs_context query coverage is inconsistent"]
    source_query_ids = qualified_query_ids(sources)
    if not set(covered).issubset(source_query_ids):
        return ["docs_context covered queries require visible source attribution"]
    return []


__all__ = [
    "ContextSelectionDecision",
    "context_selection_decision",
    "merge_query_matches",
    "qualified_query_ids",
    "validate_context_selection_payload",
]
