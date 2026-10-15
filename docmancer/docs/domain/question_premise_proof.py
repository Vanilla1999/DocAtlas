"""Negative compatibility results for former natural-language premise proof."""
from __future__ import annotations

from typing import Mapping, TypeAlias

from docmancer.docs.domain.project_answer_contract import ProofObligation

PremiseProofResult: TypeAlias = tuple[bool, int, int, str, int]


def _premise_check(obligation: ProofObligation, text: str) -> PremiseProofResult:
    return False, 0, 0, "premise_truth_unresolved", 0


def _premise_cardinality(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None,
) -> PremiseProofResult:
    return False, 0, 0, "premise_cardinality_unresolved", 0


def premise_relation_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PremiseProofResult | None:
    """Always return a negative tuple, including for an unknown relation.

    Metadata, causal wording, action synonyms and tool counts confer no credit.
    A tuple preserves the legacy ABI and provides an immutable negative trace.
    """
    if obligation.relation == "premise_check":
        return _premise_check(obligation, text)
    if obligation.relation == "premise_cardinality":
        return _premise_cardinality(obligation, text, source=source)
    return False, 0, 0, "semantic_proof_unavailable", 0


__all__ = ["PremiseProofResult", "premise_relation_proof"]
