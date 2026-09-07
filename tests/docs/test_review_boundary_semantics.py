"""Second-review regressions for source rows and whole-lookup audit boundaries."""
from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.context_windows import _focused_snippet
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def _row(edges: str, repetitions: int) -> str:
    row = "ProductionOnly | " + "details " * repetitions + "| ResetAgent clears the cache | forbidden without approval"
    return ("| " if edges in {"left", "both"} else "") + row + (" |" if edges in {"right", "both"} else "")


@pytest.mark.parametrize("edges", ["none", "left", "right", "both"])
@pytest.mark.parametrize("limit", [160, 320, 520])
def test_optional_table_edges_never_expose_a_partial_row(edges, limit):
    row = _row(edges, 100)
    text = "Target | Description | Operation | Restriction\n--- | --- | --- | ---\n" + row + "\n"
    snippet, start, end = _focused_snippet(text, ("ResetAgent clears cache",), limit=limit)
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert row in snippet or "ResetAgent" not in snippet


@pytest.mark.parametrize("edges", ["none", "left", "right", "both"])
def test_short_optional_edge_rows_remain_queryable(edges):
    row = _row(edges, 2)
    text = "\n".join(_row(edges, 1).replace("ResetAgent", f"OtherAgent{i}") for i in range(8)) + "\n" + row
    snippet, start, end = _focused_snippet(text, ("ResetAgent clears cache",), limit=160)
    assert row in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("edges", ["none", "left", "right", "both"])
def test_public_projection_does_not_certify_a_clipped_optional_edge_row(edges):
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    row = _row(edges, 100)
    source.update(content="Target | Description | Operation | Restriction\n--- | --- | --- | ---\n" + row,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ResetAgent clears cache", "exact_terms": ["ResetAgent"], "qualified": True,
                  }})
    retrieval["context_pack"] = [source]
    plan = retrieval["documentation_query_plan"]
    plan["queries"][1]["text"] = "ResetAgent clears cache"
    payload, snapshot = project_docs_context(retrieval=retrieval)
    for visible in payload.get("sources", ()):
        assert row in visible["snippet"] or "ResetAgent" not in visible["snippet"]
        assert visible["snippet"] in source["content"]
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("lookup", [
    "Which arguments does the request boundary accept except legacy arguments?",
    "Which arguments are unsupported by the request boundary?",
    "What request boundary inputs were accepted previously?",
    "How does retrieval avoid selecting outdated source chunks?",
    "How does retrieval select source chunks only from an archive?",
    "What does the documentation request boundary accept, and where is the audit log?",
    "How do retrieved chunks become selected visible sources without authentication?",
    "How do retrieved chunks become selected visible sources for another project?",
    "What does the documentation request boundary accept conditionally?",
    "How does retrieval select archived source chunks?",
])
def test_qualified_or_compound_host_lookups_cannot_gain_unqualified_audits(lookup):
    plan = build_documentation_query_plan("Explain get_docs_context request flow.", lookup_queries=(lookup,))
    assert any(query.origin == "host_lookup" and query.text == lookup for query in plan.queries)
    assert not [query for query in plan.queries if query.relation == "audited_rewrite"
                and query.public_parent_query_id == "query-lookup-1"]


@pytest.mark.parametrize("lookup", [
    "What does the documentation request boundary accept?",
    "Which inputs does the request boundary accept?",
    "What arguments are accepted by the documentation request boundary?",
    "How do retrieved chunks become selected visible sources?",
    "How does retrieval select source chunks?",
    "How are retrieved candidates selected as visible sources?",
])
def test_complete_positive_host_lookup_families_still_gain_bounded_audits(lookup):
    plan = build_documentation_query_plan("Explain get_docs_context request flow.", lookup_queries=(lookup,))
    audits = [query for query in plan.queries if query.relation == "audited_rewrite"
              and query.public_parent_query_id == "query-lookup-1"]
    assert 1 <= len(audits) <= 2
    public = plan.as_payload()["public_query_ids"]
    assert "query-lookup-1" in public
    assert not any(query.query_id in public for query in audits)


@pytest.mark.parametrize("literal", [r"\|", r"\\\|"])
def test_escaped_pipe_prose_does_not_become_an_oversized_table(literal):
    text = "Background " * 60 + literal + " ordinary text. ResetAgent requires approval."
    snippet, start, end = _focused_snippet(text, ("ResetAgent approval",), limit=160)
    assert "ResetAgent requires approval." in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("edges", ["none", "left", "right", "both"])
def test_table_restriction_cannot_be_lost_from_a_row_prefix(edges):
    row = _row(edges, 90).replace("details ", "ResetAgent ")
    text = row + "\nOtherTarget | Unrelated entry | No action | No change\n"
    snippet, start, end = _focused_snippet(text, ("ProductionOnly ResetAgent",), limit=160)
    assert row in snippet or "ProductionOnly" not in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("aliases", [1, 2])
@pytest.mark.parametrize("budget", [256, 800])
@pytest.mark.parametrize("reverse", [False, True])
def test_public_projection_prioritizes_public_queries_not_audited_alias_count(aliases, budget, reverse):
    retrieval = _host_lookup_context_retrieval()
    single, diverse = retrieval["context_pack"][:2]
    queries = [{"query_id": "query-original", "origin": "original", "text": "Explain the processing directions."}]
    queries.extend({"query_id": f"query-lookup-{index}", "origin": "host_lookup", "text": text}
                   for index, text in enumerate(("amber", "indigo", "cobalt"), 1))
    queries.extend({
        "query_id": f"query-host-rewrite-{index}", "origin": "canonical_intent", "text": text,
        "relation": "audited_rewrite", "public_parent_query_id": "query-lookup-1",
    } for index, text in enumerate(("copper", "silver")[:aliases], 1))
    single.update(path="docs/single.md", content="Amber copper silver.", retrieval_query_matches={})
    diverse.update(path="docs/diverse.md", content="Indigo cobalt.", retrieval_query_matches={})
    for query in queries[1:]:
        source = single if query.get("public_parent_query_id") or query["text"] == "amber" else diverse
        source["retrieval_query_matches"][query["query_id"]] = {
            "query_text": query["text"], "qualified": True,
            "relation": query.get("relation", "host_lookup"),
            "public_parent_query_id": query.get("public_parent_query_id"),
        }
    retrieval["context_pack"] = [diverse, single] if reverse else [single, diverse]
    retrieval["documentation_query_plan"] = {"queries": queries, "required_query_ids": []}
    payload, snapshot = project_docs_context(retrieval=retrieval, max_tokens=budget)
    assert payload["sources"][0]["path_or_url"] == "docs/diverse.md"
    assert {"query-lookup-2", "query-lookup-3"} <= set(payload["covered_query_ids"])
    assert not any(value.startswith("query-host-rewrite-") for value in payload["covered_query_ids"])
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert payload["estimated_tokens"] <= budget
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=budget) == []
