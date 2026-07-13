from __future__ import annotations

import hashlib

import pytest

from eval.task_level.analysis.task23_report import _retry_provenance, _source_artifact_hashes, build_task23_report


CONDITIONS = [
    "repo_only_strict_offline",
    "repo_plus_audited_external_context",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
]


def test_retry_provenance_is_sanitized_and_deterministic(tmp_path):
    attempt = tmp_path / "task_a" / "condition_b" / "repeat_2" / "attempts" / "attempt_1"
    attempt.mkdir(parents=True)
    (attempt / "result.json").write_text('{"status":"runner_unavailable"}', encoding="utf-8")

    provenance = _retry_provenance(tmp_path)

    assert provenance["retried_cells"] == 1
    assert provenance["total_retry_attempts"] == 1
    assert provenance["selection_rule"] == "infrastructure_failures_only"
    assert provenance["cells"] == [{
        "attempts": [{"attempt": 1, "status": "runner_unavailable"}],
        "condition_id": "condition_b",
        "repeat": 2,
        "task_id": "task_a",
    }]
    assert len(provenance["retry_attempts_sha256"]) == 64


def test_source_artifact_hashes_are_reproducible(tmp_path):
    runs = tmp_path / "runs.jsonl"
    protocol = tmp_path / "protocol.json"
    amendment = tmp_path / "amendment.json"
    replacement_screening = tmp_path / "replacement-screening.json"
    runs.write_bytes(b"runs\n")
    protocol.write_bytes(b"protocol\n")
    amendment.write_bytes(b"amendment\n")
    replacement_screening.write_bytes(b"replacement\n")

    hashes = _source_artifact_hashes(runs, protocol, amendment, replacement_screening)

    assert hashes == {
        "runs_jsonl_sha256": hashlib.sha256(b"runs\n").hexdigest(),
        "protocol_sha256": hashlib.sha256(b"protocol\n").hexdigest(),
        "amendment_sha256": hashlib.sha256(b"amendment\n").hexdigest(),
        "replacement_screening_sha256": hashlib.sha256(b"replacement\n").hexdigest(),
    }


def _protocol() -> dict:
    return {
        "schema_version": "task23-protocol-1",
        "protocol_id": "task23-test",
        "frozen_before_results": True,
        "tasks": [
            {
                "task_id": f"task_{index}",
                "source_project": f"project_{index}",
                "domain": f"domain_{index}",
                "fixture_hash": "a" * 64,
                "oracle_sha256": "b" * 64,
                "external_context_sha256": "c" * 64,
            }
            for index in range(3)
        ],
        "conditions": CONDITIONS,
        "repeats_per_task_condition": 3,
        "controls": {
            "same_model": True,
            "same_prompt_policy": True,
            "same_context_limits": True,
            "same_attempt_budget": True,
            "same_starting_state": True,
        },
        "decision_rule": {
            "resolved_rate_improvement_min": 0.10,
            "median_total_tokens_increase_max": 0.10,
            "resolved_rate_equivalence_margin": 0.02,
            "median_total_tokens_reduction_min": 0.25,
            "median_latency_increase_max": 0.10,
            "confidence_level": 0.95,
            "fail_closed_on_missing_metrics": True,
        },
    }


def _rows() -> list[dict]:
    rows = []
    for task_index in range(3):
        for repeat in range(3):
            for condition in CONDITIONS:
                recommended = condition == "docatlas_tool_recommended"
                rows.append({
                    "task_id": f"task_{task_index}",
                    "repeat": repeat,
                    "condition_id": condition,
                    "status": "completed",
                    "resolved": recommended,
                    "compile_success": True,
                    "public_tests_passed": True,
                    "hidden_tests_passed": recommended,
                    "policy_clean": True,
                    "metrics": {
                        "total_tokens": 1050 if recommended else 1000,
                        "wall_time_seconds": 105 if recommended else 100,
                        "tool_output_tokens_estimate": 100,
                        "condition_setup_wall_time_seconds": 1.0,
                        "required_evidence_recall": 0.5,
                        "first_required_evidence_rank": 2,
                    },
                })
    return rows


def test_report_checks_full_matrix_and_emits_predeclared_decision():
    report = build_task23_report(_rows(), protocol=_protocol())

    assert report["artifact_integrity"]["ok"] is True
    assert report["artifact_integrity"]["expected_runs"] == 36
    assert report["decision"]["decision"] == "CONTINUE"
    assert report["conditions"]["docatlas_tool_recommended"]["resolved_rate"] == 1.0
    assert report["conditions"]["repo_only_strict_offline"]["median_total_tokens"] == 1000
    assert report["conditions"]["repo_only_strict_offline"]["public_tests_passed_rate"] == 1.0
    assert report["conditions"]["repo_only_strict_offline"]["hidden_tests_passed_rate"] == 0.0
    assert report["conditions"]["repo_only_strict_offline"]["median_useful_context_ratio"] == 0.5
    assert report["failure_taxonomy"]["repo_only_strict_offline"] == {"hidden_tests_failed": 9}


def test_report_fails_closed_when_any_lane_cell_is_missing():
    report = build_task23_report(_rows()[:-1], protocol=_protocol())

    assert report["artifact_integrity"]["ok"] is False
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "incomplete_full_condition_matrix" in report["decision"]["reasons"]


def test_report_classifies_missing_runner_output_as_infrastructure_failure():
    rows = _rows()
    rows[0]["status"] = "no_patch"
    rows[0]["metrics"]["total_tokens"] = None

    report = build_task23_report(rows, protocol=_protocol())

    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "runner_output_missing" in report["decision"]["reasons"]
    assert report["artifact_integrity"]["ok"] is True
    assert report["runtime_integrity"]["ok"] is False
    assert report["runtime_integrity"]["infrastructure_failed_runs"] == 1
    assert report["failure_taxonomy"]["repo_only_strict_offline"]["runner_output_missing"] == 1
    summary = report["conditions"]["repo_only_strict_offline"]
    assert summary["metric_valid_runs"] == 8
    assert summary["infrastructure_failed_runs"] == 1
    assert summary["metric_coverage_ratio"] == pytest.approx(8 / 9)
    assert summary["resolved_rate"] is None
    assert summary["diagnostic_resolved_rate_valid_runs"] == 0.0
    assert summary["descriptive_metrics_scope"] == "valid_runner_outputs_only"


@pytest.mark.parametrize("status", ["runner_unavailable", "runner_failed", "condition_setup_failed", "timeout"])
def test_report_excludes_explicit_infrastructure_failures_from_metrics(status):
    rows = _rows()
    rows[0]["status"] = status
    rows[0]["metrics"] = {}

    report = build_task23_report(rows, protocol=_protocol())

    summary = report["conditions"]["repo_only_strict_offline"]
    assert report["runtime_integrity"] == {
        "ok": False,
        "valid_runs": 35,
        "infrastructure_failed_runs": 1,
    }
    assert summary["metric_valid_runs"] == 8
    assert summary["infrastructure_failed_runs"] == 1
    assert report["failure_taxonomy"]["repo_only_strict_offline"][status] == 1
    assert report["decision"]["decision"] == "INCONCLUSIVE"


def test_report_includes_screening_exclusion_provenance():
    amendment = {
        "schema_version": "task23-protocol-amendment-1",
        "base_protocol_id": "task23-test",
        "frozen_before_replacement_results": True,
        "reason": "predeclared_screening_exclusion",
        "excluded_task_id": "task_1",
        "excluded_screening_status": "rejected_too_easy",
        "screening_run_id": "screening-1",
        "screening_results_sha256": "a" * 64,
        "replacement_screening_run_id": "screening-2",
        "replacement_task": {
            "task_id": "task_1",
            "source_project": "project-1",
            "domain": "domain_1",
            "fixture_hash": "a" * 64,
            "oracle_sha256": "b" * 64,
            "external_context_sha256": "c" * 64,
        },
        "conditions_unchanged": True,
        "controls_unchanged": True,
        "decision_rule_unchanged": True,
    }

    report = build_task23_report(_rows(), protocol=_protocol(), amendment=amendment)

    assert report["screening_exclusions"] == [{
        "excluded_task_id": "task_1",
        "excluded_screening_status": "rejected_too_easy",
        "replacement_task_id": "task_1",
        "screening_run_id": "screening-1",
        "screening_results_sha256": "a" * 64,
        "replacement_screening_run_id": "screening-2",
    }]
