"""Exact query identity requires syntax, not a list of familiar prose words."""
import pytest

from docmancer.docs.domain.documentation_query_plan import technical_anchors, build_documentation_query_plan
from docmancer.docs.domain.technical_terms import extract_technical_terms


@pytest.mark.parametrize("modifier", ["repository-wide", "high-availability", "latency-sensitive", "source-backed"])
def test_unquoted_prose_modifier_remains_a_lexical_topic(modifier):
    question = f"How does {modifier} documentation retrieval preserve useful evidence?"
    assert modifier not in technical_anchors(question)
    assert any(q.text == modifier and q.origin == "lexical_topic" for q in build_documentation_query_plan(question).queries)
    terms = [term for term in extract_technical_terms(question) if term.raw == modifier]
    assert len(terms) == 1
    assert terms[0].kind == "plain_term"


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
    terms = [term for term in extract_technical_terms(question) if term.raw == "archive-store"]
    assert len(terms) == 1
    assert terms[0].kind == "cli_command"


def test_command_context_does_not_promote_an_unrelated_prose_modifier():
    question = "Run archive-store for repository-wide documentation retrieval."
    assert "archive-store" in technical_anchors(question)
    kinds = {term.raw: term.kind for term in extract_technical_terms(question)}
    assert kinds["archive-store"] == "cli_command"
    assert kinds["repository-wide"] == "plain_term"


def test_former_prose_prefix_can_be_a_real_explicit_command():
    question = "Run provider-free --help"
    assert "provider-free" in technical_anchors(question)
    assert next(term for term in extract_technical_terms(question) if term.raw == "provider-free").kind == "cli_command"


@pytest.mark.parametrize("question", [
    "Какие условия допускают preview-build версии?",
    "Πότε επιτρέπονται preview-build εκδόσεις;",
])
def test_borrowed_latin_topic_is_retained_without_claiming_command_identity(question):
    assert "preview-build" not in technical_anchors(question)
    assert any(q.text == "preview-build" and q.origin == "lexical_topic" for q in build_documentation_query_plan(question).queries)
    terms = [term for term in extract_technical_terms(question) if term.raw == "preview-build"]
    assert len(terms) == 1
    assert terms[0].kind == "plain_term"
