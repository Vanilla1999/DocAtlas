"""Quantified attribute questions require a local value, not a subject mention."""
from __future__ import annotations

from docmancer.docs.domain.answer_units import best_local_proof, extract_answer_units
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


QUESTION = "How many retry attempts does ProjectRetryPolicy allow?"


def _obligation():
    contract = build_project_answer_contract(QUESTION)
    assert not contract.unresolved_parts
    assert len(contract.proof_obligations) == 1
    return contract.proof_obligations[0]


def test_how_many_subject_attribute_builds_numeric_obligation():
    obligation = _obligation()
    assert obligation.kind == "attribute"
    assert obligation.subject == "ProjectRetryPolicy"
    assert obligation.attribute == "retry attempts"
    assert obligation.value_kind == "number"
    assert obligation.response_mode == "count"


def test_subject_mention_without_requested_numeric_attribute_is_not_proof():
    obligation = _obligation()
    text = "OrderSubmission validates a draft and delegates network retry decisions to ProjectRetryPolicy."
    units = tuple(unit for unit in extract_answer_units(text, include_soft_wrapped_prose=True) if unit.proposition)
    assert best_local_proof(obligation, units, source={"authority": "canonical"}) is None


def test_local_numeric_attribute_sentence_is_proof():
    obligation = _obligation()
    text = "ProjectRetryPolicy allows at most two retry attempts with bounded exponential backoff."
    units = tuple(unit for unit in extract_answer_units(text, include_soft_wrapped_prose=True) if unit.proposition)
    assert best_local_proof(obligation, units, source={"authority": "canonical"}) is not None
