"""Compiler unresolved state must not become apparently resolved ownership."""
import pytest

from docmancer.docs.domain.question_ownership import classify_question_ownership


@pytest.mark.parametrize("question", [
    "", " ", "unknown question", "Как это работает?", "Synchronize project docs",
    "`Client.send` returns what?", "x" * 5000,
])
def test_untyped_question_reports_unresolved_ownership(question):
    observed = classify_question_ownership(question)
    assert observed.owner == "unsupported"
    assert "unresolved_question_semantics" in observed.unresolved_parts
    assert observed.signature == ()
    assert observed == classify_question_ownership(question)
