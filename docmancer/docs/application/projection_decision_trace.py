"""Bounded private projector decisions. These events are neither context nor proof."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from .query_trace import query_trace_enabled

MAX_DECISION_EVENTS = 128


def _key(*parts: Any) -> str:
    # Hash only bounded identity material; never expose paths, prose or queries.
    raw = json.dumps([str(part or '')[:2048] for part in parts], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class ProjectionDecisionTrace:
    """One request/attempt's event log; no global state or selection side effects."""

    def __init__(self, diagnostics: dict[str, Any], *, enabled: bool | None = None) -> None:
        self.enabled = query_trace_enabled() if enabled is None else enabled
        if not self.enabled:
            return
        self.state: dict[str, Any] = {
            'schema_version': 1, 'events': [], 'counts': {},
            'variant_attempts': 0, 'omitted_events': 0,
            'selection_events_omitted': 0,
        }
        diagnostics['decision_trace'] = self.state

    def record(
        self, stage: str, decision: str, reason: str,
        candidate: Any, variant: Any = None, *,
        budget_tokens: int | None = None, previous: Any = None,
    ) -> None:
        """Record an executed branch, not an inference from missing final text."""
        if not self.enabled:
            return
        key = f'{stage}:{reason}'
        counts = self.state['counts']
        counts[key] = counts.get(key, 0) + 1
        if len(self.state['events']) >= MAX_DECISION_EVENTS:
            self.state['omitted_events'] += 1
            self.state['selection_events_omitted'] += int(stage == 'selection')
            return
        candidate = candidate if isinstance(candidate, dict) else {}
        variant = variant if isinstance(variant, dict) else {}
        identity = _key(candidate.get('project_identity'),
                        candidate.get('stable_id') or candidate.get('stable_chunk_id')
                        or candidate.get('evidence_id') or candidate.get('path') or candidate.get('source'))
        def variant_key(value: dict[str, Any]) -> str:
            return _key(identity, value.get('evidence_id'), value.get('line_start'),
                        value.get('line_end'), value.get('snippet'))
        event = {'stage': stage, 'decision': decision, 'reason': reason,
                 'candidate_key': identity, 'variant_key': variant_key(variant)}
        if budget_tokens is not None:
            event['budget_tokens'] = int(budget_tokens)
        if isinstance(previous, dict):
            event['previous_variant_key'] = variant_key(previous)
        self.state['events'].append(event)


_PREVIEW_LIMIT = 32
_MISSING = object()


def _scalar(value: Any) -> Any:
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        return value[:512]
    return {"observed_type": type(value).__name__}


def _fields(value: Any, names: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"observation": "malformed", "observed_type": type(value).__name__}
    return {name: _scalar(value[name]) for name in names if name in value}


def _preview(value: Any, *, names: tuple[str, ...] | None = None,
             producer_count: Any = _MISSING) -> dict[str, Any]:
    """Distinguish the received carrier from any unknown earlier omissions."""
    if value is _MISSING:
        return {"observation": "missing"}
    if value is None:
        return {"observation": "null"}
    if not isinstance(value, (list, tuple)):
        return {"observation": "malformed", "observed_type": type(value).__name__}
    items = [_fields(row, names) if names is not None else _scalar(row)
             for row in value[:_PREVIEW_LIMIT]]
    known = type(producer_count) is int and producer_count >= len(value)
    return {
        "observation": "recorded", "recorded_count": len(value),
        "producer_count": producer_count if known else None,
        "producer_omitted": producer_count - len(value) if known else None,
        "preview_count": len(items), "preview_omitted": len(value) - len(items),
        "items": items,
    }


def record_ranked_candidates(diagnostics: dict[str, Any], candidates: list[Any],
                             candidate_id: Any) -> None:
    """Keep the legacy preview and record the size of this exact ranked list."""
    if not query_trace_enabled():
        return
    ids = [candidate_id(item) for item in candidates[:_PREVIEW_LIMIT]]
    diagnostics["ranked_candidate_ids"] = [value for value in ids if value]
    diagnostics["ranked_observation"] = {"count": len(candidates), "ids": ids}


def record_core_sources(diagnostics: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    """This payload precedes hint restoration and facade finalizers."""
    if not query_trace_enabled():
        return
    ids = [str(source.get("evidence_id") or "") for source in sources[:_PREVIEW_LIMIT]]
    diagnostics["core_source_observation"] = {"count": len(sources), "ids": ids}


def _recorded_ids(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _preview(value)
    return _preview(value.get("ids", _MISSING), producer_count=value.get("count", _MISSING))


def _decision_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _preview(value)
    events = value.get("events", _MISSING)
    omitted = value.get("omitted_events")
    selection_omitted = value.get("selection_events_omitted")
    total = (len(events) + omitted
             if isinstance(events, list) and type(omitted) is int and omitted >= 0 else _MISSING)
    selected = ([row for row in events if isinstance(row, dict) and row.get("stage") == "selection"]
                if isinstance(events, list) else _MISSING)
    selection_total = (len(selected) + selection_omitted if isinstance(selected, list)
                       and type(selection_omitted) is int and selection_omitted >= 0 else _MISSING)
    event_fields = ("stage", "decision", "reason", "candidate_key", "variant_key",
                    "previous_variant_key", "budget_tokens")
    counts = value.get("counts", _MISSING)
    count_rows = ([{"branch": key, "count": count} for key, count in counts.items()]
                  if isinstance(counts, dict) else counts)
    return {
        **_fields(value, ("schema_version", "variant_attempts", "omitted_events", "selection_events_omitted")),
        "branch_counts": _preview(count_rows, names=("branch", "count"),
                                  producer_count=len(count_rows) if isinstance(count_rows, list) else _MISSING),
        "events": _preview(events, names=event_fields, producer_count=total),
        "selection_events": _preview(selected, names=event_fields, producer_count=selection_total),
    }


def _child(value: Any, name: str) -> Any:
    return value.get(name, _MISSING) if isinstance(value, dict) else value


def _attempt_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _preview(value)
    return {
        **_fields(value, ("attempt_kind", "qualified_variants")),
        "ranked_candidates": _recorded_ids(value.get("ranked_observation", _MISSING)),
        "prepared_qualified_variants": _preview(
            value.get("considered_variants", _MISSING), names=("candidate_id", "evidence_id"),
            producer_count=value.get("qualified_variants", _MISSING)),
        "literal_context_admissions": _preview(value.get("literal_context_admissions", _MISSING),
            names=("reason", "query_id", "source_id", "coverage_credit", "qualification_reason")),
        "core_payload_sources": _recorded_ids(value.get("core_source_observation", _MISSING)),
        "decision_trace": _decision_observation(value.get("decision_trace", _MISSING)),
    }


def same_call_projection_observation(
    raw: dict[str, Any], projection: dict[str, Any], *, delivery_blocked: bool,
) -> dict[str, Any]:
    """Copy existing operands after final validation; never rerun a producer."""
    service_trace = _child(_child(_child(raw, "ingestion_diagnostics"), "project"), "same_call_pipeline")
    projection_trace = _child(_child(raw, "retrieval_diagnostics"), "docs_context_projection")
    sources = projection.get("sources", _MISSING)
    return {
        "schema_version": 1, "callback_stage": "after_model_visible_validation",
        "delivery_blocked": delivery_blocked,
        "final_callback": {
            **_fields(projection, ("kind", "status", "context_available", "answer_supported", "answer_available", "edit_ready")),
            "sources": _preview(sources, names=("evidence_id",),
                                producer_count=len(sources) if isinstance(sources, list) else _MISSING),
        },
        "upstream_received": {
            "retrieved_candidates": _preview(_child(service_trace, "retrieved_candidates"),
                names=("stable_chunk_id", "document_id", "source_id", "query_id")),
            "qualification_outcomes": _preview(_child(service_trace, "qualification_outcomes"),
                names=("stable_chunk_id", "document_id", "source_id", "query_id", "outcome", "reason")),
        },
        "returned_core_diagnostics": _attempt_observation(projection_trace),
        "primary_attempt": _attempt_observation(_child(projection_trace, "primary_attempt")),
        "hint_attempt": _attempt_observation(_child(projection_trace, "hint_attempt")),
        "claim_boundary": (
            "Core payloads precede facade finalizers; prepared variants are not accepted sources. "
            "Event keys identify recorded branches, not source text. Unknown upstream omissions "
            "stay unknown; previews and decision-log omissions cannot prove an absent first loss."
        ),
    }
