"""Canonical, provider-free projection from rich retrieval to model-visible context."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from copy import deepcopy
from dataclasses import replace
from typing import Any, Iterable

from docmancer.docs.application.action_packet import evidence_identity_for_item, validate_action_packet
from docmancer.docs.application.context_selection import validate_context_selection_payload
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
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
    build_requirements,
)
from docmancer.docs.domain.answer_units import materialize_answer_units
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows
from docmancer.docs.domain.context_budget import PROJECT_CONTEXT_BUDGET
from docmancer.docs.application.insufficient_projection import (
    apply_terminal_insufficient_projection,
    bounded_missing_value,
    compact_recovery_action_for_budget,
)
from docmancer.docs.application.model_visible_projection_helpers import (
    bounded_action as _bounded_action,
    cited_patch_items as _cited_patch_items,
    sanitized_projection_manifest,
    canonical_projection_bytes,
    estimate_projection_tokens,
    docs_context_budget_tokens,
)

DOCS_ANSWER_MAX_TOKENS = 800
DOCS_CONTEXT_MAX_TOKENS = PROJECT_CONTEXT_BUDGET.max_tokens
INSUFFICIENT_EVIDENCE_MAX_TOKENS = 300
MAX_DOCS_SOURCES = PROJECT_CONTEXT_BUDGET.max_sources
DOCS_SOURCE_FIELDS = frozenset({"evidence_id", "path_or_url", "section", "snippet",
                                "version_binding", "content_sha256"})
DOCS_CONTEXT_SOURCE_FIELDS = frozenset({
    "evidence_id", "path_or_url", "section", "snippet", "version_binding",
    "content_sha256", "project_identity", "line_start", "line_end",
    "authority", "scope",
})
PATCH_SOURCE_FIELDS = frozenset({"evidence_id", "path", "symbol_or_section", "authority",
                                 "instruction_trust", "scope", "version_binding", "content_sha256"})
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
_OPTIONAL_INSUFFICIENT_KEYS = ("operational_status", "context_available", "disposition")

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


def _request_input_limit_failures(question: str, retrieval: dict[str, Any], decision: Any = None) -> list[str]:
    """Validate current bounded inputs independently of cached answer decisions."""
    fresh = build_requirements(
        question, profile="project_docs_answer",
        required_evidence_paths=retrieval.get("required_evidence_paths") or (),
        required_target_paths=retrieval.get("required_target_paths") or (),
        public_requirements=retrieval.get("public_requirements") or (),
    )
    failures = {row.requirement_id for row in fresh if row.requirement_id.startswith("input_limit:")}
    failures.update(str(value) for value in retrieval.get("missing_requirement_ids") or ()
                    if str(value).startswith("input_limit:"))
    selection = decision if decision is not None else retrieval.get("selection_decision")
    if isinstance(selection, dict):
        missing = selection.get("missing_requirements") or ()
    else:
        missing = getattr(selection, "missing_requirements", ())
    failures.update(str(value) for value in missing if str(value).startswith("input_limit:"))
    requirements = retrieval.get("requirements") or ()
    if isinstance(requirements, dict):
        requirements = requirements.get("requirements") or ()
    for row in requirements:
        identity = row.get("requirement_id", "") if isinstance(row, dict) else getattr(row, "requirement_id", "")
        if str(identity).startswith("input_limit:"):
            failures.add(str(identity))
    return sorted(failures)


def _requires_exact_snapshot(retrieval: dict[str, Any], decision: Any = None) -> bool:
    if retrieval.get("exact_snapshot_required"):
        return True
    selection = decision if decision is not None else retrieval.get("selection_decision")
    selected_requirements = (selection.get("requirements") if isinstance(selection, dict)
                             else getattr(selection, "requirements", None))
    for contract in (retrieval.get("requirements"), selected_requirements):
        rows = contract.get("requirements", ()) if isinstance(contract, dict) else contract or ()
        for row in rows:
            kind = row.get("kind") if isinstance(row, dict) else getattr(row, "kind", None)
            mandatory = row.get("mandatory", True) if isinstance(row, dict) else getattr(row, "mandatory", True)
            if kind == "exact_snapshot" and mandatory:
                return True
    return False


def _normalize_projection_requirements(value: Any) -> EvidenceRequirementSet | None:
    """Hydrate current contracts once; malformed serialization is not no scope."""
    if value is None:
        return None
    if isinstance(value, EvidenceRequirementSet):
        rows = value.requirements
        metadata = None
    elif isinstance(value, dict):
        if "requirements" not in value:
            raise ValueError("serialized requirements are missing their rows")
        rows = value["requirements"]
        metadata = {key: item for key, item in value.items() if key != "requirements"}
    else:
        rows = value
        metadata = {}
    if not isinstance(rows, (list, tuple)):
        raise ValueError("requirements must be a row sequence")
    normalized = []
    for row in rows:
        if isinstance(row, dict):
            row = EvidenceRequirement(**row)
        if not isinstance(row, EvidenceRequirement):
            raise ValueError("invalid evidence requirement row")
        if any(not isinstance(item, str) or not item.strip() for item in (
            row.requirement_id, row.kind, row.value, row.public_provenance,
        )) or not isinstance(row.mandatory, bool):
            raise ValueError("invalid evidence requirement binding")
        normalized.append(row)
    for kind in ("project_identity", "module_id", "exact_version"):
        if len({row.value for row in normalized if row.kind == kind and row.mandatory}) > 1:
            raise ValueError("conflicting mandatory request scope")
    if metadata is None:
        return replace(value, requirements=tuple(normalized))
    return EvidenceRequirementSet(requirements=tuple(normalized), **metadata)


def project_docs_answer(
    *,
    question: str,
    retrieval: dict[str, Any],
    max_tokens: int = DOCS_ANSWER_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
    canonical_selection: SelectionDecision | AggregateMixedSelectionDecision | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Create one deduplicated source list and an internal immutable snapshot."""

    blocked = _explicit_delivery_block(retrieval, kind="docs_answer", max_tokens=max_tokens)
    if blocked is not None:
        return blocked, {}
    try:
        current_requirements = _normalize_projection_requirements(retrieval.get("requirements"))
    except (ValueError, TypeError, AttributeError):
        return project_insufficient(
            kind="docs_answer", missing=["Current context requirements are invalid."],
            recommended_next_action=None, max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
        ), {}
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
                "context_available": False,
                "answer_supported": False,
                "answer_available": False,
                "edit_ready": False,
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
        try:
            decision = select_evidence(
                candidates,
                question=question,
                config=selection_config,
                trust_contract=retrieval.get("trust_contract") or {},
                exact_version=_requested_exact_version(retrieval),
                required_evidence_paths=retrieval.get("required_evidence_paths") or (),
                required_target_paths=retrieval.get("required_target_paths") or (),
                public_requirements=retrieval.get("public_requirements") or (),
                requirements=current_requirements,
                library_requirement_contract=retrieval.get("library_requirement_contract"),
                project_identity=retrieval.get("project_identity"),
                module_id=retrieval.get("module_id"),
            )
        except (ValueError, TypeError, AttributeError):
            return project_insufficient(
                kind="docs_answer", missing=["Current context scope could not be validated."],
                recommended_next_action=None, max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
            ), {}
    # Recheck supplied/cached selections under current technical eligibility.
    # Old support booleans and semantic assignments are never projection authority.
    if canonical_decision_supplied:
        fresh_scope = build_requirements(
            question, profile=selection_config.profile,
            required_evidence_paths=retrieval.get("required_evidence_paths") or (),
            required_target_paths=retrieval.get("required_target_paths") or (),
            public_requirements=retrieval.get("public_requirements") or (),
            exact_version=_requested_exact_version(retrieval),
            project_identity=retrieval.get("project_identity"), module_id=retrieval.get("module_id"),
        )
        try:
            current_rows = tuple(current_requirements) if current_requirements is not None else ()
            merged: dict[str, EvidenceRequirement] = {}
            for contract in (current_rows, fresh_scope, decision.requirements):
                for row in contract:
                    previous = merged.get(row.requirement_id)
                    if previous is not None:
                        if previous != row and (previous.mandatory or row.mandatory):
                            raise ValueError("conflicting mandatory requirement identity")
                        continue
                    merged[row.requirement_id] = row
            # Multiple mandatory scope bindings cannot be treated as alternatives.
            # In particular, an old path must not widen the current path allowlist.
            for kind in ("project_identity", "module_id", "exact_version", "evidence_path"):
                scopes = [
                    {row.value for row in contract if row.kind == kind and row.mandatory}
                    for contract in (current_rows, fresh_scope, decision.requirements)
                ]
                nonempty = [scope for scope in scopes if scope]
                if kind != "evidence_path" and any(len(scope) > 1 for scope in nonempty):
                    raise ValueError("conflicting mandatory request scope")
                if nonempty and any(scope != nonempty[0] for scope in nonempty[1:]):
                    raise ValueError("conflicting mandatory request scope")
            checked_requirements = replace(decision.requirements, requirements=tuple(merged.values()))
            decision = select_evidence(
                [candidate.original for candidate in decision.selected_candidates],
                question=question, config=selection_config, requirements=checked_requirements,
                trust_contract=retrieval.get("trust_contract") or {},
                project_identity=retrieval.get("project_identity"), module_id=retrieval.get("module_id"),
            )
        except (ValueError, TypeError, AttributeError):
            return project_insufficient(
                kind="docs_answer", missing=["Canonical context scope could not be revalidated."],
                recommended_next_action=None, max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
            ), {}
    if selection_diagnostics is not None:
        selection_diagnostics.update(decision.audit_manifest())
    technical_failures = _request_input_limit_failures(question, retrieval, decision)
    # Apply the established question bound even to generic and cached profiles.
    # Context-only is a weaker answer claim, not permission to bypass limits.
    if len(question) > 4_000 and "input_limit:question" not in technical_failures:
        technical_failures.append("input_limit:question")
    if technical_failures:
        return project_insufficient(
            kind="docs_answer", missing=technical_failures,
            recommended_next_action=None,
            max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
        ), {}
    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    omitted = len(decision.omissions)
    selected_candidates = list(decision.selected_candidates)
    exact_snapshot_required = _requires_exact_snapshot(retrieval, decision)
    for candidate in selected_candidates:
        if exact_snapshot_required and candidate.docs_snapshot_exact is not True:
            omitted += 1
            continue
        if len(sources) >= MAX_DOCS_SOURCES:
            omitted += 1
            continue
        scoped_paths = {row.value.replace("\\", "/").casefold().removeprefix("./")
                        for row in decision.requirements if row.kind == "evidence_path" and row.mandatory}
        source_path = candidate.path_or_url.replace("\\", "/").casefold().removeprefix("./")
        if scoped_paths and not any(source_path == path or source_path.endswith("/" + path) for path in scoped_paths):
            omitted += 1
            continue
        original = candidate.original
        expected_identity = retrieval.get("project_identity")
        identity = str(original.get("project_identity") or "").strip()
        if (
            ((expected_identity or original.get("source_class") == "project_doc") and not identity)
            or (expected_identity and identity != expected_identity)
            or original.get("stale")
            or str(original.get("freshness") or "current") != "current"
            or str(original.get("index_freshness") or "synchronized") != "synchronized"
            or not lifecycle_allows(original, "current")
        ):
            omitted += 1
            continue
        requested_version = _requested_exact_version(retrieval)
        if requested_version and candidate.resolved_version != requested_version:
            omitted += 1
            continue
        item = dict(candidate.original)
        # Render exactly the normalized eligible display, never an unselected
        # metadata code block or a larger raw-content alias.
        item.pop("code", None)
        item.update(snippet=candidate.display_text, display_text=candidate.display_text,
                    source_url=candidate.path_or_url, heading_path=candidate.section,
                    version_binding=candidate.version_binding)
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

    # Incompleteness is not a source-safety failure. Confirmation, trust and
    # technical eligibility still fail closed; answer availability does not.
    if (retrieval.get("requires_confirmation")
        or retrieval.get("status") == "confirmation_required" or decision.unresolved_conflicts):
        sources, snapshot = [], {}
    payload: dict[str, Any] = {
        "status": "ok",
        "kind": "docs_answer",
        "retrieval_only": True,
        "answer_policy": "cite_only",
        "answer_supported": False, "answer_available": False, "edit_ready": False,
        "support_status": "insufficient_evidence", "reason_code": "context_only",
        "context_available": bool(sources),
        "satisfied_requirement_ids": [], "selected_evidence_ids": [],
        "mandatory_coverage": 0.0, "evidence_coverage": 0.0,
        "sources": sources,
        "omitted_counts": {"sources": omitted} if omitted else {},
        "estimated_tokens": 0,
    }
    limit = min(DOCS_ANSWER_MAX_TOKENS, max_tokens)
    while sources and estimate_projection_tokens(payload) > limit:
        dropped = sources.pop()
        snapshot.pop(dropped["evidence_id"], None)
        omitted += 1
        payload["omitted_counts"] = {"sources": omitted}
    payload["context_available"] = bool(sources)
    if not sources:
        return project_insufficient(
            kind="docs_answer", missing=["No safe bounded selected context is available."],
            recommended_next_action=None, max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, limit),
        ), {}
    _refresh_estimate(payload)
    return payload, snapshot


def _explicit_delivery_block(
    retrieval: dict[str, Any], *, kind: str, max_tokens: int,
) -> dict[str, Any] | None:
    """Keep explicit operational/consent vetoes ahead of quote recovery."""
    delivery = retrieval.get("delivery_decision")
    delivery = delivery if isinstance(delivery, dict) else {}
    confirmation = bool(retrieval.get("requires_confirmation")
                        or retrieval.get("status") == "confirmation_required")
    if not confirmation and delivery.get("deliverable") is not False:
        return None
    reason = str(delivery.get("reason_code") or retrieval.get("reason_code")
                 or ("confirmation_required" if confirmation else "delivery_blocked"))[:120]
    payload = project_insufficient(
        kind=kind, missing=[reason], recommended_next_action=None,
        max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
    )
    payload.update(
        reason_code=reason, context_available=False, answer_supported=False,
        answer_available=False, edit_ready=False, support_status="insufficient_evidence",
        requires_confirmation=confirmation,
        delivery_decision={"deliverable": False, "reason_code": reason},
    )
    if retrieval.get("confirmation_reason"):
        payload["confirmation_reason"] = str(retrieval["confirmation_reason"])[:120]
    if retrieval.get("status"):
        payload["operational_status"] = str(retrieval["status"])[:120]
    bound_insufficient_projection(payload, max_tokens=max_tokens)
    return payload


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
    *, packet: dict[str, Any], evidence_items: Iterable[dict[str, Any]],
    project_path: str | None = None, module_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Preserve the complete admitted v4 windows, without edit authorization."""
    from .action_packet import refresh_action_packet_estimate

    evidence_items = tuple(evidence_items)
    packet_errors = validate_action_packet(
        packet, evidence_items=evidence_items, project_path=project_path, module_path=module_path,
    )
    if packet_errors:
        failure = {
            "schema_version": 4, "result": "failure", "completeness": "unavailable",
            "edit_ready": False, "kind": "patch_context",
            "missing": ["invalid_action_packet"], "estimated_tokens": 1,
        }
        refresh_action_packet_estimate(failure)
        return failure, {}

    raw_evidence: dict[str, dict[str, Any]] = {}
    for original in evidence_items:
        if not isinstance(original, dict):
            continue
        for authority in ("canonical", "supporting"):
            candidate = deepcopy(original)
            candidate["_packet_authority"] = authority
            evidence_id, _, _ = evidence_identity_for_item(candidate)
            raw_evidence.setdefault(evidence_id, deepcopy(original))
    snapshot: dict[str, dict[str, Any]] = {
        "__action_packet__": {
            "packet": deepcopy(packet), "evidence_items": deepcopy(evidence_items),
            "project_path": project_path, "module_path": module_path,
        },
    }
    for row in packet.get("sources") or []:
        evidence_id = row["evidence_id"]
        snapshot[evidence_id] = _snapshot_entry(raw_evidence[evidence_id], deepcopy(row))
    payload = deepcopy(packet)
    payload["kind"] = "patch_context"
    refresh_action_packet_estimate(payload)
    return payload, snapshot


def patch_search_targets(packet: dict[str, Any]) -> list[dict[str, str]]:
    """Return only explicitly supplied targets, without representation limits."""
    mutation = packet.get("mutation_intent") or {}
    targets = [
        {"kind": row["kind"], "value": row["value"]}
        for row in mutation.get("requested_targets") or []
        if isinstance(row, dict) and row.get("kind") in {"path", "symbol"}
        and isinstance(row.get("value"), str) and row["value"]
    ]
    requirements = packet.get("requirements") or []
    if isinstance(requirements, dict):
        requirements = requirements.get("requirements") or []
    targets.extend(
        {"kind": "path", "value": row["value"]}
        for row in requirements
        if isinstance(row, dict) and row.get("kind") == "target_path"
        and isinstance(row.get("value"), str) and row["value"]
    )
    return [dict(kind=kind, value=value) for kind, value in dict.fromkeys(
        (row["kind"], row["value"]) for row in targets
    )]


def _validate_patch_projection(
    payload: dict[str, Any], *, snapshot: dict[str, dict[str, Any]],
) -> list[str]:
    from .action_packet import refresh_action_packet_estimate, serialize_action_packet

    metadata = {"kind", "recommended_next_action", "source_search_status"}
    core = {key: deepcopy(value) for key, value in payload.items() if key not in metadata}
    estimated = deepcopy(payload)
    refresh_action_packet_estimate(estimated)
    errors = []
    if payload.get("estimated_tokens") != estimated["estimated_tokens"]:
        errors.append("projection estimate mismatch")
    refresh_action_packet_estimate(core)
    canonical = snapshot.get("__action_packet__") or {}
    if not isinstance(canonical, dict):
        return ["invalid canonical patch snapshot"]
    evidence = canonical.get("evidence_items", ())
    if not isinstance(evidence, (tuple, list)):
        return ["invalid canonical patch evidence"]
    errors.extend(validate_action_packet(
        core, evidence_items=evidence, project_path=canonical.get("project_path"),
        module_path=canonical.get("module_path"),
    ))
    if errors:
        return errors
    if canonical:
        if (not isinstance(canonical.get("packet"), dict)
            or serialize_action_packet(core) != serialize_action_packet(canonical["packet"])):
            errors.append("patch packet does not match the internal snapshot")
    elif core.get("sources") or core.get("requirements") or core.get("mutation_intent"):
        errors.append("patch contract is missing its canonical snapshot")
    ids = set()
    for source in core.get("sources") or []:
        if not isinstance(source, dict):
            continue
        identity = source.get("evidence_id")
        if not isinstance(identity, str):
            continue
        ids.add(identity)
        bound = snapshot.get(identity) or {}
        if not isinstance(bound, dict):
            errors.append("invalid patch source snapshot")
            continue
        if source != bound.get("projected_source"):
            errors.append("patch source does not match the internal snapshot")
        if bound.get("source") not in evidence:
            errors.append("patch snapshot source does not match admitted evidence")
    if set(snapshot) - {"__action_packet__"} != ids:
        errors.append("patch snapshot evidence identities do not match visible sources")
    errors.extend(_patch_recovery_errors(payload, core))
    return errors


def _patch_recovery_errors(payload: dict[str, Any], core: dict[str, Any]) -> list[str]:
    errors = []
    action = payload.get("recommended_next_action")
    search_status = payload.get("source_search_status")
    if ("recommended_next_action" in payload and action is None
        or "source_search_status" in payload and search_status is None):
        errors.append("empty patch recovery metadata must be omitted")
    if action is not None:
        targets = patch_search_targets(core)
        expected = {
            "tool": "code_search", "type": "search_local_source",
            "handled_by": "coding_agent", "auto_execute": False,
            "requires_confirmation": False, "repeat_docs_context": False,
            "query_terms": [row["value"] for row in targets],
            "suggested_doc_paths": [row["value"] for row in targets if row["kind"] == "path"],
            "suggested_symbols": [row["value"] for row in targets if row["kind"] == "symbol"],
        }
        expected = {key: value for key, value in expected.items() if value != []}
        if (not targets or not isinstance(action, dict) or action != expected
            or search_status != "required"
            or any(action.get(key) is not False for key in (
                "auto_execute", "requires_confirmation", "repeat_docs_context",
            ))):
            errors.append("invalid non-authorizing patch recovery metadata")
    elif search_status is not None:
        errors.append("patch source search status requires explicit recovery metadata")
    return errors


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
    if kind == "patch_context":
        payload["edit_ready"] = False
    if kind == "docs_answer":
        payload.update(answer_supported=False, answer_available=False, edit_ready=False)
    if kind == "docs_context":
        from .context_quality import context_quality
        payload["context_quality"] = context_quality(sources=())
        payload["read_next"] = []
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
    payload: Any, *, snapshot: dict[str, dict[str, Any]], max_tokens: int | None = None,
    canonical_selection: SelectionDecision | AggregateMixedSelectionDecision | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["model-visible projection must be an object"]
    if payload.get("kind") == "patch_context":
        return _validate_patch_projection(payload, snapshot=snapshot)
    if max_tokens is None:
        return ["docs projections require a token budget"]
    forbidden = sorted(_find_forbidden_keys(payload))
    if forbidden:
        errors.append("forbidden model-visible keys: " + ", ".join(forbidden))
    status, kind = payload.get("status"), payload.get("kind")
    if kind not in {"docs_answer", "docs_context", "patch_context"}:
        errors.append("invalid projection kind")
    if status not in {"ok", "truncated", "insufficient_evidence"}:
        errors.append("invalid projection status")
    if "edit_ready" in payload and payload.get("edit_ready") is not False:
        errors.append("context projection must not authorize edits")
    if kind == "patch_context" and payload.get("edit_ready") is not False:
        errors.append("patch context must not authorize edits")
    if kind == "docs_answer" and status in {"ok", "truncated"} and payload.get("retrieval_only") is not True:
        errors.append("docs answer projection requires current retrieval-only policy")
    limit = (
        min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens)
        if status == "insufficient_evidence"
        else max_tokens
    )
    actual = estimate_projection_tokens(payload)
    if payload.get("estimated_tokens") != actual or actual > limit:
        errors.append("projection estimate mismatch or budget exceeded")
    if (
        kind == "docs_context"
        and status in {"ok", "truncated"}
        and docs_context_budget_tokens(payload) > max_tokens
    ):
        errors.append("docs_context conservative budget exceeded")
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
        optional = {"source_uri"} if kind == "docs_context" else set()
        missing = sorted(allowed_fields - set(source))
        unknown = sorted(set(source) - allowed_fields - optional)
        for key in missing:
            errors.append(f"projection source field is missing: {key}")
        if unknown:
            errors.append(
                "projection source contains unknown fields: " + ", ".join(unknown)
            )
        if set(expected) - optional != allowed_fields:
            errors.append("internal snapshot projected source schema is invalid")
        if (set(source) & optional != set(expected) & optional
            or source.get("source_uri") != expected.get("source_uri")):
            errors.append("projection source locator does not match the internal snapshot")
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
    if kind == "docs_answer" and payload.get("retrieval_only") is True:
        if (payload.get("answer_supported") is not False
            or payload.get("answer_available") is not False or payload.get("edit_ready") is not False
            or payload.get("answer_policy") != "cite_only"):
            errors.append("retrieval-only docs quotes must not authorize answers or edits")
        if (payload.get("answer") or payload.get("answer_evidence_ids")
            or payload.get("selected_evidence_ids") or payload.get("satisfied_requirement_ids")
            or payload.get("mandatory_coverage") != 0.0 or payload.get("evidence_coverage") != 0.0):
            errors.append("retrieval-only docs quotes must not claim proof coverage")
    elif kind == "docs_answer":
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
                if not validate_assignment_binding(
                    requirement, candidate, assignment, requirements=decision.requirements,
                ):
                    errors.append("model-visible assignment failed unit proof revalidation")
                    continue
                unit = resolve_assignment_unit(candidate, assignment)
                if unit is not None and unit.text not in str(visible.get("snippet") or ""):
                    errors.append("model-visible assignment unit is absent from its cited source")
    if kind == "docs_context":
        if payload.get("answer_policy") != "cite_only":
            errors.append("docs_context answer policy must be cite_only")
        if payload.get("answer_supported") is not False or payload.get("answer_available") is not False:
            errors.append("docs_context must not claim a supported answer")
        if payload.get("edit_ready") is not False:
            errors.append("docs_context must not authorize edits")
        if payload.get("implementation_guidance") or payload.get("invariants") or payload.get("targets"):
            errors.append("docs_context must not contain edit guidance")
        if any(not str(source.get("project_identity") or "").strip() for source in sources):
            errors.append("docs_context sources require project identity")
        errors.extend(validate_context_selection_payload(payload, sources, snapshot=snapshot))
    if kind == "patch_context":
        mutation = payload.get("mutation_intent")
        if not isinstance(mutation, dict):
            errors.append("patch context requires a mutation intent contract")
        elif mutation.get("operation") != "none" and mutation.get("ready") is not True:
            errors.append("successful patch context requires operation-aware target readiness")
        if any(source.get("instruction_trust") != "untrusted_data" for source in sources):
            errors.append("patch context sources must remain untrusted document data")
        if any((payload.get("checks") or {}).get(field) for field in ("compile", "tests", "semantic_checks")):
            errors.append("patch context cannot promote document data to workflow checks")
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
    display_snippet: str | None = None,
) -> dict[str, Any] | None:
    path = str(item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or "").strip()
    section = str(item.get("heading_path") or item.get("title") or "document").strip()
    snippet = display_snippet if display_snippet is not None else (
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
    # Source quotation is not proof of actionability; no prose exemption.
    return True


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
