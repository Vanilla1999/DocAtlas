from __future__ import annotations

import hashlib

import pytest

from eval.task_level.analysis.task23_report import (
    _publish_report_artifacts,
    _retry_provenance,
    _source_artifact_hashes,
    build_task23_report,
    write_sanitized_run_bundle,
)


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
    sanitized = tmp_path / "sanitized.jsonl"
    sanitized.write_bytes(b"sanitized\n")

    hashes = _source_artifact_hashes(runs, protocol, amendment, replacement_screening, sanitized)

    assert hashes == {
        "runs_jsonl_sha256": hashlib.sha256(b"runs\n").hexdigest(),
        "protocol_sha256": hashlib.sha256(b"protocol\n").hexdigest(),
        "amendment_sha256": hashlib.sha256(b"amendment\n").hexdigest(),
        "replacement_screening_sha256": hashlib.sha256(b"replacement\n").hexdigest(),
        "sanitized_runs_sha256": hashlib.sha256(b"sanitized\n").hexdigest(),
    }


def test_sanitized_bundle_keeps_rescorable_patch_and_removes_local_paths(tmp_path):
    run_dir = tmp_path / "run"
    cell = run_dir / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")
    (cell / "trajectory.normalized.json").write_text(
        '[{"sequence": 1, "tool_name": "Bash", "result_summary": "checked"}]',
        encoding="utf-8",
    )
    output = tmp_path / "bundle.jsonl"
    rows = [{
        "task_id": "task_a",
        "condition_id": "condition_a",
        "repeat": 0,
        "status": "completed",
        "resolved": False,
        "patch_path": "/private/local/patch.diff",
        "trajectory_path": "/private/local/trajectory.json",
        "metrics": {"total_tokens": 10},
    }]

    integrity = write_sanitized_run_bundle(rows, run_dir, output)
    payload = __import__("json").loads(output.read_text(encoding="utf-8"))

    assert payload["patch"] == "diff --git a/a b/a\n"
    assert payload["trajectory"][0]["result_summary"] == "checked"
    assert "/private/local" not in output.read_text(encoding="utf-8")
    assert integrity["integrity_ok"] is True


def test_sanitized_bundle_fails_closed_on_missing_completed_patch(tmp_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "trajectory.normalized.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="has no patch"):
        write_sanitized_run_bundle([{
            "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
            "status": "completed", "metrics": {"total_tokens": 1},
        }], tmp_path / "run", tmp_path / "bundle.jsonl")


def test_sanitized_bundle_rejects_local_paths_inside_trajectory(tmp_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")
    (cell / "trajectory.normalized.json").write_text(
        '[{"result_summary":"read /workspace/private/source.py"}]', encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsanitized"):
        write_sanitized_run_bundle([{
            "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
            "status": "completed", "metrics": {"total_tokens": 1},
        }], tmp_path / "run", tmp_path / "bundle.jsonl")


def test_sanitized_bundle_allows_file_marker_ending_in_backslash(tmp_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")
    (cell / "trajectory.normalized.json").write_text(
        __import__("json").dumps([{"result_summary": "FILE:\\"}]), encoding="utf-8",
    )

    integrity = write_sanitized_run_bundle([{
        "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
        "status": "completed", "metrics": {"total_tokens": 1},
    }], tmp_path / "run", tmp_path / "bundle.jsonl")

    assert integrity["integrity_ok"] is True


@pytest.mark.parametrize("local_path", ["E:\\private\\file.txt", "/etc/passwd", "\\\\server\\share\\secret"])
def test_sanitized_bundle_rejects_absolute_local_paths(tmp_path, local_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")
    (cell / "trajectory.normalized.json").write_text(
        __import__("json").dumps([{"result_summary": f"read {local_path}"}]), encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsanitized"):
        write_sanitized_run_bundle([{
            "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
            "status": "completed", "metrics": {"total_tokens": 1},
        }], tmp_path / "run", tmp_path / "bundle.jsonl")


def test_sanitized_bundle_requires_protocol_identifiers(tmp_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text("diff --git a/a b/a\n", encoding="utf-8")
    (cell / "trajectory.normalized.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="immutable task identifiers"):
        write_sanitized_run_bundle([{
            "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
            "status": "completed", "metrics": {"total_tokens": 1},
        }], tmp_path / "run", tmp_path / "bundle.jsonl", protocol={"tasks": [{"task_id": "task_a"}]})


def test_sanitized_bundle_allows_local_path_literal_in_patch_body(tmp_path):
    cell = tmp_path / "run" / "task_a" / "condition_a" / "repeat_0"
    cell.mkdir(parents=True)
    (cell / "patch.diff").write_text(
        "diff --git a/test.py b/test.py\n--- a/test.py\n+++ b/test.py\n@@ -0,0 +1 @@\n+TMP = '/tmp/example'\n",
        encoding="utf-8",
    )
    (cell / "trajectory.normalized.json").write_text("[]", encoding="utf-8")

    integrity = write_sanitized_run_bundle([{
        "task_id": "task_a", "condition_id": "condition_a", "repeat": 0,
        "status": "completed", "metrics": {"total_tokens": 1},
    }], tmp_path / "run", tmp_path / "bundle.jsonl")

    assert integrity["integrity_ok"] is True


def test_report_publication_preserves_previous_artifacts_when_staging_fails(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    bundle = tmp_path / "report_runs.sanitized.jsonl"
    output.write_text("old report", encoding="utf-8")
    bundle.write_text("old bundle", encoding="utf-8")

    def fail_bundle(*args, **kwargs):
        raise ValueError("staging failed")

    monkeypatch.setattr(
        "eval.task_level.analysis.task23_report.write_sanitized_run_bundle",
        fail_bundle,
    )

    with pytest.raises(ValueError, match="staging failed"):
        _publish_report_artifacts({}, [], tmp_path, output, bundle, protocol={})

    assert output.read_text(encoding="utf-8") == "old report"
    assert bundle.read_text(encoding="utf-8") == "old bundle"
    assert not list(tmp_path.glob("*.tmp"))


def test_report_publication_preserves_consistent_pair_when_report_replace_fails(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    bundle = tmp_path / "report_runs.sanitized.jsonl"
    old_bundle = b"old bundle"
    old_hash = hashlib.sha256(old_bundle).hexdigest()
    old_report = {"source_artifacts": {"sanitized_runs_sha256": old_hash}}
    output.write_text(__import__("json").dumps(old_report), encoding="utf-8")
    bundle.write_bytes(old_bundle)

    def write_same_bundle(rows, run_dir, destination, *, protocol=None):
        destination.write_bytes(old_bundle)
        return {"integrity_ok": True, "rows_written": 0, "sha256": old_hash}

    original_replace = __import__("pathlib").Path.replace

    def fail_report_replace(path, target):
        if target == output:
            raise OSError("report replace failed")
        return original_replace(path, target)

    monkeypatch.setattr(
        "eval.task_level.analysis.task23_report.write_sanitized_run_bundle",
        write_same_bundle,
    )
    monkeypatch.setattr("pathlib.Path.replace", fail_report_replace)

    with pytest.raises(OSError, match="report replace failed"):
        _publish_report_artifacts({"source_artifacts": {}}, [], tmp_path, output, bundle, protocol={})

    assert __import__("json").loads(output.read_text(encoding="utf-8")) == old_report
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == old_hash


def test_report_publication_refuses_to_overwrite_immutable_bundle(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    bundle = tmp_path / "report_runs.sanitized.jsonl"
    output.write_text("old report", encoding="utf-8")
    bundle.write_bytes(b"old bundle")

    def write_changed_bundle(rows, run_dir, destination, *, protocol=None):
        destination.write_bytes(b"new bundle")
        return {"integrity_ok": True, "rows_written": 0}

    monkeypatch.setattr(
        "eval.task_level.analysis.task23_report.write_sanitized_run_bundle",
        write_changed_bundle,
    )

    with pytest.raises(FileExistsError, match="immutable sanitized bundle"):
        _publish_report_artifacts({}, [], tmp_path, output, bundle, protocol={})

    assert output.read_text(encoding="utf-8") == "old report"
    assert bundle.read_bytes() == b"old bundle"


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
                    "budget": {
                        "max_input_tokens": 2000,
                        "max_output_tokens": 1000,
                        "max_turns": 40,
                        "max_turns_enforced_by_runner": True,
                        "input_tokens_exceeded": False,
                        "output_tokens_exceeded": False,
                    },
                    "metrics": {
                        "total_tokens": 1050 if recommended else 1000,
                        "input_tokens": 900,
                        "output_tokens": 100,
                        "wall_time_seconds": 105 if recommended else 100,
                        "tool_output_tokens_estimate": 100,
                        "useful_context_ratio": None,
                        "docs_output_evidence_coverage": 0.25,
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
    assert report["conditions"]["repo_only_strict_offline"]["median_useful_context_ratio"] is None
    assert report["conditions"]["repo_only_strict_offline"]["median_docs_output_evidence_coverage"] == 0.25
    assert report["conditions"]["docatlas_tool_recommended"]["input_budget_exceeded_runs"] == 0
    assert report["failure_taxonomy"]["repo_only_strict_offline"] == {"hidden_tests_failed": 9}


def test_report_fails_closed_when_any_lane_cell_is_missing():
    report = build_task23_report(_rows()[:-1], protocol=_protocol())

    assert report["artifact_integrity"]["ok"] is False
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "incomplete_full_condition_matrix" in report["decision"]["reasons"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", "unexpected_task"),
        ("condition_id", "unexpected_condition"),
        ("repeat", 3),
        ("repeat", "0"),
        ("repeat", [0]),
    ],
)
def test_report_fails_closed_on_out_of_protocol_rows(field, value):
    rows = _rows()
    extra = dict(rows[0])
    extra[field] = value
    rows.append(extra)

    report = build_task23_report(rows, protocol=_protocol())

    assert report["artifact_integrity"]["ok"] is False
    assert report["artifact_integrity"]["actual_runs"] == 37
    assert report["artifact_integrity"]["unexpected_cells"]
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "incomplete_full_condition_matrix" in report["decision"]["reasons"]


def test_report_fails_closed_on_duplicate_expected_cell():
    rows = _rows()
    rows.append(dict(rows[0]))

    report = build_task23_report(rows, protocol=_protocol())

    assert report["artifact_integrity"]["ok"] is False
    assert report["artifact_integrity"]["duplicate_cells"]
    assert report["decision"]["decision"] == "INCONCLUSIVE"


def test_report_fails_closed_when_declared_token_budget_is_exceeded():
    rows = _rows()
    rows[0]["metrics"]["input_tokens"] = 2001
    rows[0]["budget"]["input_tokens_exceeded"] = True

    report = build_task23_report(rows, protocol=_protocol())

    assert report["budget_integrity"]["ok"] is False
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "declared_token_budget_exceeded" in report["decision"]["reasons"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.pop("budget"),
        lambda row: row["budget"].pop("max_input_tokens"),
        lambda row: row["budget"].pop("input_tokens_exceeded"),
        lambda row: row["budget"].update(input_tokens_exceeded=True),
    ],
)
def test_report_fails_closed_when_budget_is_missing_incomplete_or_inconsistent(mutation):
    rows = _rows()
    mutation(rows[0])

    report = build_task23_report(rows, protocol=_protocol())

    assert report["budget_integrity"]["ok"] is False
    assert report["budget_integrity"]["unknown_runs"] == 1
    assert report["conditions"]["repo_only_strict_offline"]["budget_unknown_runs"] == 1
    assert report["conditions"]["repo_only_strict_offline"]["input_budget_exceeded_runs"] == 0
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "missing_or_invalid_budget_metrics" in report["decision"]["reasons"]


def test_report_fails_closed_when_max_turn_budget_is_not_enforced():
    rows = _rows()
    rows[0]["budget"]["max_turns_enforced_by_runner"] = False

    report = build_task23_report(rows, protocol=_protocol())

    assert report["budget_integrity"]["ok"] is False
    assert report["budget_integrity"]["max_turns_unenforced_runs"] == 1
    assert report["conditions"]["repo_only_strict_offline"]["max_turns_unenforced_runs"] == 1
    assert report["decision"]["decision"] == "INCONCLUSIVE"
    assert "max_turn_budget_not_enforced" in report["decision"]["reasons"]


def test_report_never_republishes_legacy_useful_context_proxy():
    rows = _rows()
    rows[0]["metrics"]["useful_context_ratio"] = 0.75

    report = build_task23_report(rows, protocol=_protocol())

    summary = report["conditions"]["repo_only_strict_offline"]
    assert summary["median_useful_context_ratio"] is None
    assert summary["useful_context_ratio_method"] == "not_measured_without_chunk_usage_attribution"


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
