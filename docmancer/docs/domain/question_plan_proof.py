"""Fail-closed compatibility adapters for former semantic QuestionPlan proof.

No subject synonym, topical relation or expected product answer is proof.
Source identity/span/condition validation remains with the surrounding owners.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation


@dataclass(frozen=True, slots=True)
class PlannedProof:
    valid: bool
    relation_score: int = 0
    value_score: int = 0
    reason: str = ""
    subject_score: int = 0


def _semantic_terms(value: object) -> set[str]:
    """Literal tokens only, without translated/inflected semantic identities."""
    return set(re.findall(r"[^\W]+", str(value or ""), re.UNICODE))


def _bounded_subject_aliases(subject: str) -> tuple[str, ...]:
    return ()


def _proposition_clauses(text: str) -> tuple[str, ...]:
    """Keep bounded source segmentation; it does not authorize entailment."""
    source = str(text or "")
    clauses: list[str] = []
    start = 0
    for boundary in re.finditer(r"(?:[.!?](?=\s|$)|;|\n)", source):
        end = boundary.end()
        clause = source[start:end].strip()
        if clause:
            clauses.append(clause)
        start = end
    tail = source[start:].strip()
    if tail:
        clauses.append(tail)
    return tuple(clauses)


def relation_proof(
    obligation: ProofObligation, text: str, *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    # Return an explicit negative verdict, not None (legacy fallback).
    return PlannedProof(False, reason="semantic_proof_unavailable")


def usage_proof(
    obligation: ProofObligation, text: str, *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    return PlannedProof(False, reason="semantic_proof_unavailable")


def workflow_proof(
    obligation: ProofObligation, text: str, *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    return PlannedProof(False, reason="semantic_proof_unavailable")


def behavior_proof(
    obligation: ProofObligation, text: str, *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    return PlannedProof(False, reason="semantic_proof_unavailable")


__all__ = [
    "PlannedProof", "behavior_proof", "relation_proof", "usage_proof",
    "workflow_proof",
]
