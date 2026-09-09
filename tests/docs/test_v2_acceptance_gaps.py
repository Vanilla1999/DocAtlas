"""Frozen V2 positive gaps must retain their semantic witnesses end to end."""
from __future__ import annotations

import pytest

from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
from scripts.run_project_docs_self_host_gate import LiveCase, run
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


def _run_case(case_id: str, lane: str):
    case = next(row for row in load_cases(lane) if row["id"] == case_id)
    result = run(cases=(LiveCase(
        case_id=case["id"], question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    return case, payload, evaluate_case(case, payload)


def _assert_semantic_positive(case_id: str, lane: str) -> None:
    _, payload, verdict = _run_case(case_id, lane)
    assert all(verdict["hard_gates"].values()), verdict
    assert verdict["false_full_coverage"] is False
    assert all(row["met"] for row in verdict["obligations"]), {
        "obligations": verdict["obligations"], "sources": payload.get("sources"),
        "covered_query_ids": payload.get("covered_query_ids"),
        "missing_query_ids": payload.get("missing_query_ids"),
    }
    assert verdict["semantic_useful"] is True
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload.get("sources") or ()) <= 3 and payload["estimated_tokens"] <= 800


def test_v2_natural_chunking_keeps_parent_and_child_witnesses():
    _assert_semantic_positive("v2-natural-chunking", "natural")


def test_v2_review_ready_keeps_reading_and_test_witnesses():
    _assert_semantic_positive("v2-paraphrase-review-ready", "exposed_paraphrases")


def test_v2_search_trust_keeps_selection_proof_and_context_witnesses():
    _assert_semantic_positive("v2-paraphrase-search-trust", "exposed_paraphrases")


def test_single_intent_context_aliases_derive_only_original_retrieval_lineage():
    for question in (
        "Что это за проект и какую проблему он решает?",
        "Как система выбирает доказательства?",
        "Как большой документ превращается в родительские секции и небольшие поисковые фрагменты, есть ли у них ограничение размера?",
    ):
        plan = build_documentation_query_plan(question)
        aliases = [row for row in plan.queries if row.origin == "canonical_intent"]
        assert aliases
        assert all(row.relation == "audited_rewrite" for row in aliases)
        assert all(row.public_parent_query_id == "query-original" for row in aliases)
        assert plan.queries[0].coverage_required is False


def test_original_lineage_rejects_multi_intent_unknown_negated_and_hypothetical_questions():
    for question in (
        "Explain project architecture and testing",
        "Explain UnknownLedger project architecture",
        "Explain project architecture and the imaginary orbital subsystem",
        "Explain project architecture that must not use indexing",
    ):
        aliases = [
            row for row in build_documentation_query_plan(question).queries
            if row.origin == "canonical_intent"
        ]
        assert all(row.public_parent_query_id is None for row in aliases)
        assert all(row.relation == "host_lookup" for row in aliases)


@pytest.mark.parametrize("question, lookup", [
    ("Что проверить, если проектная документация устарела или ничего не находится?",
     "troubleshooting stale project documentation no results"),
    ("Где хранится индекс и как он изолирован для каждого проекта?",
     "project documentation storage index isolation"),
])
def test_equivalent_host_lookup_may_derive_original_retrieval_lineage(question, lookup):
    plan = build_documentation_query_plan(question, lookup_queries=(lookup,))
    host = next(q for q in plan.queries if q.query_id == "query-lookup-1")
    assert host.origin == "host_lookup"
    assert host.relation == "audited_rewrite"
    assert host.public_parent_query_id == "query-original"


def test_arbitrary_host_lookup_cannot_derive_original_retrieval_lineage():
    plan = build_documentation_query_plan(
        "Explain project architecture",
        lookup_queries=("troubleshooting stale documentation no results",),
    )
    host = next(q for q in plan.queries if q.query_id == "query-lookup-1")
    assert host.relation == "host_lookup"
    assert host.public_parent_query_id is None
