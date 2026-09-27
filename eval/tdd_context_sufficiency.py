"""Aggregate reviewed evidence assessments without changing any frozen evaluator.

This report-only policy is for annotated, answerable cases. It is not a semantic
judge, a runtime authorization rule, or a measure of the host model's answer.
External integrity, transport and budget checks must be supplied explicitly;
None means not measured, never an implicit success.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_STATES = ("supported", "missing", "contradicted", "needs_review")
_REVIEW_FIELDS = ("review_queue", "unreviewed_sources", "rejected_sources")


def _claims(value: Any, label: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a claim mapping")
    checked = {}
    for key, row in value.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(row, Mapping):
            raise ValueError(f"{label} requires nonempty string IDs and object rows")
        status = row.get("status")
        if not isinstance(status, str) or status not in _STATES:
            raise ValueError(f"Unknown claim status in {label}:{key}")
        unknown = row.get("unreviewed_evidence_ids")
        if not isinstance(unknown, list) or any(
            not isinstance(item, str) or not item.strip() for item in unknown
        ):
            raise ValueError(f"{label}:{key} requires an explicit unreviewed ID list")
        checked[key] = row
    return checked


def summarize_assessment(
    assessment: Mapping[str, Any],
    *,
    required_ids: Sequence[str],
    transport_ok: bool | None,
    citation_integrity: bool | None,
    budget_ok: bool | None,
) -> dict[str, Any]:
    """Summarize assess_context output with an independently supplied inventory.

    Definite failure dominates pending review, but both remain visible. Pending
    review is not called an incorrect answer. Optional claims cannot change the
    required denominator; optional contradictions still block acceptance.
    Malformed input is an evaluator error (ValueError), not a model failure.
    """
    if not isinstance(assessment, Mapping):
        raise ValueError("assessment must be an object")
    case_id = assessment.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a nonempty string")
    if isinstance(required_ids, (str, bytes)) or not isinstance(required_ids, Sequence):
        raise ValueError("required_ids must be an explicit sequence of claim IDs")
    ids = tuple(required_ids)
    if not ids or any(not isinstance(key, str) or not key.strip() for key in ids):
        raise ValueError("Required claim IDs must be nonempty strings")
    if len(set(ids)) != len(ids):
        raise ValueError("Required claim IDs must be unique")
    claims = _claims(assessment.get("claims"), "claims")
    optional = _claims(assessment.get("optional_claims"), "optional_claims")
    if set(claims) != set(ids):
        raise ValueError("Assessed required claims differ from the supplied inventory")
    if set(optional) & set(ids):
        raise ValueError("Required and optional claim IDs must not overlap")
    for field in _REVIEW_FIELDS:
        value = assessment.get(field)
        if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
            raise ValueError(f"{field} must be an explicit list of objects")
    checks = {
        "transport_ok": transport_ok,
        "citation_integrity": citation_integrity,
        "budget_ok": budget_ok,
    }
    if any(value is not None and type(value) is not bool for value in checks.values()):
        raise ValueError("Verification checks must be bool or None, not truthy values")
    groups = {
        state: sorted(key for key in ids if claims[key]["status"] == state)
        for state in _STATES
    }
    supported = len(groups["supported"])
    for field, actual in (("required_count", len(ids)), ("required_supported", supported)):
        if field in assessment and (
            type(assessment[field]) is not int or assessment[field] != actual
        ):
            raise ValueError(f"Inconsistent assessment counter: {field}")
    all_claims = (*claims.values(), *optional.values())
    review_required = bool(
        assessment["review_queue"] or assessment["unreviewed_sources"]
        or any(row["status"] == "needs_review" or row["unreviewed_evidence_ids"] for row in all_claims)
    )
    contradiction = any(row["status"] == "contradicted" for row in all_claims)
    rejected = bool(assessment["rejected_sources"])
    failed_checks = sorted(key for key, value in checks.items() if value is False)
    unmeasured = sorted(key for key, value in checks.items() if value is None)
    full = supported == len(ids)
    if contradiction or groups["missing"] or rejected or failed_checks:
        verdict = "FAIL"
    elif review_required:
        verdict = "REVIEW_REQUIRED"
    elif unmeasured:
        verdict = "NOT_EVALUATED"
    else:
        verdict = "PASS"
    reasons = []
    if groups["missing"]:
        reasons.append("required_fact_missing")
    if contradiction:
        reasons.append("contradictory_evidence")
    if rejected:
        reasons.append("source_policy_rejected")
    if review_required:
        reasons.append("pending_review")
    reasons.extend(f"{key}_failed" for key in failed_checks)
    if unmeasured:
        reasons.append("verification_incomplete")
    return {
        "schema_version": "docatlas-context-sufficiency-summary-v1",
        "case_id": case_id,
        "report_only": True,
        "required_count": len(ids),
        "required_supported": supported,
        "required_claim_coverage": supported / len(ids),
        "full_required_coverage": full,
        "claim_ids_by_status": groups,
        "review_required": review_required,
        "review_complete": not review_required,
        "review_queue_count": len(assessment["review_queue"]),
        "unreviewed_source_count": len(assessment["unreviewed_sources"]),
        "rejected_source_count": len(assessment["rejected_sources"]),
        **checks,
        "unmeasured_checks": unmeasured,
        "final_answer_quality": "NOT_MEASURED",
        "verdict": verdict,
        "reasons": sorted(reasons),
    }
