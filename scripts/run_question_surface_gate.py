#!/usr/bin/env python3
"""Preserve the frozen question corpus under the retrieval-only contract.

The v1 signatures describe the retired NL-to-proof compiler. Keep them and the
100 original questions as historical inputs, not as permission to invent an
answer contract. A real member-backed positive and an absent-identifier
negative keep fail-closed semantic parsing from becoming an always-empty API.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    build_project_answer_contract, can_authorize_docs_answer,
)
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.domain.question_plan import compile_question_plan
from docmancer.mcp.docs_server import call_docs_tool_payload
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project

CASES_PATH = ROOT / "eval" / "project_answer_surface_v1" / "cases.json"
FROZEN_CASES_SHA256 = "0616d67ef86e134365c5192701f9a6b6173e13326c08ba58a5b049147f3e81f1"
SIGNATURE_FIELDS = (
    "kind", "subject", "attribute", "relation", "target", "value_kind",
    "expected_value", "item_kind", "cardinality", "response_mode", "context",
)


def _owner(question: str, contract: Any) -> str:
    plan = compile_question_plan(question)
    if contract.unresolved_parts or plan.unresolved_parts:
        return "unresolved_semantics"
    if plan.facets:
        return "question_plan"
    if contract.proof_obligations:
        return "legacy"
    return "silent_empty"


def _check_request(question: str) -> None:
    contract = build_project_answer_contract(question)
    plan = compile_question_plan(question)
    assert _owner(question, contract) == "unresolved_semantics", "unreported_empty_semantics"
    assert plan.clauses == (question,), "original_question_changed"
    assert plan.unresolved_parts, "unresolved_semantics_not_reported"
    assert not plan.facets and not plan.consumed_spans, "invented_semantic_interpretation"
    assert plan.component_scope_complete is False, "invented_semantic_completeness"
    expected_hash = hashlib.sha256(json.dumps(
        question, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    assert contract.question_hash == expected_hash, "original_question_identity_lost"
    assert not any((contract.proof_obligations, contract.subjects,
                    contract.retrieval_hints, contract.concept_queries)), "invented_answer_contract"
    assert contract.component_scope_complete is False, "invented_answer_completeness"
    assert can_authorize_docs_answer(contract) is False, "question_authorizes_answer"
    assert not build_project_retrieval_aliases(question), "generated_retrieval_alias"

    # Quotation is explicit host input. It remains a separate lookup and never
    # supplies coverage for query-original. The fixed Unicode literal also
    # exercises preservation without a query normalizer supplying the oracle.
    lookup = "  Exact_HOST_lookup Ω  "
    for lookups in ((), (lookup,)):
        retrieval = build_documentation_query_plan(question, lookup_queries=lookups)
        assert retrieval.original_question == question, "retrieval_question_changed"
        assert retrieval.component_scope_complete is False, "retrieval_claims_semantic_completeness"
        rows = retrieval.queries
        expected = [("query-original", question, "original", "direct", True)]
        if lookups:
            expected.append(("query-lookup-1", lookup, "host_lookup", "host_lookup", False))
        assert [(row.query_id, row.text, row.origin, row.relation, row.coverage_required)
                for row in rows] == expected, "query_provenance_changed"
        assert all(row.public_parent_query_id is None for row in rows), "lookup_borrowed_original_credit"


def _public_sentinels(cases: list[dict[str, Any]]) -> dict[str, Any]:
    command = "doc-atlas mcp docs-serve"
    original = (
        "# Docs MCP server\n\n"
        f"The command that starts the Docs MCP server is `{command}`.\n"
    )
    # Case 20 is one of the unchanged original questions, not a generated query
    # constructed by reading whatever the implementation happened to return.
    question = next(row["question"] for row in cases if row["id"] == 20)
    assert question == "What command starts the Docs MCP server?"
    with tempfile.TemporaryDirectory(prefix="docatlas-question-surface-") as temporary:
        root = Path(temporary)
        project = root / "project"
        write_project(project, {"README.md": original})
        with isolated_service(root / "state") as (service, config):
            ingest = index_project(service, config, project)
            assert ingest["indexed_paths"] == ["README.md"], "positive_fixture_not_indexed"
            generation = service.member_storage_policy.generation()
            positive = call_docs_tool_payload("get_docs_context", {
                "question": question, "project_path": str(project), "scope": "project",
            }, service)
            assert positive.get("status") == "ok", "known_positive_did_not_return_context"
            assert positive.get("kind") == "docs_context"
            assert positive.get("context_available") is True, "always_empty_context"
            rows = positive.get("sources") or []
            assert rows and any(command in row.get("snippet", "") for row in rows), "known_source_fact_lost"
            identity = "local:" + hashlib.sha256(str(project.resolve()).encode()).hexdigest()
            for row in rows:
                assert row["path_or_url"] == "README.md", "source_path_changed"
                assert row["snippet"] and row["snippet"] in original, "source_text_invented"
                assert row.get("project_identity") == identity, "foreign_project_evidence"
                assert row.get("scope") == "project", "source_scope_widened"
                assert re.fullmatch(r"[0-9a-f]{64}", row.get("content_sha256", "")), "source_hash_format"
            for key in ("answer_supported", "answer_available", "edit_ready"):
                assert positive.get(key) is False, f"context_grants_{key}"

            negative = call_docs_tool_payload("get_docs_context", {
                "question": "What is the documented value of ZXQV_ABSENT_PROTOCOL_923?",
                "project_path": str(project), "scope": "project",
            }, service)
            assert negative.get("status") == "insufficient_evidence", "absent_fact_claimed_available"
            assert not negative.get("sources"), "unrelated_source_admitted"
            assert negative.get("context_available") is False, "silent_empty_success"
            assert negative.get("missing"), "missing_context_not_explained"
            assert all(negative.get(key) is not True for key in
                       ("answer_supported", "answer_available", "edit_ready")), "absence_grants_authority"
            assert service.member_storage_policy.generation() == generation, "read_changed_generation"
            assert (project / "README.md").read_text(encoding="utf-8") == original, "read_changed_source"

            # Metamorphic witness: retain the exact question and remove only
            # the source fact through another confirmed member transaction.
            # A cached/hard-coded command must disappear; related honest
            # context may remain, so absence is not equated with empty output.
            removed = ("# Docs MCP server\n\n"
                       "This document does not specify a command for starting the Docs MCP server.\n")
            (project / "README.md").write_text(removed, encoding="utf-8")
            updated = index_project(service, config, project)
            assert updated["generation_id"] != generation, "changed_source_not_committed"
            after_removal = call_docs_tool_payload("get_docs_context", {
                "question": question, "project_path": str(project), "scope": "project",
            }, service)
            assert after_removal.get("status") in {"ok", "insufficient_evidence"}, "removal_probe_failed"
            assert command not in json.dumps(after_removal, ensure_ascii=False), "removed_fact_still_returned"
            for source in after_removal.get("sources") or []:
                assert source.get("path_or_url") == "README.md" and source.get("snippet") in removed, "old_source_generation_returned"
            assert all(after_removal.get(key) is not True for key in
                       ("answer_supported", "answer_available", "edit_ready")), "removed_fact_grants_authority"
            assert service.member_storage_policy.generation() == updated["generation_id"], "removal_read_changed_generation"
            return {"positive": "source_fact_preserved", "negative": "absent_identifier_rejected",
                    "transformation": "same_question_removed_fact_not_returned",
                    "positive_tokens": positive["estimated_tokens"],
                    "negative_tokens": negative["estimated_tokens"]}


def main() -> int:
    raw = CASES_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_CASES_SHA256:
        raise SystemExit("question surface gate: original v1 corpus changed; review a separate migration")
    payload = json.loads(raw)
    if payload.get("schema_version") != 1 or tuple(payload.get("signature_fields", ())) != SIGNATURE_FIELDS:
        raise SystemExit("question surface gate: invalid frozen corpus schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or [case.get("id") for case in cases] != list(range(1, 101)):
        raise SystemExit("question surface gate: expected original IDs 1..100")
    categories = Counter(str(case.get("category", "")) for case in cases)
    if len(categories) != 10 or set(categories.values()) != {10}:
        raise SystemExit("question surface gate: expected ten 10-case categories")
    failures: list[str] = []
    passed_by_category: Counter[str] = Counter()
    for case in cases:
        try:
            _check_request(case["question"])
        except AssertionError as error:
            failures.append(f"case {case['id']:03d} {case['question']!r}: {error}")
        else:
            passed_by_category[case["category"]] += 1
    for category in sorted(categories):
        print(f"{category}: {passed_by_category[category]}/{categories[category]}")
    if failures:
        print("question surface gate: FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    sentinels = _public_sentinels(cases)
    print(json.dumps({"corpus_sha256": FROZEN_CASES_SHA256,
                      "contract": "retrieval_only_original_request", "public_sentinels": sentinels}, sort_keys=True))
    print("question surface gate: PASS (100 original inputs; member-backed positive, absent-fact negative, source-removal transformation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
