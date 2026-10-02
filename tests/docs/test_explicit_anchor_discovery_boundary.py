"""Literal discovery preferences never manufacture semantic coverage."""
import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.retrieval.dispatch import RetrievalDispatcher


def _chunk(body, parent="intro", source="docs/guide.md", **metadata):
    return RetrievedChunk(source=source, chunk_index=0, text=body, score=1.0,
        metadata={"source_class": "project_file", "parent_logical_id": parent,
                  "project_identity": "repo", "lifecycle_status": "active",
                  "authority": "source_of_truth", **metadata})


@pytest.mark.parametrize("question,expected", [
    ("behavior: deployment.", ("behavior", "deployment")),
    ("поведение: настройка.", ("поведение", "настройка")),
    ('`behavior:` "deployment."', ("behavior:", "deployment.")),
    ("docs/guide.md namespace::", ("docs/guide.md", "namespace::")),
    ("meet_type. RequestHandler. CACHE_MODE.", ("meet_type.", "requesthandler.", "cache_mode.")),
])
def test_lexical_sentence_punctuation_does_not_change_explicit_literals(question, expected):
    assert documentation_query_terms(question) == expected
    assert build_documentation_query_plan(question).original_question == question


def test_parent_diversity_preserves_source_positions_and_global_capacity():
    first = _chunk("storage retention timeout", "section")
    repeated = _chunk("storage retention timeout extra", "section")
    intro = _chunk("storage retention", "intro")
    other = _chunk("storage retention", "other", "docs/other.md")
    ranked = RetrievalDispatcher._rank_project_bodies_within_source(
        "storage retention timeout", [first, other, repeated, intro])
    assert ranked == [first, other, intro, repeated]
    assert [row.source for row in ranked] == [row.source for row in [first, other, repeated, intro]]


def test_parent_diversity_cannot_displace_a_harder_exact_identity():
    first = _chunk("FooEngine storage retention", "section")
    repeated = _chunk("FooEngine storage retention", "section")
    wrong = _chunk("BarEngine storage retention", "intro")
    assert RetrievalDispatcher._rank_project_bodies_within_source(
        "`FooEngine` storage retention", [first, repeated, wrong]) == [first, repeated, wrong]


@pytest.mark.parametrize("body,metadata,admitted", [
    ("FooEngine default behavior is documented here.", {}, True),
    ("FooEngine default behavior is documented here.", {"project_identity": "other"}, False),
    ("# FooEngine\n\nUnrelated storage details.", {}, False),
    ("BarEngine default behavior is documented here.", {}, False),
])
def test_anchor_cross_check_keeps_source_guards_and_no_parent_coverage(body, metadata, admitted):
    question = "Explain FooEngine behavior and an unknown private deployment value."
    plan = build_documentation_query_plan(question)
    chunk = _qualify_candidate_lookups([_chunk(body, **metadata)], plan,
        expected_project_identity="repo", lifecycle_intent="current")[0]
    matches = chunk.metadata["retrieval_query_matches"]
    anchor = next(query for query in plan.queries if query.text == "FooEngine")
    assert matches[anchor.query_id]["qualified"] is admitted
    assert matches["query-original"]["qualified"] is False
    assert not matches["query-original"].get("derived_from_query_ids")


def test_literal_rescue_does_not_compete_with_an_independently_qualified_packet():
    plan = build_documentation_query_plan("Explain FooEngine storage retention.")
    chunks = _qualify_candidate_lookups([
        _chunk("FooEngine storage retention is documented."),
        _chunk("FooEngine describes unrelated network details.", "other"),
    ], plan, expected_project_identity="repo", lifecycle_intent="current")
    assert chunks[0].metadata["retrieval_query_matches"]["query-original"]["qualified"] is True
    anchor_ids = {query.query_id for query in plan.queries if query.origin == "exact_anchor"}
    assert anchor_ids
    assert all(not anchor_ids.intersection(chunk.metadata["retrieval_query_matches"]) for chunk in chunks)
