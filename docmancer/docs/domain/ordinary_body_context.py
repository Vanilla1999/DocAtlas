"""Source-bound context admission without inferred relevance or answer authority."""
from __future__ import annotations

from typing import Any, Mapping

from .original_body_discovery import (
    original_body_discovery_binding,
    original_body_derivation_binding,
)
from .source_subject_binding import prepared_owner_rejection


def body_request_constraint_rejection(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> str | None:
    """Question-wide names do not determine source validity."""
    return None


def ordinary_body_context_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    return source_valid_original_candidate_witness(
        question=question, evidence_text=evidence_text, candidate=candidate,
    )


def policy_valid_original_candidate_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    return source_valid_original_candidate_witness(
        question=question, evidence_text=evidence_text, candidate=candidate,
    )


def source_valid_original_candidate_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
    native_candidate: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a complete verified window; source validity is not relevance."""
    binding = (
        original_body_discovery_binding(question=question, body=evidence_text, candidate=candidate)
        if native_candidate is None else original_body_derivation_binding(
            question=question, body=evidence_text, candidate=candidate, native_candidate=native_candidate,
        )
    )
    if binding is None or not evidence_text.strip():
        return None
    evidence = candidate["_reference_evidence"]
    if prepared_owner_rejection(evidence) is not None:
        return None
    start, end = evidence["char_start"], evidence["char_end"]
    return {
        "kind": "source_valid_original_candidate_v1", "relevance_unassessed": True,
        "admission_contract": "source_only_heuristic_removal_v1", "coverage_credit": False,
        "text": evidence["raw_document"][start:end],
        "char_start": start, "char_end": end,
        "block_char_start": start, "block_char_end": end,
        "native_discovery_binding_sha256": binding,
    }
