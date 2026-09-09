"""Frozen V2 positive gaps must retain their semantic witnesses end to end."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
from scripts.run_project_docs_self_host_gate import LiveCase, run
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIRECT_15_PATH = _REPO_ROOT / "eval/direct_docatlas_questions_15/cases.json"


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
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan

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
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan

    for question in (
        "Explain project architecture and testing",
        "Explain UnknownLedger project architecture",
        "Explain project architecture and the imaginary orbital subsystem",
        "Explain project architecture that must not use indexing",
    ):
        aliases = [row for row in build_documentation_query_plan(question).queries if row.origin == "canonical_intent"]
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
        "Explain project architecture", lookup_queries=("troubleshooting stale documentation no results",),
    )
    host = next(q for q in plan.queries if q.query_id == "query-lookup-1")
    assert host.relation == "host_lookup"
    assert host.public_parent_query_id is None


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _direct_15_payload() -> dict[str, object]:
    return json.loads(_DIRECT_15_PATH.read_text(encoding="utf-8"))


def test_direct_15_sidecar_witnesses_are_current_and_outside_project_catalog():
    sidecar = _direct_15_payload()
    assert sidecar["baseline_commit"] == "e179471527e009c88f77acbdaeeeeb8ad1c8d316"
    assert sidecar["request_contract"] == {
        "scope": "all", "lookup_queries": "absent",
        "maximum_sources": 3, "maximum_estimated_tokens": 800,
    }
    assert [row["id"] for row in sidecar["cases"]] == [f"Q{index:02d}" for index in range(1, 16)]

    for source_path, metadata in sidecar["sources"].items():
        path = _REPO_ROOT / source_path
        assert path.is_file(), source_path
        assert _git_blob_sha(path) == metadata["git_blob_sha"], source_path

    for case in sidecar["cases"]:
        assert case["fact_groups"], case["id"]
        for group in case["fact_groups"]:
            assert group["witnesses"], (case["id"], group["id"])
            for witness in group["witnesses"]:
                source_text = (_REPO_ROOT / witness["path"]).read_text(encoding="utf-8")
                assert witness["text"] in source_text, (case["id"], group["id"], witness)

    catalog_text = (_REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")
    assert "eval/direct_docatlas_questions_15" not in catalog_text


def test_direct_15_question_only_visible_payload_covers_every_explicit_fact_group():
    sidecar = _direct_15_payload()
    live_cases = []
    for row in sidecar["cases"]:
        required_fact_groups = tuple(
            tuple((witness["path"], witness["text"]) for witness in group["witnesses"])
            for group in row["fact_groups"]
        )
        relevant_paths = tuple(dict.fromkeys(
            path for alternatives in required_fact_groups for path, _ in alternatives
        ))
        live_cases.append(LiveCase(
            case_id=row["id"],
            question=row["question"],
            relevant_paths=relevant_paths,
            required_fact_groups=required_fact_groups,
            expected_kind="docs_context",
            lookup_queries=(),
            scope="all",
        ))

    report = run(cases=tuple(live_cases), negative_cases=())
    results = {row["case_id"]: row for row in report["results"]}
    assert set(results) == {f"Q{index:02d}" for index in range(1, 16)}

    failures = {}
    for case_id, row in results.items():
        payload = row["payload"]
        checks = row["checks"]
        public_query_ids = {
            str(value)
            for value in (*(payload.get("covered_query_ids") or ()), *(payload.get("missing_query_ids") or ()))
        }
        case_failures = {
            "status_ok": checks.get("status_ok"),
            "kind_matches": checks.get("kind_matches"),
            "source_backed": checks.get("source_backed"),
            "context_contract": checks.get("context_contract"),
            "required_facts": checks.get("required_facts"),
            "citation_integrity": checks.get("citation_integrity"),
            "no_lookup_queries": not any(value.startswith("query-lookup-") for value in public_query_ids),
            "source_budget": len(payload.get("sources") or ()) <= 3,
            "token_budget": int(payload.get("estimated_tokens") or 0) <= 800,
            "retrieval_only": payload.get("answer_supported") is False and payload.get("edit_ready") is False,
        }
        if not all(case_failures.values()):
            failures[case_id] = {
                "checks": case_failures,
                "fact_checks": row.get("fact_checks"),
                "sources": payload.get("sources"),
                "covered_query_ids": payload.get("covered_query_ids"),
                "missing_query_ids": payload.get("missing_query_ids"),
            }

    assert not failures, failures
