"""Compatibility helpers: source scope and lexical modality are not proof."""
from __future__ import annotations

from docmancer.docs.application.evidence_models import EvidenceCandidate, EvidenceRequirement


def source_scoped_behavioral_match(
    requirement: EvidenceRequirement,
    unit_text: str,
    candidate: EvidenceCandidate,
) -> bool:
    # Technical source/identity guards remain in selector eligibility. This
    # semantic predicate cannot authorize a behavioral source_fact obligation.
    return False


def source_fact_unit_semantic_score(text: str) -> int:
    return 0


__all__ = ["source_fact_unit_semantic_score", "source_scoped_behavioral_match"]
