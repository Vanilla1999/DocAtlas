"""Exact query identity requires syntax, not a list of familiar prose words."""
import pytest

from docmancer.docs.domain.documentation_query_plan import technical_anchors
from docmancer.docs.domain.technical_terms import extract_technical_terms


@pytest.mark.parametrize("modifier", ["repository-wide", "high-availability", "latency-sensitive", "source-backed"])
def test_unquoted_prose_modifier_is_not_a_mandatory_command_identity(modifier):
    question = f"How does {modifier} documentation retrieval preserve useful evidence?"
    assert modifier not in technical_anchors(question)
    assert modifier not in {term.raw for term in extract_technical_terms(question)}


@pytest.mark.parametrize("question", [
    "How do I run archive-store safely?",
    "What does the command archive-store do?",
    "Explain the archive-store command.",
    "Как запустить команду archive-store?",
    "archive-store --dry-run",
    "archive-store",
    "Which scopes does archive-store support?",
    "What does archive-store preserve?",
    "What is dry_run in archive-store?",
    "How does `archive-store` work?",
    'How does "archive-store" work?',
])
def test_explicit_command_syntax_retains_exact_hyphenated_identity(question):
    assert "archive-store" in technical_anchors(question)


def test_command_context_does_not_promote_an_unrelated_prose_modifier():
    question = "Run archive-store for repository-wide documentation retrieval."
    assert "archive-store" in technical_anchors(question)
    assert "repository-wide" not in technical_anchors(question)


def test_former_prose_prefix_can_be_a_real_explicit_command():
    assert "provider-free" in technical_anchors("Run provider-free --help")


@pytest.mark.parametrize("question", [
    "Какие условия допускают preview-build версии?",
    "Πότε επιτρέπονται preview-build εκδόσεις;",
])
def test_borrowed_latin_topic_is_retained_without_claiming_command_identity(question):
    assert "preview-build" in technical_anchors(question)
    terms = [term for term in extract_technical_terms(question) if term.raw == "preview-build"]
    assert len(terms) == 1
    assert terms[0].kind == "plain_term"
