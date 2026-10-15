"""Bounded private projector decisions. These events are neither context nor proof."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any
from .query_trace import query_trace_enabled

MAX_DECISION_EVENTS = 128
MAX_CONTEXT_FLOW_EVENTS = 256
MAX_CONTEXT_FLOW_SOURCES = 64
MAX_CONTEXT_FLOW_CHARS = 262_144


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


_FLOW_ROW_FIELDS = (
    "evidence_id", "source_key", "source_sha256", "candidate_key",
    "reference_char_start", "reference_char_end", "line_start", "line_end",
    "visible_char_start", "visible_char_end", "visible_span_observation",
    "snippet_sha256", "snippet_characters", "snippet_hash_observation",
)


def _flow_source(candidate: Any) -> dict[str, Any]:
    """Describe declared binding fields, without rereading or authorizing them."""
    if not isinstance(candidate, dict):
        return {"observation": "missing_snapshot"}
    ref = candidate.get("_reference_evidence")
    if not isinstance(ref, dict) or not isinstance(ref.get("source"), dict):
        return {"observation": "missing_reference"}
    identity = ref["source"]
    scope = identity.get("scope") or {}
    if not isinstance(scope, dict):
        return {"observation": "malformed_scope"}
    digest = identity.get("content_sha256")
    digest = digest if (isinstance(digest, str) and len(digest) == 64
                        and all(c in "0123456789abcdef" for c in digest)) else None
    return {
        "source_key": _key(identity.get("document_id"), identity.get("canonical_path"),
                           digest, scope.get("project_id"), scope.get("snapshot_id"), scope.get("version")),
        "source_sha256": digest,
        "candidate_key": _key(candidate.get("project_identity"),
                              candidate.get("stable_id") or candidate.get("stable_chunk_id")
                              or candidate.get("evidence_id") or candidate.get("path") or candidate.get("source")),
        "reference_char_start": ref.get("char_start") if type(ref.get("char_start")) is int else None,
        "reference_char_end": ref.get("char_end") if type(ref.get("char_end")) is int else None,
    }


def _flow_row(row: Any, candidate: Any) -> dict[str, Any]:
    """Locate only a unique exact visible occurrence in the held reference window.

    A reference envelope is never reported as the visible snippet. These are
    diagnostic coordinates, not another source validation or discovery receipt.
    Large or ambiguous windows are explicitly unavailable, not normalized.
    """
    result = _flow_source(candidate)
    row = row if isinstance(row, dict) else {}
    result.update(
        evidence_id=_scalar(row.get("evidence_id")),
        line_start=row.get("line_start") if type(row.get("line_start")) is int else None,
        line_end=row.get("line_end") if type(row.get("line_end")) is int else None,
        visible_char_start=None, visible_char_end=None,
        visible_span_observation="unavailable", snippet_sha256=None,
        snippet_characters=None, snippet_hash_observation="unavailable",
    )
    snippet = row.get("snippet")
    if not isinstance(snippet, str) or not snippet:
        result["visible_span_observation"] = "missing_snippet"
        return result
    result["snippet_characters"] = len(snippet)
    if len(snippet) > MAX_CONTEXT_FLOW_CHARS:
        result.update(visible_span_observation="diagnostic_character_limit",
                      snippet_hash_observation="diagnostic_character_limit")
        return result
    result.update(snippet_sha256=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                  snippet_hash_observation="recorded")
    ref = candidate.get("_reference_evidence") if isinstance(candidate, dict) else None
    if not isinstance(ref, dict):
        return result
    raw, start, end = ref.get("raw_document"), ref.get("char_start"), ref.get("char_end")
    if (not isinstance(raw, str) or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(raw)):
        result["visible_span_observation"] = "invalid_reference_bounds"
        return result
    if end - start > MAX_CONTEXT_FLOW_CHARS:
        result["visible_span_observation"] = "diagnostic_character_limit"
        return result
    position = raw.find(snippet, start, end)
    if position < 0:
        result["visible_span_observation"] = "no_exact_occurrence"
    elif raw.find(snippet, position + 1, end) >= 0:
        result["visible_span_observation"] = "ambiguous_occurrence"
    else:
        result.update(visible_char_start=position, visible_char_end=position + len(snippet),
                      visible_span_observation="exact_occurrence")
    return result


class ProjectionFlowTrace:
    """Bounded observations of executed finalizers; never an input to decisions."""

    def __init__(self, retrieval: dict[str, Any]) -> None:
        self.enabled = query_trace_enabled()
        self.retrieval = retrieval if self.enabled else None

    def _event(self, stage: str, kind: str, **fields: Any) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        state = None
        try:
            diagnostics = self.retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
                "docs_context_projection", {})
            state = diagnostics.setdefault("context_flow", {
                "schema_version": 1, "event_count": 0, "omitted_events": 0,
                "event_limit": MAX_CONTEXT_FLOW_EVENTS, "source_limit": MAX_CONTEXT_FLOW_SOURCES,
                "diagnostic_character_limit": MAX_CONTEXT_FLOW_CHARS,
                "diagnostic_error_count": 0, "events": [],
            })
            state["event_count"] += 1
            if len(state["events"]) >= MAX_CONTEXT_FLOW_EVENTS:
                state["omitted_events"] += 1
                # Retain the outer recheck/budget boundaries even when detailed
                # per-row trial events exhaust the same fixed-size trace. Every
                # displaced event stays counted; this never changes selection.
                outer = {"recheck.input", "recheck.output", "budget.input", "budget.output"}
                if kind != "boundary" or stage not in outer:
                    return None
                replace = next((index for index in range(len(state["events"]) - 1, -1, -1)
                                if state["events"][index].get("event") != "boundary"
                                or state["events"][index].get("stage") not in outer), None)
                if replace is None:
                    return None
                del state["events"][replace]
            event = {"sequence": state["event_count"], "stage": stage, "event": kind, **fields}
            state["events"].append(event)
            return event
        except Exception as exc:
            # Malformed/missing carriers remain explicit in the serializer;
            # diagnostic allocation must never change a delivery decision.
            try:
                if isinstance(state, dict):
                    state["diagnostic_error_count"] = state.get("diagnostic_error_count", 0) + 1
                    state["last_diagnostic_error_type"] = type(exc).__name__
                    if isinstance(state.get("events"), list) and type(state.get("event_count")) is int:
                        state["omitted_events"] = max(0, state["event_count"] - len(state["events"]))
            except Exception:
                pass
            return None

    def _failure(self, event: dict[str, Any], exc: Exception) -> None:
        event.update(observation="diagnostic_error", error_type=type(exc).__name__)
        try:
            state = self.retrieval["retrieval_diagnostics"]["docs_context_projection"]["context_flow"]
            state["diagnostic_error_count"] += 1
            state["last_diagnostic_error_type"] = type(exc).__name__
        except Exception:
            pass

    def boundary(self, stage: str, payload: dict, snapshot: dict, **fields: Any) -> int | None:
        event = self._event(stage, "boundary", **fields)
        if event is None:
            return None
        try:
            rows = payload.get("sources")
            if not isinstance(rows, (list, tuple)):
                event["observation"] = "missing_sources" if rows is None else "malformed_sources"
            else:
                event.update(observation="recorded", source_count=len(rows),
                             source_rows_omitted=max(0, len(rows) - MAX_CONTEXT_FLOW_SOURCES), rows=[])
                for row in rows[:MAX_CONTEXT_FLOW_SOURCES]:
                    bound = snapshot.get(row.get("evidence_id")) if isinstance(row, dict) else None
                    source = bound.get("source") if isinstance(bound, dict) else None
                    event["rows"].append(_flow_row(row, source))
        except Exception as exc:
            self._failure(event, exc)
        return event["sequence"]

    def recheck(self, stage: str, *, row: dict, candidate: Any, native: Any,
                receipt: dict | None, rejection: dict | None, **fields: Any) -> None:
        event = self._event(stage, "recheck_attempt", **fields)
        if event is None:
            return
        try:
            event.update(observation="recorded", target=_flow_row(row, candidate), native=_flow_source(native))
            if receipt is not None:
                window = receipt.get("body_window") or {}
                native_span = receipt.get("native_span") or ()
                event.update(outcome="accepted", checkpoint="complete", axis=None,
                             reason=receipt.get("route"), route=receipt.get("route"),
                             accepted_derivation=receipt.get("derivation"),
                             checked_visible_char_start=window.get("char_start"),
                             checked_visible_char_end=window.get("char_end"),
                             checked_native_char_start=native_span[0] if len(native_span) == 2 else None,
                             checked_native_char_end=native_span[1] if len(native_span) == 2 else None)
            else:
                event.update(outcome="error" if event.get("error_type") else "rejected",
                             **_fields(rejection or {}, ("checkpoint", "axis", "reason")))
                if not (rejection or {}).get("reason"):
                    event["reason"] = "rejection_diagnostics_unavailable"
        except Exception as exc:
            self._failure(event, exc)

    def row_outcome(self, stage: str, *, row: dict, candidate: Any, **fields: Any) -> None:
        event = self._event(stage, "recheck_row", **fields)
        if event is None:
            return
        try:
            event.update(observation="recorded", target=_flow_row(row, candidate))
        except Exception as exc:
            self._failure(event, exc)


def _context_flow_observation(value: Any) -> dict[str, Any]:
    """Only known bounded identity/coordinate fields cross the diagnostic sink."""
    if not isinstance(value, dict):
        return _preview(value)
    events = value.get("events")
    if not isinstance(events, list):
        return {"observation": "malformed", "reason": "missing_flow_events"}
    result = {
        "observation": "recorded",
        **_fields(value, ("schema_version", "event_count", "omitted_events", "event_limit",
                          "source_limit", "diagnostic_character_limit", "diagnostic_error_count",
                          "last_diagnostic_error_type")),
        "recorded_events": len(events),
        "serialization_omitted_events": max(0, len(events) - MAX_CONTEXT_FLOW_EVENTS), "events": [],
    }
    event_fields = (
        "sequence", "stage", "event", "observation", "error_type", "source_count", "source_rows_omitted",
        "call_sequence", "row_ordinal", "attempt_ordinal", "derivation", "seed_ordinal", "active",
        "outcome", "checkpoint", "axis", "reason", "route", "accepted_derivation",
        "checked_visible_char_start", "checked_visible_char_end", "checked_native_char_start",
        "checked_native_char_end", "attempts", "seed_count",
        "seed_source_mismatches", "seed_span_unavailable", "seed_bounds_invalid", "occurrence_available",
    )
    for event in events[:MAX_CONTEXT_FLOW_EVENTS]:
        item = _fields(event, event_fields)
        if isinstance(event, dict):
            for name in ("target", "native"):
                if name in event:
                    item[name] = _fields(event[name], ("observation", *_FLOW_ROW_FIELDS))
            if isinstance(event.get("rows"), list):
                item["rows"] = [_fields(row, ("observation", *_FLOW_ROW_FIELDS))
                                for row in event["rows"][:MAX_CONTEXT_FLOW_SOURCES]]
                item["serialization_omitted_source_rows"] = max(0, len(event["rows"]) - MAX_CONTEXT_FLOW_SOURCES)
        result["events"].append(item)
    return result


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


def _work_observation(value: Any, names: tuple[str, ...], *,
                      counts: tuple[str, ...] = ()) -> dict[str, Any]:
    """Copy bounded counters/timings only; never execute a measurement here."""
    if not isinstance(value, dict):
        return _preview(value)
    result = _fields(value, names)
    for name in names:
        number = value.get(name)
        if type(number) is float:
            result[name] = number if math.isfinite(number) else None
    for name in counts:
        values = value.get(name, _MISSING)
        rows = ([{"reason": key, "count": count} for key, count in values.items()]
                if isinstance(values, dict) else values)
        result[name] = _preview(rows, names=("reason", "count"),
                               producer_count=len(rows) if isinstance(rows, list) else _MISSING)
    return result


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
        "joint_work": _work_observation(value.get("joint_work", _MISSING), (
            "draft_attempts", "finish_rejections", "lineage_rejections",
            "validation_rejections", "coverage_rejections", "yielded")),
        "experimental_budget": _work_observation(value.get("experimental_budget", _MISSING), (
            "limit", "input_cost", "output_cost", "measure", "attempts",
            "native_fallbacks", "omitted_source_count", "source_count", "read_next_omitted")),
        "experimental_source_recheck": _work_observation(value.get("experimental_source_recheck", _MISSING), (
            "checked", "retained"), counts=("routes",)),
        "experimental_native_restore": _work_observation(value.get("experimental_native_restore", _MISSING), (
            "checked", "restored", "already_covered", "rejected")),
        "context_flow": _context_flow_observation(value.get("context_flow", _MISSING)),
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
            "prepared_parents": _work_observation(_child(service_trace, "prepared_parents"), (
                "prepared_enabled", "documents", "prepared_hits", "parser_calls", "parser_ms",
                "parent_rows", "parent_selects", "prepared_read_ms", "prepared_verification_ms"),
                counts=("miss_reasons",)),
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
