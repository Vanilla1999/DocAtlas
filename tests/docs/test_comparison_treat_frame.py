import pytest

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
