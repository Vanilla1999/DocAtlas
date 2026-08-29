"""Canonical, provider-free projection from rich retrieval to model-visible context."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import zlib
from copy import deepcopy
from typing import Any, Iterable

from docmancer.docs.application.action_packet import evidence_identity_for_item
from docmancer.docs.application.context_selection import validate_context_selection_payload
from docmancer.docs.application.evidence_selection import (
    AggregateMixedSelectionDecision,
    EvidenceAssignment,
    EvidenceCandidate,
    SelectionDecision,
    docs_selection_config,
    library_docs_selection_config,
    project_docs_selection_config,
    resolve_assignment_unit,
    select_evidence,
    validate_assignment_binding,
)
from docmancer.docs.domain.answer_units import materialize_answer_units
from docmancer.docs.domain.request_intent import model_projection_kind
from docmancer.docs.application.insufficient_projection import (
    apply_terminal_insufficient_projection,
    bounded_missing_value,
    compact_recovery_action_for_budget,
)
from docmancer.docs.application.model_visible_projection_helpers import (
    bounded_action as _bounded_action,
    cited_patch_items as _cited_patch_items,
    sanitized_projection_manifest,
)


DOCS_ANSWER_MAX_TOKENS = 800
DOCS_CONTEXT_MAX_TOKENS = 800
PATCH_CONTEXT_TARGET_TOKENS = 1_500
PATCH_CONTEXT_HARD_TOKENS = 2_000
INSUFFICIENT_EVIDENCE_MAX_TOKENS = 300
MAX_DOCS_SOURCES = 3
DOCS_SOURCE_FIELDS = frozenset({
    "evidence_id", "path_or_url", "section", "snippet", "version_binding",
    "content_sha256",
})
DOCS_CONTEXT_SOURCE_FIELDS = frozenset({
    "evidence_id", "path_or_url", "section", "snippet", "version_binding",
    "content_sha256", "project_identity", "line_start", "line_end",
    "authority", "scope", "retrieval_query_ids", "retrieval_query_matches",
})
PATCH_SOURCE_FIELDS = frozenset({
    "evidence_id", "path", "symbol_or_section", "authority",
    "instruction_trust", "scope", "version_binding", "content_sha256",
})
_ACTIONABLE_QUESTION_RE = re.compile(
    r"\b(?:how\s+(?:do|can|should)\s+(?:i|we)\s+(?:configure|set|call|run|use)"
    r"|(?:configure|set|call|run)\s+(?:up\s+)?(?:the\s+)?"
    r"|command\s+to\b)",
    re.IGNORECASE,
)
_ACTIONABLE_SNIPPET_RE = re.compile(
    r"(?:[A-Za-z_][\w.-]*\s*=\s*[^=]|\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\s*\("
    r"|(?:^|\n)\s*(?:\$\s*)?[\w./-]+\s+--?[\w-]+"
    r"|```|\b(?:set|configure|export)\s+[A-Za-z_][\w.-]*\s+(?:to\s+)?\S+)",
    re.IGNORECASE,
)
_ACTIONABLE_LIMITATION = (
    "The selected evidence does not provide a concrete configuration key, "
    "value, command, or API call."
)
FORBIDDEN_MODEL_KEYS = frozenset({
    "context_pack", "content", "surrounding_context", "ingestion_diagnostics",
    "retrieval_diagnostics", "diagnostics", "repo_map", "code_graph",
    "primary_snippet", "primary_snippets", "primary_snippet_alternatives",
    "supporting_snippets", "successful_logs", "indexing_logs", "test_logs",
})
SUPPORT_ENVELOPE_KEYS = (
    "answer_supported", "answer_available", "support_status", "decision",
    "reason_code", "missing_requirement_ids", "satisfied_requirement_ids",
    "mandatory_requirement_ids", "mandatory_coverage", "evidence_coverage",
    "selected_evidence_ids", "requirements_hash", "selector_config_hash",
    "eligibility_contract_hash", "candidate_trace_hash", "selection_hash",
    "assignment_hash", "decision_hash",
)
SUPPORT_ENVELOPE_ENCODING = "zlib+base64url"
_MINIMAL_MISSING = "Required source-backed evidence is unavailable."
_INSUFFICIENT_SUPPORT_KEYS = (
    "answer_supported", "answer_available", "support_status", "reason_code",
    "decision_hash",
)
_OPTIONAL_INSUFFICIENT_KEYS = (
    "operational_status", "context_available", "disposition",
)

def canonical_projection_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def estimate_projection_tokens(value: Any) -> int:
    size = len(canonical_projection_bytes(value))
    return max(1, math.ceil(size / 4))


def encode_support_envelope(value: dict[str, Any]) -> dict[str, str]:
    """Encode a complete canonical support envelope for tiny public budgets."""

    canonical = {
        key: deepcopy(value[key])
        for key in SUPPORT_ENVELOPE_KEYS
        if key in value
    }
    compressed = zlib.compress(canonical_projection_bytes(canonical), level=9)
    return {
        "encoding": SUPPORT_ENVELOPE_ENCODING,
        "data": base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("="),
    }


def decode_support_envelope(value: Any) -> dict[str, Any]:
    """Decode the deterministic bounded transport, rejecting malformed input."""

    if not isinstance(value, dict) or value.get("encoding") != SUPPORT_ENVELOPE_ENCODING:
        raise ValueError("unsupported support envelope encoding")
    encoded = value.get("data")
    if not isinstance(encoded, str) or not encoded or len(encoded) > 8_192:
        raise ValueError("invalid support envelope data")
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        raw = zlib.decompress(base64.b64decode(padded, altchars=b"-_", validate=True))
        decoded = json.loads(raw)
    except (ValueError, TypeError, zlib.error, json.JSONDecodeError) as exc:
        raise ValueError("invalid support envelope data") from exc
    if len(raw) > 32_000 or not isinstance(decoded, dict):
        raise ValueError("invalid support envelope payload")
    if set(decoded) != set(SUPPORT_ENVELOPE_KEYS):
        raise ValueError("incomplete support envelope payload")
    return decoded


def projection_kind(question: str) -> str:
    """Classify explicit change requests without treating how-to questions as edits."""

    return model_projection_kind(question)


def _unit_materialized_item(
    candidate: EvidenceCandidate,
    assignments: Iterable[EvidenceAssignment],
) -> dict[str, Any] | None:
    """Return a source item containing only canonically assigned answer units."""

    units = []
    seen: set[str] = set()
    for assignment in sorted(
        assignments,
        key=lambda item: (
            item.unit_char_start if item.unit_char_start is not None else 10**9,
            item.requirement_id,
        ),
    ):
        unit = resolve_assignment_unit(candidate, assignment)
        if unit is None or unit.unit_id in seen:
            continue
        seen.add(unit.unit_id)
        units.append(unit)
    if not units:
        return None
    material = materialize_answer_units(candidate.display_text, units)
    if not material.strip():
        return None
    item = dict(candidate.original)
    # ``_docs_source`` prefers code/snippet/content in that order.  Remove any
    # whole-chunk aliases before installing the bounded assigned material.
    item.pop("code", None)
    item["snippet"] = material
    item["content"] = material
    item["display_text"] = material
    item["heading_path"] = candidate.section
    item["source_url"] = candidate.path_or_url
    item["version_binding"] = candidate.version_binding
    return item


def project_docs_answer(
    *,
    question: str,
    retrieval: dict[str, Any],
    max_tokens: int = DOCS_ANSWER_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
    canonical_selection: SelectionDecision | AggregateMixedSelectionDecision | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Create one deduplicated source list and an internal immutable snapshot."""

    candidates = _docs_candidates(retrieval)
    selection_config = (
        library_docs_selection_config(max_tokens)
        if retrieval.get("selection_profile") == "library_docs_answer"
        else project_docs_selection_config(max_tokens)
        if retrieval.get("selection_profile") == "project_docs_answer"
        else docs_selection_config(max_tokens)
    )
    selection_profile = str(retrieval.get("selection_profile") or "generic")
    is_library_answer = selection_profile == "library_docs_answer"
    strict_selection_profile = selection_profile in {"library_docs_answer", "project_docs_answer"}
    decision = (
        canonical_selection.selection_decision
        if isinstance(canonical_selection, AggregateMixedSelectionDecision)
        else canonical_selection
    )
    if decision is None and isinstance(retrieval.get("selection_decision"), SelectionDecision):
        decision = retrieval["selection_decision"]
    canonical_decision_supplied = decision is not None
    has_canonical_selection = strict_selection_profile or canonical_decision_supplied
    if is_library_answer:
        if decision is None:
            payload = project_insufficient(
                kind="docs_answer",
                missing=["Canonical library support decision is unavailable."],
                recommended_next_action=retrieval.get("next_action"),
                max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
            )
            payload.update({
                "operational_status": str(retrieval.get("status") or "unknown"),
                "context_available": bool(candidates),
                "answer_supported": False,
                "answer_available": False,
                "support_status": "insufficient_evidence",
                "reason_code": "canonical_support_decision_missing",
                "missing_requirement_ids": ["canonical_support_decision"],
                "satisfied_requirement_ids": [],
                "mandatory_requirement_ids": [],
                "mandatory_coverage": 0.0,
                "evidence_coverage": 0.0,
                "selected_evidence_ids": [],
                "decision_hash": None,
            })
            _refresh_estimate(payload)
            return payload, {}
    elif decision is None:
        decision = select_evidence(
            candidates,
            question=question,
            config=selection_config,
            trust_contract=retrieval.get("trust_contract") or {},
            exact_version=_requested_exact_version(retrieval),
            required_evidence_paths=retrieval.get("required_evidence_paths") or (),
            required_target_paths=retrieval.get("required_target_paths") or (),
            public_requirements=retrieval.get("public_requirements") or (),
            requirements=retrieval.get("requirements"),
            library_requirement_contract=retrieval.get("library_requirement_contract"),
            project_identity=retrieval.get("project_identity"),
            module_id=retrieval.get("module_id"),
        )
    has_canonical_selection = strict_selection_profile or canonical_decision_supplied
    if selection_diagnostics is not None:
        selection_diagnostics.update(decision.audit_manifest())
    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    omitted = len(decision.omissions)
    use_unit_projection = (
        retrieval.get("selection_profile") == "project_docs_answer"
        or any(assignment.unit_id for assignment in decision.assignments)
    )
    assigned_ids = {
        assignment.evidence_id for assignment in decision.assignments
    } if has_canonical_selection else {
        candidate.stable_id for candidate in decision.selected_candidates
    }
    candidates_by_id = {candidate.stable_id: candidate for candidate in decision.selected_candidates}
    selected_candidates = [
        candidates_by_id[evidence_id]
        for evidence_id in decision.support_decision.selected_evidence_ids
        if evidence_id in candidates_by_id and evidence_id in assigned_ids
    ] if has_canonical_selection else [
        candidate for candidate in decision.selected_candidates
        if candidate.stable_id in assigned_ids
    ]
    if len(selected_candidates) > 6:
        selected_candidates = []
    for candidate in selected_candidates:
        candidate_assignments = tuple(
            assignment for assignment in decision.assignments
            if assignment.evidence_id == candidate.stable_id
        )
        item = (
            _unit_materialized_item(candidate, candidate_assignments)
            if has_canonical_selection and use_unit_projection
            else dict(candidate.original)
        )
        if item is None:
            omitted += 1
            continue
        normalized = _docs_source(
            item,
            evidence_id=candidate.stable_id if has_canonical_selection else None,
        )
        if normalized is None:
            omitted += 1
            continue
        evidence_id = normalized["evidence_id"]
        sources.append(normalized)
        snapshot[evidence_id] = _snapshot_entry(item, normalized)

    canonical_can_override = (
        has_canonical_selection
        and decision.support_decision.answer_supported
        and bool(decision.support_decision.mandatory_requirement_ids)
        and {
            assignment.requirement_id for assignment in decision.assignments
        }.issuperset(decision.support_decision.mandatory_requirement_ids)
    )
    retrieval_issues = _docs_retrieval_issues(
        retrieval,
        canonical_supported=canonical_can_override,
    )
    support = (
        _docs_support_decision(
            retrieval=retrieval,
            decision=decision,
            context_available=bool(candidates),
        )
        if has_canonical_selection
        else {}
    )
    if has_canonical_selection and decision.support_decision.answer_supported:
        selected_ids = list(decision.support_decision.selected_evidence_ids)
        visible_ids = [source["evidence_id"] for source in sources]
        if visible_ids != selected_ids:
            payload = project_insufficient(
                kind="docs_answer",
                missing=["A selected support witness could not be materialized safely."],
                recommended_next_action=None,
                max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
            )
            payload.update({
                "operational_status": str(retrieval.get("status") or "unknown"),
                "context_available": bool(candidates),
                "reason_code": "support_witness_not_materialized",
            })
            bound_insufficient_projection(
                payload, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
            )
            return payload, snapshot
        visible_candidates = {candidate.stable_id: candidate for candidate in selected_candidates}
        requirements_by_id = {
            requirement.requirement_id: requirement
            for requirement in decision.requirements
        }
        invalid_assignments = [
            assignment for assignment in decision.assignments
            if assignment.evidence_id not in visible_candidates
            or assignment.requirement_id not in requirements_by_id
            or not validate_assignment_binding(
                requirements_by_id[assignment.requirement_id],
                visible_candidates[assignment.evidence_id],
                assignment,
            )
            or (
                assignment.unit_id is not None
                and resolve_assignment_unit(
                    visible_candidates[assignment.evidence_id], assignment,
                ).text not in next(
                    source["snippet"] for source in sources
                    if source["evidence_id"] == assignment.evidence_id
                )
            )
        ]
        if invalid_assignments:
            payload = project_insufficient(
                kind="docs_answer",
                missing=["A mandatory support assignment could not be materialized safely."],
                recommended_next_action=None,
                max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
            )
            payload["reason_code"] = "support_assignment_not_materialized"
            return payload, snapshot
    if decision.status != "ok" or not sources or retrieval_issues:
        missing = list(decision.missing_requirements)
        missing.extend(decision.unresolved_conflicts)
        missing.extend(retrieval_issues)
        missing.append(str(retrieval.get("message") or "No complete source-backed documentation answer is available."))
        payload = project_insufficient(
            kind="docs_answer", missing=missing,
            recommended_next_action=retrieval.get("next_action"), max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        )
        payload.update(support)
        if not payload.get("reason_code") and retrieval.get("reason_code"):
            payload["reason_code"] = retrieval["reason_code"]
        bound_insufficient_projection(
            payload, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        )
        return payload, snapshot

    answer, answer_evidence_ids, answer_limited = _answer_text(
        question,
        retrieval,
        sources,
        require_all_sources=has_canonical_selection,
    )
    if has_canonical_selection:
        answer_evidence_ids = list(decision.support_decision.selected_evidence_ids)
    omitted_counts = {"sources": omitted} if omitted else {}
    if answer_limited:
        omitted_counts["answer_details"] = 1
    payload: dict[str, Any] = {
        "status": "ok",
        "kind": "docs_answer",
        "answer": answer,
        "answer_evidence_ids": answer_evidence_ids,
        "sources": sources,
        "omitted_counts": omitted_counts,
        **support,
        "estimated_tokens": 0,
    }
    if answer_limited:
        payload["limitations"] = [_ACTIONABLE_LIMITATION]
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > min(DOCS_ANSWER_MAX_TOKENS, max_tokens):
        fallback = project_insufficient(
            kind="docs_answer", missing=["Selected evidence exceeds the answer budget."],
            recommended_next_action=None, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        )
        fallback.update(support)
        bound_insufficient_projection(
            fallback, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        )
        return fallback, snapshot
    return payload, snapshot


def _requested_exact_version(retrieval: dict[str, Any]) -> str | None:
    """Return a version only when retrieval says the binding is exact."""

    exactness = str(retrieval.get("docs_exactness") or "").casefold().replace("-", "_")
    if exactness not in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
        return None
    value = retrieval.get("requested_version") or retrieval.get("resolved_version")
    return str(value).strip() if value is not None and str(value).strip() else None


def _docs_support_decision(*, retrieval: dict[str, Any], decision: Any, context_available: bool) -> dict[str, Any]:
    canonical = decision.support_decision
    support = {
        **canonical.as_payload(),
        "operational_status": str(retrieval.get("status") or "unknown"),
        "context_available": context_available,
    }
    return support


def bound_insufficient_projection(payload: dict[str, Any], *, max_tokens: int) -> None:
    """Produce a valid bounded failure projection for every requested budget."""

    limit = min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max(1, int(max_tokens)))
    envelope = _compact_insufficient_support(payload)
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        if envelope is not None:
            payload["support_envelope"] = envelope
            _refresh_estimate(payload)
            if estimate_projection_tokens(payload) <= limit:
                return
            payload.pop("support_envelope", None)
            _refresh_estimate(payload)
        return
    action = payload.get("recommended_next_action")
    original_action = deepcopy(action) if isinstance(action, dict) else None
    action_fits, protected_confirmation = compact_recovery_action_for_budget(
        payload, limit, estimate_tokens=estimate_projection_tokens, refresh_estimate=_refresh_estimate
    )
    if action_fits:
        return
    if not protected_confirmation:
        payload.pop("recommended_next_action", None)
    missing = payload.get("missing")
    bounded_missing = bounded_missing_value(missing, default=_MINIMAL_MISSING)
    while (
        estimate_projection_tokens(payload) > limit
        and isinstance(missing, list)
        and len(missing) > 1
    ):
        missing.pop()
        _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return
    for key in _OPTIONAL_INSUFFICIENT_KEYS:
        payload.pop(key, None)
        _refresh_estimate(payload)
        if estimate_projection_tokens(payload) <= limit:
            return
    payload["missing"] = [bounded_missing]
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return
    # Terminal fallback retains only bounded support/recovery metadata and, when
    # it fits, one compact machine-readable missing requirement id.
    apply_terminal_insufficient_projection(
        payload,
        kind=payload.get("kind"),
        missing=bounded_missing,
        original_action=original_action,
        support_keys=_INSUFFICIENT_SUPPORT_KEYS,
    )
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > limit:
        payload.pop("recommended_next_action", None)
        _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > limit and bounded_missing != _MINIMAL_MISSING:
        payload["missing"] = [_MINIMAL_MISSING]
        _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > limit:
        raise ValueError("minimum insufficient-evidence projection exceeds the requested budget")


def _compact_insufficient_support(payload: dict[str, Any]) -> dict[str, str] | None:
    """Replace audit-only support fields with a model-readable summary."""

    envelope_payload = {
        key: deepcopy(payload[key])
        for key in SUPPORT_ENVELOPE_KEYS
        if key in payload and payload[key] is not None
    }
    summary = {
        key: deepcopy(payload[key])
        for key in _INSUFFICIENT_SUPPORT_KEYS
        if key in payload and payload[key] is not None
    }
    if "answer_supported" in payload:
        summary.update({
            "answer_supported": False,
            "answer_available": False,
            "support_status": "insufficient_evidence",
        })
    for key in SUPPORT_ENVELOPE_KEYS:
        payload.pop(key, None)
    payload.pop("support_envelope", None)
    payload.update(summary)
    return (
        encode_support_envelope(envelope_payload)
        if set(envelope_payload) == set(SUPPORT_ENVELOPE_KEYS)
        else None
    )


def project_patch_context(
    *, packet: dict[str, Any], evidence_items: Iterable[dict[str, Any]], max_tokens: int = PATCH_CONTEXT_TARGET_TOKENS
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Flatten a validated ActionPacket without exposing its rich evidence input."""

    raw_evidence: dict[str, dict[str, Any]] = {}
    for original in evidence_items:
        if not isinstance(original, dict):
            continue
        for authority in ("canonical", "supporting"):
            candidate = deepcopy(original)
            candidate["_packet_authority"] = authority
            evidence_id, _, _ = evidence_identity_for_item(candidate)
            raw_evidence.setdefault(evidence_id, deepcopy(original))
    if packet.get("status") == "insufficient_evidence":
        return project_insufficient(
            kind="patch_context",
            missing=list(packet.get("missing_evidence") or ["Required patch evidence is unavailable."]),
            recommended_next_action=None,
            max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), {}

    snapshot: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for row in packet.get("source_of_truth") or []:
        evidence_id = str(row.get("evidence_id") or "")
        item = raw_evidence.get(evidence_id)
        if not item:
            continue
        digest = _source_digest(item)
        projected = {**deepcopy(row), "content_sha256": digest}
        sources.append(projected)
        snapshot[evidence_id] = _snapshot_entry(item, projected)

    mutation_ready = bool((packet.get("mutation_intent") or {}).get("ready"))
    mandatory_assignments_survived = not bool(
        (packet.get("omitted_counts") or {}).get("mandatory_requirements")
    )
    packet_valid = packet.get("status") in {"ok", "truncated"}
    payload: dict[str, Any] = {
        "status": packet.get("status"),
        "kind": "patch_context",
        "schema_version": packet.get("schema_version"),
        "objective": deepcopy((packet.get("task_interpretation") or {}).get("objective")),
        "acceptance_conditions": deepcopy((packet.get("task_interpretation") or {}).get("acceptance_conditions") or []),
        "sources": sources,
        "targets": deepcopy(packet.get("target_surface") or {"likely_files": [], "symbols": []}),
        "invariants": deepcopy(packet.get("required_invariants") or []),
        "forbidden_changes": deepcopy(packet.get("forbidden_changes") or []),
        "implementation_guidance": deepcopy(packet.get("implementation_guidance") or []),
        "checks": deepcopy(packet.get("validation") or {"compile": [], "tests": [], "semantic_checks": []}),
        "mutation_intent": deepcopy(packet.get("mutation_intent") or {}),
        "mutation_ready": mutation_ready,
        "edit_ready": packet_valid and mutation_ready and mandatory_assignments_survived,
        "investigation_allowed": True,
        "source_search_status": "not_required",
        "uncertainties": deepcopy(packet.get("uncertainties") or []),
        "omitted_counts": deepcopy(packet.get("omitted_counts") or {}),
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    limit = min(PATCH_CONTEXT_HARD_TOKENS, max(256, int(max_tokens)))
    estimated_tokens = estimate_projection_tokens(payload)
    for optional_key in ("objective", "uncertainties", "omitted_counts"):
        if estimated_tokens <= limit:
            break
        if optional_key not in payload:
            continue
        if optional_key == "uncertainties" and payload.get(optional_key):
            continue
        payload.pop(optional_key, None)
        payload["status"] = "truncated"
        _refresh_estimate(payload)
        estimated_tokens = estimate_projection_tokens(payload)
    if estimated_tokens > limit:
        return project_insufficient(
            kind="patch_context",
            missing=[
                "The validated patch context, including selected evidence guidance, "
                "cannot be preserved within the model-visible budget "
                f"({estimated_tokens} > {limit})."
            ],
            recommended_next_action=None, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), snapshot
    return payload, snapshot


def project_insufficient(
    *, kind: str, missing: Iterable[str], recommended_next_action: Any, max_tokens: int = INSUFFICIENT_EVIDENCE_MAX_TOKENS
) -> dict[str, Any]:
    messages = [str(item).strip() for item in missing if str(item).strip()][:5]
    payload: dict[str, Any] = {
        "status": "insufficient_evidence",
        "kind": kind,
        "missing": messages or [_MINIMAL_MISSING],
        "estimated_tokens": 0,
    }
    action = _bounded_action(recommended_next_action)
    if action:
        payload["recommended_next_action"] = action
    _refresh_estimate(payload)
    while estimate_projection_tokens(payload) > min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens) and len(payload["missing"]) > 1:
        payload["missing"].pop()
        _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens):
        bound_insufficient_projection(payload, max_tokens=max_tokens)
    return payload


def validate_model_visible_projection(
    payload: Any, *, snapshot: dict[str, dict[str, Any]], max_tokens: int,
    canonical_selection: SelectionDecision | AggregateMixedSelectionDecision | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["model-visible projection must be an object"]
    forbidden = sorted(_find_forbidden_keys(payload))
    if forbidden:
        errors.append("forbidden model-visible keys: " + ", ".join(forbidden))
    status, kind = payload.get("status"), payload.get("kind")
    if kind not in {"docs_answer", "docs_context", "patch_context"}:
        errors.append("invalid projection kind")
    if status not in {"ok", "truncated", "insufficient_evidence"}:
        errors.append("invalid projection status")
    limit = (
        min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens)
        if status == "insufficient_evidence"
        else max_tokens
    )
    actual = estimate_projection_tokens(payload)
    if payload.get("estimated_tokens") != actual or actual > limit:
        errors.append("projection estimate mismatch or budget exceeded")
    if status == "insufficient_evidence":
        transport = payload.get("support_envelope")
        transport_support: dict[str, Any] | None = None
        if transport is not None:
            try:
                transport_support = decode_support_envelope(transport)
            except ValueError as exc:
                errors.append(str(exc))
        for key, expected in (
            ("answer_supported", False),
            ("answer_available", False),
            ("support_status", "insufficient_evidence"),
        ):
            if key in payload and payload[key] != expected:
                errors.append(f"insufficient evidence has inconsistent {key}")
        if transport_support is not None:
            for key in _INSUFFICIENT_SUPPORT_KEYS:
                if key in payload and key in transport_support and payload[key] != transport_support[key]:
                    errors.append(f"support envelope {key} does not match the model summary")
        if payload.get("implementation_guidance") or payload.get("invariants") or payload.get("targets"):
            errors.append("insufficient evidence must not authorize edits")
        decision = (
            canonical_selection.selection_decision
            if isinstance(canonical_selection, AggregateMixedSelectionDecision)
            else canonical_selection
        )
        if decision is not None:
            visible_hash = payload.get("decision_hash")
            envelope_hash = (
                transport_support.get("decision_hash")
                if transport_support is not None else None
            )
            if visible_hash not in {None, decision.support_decision.decision_hash}:
                errors.append("projection decision hash does not match canonical selection")
            if envelope_hash not in {None, decision.support_decision.decision_hash}:
                errors.append("support envelope decision hash does not match canonical selection")
        return errors
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("successful projections require sources")
        return errors
    if kind in {"docs_answer", "docs_context"} and len(sources) > MAX_DOCS_SOURCES:
        errors.append(f"{kind} exceeds source limit")
    ids: set[str] = set()
    allowed_fields = (
        DOCS_SOURCE_FIELDS if kind == "docs_answer" else
        DOCS_CONTEXT_SOURCE_FIELDS if kind == "docs_context" else
        PATCH_SOURCE_FIELDS
    )
    for source in sources:
        if not isinstance(source, dict):
            errors.append("projection source must be an object")
            continue
        evidence_id = str(source.get("evidence_id") or "")
        bound = snapshot.get(evidence_id)
        if not evidence_id or not bound:
            errors.append("projection evidence_id does not resolve to the internal snapshot")
            continue
        expected = bound.get("projected_source")
        if not isinstance(expected, dict):
            errors.append("internal snapshot is missing its canonical projected source")
            continue
        missing = sorted(allowed_fields - set(source))
        unknown = sorted(set(source) - allowed_fields)
        for key in missing:
            errors.append(f"projection source field is missing: {key}")
        if unknown:
            errors.append(
                "projection source contains unknown fields: " + ", ".join(unknown)
            )
        if set(expected) != allowed_fields:
            errors.append("internal snapshot projected source schema is invalid")
        if source.get("content_sha256") != expected.get("content_sha256"):
            errors.append("projection source hash does not match the internal snapshot")
        bound_source = bound.get("source")
        if (
            not isinstance(bound_source, dict)
            or _source_digest(bound_source) != expected.get("content_sha256")
        ):
            errors.append("internal snapshot hash does not match its source content")
        for key in sorted(allowed_fields & set(source) & set(expected)):
            if source.get(key) != expected.get(key):
                errors.append(f"projection source {key} does not match the internal snapshot")
        ids.add(evidence_id)
    if kind == "docs_answer":
        answer_refs = payload.get("answer_evidence_ids")
        if not isinstance(answer_refs, list) or not answer_refs or any(ref not in ids for ref in answer_refs):
            errors.append("docs_answer claims require valid evidence IDs")
        decision = (
            canonical_selection.selection_decision
            if isinstance(canonical_selection, AggregateMixedSelectionDecision)
            else canonical_selection
        )
        if decision is not None:
            if payload.get("answer_supported") is not True:
                errors.append("successful docs answer must be supported")
            assigned_witnesses = {
                assignment.evidence_id for assignment in decision.assignments
            }
            if ids != assigned_witnesses or set(answer_refs or ()) != assigned_witnesses:
                errors.append("model-visible evidence does not match aggregate assigned witnesses")
            visible_sources = {
                str(source.get("evidence_id") or ""): source
                for source in sources if isinstance(source, dict)
            }
            candidates_by_id = {
                candidate.stable_id: candidate
                for candidate in decision.selected_candidates
            }
            requirements_by_id = {
                requirement.requirement_id: requirement
                for requirement in decision.requirements
            }
            for assignment in decision.assignments:
                candidate = candidates_by_id.get(assignment.evidence_id)
                requirement = requirements_by_id.get(assignment.requirement_id)
                visible = visible_sources.get(assignment.evidence_id)
                if candidate is None or requirement is None or visible is None:
                    errors.append("model-visible assignment does not resolve to canonical evidence")
                    continue
                if not validate_assignment_binding(requirement, candidate, assignment):
                    errors.append("model-visible assignment failed unit proof revalidation")
                    continue
                unit = resolve_assignment_unit(candidate, assignment)
                if unit is not None and unit.text not in str(visible.get("snippet") or ""):
                    errors.append("model-visible assignment unit is absent from its cited source")
    if kind == "docs_context":
        if payload.get("answer_supported") is not False or payload.get("answer_available") is not False:
            errors.append("docs_context must not claim a supported answer")
        if payload.get("edit_ready") is not False:
            errors.append("docs_context must not authorize edits")
        if payload.get("implementation_guidance") or payload.get("invariants") or payload.get("targets"):
            errors.append("docs_context must not contain edit guidance")
        if any(not str(source.get("project_identity") or "").strip() for source in sources):
            errors.append("docs_context sources require project identity")
        errors.extend(validate_context_selection_payload(payload, sources))
    if kind == "patch_context":
        mutation = payload.get("mutation_intent")
        if not isinstance(mutation, dict):
            errors.append("patch context requires a mutation intent contract")
        elif mutation.get("operation") != "none" and mutation.get("ready") is not True:
            errors.append("successful patch context requires operation-aware target readiness")
        if payload.get("edit_ready") is not bool(
            status in {"ok", "truncated"}
            and payload.get("mutation_ready") is True
            and not (payload.get("omitted_counts") or {}).get("mandatory_requirements")
            and payload.get("source_search_status") != "required"
        ):
            errors.append("patch context edit readiness is inconsistent with validated support")
        for item in _cited_patch_items(payload):
            refs = item.get("evidence_ids")
            if not isinstance(refs, list) or not refs or any(ref not in ids for ref in refs):
                errors.append("factual patch item has missing or unknown evidence_ids")
                break
    return errors


def _docs_candidates(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    values = [retrieval.get("primary_snippet"), *(retrieval.get("primary_snippets") or []), *(retrieval.get("supporting_snippets") or []), *(retrieval.get("context_pack") or [])]
    return [dict(item) for item in values if isinstance(item, dict)]


def _docs_source(
    item: dict[str, Any], *, evidence_id: str | None = None,
) -> dict[str, Any] | None:
    path = str(item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or "").strip()
    section = str(item.get("heading_path") or item.get("title") or "document").strip()
    snippet = (
        item.get("code") or item.get("snippet") or item.get("content")
        or item.get("display_text")
    )
    if isinstance(snippet, dict):
        snippet = snippet.get("code") or snippet.get("text") or snippet.get("content")
    snippet = str(snippet or "").strip()
    version = str(item.get("version_binding") or item.get("version") or item.get("requested_version") or "unversioned")
    if (
        not path or not snippet or len(path) > 500 or len(section) > 300
        or len(snippet) > 3_000 or len(version) > 100
    ):
        return None
    digest = _source_digest(item)
    identity = canonical_projection_bytes({"path": path, "section": section, "sha256": digest})
    return {
        "evidence_id": evidence_id or "ev-" + hashlib.sha256(identity).hexdigest()[:16],
        "path_or_url": path,
        "section": section,
        "snippet": snippet,
        "version_binding": version,
        "content_sha256": digest,
    }


def _source_digest(item: dict[str, Any]) -> str:
    material = {
        "path": item.get("path") or item.get("source") or item.get("url") or item.get("source_url"),
        "section": item.get("heading_path") or item.get("title"),
        "content": item.get("content") or item.get("display_text"),
        "snippet": item.get("snippet") or item.get("code"),
        "version": item.get("version_binding") or item.get("version") or item.get("requested_version"),
    }
    return hashlib.sha256(canonical_projection_bytes(material)).hexdigest()


def _snapshot_entry(
    original: dict[str, Any], projected: dict[str, Any]
) -> dict[str, Any]:
    """Bind both raw source content and the exact model-visible source row."""

    canonical = dict(projected)
    # Keep the flat fields for the frozen Task 43 evaluator. New validation is
    # deliberately bound to projected_source so deleting or injecting a field
    # cannot exploit the evaluator's backwards-compatible snapshot shape.
    return {
        "source": deepcopy(original),
        "projected_source": canonical,
        **canonical,
    }


def _answer_text(
    question: str,
    retrieval: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    require_all_sources: bool = False,
) -> tuple[str, list[str], bool]:
    """Return only text that is directly present in one or more projected sources."""

    explicit = retrieval.get("answer")
    if isinstance(explicit, str) and explicit.strip():
        normalized = " ".join(explicit.split()).casefold()
        refs = [
            str(source["evidence_id"])
            for source in sources
            if normalized and normalized in " ".join(str(source.get("snippet") or "").split()).casefold()
        ]
        required_refs = [str(source["evidence_id"]) for source in sources]
        if refs and (not require_all_sources or refs == required_refs):
            answer = explicit.strip()
            limited = _needs_actionable_limitation(question, answer)
            return answer, refs, limited
    if require_all_sources:
        snippets = [str(source["snippet"]).strip() for source in sources]
        answer = "\n\n".join(dict.fromkeys(snippet for snippet in snippets if snippet))
        refs = [str(source["evidence_id"]) for source in sources]
        limited = _needs_actionable_limitation(question, answer)
        return answer, refs, limited
    primary = sources[0]
    answer = str(primary["snippet"])
    limited = _needs_actionable_limitation(question, answer)
    return answer, [str(primary["evidence_id"])], limited


def _needs_actionable_limitation(question: str, answer: str) -> bool:
    return bool(
        _ACTIONABLE_QUESTION_RE.search(question)
        and not _ACTIONABLE_SNIPPET_RE.search(answer)
    )


def _docs_retrieval_issues(
    retrieval: dict[str, Any], *, canonical_supported: bool = False
) -> list[str]:
    issues: list[str] = []
    status = str(retrieval.get("status") or "success").strip().lower()
    if status != "success":
        issues.append(f"Documentation retrieval is incomplete (status={status}).")
    if not canonical_supported and retrieval.get("answer_available") is False:
        issues.append("The requested documentation evidence is not currently available.")
    if retrieval.get("requires_confirmation"):
        issues.append("Documentation retrieval requires explicit confirmation.")
    if not canonical_supported and retrieval.get("answer_type") in {"navigation_only", "partial_navigational", "partial", "unavailable"}:
        issues.append("The retrieval result is not a complete source-backed answer.")
    completeness = retrieval.get("answer_completeness")
    if isinstance(completeness, dict) and not canonical_supported:
        if (
            completeness.get("source_search_required")
            and completeness.get("source_search_status") != "completed"
        ):
            issues.append("Source search is required before answering.")
        completeness_status = str(completeness.get("status") or "").strip().lower()
        if completeness_status and completeness_status not in {"exact", "complete"}:
            issues.append(f"Evidence completeness is {completeness_status}.")
    lanes = retrieval.get("lanes")
    if isinstance(lanes, dict):
        failed = sorted(
            str(name) for name, lane in lanes.items()
            if isinstance(lane, dict)
            and str(lane.get("status") or "").strip().lower() not in {"success", "not_requested"}
        )
        if failed:
            issues.append("Required documentation lanes are incomplete: " + ", ".join(failed[:5]) + ".")
    return issues


def _find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_MODEL_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_find_forbidden_keys(child))
    return found


def _refresh_estimate(payload: dict[str, Any]) -> None:
    payload["estimated_tokens"] = 0
    for _ in range(3):
        actual = estimate_projection_tokens(payload)
        if payload["estimated_tokens"] == actual:
            break
        payload["estimated_tokens"] = actual
