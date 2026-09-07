"""Review regressions for query-local identity, negation and public coverage."""
from __future__ import annotations

import pytest

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from tests.docs.test_project_doc_ranking import FakeChunk


@pytest.mark.parametrize("lookups", [
    ("project architecture",),
    ("What does BarEngine do?",),
    ("What does BarEngine do?", "project architecture"),
    ("project architecture", "What does BarEngine do?"),
])
def test_host_lookups_cannot_replace_original_alias_exact_terms(lookups):
    question = "Explain FooEngine architecture."
    baseline = build_documentation_query_plan(question)
    with_lookups = build_documentation_query_plan(question, lookup_queries=lookups)
    original_aliases = {
        query.query_id: query.parent_exact_terms
        for query in baseline.queries if query.query_id.startswith("query-intent-")
    }
    assert original_aliases
    assert all("fooengine" in terms for terms in original_aliases.values())
    assert {
        query.query_id: query.parent_exact_terms
        for query in with_lookups.queries if query.query_id.startswith("query-intent-")
    } == original_aliases


@pytest.mark.parametrize("negation", ["doesn't", "doesn’t", "cannot", "can't", "can’t", "won't"])
def test_negated_host_contractions_cannot_gain_positive_audited_lineage(negation):
    question = "Explain the get_docs_context request flow."
    lookup = f"What arguments {negation} the documentation request boundary accept?"
    plan = build_documentation_query_plan(question, lookup_queries=(lookup,))
    assert any(query.origin == "host_lookup" and query.text == lookup for query in plan.queries)
    assert not [
        query for query in plan.queries
        if query.relation == "audited_rewrite"
        and query.public_parent_query_id == "query-lookup-1"
    ]


def test_multiple_audited_rewrites_do_not_multiply_public_coverage_priority():
    question = "Explain the processing stages."
    parent = "query-lookup-1"
    aliases = {
        f"query-host-rewrite-{index}": {
            "qualified": True, "relation": "audited_rewrite",
            "public_parent_query_id": parent,
        }
        for index in range(1, 4)
    }
    duplicated = FakeChunk(
        "docs/single.md", "Stages", 1.0,
        metadata={"retrieval_query_matches": {parent: {"qualified": True}, **aliases}},
    )
    diverse = FakeChunk(
        "docs/diverse.md", "Stages", 1.0,
        metadata={"retrieval_query_matches": {
            f"query-lookup-{index}": {"qualified": True} for index in range(2, 5)
        }},
    )
    ranked = rerank_project_doc_chunks(
        [duplicated, diverse], question=question,
        intent=classify_project_query_intent(question), limit=1,
    )
    assert [chunk.path for chunk in ranked] == ["docs/diverse.md"]
