from __future__ import annotations

from eval.project_answer_quality_v4_protocol import run, validate_protocol_lock


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
    assert all(row["kind"] for row in report["results"])
    assert all(
        len(citation["content_sha256"]) == 64
        for row in report["results"]
        for citation in row["citations"]
    )
