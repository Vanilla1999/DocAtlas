"""Fail-closed compatibility boundary for former NL governance proof.

Authority identities remain protocol values, not evidence of policy meaning.
Neither canonical metadata nor a supplied proposition authorizes an answer.
"""
from __future__ import annotations

from typing import Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.question_plan_proof import (
    PlannedProof,
    relation_proof as _legacy_relation_proof,
)

_GOVERNANCE_RELATIONS = frozenset({
    "governed_scope", "governance_facet", "governance_ownership",
    "governance_requirement", "governance_state", "governance_version",
})
_CANONICAL_AUTHORITIES = frozenset({
    "canonical", "source_of_truth", "official", "primary",
    "project_owned", "project_rule",
})


def _canonical_source(source: Mapping[str, object] | None) -> bool:
    if not source:
        return False
    authority = str(source.get("project_doc_authority") or source.get("authority") or "").casefold()
    return authority in _CANONICAL_AUTHORITIES


def relation_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PlannedProof | None:
    """Return an immutable negative verdict; unknown relations cannot fall through."""
    if obligation.relation not in _GOVERNANCE_RELATIONS:
        return _legacy_relation_proof(obligation, text, source=source)
    if not _canonical_source(source):
        return PlannedProof(False, reason="governance_authority_missing")
    return PlannedProof(False, reason="semantic_proof_unavailable")


__all__ = ["relation_proof"]
