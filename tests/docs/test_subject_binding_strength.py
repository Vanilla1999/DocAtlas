from __future__ import annotations

import pytest

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


@pytest.mark.parametrize("lead", ["Since", "From"])
def test_version_capability_binds_subject_from_grammar_not_sentence_lead(lead: str):
    question = (
        f"{lead} which version can preview be configured separately "
        "for linting and formatting?"
    )
    contract = build_project_answer_contract(question)
    version = [
        item for item in contract.proof_obligations
        if item.kind == "attribute" and item.attribute == "version"
    ]

    assert len(version) == 1
    assert version[0].subject.casefold() == "preview"
    assert version[0].query_span_text is not None
    assert lead.casefold() not in {item.subject.casefold() for item in contract.proof_obligations}


def test_explicit_technical_version_subject_keeps_strong_identity():
    question = "Since which version can `lint.preview` be configured separately?"
    contract = build_project_answer_contract(question)
    version = [
        item for item in contract.proof_obligations
        if item.kind == "attribute" and item.attribute == "version"
    ]

    assert len(version) == 1
    assert version[0].subject == "lint.preview"
    assert version[0].subject_kind == "config_key"
