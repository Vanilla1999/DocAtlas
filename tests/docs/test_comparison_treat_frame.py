import pytest

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.question_plan import _semantic_comparison, compile_question_plan
from docmancer.docs.domain.question_semantic_frames import match_comparison_frame


@pytest.mark.parametrize(
    "question,left,right,context",
    [
        (
            "How should current documentation answers treat CHANGELOG.md "
            "compared with current source-of-truth documentation?",
            "CHANGELOG.md",
            "current source-of-truth documentation",
            "current documentation answers",
        ),
        (
            "How should current API answers treat NOTES.rst "
            "compared with maintained interface documentation?",
            "NOTES.rst",
            "maintained interface documentation",
            "current API answers",
        ),
        (
            "How should current API answers treat `NOTES.rst` "
            "compared to maintained interface documentation?",
            "NOTES.rst",
            "maintained interface documentation",
            "current API answers",
        ),
    ],
)
def test_treat_comparison_keeps_operands_and_context(question, left, right, context):
    frame = match_comparison_frame(question)
    assert frame is not None
    assert frame.left == left
    assert frame.right == right
    assert getattr(frame, "context", None) == context


@pytest.mark.parametrize(
    "question",
    [
        "Compare Alpha with Beta.",
        "How does Alpha differ from Beta?",
        "What is the difference between Alpha and Beta?",
        "Сравни Alpha с Beta.",
    ],
)
def test_existing_forms_are_unchanged(question):
    frame = match_comparison_frame(question)
    assert frame is not None
    assert (frame.left, frame.right) == ("Alpha", "Beta")
    assert getattr(frame, "context", None) is None


@pytest.mark.parametrize(
    "question",
    [
        "The words compared with occur in an example.",
        "How should callers treat Alpha compared with Alpha?",
        "How should callers treat Alpha compared with?",
    ],
)
def test_noncomparison_or_invalid_operands_are_not_invented(question):
    assert match_comparison_frame(question) is None

def test_comparison_plan_keeps_current_answer_context():
    question = (
        "How should current documentation answers treat CHANGELOG.md "
        "compared with current source-of-truth documentation?"
    )
    plan = _semantic_comparison(question)
    assert plan is not None
    assert len(plan.facets) == 1
    facet = plan.facets[0]
    assert facet.subject == "CHANGELOG.md"
    assert facet.target == "current source-of-truth documentation"
    assert facet.relation == "contrast"
    assert facet.context == "current documentation answers"

def test_compound_comparison_does_not_hide_unresolved_request():
    plan = compile_question_plan(
        "How should current documentation answers treat CHANGELOG.md "
        "compared with current source-of-truth documentation? "
        "Also explain deletion permissions."
    )
    assert plan.unresolved_parts
    assert any("deletion permissions" in part.casefold() for part in plan.unresolved_parts)

def test_treat_comparison_emits_relation_probes_without_answer_terms():
    questions = (
        "How should current documentation answers treat CHANGELOG.md "
        "compared with current source-of-truth documentation?",
        "How should current API answers treat NOTES.rst "
        "compared with maintained interface documentation?",
    )
    for question in questions:
        plan = build_documentation_query_plan(
            question,
            requirements=build_requirements(question, profile="project_docs_answer"),
        )
        relation = [
            row.text.casefold()
            for row in plan.queries
            if row.query_id.startswith("query-relation-")
        ]
        frame = match_comparison_frame(question)
        assert frame is not None
        assert relation
        assert any(
            frame.left.casefold() in text and frame.right.casefold() in text
            for text in relation
        )
        assert not any(
            term in " ".join(relation)
            for term in ("release-history", "primary only", "historical authority")
        )

