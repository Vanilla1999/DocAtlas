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
