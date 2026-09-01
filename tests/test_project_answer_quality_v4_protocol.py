from __future__ import annotations

from eval.project_answer_quality_protocol import (
    ExpectedOutcome,
    _expected_projection_contract,
    _query_coverage,
)
from eval.project_answer_quality_v4_protocol import load_cases, run, validate_protocol_lock


def test_project_answer_quality_v4_protocol_lock_and_full_production_path_pass():
    validate_protocol_lock()
    report = run()
    assert report["verdict"] == "PASS"
    assert report["run_mode"] == "hermetic"
    assert report["passed_count"] == report["case_count"] == 20
    assert report["stage_metrics"]["candidate_recall_at_k"] == 1.0
    assert report["stage_metrics"]["selected_obligation_coverage"] == 1.0
    assert report["stage_metrics"]["abstention_correctness"] == 1.0
    assert report["stage_metrics"]["contamination_free"] == 1.0
    assert report["stage_metrics"]["mrr"] == 1.0
    assert report["stage_metrics"]["false_abstention_count"] == 0
    expected_kinds = {case.case_id: case.expected.kind for case in load_cases()}
    assert all(
        row["kind"] == expected_kinds[row["case_id"]]
        for row in report["results"]
    )
    assert all(
        len(citation["content_sha256"]) == 64
        for row in report["results"]
        for citation in row["citations"]
    )


def test_query_coverage_preserves_explicit_zero_for_supported_answers():
    assert _query_coverage({
        "kind": "docs_answer",
        "answer_supported": True,
        "mandatory_coverage": 0.0,
    }) == 0.0
    assert _query_coverage({
        "kind": "docs_answer",
        "answer_supported": True,
    }) == 1.0


def test_expected_projection_contract_rejects_correct_status_with_wrong_kind():
    expected = ExpectedOutcome(
        status="ok",
        kind="docs_answer",
        evidence_paths=(),
        required_fragments=(),
        forbidden_fragments=(),
        forbidden_paths=(),
    )
    status_kind, authorization = _expected_projection_contract(expected, {
        "status": "ok",
        "kind": "docs_context",
        "answer_supported": False,
        "answer_available": False,
        "edit_ready": False,
    })
    assert status_kind is False
    assert authorization is False
