"""Frozen V2 positive gaps must retain their semantic witnesses end to end."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
from scripts.run_project_docs_self_host_gate import LiveCase, run
import scripts.run_project_docs_self_host_gate as self_host_gate
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


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _direct_15_payload() -> dict[str, object]:
    return json.loads(_DIRECT_15_PATH.read_text(encoding="utf-8"))


def _assert_direct_15_sidecar() -> None:
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

    cases = []
    for case in sidecar["cases"]:
        assert case["fact_groups"], case["id"]
        required_fact_groups = []
        for group in case["fact_groups"]:
            assert group["witnesses"], (case["id"], group["id"])
            alternatives = []
            for witness in group["witnesses"]:
                source_text = (_REPO_ROOT / witness["path"]).read_text(encoding="utf-8")
                assert witness["text"] in source_text, (case["id"], group["id"], witness)
                alternatives.append((witness["path"], witness["text"]))
            required_fact_groups.append(tuple(alternatives))
        cases.append((case, tuple(required_fact_groups)))

    catalog_text = (_REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")
    assert "eval/direct_docatlas_questions_15" not in catalog_text

    previous_home = os.environ.get("DOCATLAS_HOME")
    failures = {}
    call_count = 0
    try:
        with TemporaryDirectory(prefix="docatlas-direct-15-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCATLAS_HOME"] = str(tmp / "home")
            config = self_host_gate.DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = self_host_gate.LibraryDocsService(
                config=config,
                config_source="explicit",
                registry=self_host_gate.LibraryRegistry(config.index.db_path),
                agent=self_host_gate.DocmancerAgent(config=config),
                job_tracker=self_host_gate.DocsJobTracker(),
            )
            sync = service.sync_project_docs(str(_REPO_ROOT), with_vectors=False)
            assert getattr(sync, "status", None) == "success"

            for case, required_fact_groups in cases:
                payload, snapshot = self_host_gate._call_with_snapshot(
                    {
                        "question": case["question"],
                        "project_path": str(_REPO_ROOT),
                        "scope": "all",
                    },
                    service,
                )
                call_count += 1
                payload = dict(payload or {})
                sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
                public_query_ids = {
                    str(value)
                    for value in (
                        *(payload.get("covered_query_ids") or ()),
                        *(payload.get("missing_query_ids") or ()),
                    )
                }
                fact_checks = {
                    f"fact-group-{index}": any(
                        str(source.get("path_or_url") or "") == path
                        and fragment.casefold() in str(source.get("snippet") or "").casefold()
                        for path, fragment in alternatives
                        for source in sources if isinstance(source, dict)
                    )
                    for index, alternatives in enumerate(required_fact_groups, 1)
                }
                observer_counts = ((payload.get("diagnostics") or {}).get("observer_counts") or {})
                checks = {
                    "status_ok": payload.get("status") == "ok",
                    "kind_matches": payload.get("kind") == "docs_context",
                    "source_backed": bool(sources),
                    "context_contract": self_host_gate._validate_context_result(payload) is None,
                    "required_facts": all(fact_checks.values()),
                    "citation_integrity": self_host_gate._citation_integrity(payload, snapshot),
                    "no_packs_contamination": not self_host_gate._packs_contamination(case["question"], payload),
                    "no_lookup_queries": not any(value.startswith("query-lookup-") for value in public_query_ids),
                    "source_budget": len(sources) <= 3,
                    "token_budget": int(payload.get("estimated_tokens") or 0) <= 800,
                    "retrieval_only": payload.get("answer_supported") is False and payload.get("edit_ready") is False,
                    "one_retrieval_call": observer_counts.get("retrieval_calls") == 1,
                    "one_validation_call": observer_counts.get("validation_calls") == 1,
                }
                if not all(checks.values()):
                    failures[case["id"]] = {
                        "checks": checks,
                        "fact_checks": fact_checks,
                        "sources": sources,
                        "covered_query_ids": payload.get("covered_query_ids"),
                        "missing_query_ids": payload.get("missing_query_ids"),
                        "query_intent": (payload.get("diagnostics") or {}).get("query_intent"),
                    }
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home

    assert call_count == 15
    assert not failures, failures


def test_v2_natural_chunking_keeps_parent_and_child_witnesses():
    _assert_semantic_positive("v2-natural-chunking", "natural")


def test_v2_review_ready_keeps_reading_and_test_witnesses():
    _assert_semantic_positive("v2-paraphrase-review-ready", "exposed_paraphrases")


def test_v2_search_trust_keeps_selection_proof_and_context_witnesses():
    _assert_semantic_positive("v2-paraphrase-search-trust", "exposed_paraphrases")
    _assert_direct_15_sidecar()


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
