import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup
from docmancer.docs.domain.query_terms import query_constraint_roles


@pytest.mark.parametrize("term", ["API", "SDK", "RPC"])
def test_bare_acronym_does_not_invent_a_semantic_subject(term):
    roles = query_constraint_roles(f"How should current {term} behavior use history?")
    assert term.casefold() not in roles.bound_subjects
    assert term.casefold() in roles.retrieval_anchors


@pytest.mark.parametrize("term", ["API", "Client.send", "cache_mode", "--strict"])
def test_explicit_quoted_identifier_remains_hard(term):
    roles = query_constraint_roles(f"How does `{term}` behave?")
    assert term.casefold() in roles.hard_exact


def test_camelcase_subject_is_not_silently_dropped():
    roles = query_constraint_roles("When do QueueTasks stop?")
    assert "queuetasks" in roles.bound_subjects


def test_unresolved_bare_anchor_retains_base_strict_fallback():
    question = "How should current API behavior use historical release notes?"
    body = (
        "For current behavior, maintained documentation is primary evidence. "
        "Historical release notes may supplement it."
    )
    lookup = DocumentationLookup("query-original", question, "original")
    chunk = RetrievedChunk(
        source="docs/authority.md", chunk_index=0, text=body, score=1,
        metadata={"project_identity": "repo"},
    )
    tagged = _tag_retrieval_query(
        [chunk], lookup.query_id, lookup.text, lookup,
        expected_project_identity="repo", lifecycle_intent="current",
    )[0]
    trace = tagged.metadata["retrieval_query_matches"]["query-original"]
    assert trace["qualified"] is False
    assert "api" in trace.get("missing_exact_terms", ())


def test_quoted_api_still_requires_literal_identity():
    question = "How does `API` behave?"
    lookup = DocumentationLookup("query-original", question, "original")
    chunk = RetrievedChunk(
        source="docs/authority.md", chunk_index=0,
        text="This describes current behavior without the identifier.", score=1,
        metadata={"project_identity": "repo"},
    )
    tagged = _tag_retrieval_query(
        [chunk], lookup.query_id, lookup.text, lookup,
        expected_project_identity="repo", lifecycle_intent="current",
    )[0]
    trace = tagged.metadata["retrieval_query_matches"]["query-original"]
    assert trace["qualified"] is False
    assert "api" in trace.get("missing_exact_terms", ())

@pytest.mark.parametrize("term", ["HTTPX", "CORS"])
def test_long_bare_acronym_can_bind_source_scope_without_becoming_local_hard_exact(term):
    roles = query_constraint_roles(f"What is {term} default behavior?")
    assert term.casefold() not in roles.hard_exact
    assert term.casefold() in roles.bound_subjects


@pytest.mark.parametrize("question,expected", [
    ("Which task ID does enqueue_task return?", {"id", "enqueue_task"}),
    ("What does missing_symbol mean?", {"missing_symbol"}),
])
def test_short_acronym_and_symbol_shaped_tokens_remain_hard_identity(question, expected):
    roles = query_constraint_roles(question)
    assert expected <= set(roles.hard_exact)
