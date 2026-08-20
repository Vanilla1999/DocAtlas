"""Bounded diagnostics for why source-backed proof could not be completed.

The classifier is deliberately derived from an already-computed selection
verdict.  It never changes selection, support hashes, or answer semantics; it
only explains the failed stage without exposing raw document content.
"""
from __future__ import annotations

from typing import Any, Mapping


PROOFABILITY_SCHEMA_VERSION = 1
_MAX_REASON_CODES = 4
_MAX_MISSING_REQUIREMENTS = 8
_MAX_OMISSION_REASONS = 8

_ELIGIBILITY_REASON_ORDER = (
    "stale",
    "wrong_version",
    "unknown_version",
    "forbidden_source",
    "outside_scope",
    "instruction_risk",
    "invalid_identity",
    "query_identifier_conflict",
    "query_intent_mismatch",
)


def _nonnegative_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if parsed >= 0 else default


def _omission_counts(decision: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for omission in getattr(decision, "omissions", ()) or ():
        code = str(getattr(omission, "reason_code", "") or "").strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _missing_values(decision: Any) -> tuple[str, ...]:
    return tuple(
        str(value).strip()
        for value in getattr(decision, "missing_requirements", ()) or ()
        if str(value).strip()
    )


def _has_missing_suffix(values: tuple[str, ...], suffix: str) -> bool:
    return any(value == suffix or value.endswith(":" + suffix) for value in values)


def diagnose_proofability(decision: Any) -> dict[str, Any]:
    """Return a small deterministic explanation of a selection verdict.

    ``source_documentation`` is used only when the selector has concrete
    evidence that the source material itself is structurally insufficient:
    navigation-only material, conflicting statements, fragmented support that
    cannot fit the bounded proof, or selected evidence that cannot localize all
    mandatory propositions. Retrieval and policy failures remain separate so a
    documentation author is not blamed for an indexing/routing problem.
    """

    support = getattr(decision, "support_decision", None)
    if (
        str(getattr(decision, "status", "")) == "ok"
        and bool(getattr(support, "answer_supported", False))
    ):
        return {
            "schema_version": PROOFABILITY_SCHEMA_VERSION,
            "status": "provable",
            "origin": "none",
            "documentation_issue": False,
            "reason_codes": [],
        }

    metrics: Mapping[str, Any] = (
        getattr(decision, "metrics", {})
        if isinstance(getattr(decision, "metrics", {}), Mapping)
        else {}
    )
    omissions = _omission_counts(decision)
    missing = _missing_values(decision)
    conflicts = tuple(
        str(value).strip()
        for value in getattr(decision, "unresolved_conflicts", ()) or ()
        if str(value).strip()
    )
    selected_candidates = tuple(getattr(decision, "selected_candidates", ()) or ())
    assignments = tuple(getattr(decision, "assignments", ()) or ())

    selected_count = _nonnegative_int(
        metrics.get("selected_count", metrics.get("selected_spans")),
        len(selected_candidates),
    )
    candidate_count = _nonnegative_int(
        metrics.get("candidate_count"),
        selected_count + sum(omissions.values()),
    )
    eligible_count = _nonnegative_int(metrics.get("eligible_count"), selected_count)

    mandatory_ids = tuple(
        str(value)
        for value in getattr(support, "mandatory_requirement_ids", ()) or ()
        if str(value)
    )
    missing_ids = tuple(
        str(value)
        for value in getattr(support, "missing_requirement_ids", ()) or ()
        if str(value)
    )

    reason_codes: list[str] = []
    origin = "selection"
    documentation_issue = False
    recommended_doc_action: str | None = None

    if conflicts:
        origin = "source_documentation"
        documentation_issue = True
        reason_codes.append("conflicting_authoritative_evidence")
        recommended_doc_action = "resolve_conflicting_statements"

    if _has_missing_suffix(missing, "bounded_evidence_not_materializable"):
        origin = "source_documentation"
        documentation_issue = True
        reason_codes.append("fragmented_support_exceeds_bound")
        recommended_doc_action = recommended_doc_action or "co_locate_required_facts"

    if omissions.get("navigation_only", 0) > 0:
        origin = "source_documentation"
        documentation_issue = True
        reason_codes.append("navigation_only_evidence")
        recommended_doc_action = recommended_doc_action or "add_factual_documentation"

    if not reason_codes:
        if candidate_count == 0:
            origin = "retrieval"
            reason_codes.append("no_candidate_evidence")
        elif eligible_count == 0:
            origin = "eligibility"
            reason_codes.append("all_candidate_evidence_ineligible")
            for omission_code in _ELIGIBILITY_REASON_ORDER:
                if omissions.get(omission_code, 0):
                    reason_codes.append("ineligible_" + omission_code)
                    if len(reason_codes) >= _MAX_REASON_CODES:
                        break
        elif missing_ids and selected_count > 0:
            origin = "source_documentation"
            documentation_issue = True
            if mandatory_ids and len(assignments) < len(mandatory_ids):
                reason_codes.append("mandatory_support_not_localized")
                recommended_doc_action = "add_explicit_proposition"
            else:
                reason_codes.append("mandatory_requirement_uncovered")
                recommended_doc_action = "document_missing_requirement"
        elif missing_ids:
            origin = "selection"
            reason_codes.append("no_bounded_support_selection")
        else:
            reason_codes.append("support_not_provable")

    bounded_omissions = {
        key: omissions[key]
        for key in sorted(omissions)[:_MAX_OMISSION_REASONS]
    }
    result: dict[str, Any] = {
        "schema_version": PROOFABILITY_SCHEMA_VERSION,
        "status": "blocked",
        "origin": origin,
        "documentation_issue": documentation_issue,
        "reason_codes": reason_codes[:_MAX_REASON_CODES],
        "candidate_count": candidate_count,
        "eligible_count": eligible_count,
        "selected_count": selected_count,
        "assignment_count": len(assignments),
        "missing_requirement_ids": list(missing_ids[:_MAX_MISSING_REQUIREMENTS]),
        "omission_counts": bounded_omissions,
    }
    if recommended_doc_action:
        result["recommended_doc_action"] = recommended_doc_action
    return result


__all__ = ["PROOFABILITY_SCHEMA_VERSION", "diagnose_proofability"]
