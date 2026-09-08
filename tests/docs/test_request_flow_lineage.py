"""Request-flow retrieval may use audited internal rewrites without inventing public proof."""
from __future__ import annotations

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import derived_parent_trace


QUESTION = "Как проходит запрос get_docs_context от MCP-входа до выбора источников?"
LOOKUPS = (
    "What does the documentation request boundary accept?",
    "How does the application pass a project question to retrieval?",
    "How do retrieved chunks become selected visible sources?",
)


def _plan(lookups=LOOKUPS):
    return build_documentation_query_plan(QUESTION, lookup_queries=tuple(lookups), requirements=())


def _audited(plan):
    return tuple(query for query in plan.queries if query.relation == "audited_rewrite")


def test_request_flow_host_lookups_gain_bounded_audited_rewrites():
    plan = _plan()
    host = {query.query_id: query.text for query in plan.queries if query.origin == "host_lookup"}
    assert host == {
        "query-lookup-1": LOOKUPS[0],
        "query-lookup-2": LOOKUPS[1],
        "query-lookup-3": LOOKUPS[2],
    }
    rewrites = _audited(plan)
    pairs = {(query.public_parent_query_id, query.text) for query in rewrites}
    assert ("query-lookup-1", "get_docs_context question project_path lookup_queries module_path scope") in pairs
    assert ("query-lookup-3", "retrieval gateway filtered project chunks") in pairs
    assert ("query-lookup-3", "selection maximizes distinct visible query coverage") in pairs


def test_audited_host_rewrites_are_not_public_query_ids():
    payload = _plan().as_payload()
    public = set(payload["public_query_ids"])
    for query in payload["queries"]:
        if query["relation"] == "audited_rewrite" and query["public_parent_query_id"].startswith("query-lookup-"):
            assert query["query_id"] not in public
            assert query["public_parent_query_id"] in public


def test_audited_host_rewrite_count_is_bounded():
    rewrites = [
        query for query in _audited(_plan())
        if str(query.public_parent_query_id or "").startswith("query-lookup-")
    ]
    assert 1 <= len(rewrites) <= 4


def test_negated_host_lookup_is_not_rewritten():
    plan = _plan((
        "What does the documentation request boundary not accept?",
        LOOKUPS[1],
        "How do retrieved chunks not become selected visible sources?",
    ))
    assert not [
        query for query in _audited(plan)
        if query.public_parent_query_id in {"query-lookup-1", "query-lookup-3"}
    ]


def test_host_lookup_with_unrelated_exact_identifier_is_not_rewritten():
    plan = _plan((
        "What does FooEngine documentation request boundary accept?",
        LOOKUPS[1],
        "How do FooEngine retrieved chunks become selected visible sources?",
    ))
    assert not [
        query for query in _audited(plan)
        if query.public_parent_query_id in {"query-lookup-1", "query-lookup-3"}
    ]


def test_generic_canonical_alias_cannot_derive_host_parent_coverage():
    trace = {
        "qualified": True,
        "relation": "host_lookup",
        "missing_parent_exact_terms": [],
    }
    assert derived_parent_trace(
        trace,
        source_query_id="query-intent-1",
        parent_query_id="query-lookup-3",
    ) is None


def test_request_flow_public_contract_remains_four_fact_fail_safe():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-natural-request-flow")
    result = run(cases=(LiveCase(
        case_id=case["id"], question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert {row["id"] for row in verdict["obligations"] if row["met"]} == {
        "flow_mcp", "flow_application", "flow_gateway", "flow_selection",
    }
    assert verdict["semantic_useful"] is True
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3
    assert payload["estimated_tokens"] <= 800
