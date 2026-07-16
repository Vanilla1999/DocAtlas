from __future__ import annotations

import json
from pathlib import Path

from eval.retrieval_quality_baseline import compare_to_baseline, run_baseline


ROOT = Path(__file__).resolve().parents[1]


def test_provider_free_baseline_is_deterministic_and_bound_to_revisions(tmp_path):
    first = run_baseline(tmp_path / "first")
    second = run_baseline(tmp_path / "second")

    assert first["provider_free"] is True
    assert first["deterministic_result_digest"] == second["deterministic_result_digest"]
    assert first["dataset_digests"] == second["dataset_digests"]
    assert first["index_revision"] == second["index_revision"]
    assert first["retrieval_config_hash"] == second["retrieval_config_hash"]
    assert first["code_revision"] == second["code_revision"]
    assert first["code_revision_kind"] == "source-content-sha256"
    assert first["index_schema_version"] == "sqlite-sections-v1"
    assert set(first["splits"]) == {"development", "holdout", "adversarial"}
    assert first["fixture_backed_datasets_executed"] == [
        "eval/retrieval_quality/development.json",
        "eval/retrieval_quality/holdout.json",
        "eval/retrieval_quality/adversarial.json",
    ]
    assert any(
        row["path"] == "eval/fastapi_golden.yaml"
        and row["execution_status"] == "snapshot_only_external_corpus"
        for row in first["legacy_golden_inventory"]
    )


def test_case_artifacts_trace_candidates_without_full_document_fields(tmp_path):
    run_baseline(tmp_path)
    case_path = tmp_path / "cases" / "adversarial__legal_title_distractor.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))

    assert case["first_expected_rank"] == 1
    assert case["metrics"]["authoritative_source_at_1"] is True
    assert case["metrics"]["model_visible_tokens"] <= 800
    assert case["candidates"][0]["ranking"]["score_direction"] == "higher_is_better"
    assert len(case["candidates"][0]["excerpt"]) <= 200
    assert "text" not in case["candidates"][0]
    assert "content" not in case["candidates"][0]


def test_baseline_gate_rejects_holdout_quality_regression(tmp_path):
    baseline = run_baseline(tmp_path / "baseline")
    current = json.loads(json.dumps(baseline))
    current["splits"]["holdout"]["recall@5"] = 0.0
    current["splits"]["holdout"]["mrr"] = 0.0

    errors = compare_to_baseline(current, baseline)

    assert "holdout:recall@5_regressed" in errors
    assert "holdout:mrr_regressed" in errors


def test_baseline_gate_rejects_single_case_regression_hidden_by_aggregate(tmp_path):
    baseline = run_baseline(tmp_path / "baseline")
    current = json.loads(json.dumps(baseline))
    case_id = "holdout:version_migration"
    current["case_gates"][case_id]["recall@5"] = 0.0
    current["case_gates"][case_id]["required_fact_pass"] = False

    errors = compare_to_baseline(current, baseline)

    assert f"{case_id}:recall@5_regressed" in errors
    assert f"{case_id}:required_fact_regressed" in errors


def test_baseline_gate_rejects_projection_and_applicable_metric_regressions(tmp_path):
    baseline = run_baseline(tmp_path / "baseline")
    current = json.loads(json.dumps(baseline))
    insufficient = current["case_gates"]["holdout:insufficient_evidence"]
    insufficient["projection_status"] = "ok"
    insufficient["insufficient_evidence_pass"] = False
    exact = current["case_gates"]["development:exact_api_identifier"]
    exact["ndcg@20"] = 0.0
    exact["authoritative_source_at_1"] = False
    exact["exact_identifier_at_1"] = False
    exact["snippet_required_pass"] = False

    errors = compare_to_baseline(current, baseline)

    assert "holdout:insufficient_evidence:projection_status_regressed" in errors
    assert "holdout:insufficient_evidence:insufficient_evidence_pass_regressed" in errors
    assert "development:exact_api_identifier:ndcg@20_regressed" in errors
    assert "development:exact_api_identifier:authoritative_source_at_1_regressed" in errors
    assert "development:exact_api_identifier:exact_identifier_at_1_regressed" in errors
    assert "development:exact_api_identifier:snippet_required_pass_regressed" in errors


def test_baseline_gate_rejects_paraphrase_group_regression(tmp_path):
    baseline = run_baseline(tmp_path / "baseline")
    current = json.loads(json.dumps(baseline))
    group = current["paraphrase_group_gates"]["docatlas_offline_policy"]
    group["minimum_reciprocal_rank"] = 0.0
    group["forbidden_source_violations"] += 1

    errors = compare_to_baseline(current, baseline)

    assert "paraphrase:docatlas_offline_policy:minimum_reciprocal_rank_regressed" in errors
    assert "paraphrase:docatlas_offline_policy:forbidden_source_violations_regressed" in errors


def test_non_applicable_rates_are_null_and_stale_cases_are_removed(tmp_path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir(parents=True)
    (case_dir / "stale.json").write_text("{}", encoding="utf-8")

    summary = run_baseline(tmp_path)

    assert summary["splits"]["development"]["insufficient_evidence_pass_rate"] is None
    assert summary["splits"]["adversarial"]["exact_identifier_at_1_rate"] is None
    assert not (case_dir / "stale.json").exists()


def test_current_ranking_passes_the_checked_in_frozen_gate(tmp_path):
    current = run_baseline(tmp_path)
    baseline = json.loads(
        (ROOT / "eval/retrieval_quality/baseline_v1/summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert compare_to_baseline(current, baseline) == []
    # The exact digest characterizes one code revision. Later roadmap tasks are
    # allowed to change projection/chunking code, but must still pass every
    # frozen quality gate. Preserve byte-exactness whenever the bound code is
    # unchanged instead of making all future accepted improvements rewrite the
    # Task 39 baseline.
    if current["code_revision"] == baseline["code_revision"]:
        assert current["deterministic_result_digest"] == baseline["deterministic_result_digest"]
