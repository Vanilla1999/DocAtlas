from __future__ import annotations

from eval.library_retrieval_quality_baseline import evaluate_cases, evaluate_report, load_cases


def test_library_eval_adapter_loads_all_splits_with_unique_cases():
    cases, digests = load_cases()

    assert set(digests) == {"development.json", "holdout.json", "adversarial.json"}
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["split"] for case in cases} == {"development", "holdout", "adversarial"}


def test_library_eval_adapter_delegates_to_canonical_evidence_evaluator():
    cases, _ = load_cases()

    results = evaluate_cases(cases)

    assert [result["case_id"] for result in results] == [case["case_id"] for case in cases]
    assert all("checks" in result and "selection_hash" in result for result in results)


def test_library_eval_report_reuses_existing_metrics_and_adds_only_declared_fields():
    cases, _ = load_cases()

    report = evaluate_report(cases)

    assert report["provider_free"] is True
    assert report["dataset_digest_match"] is True
    assert set(report["retrieval"]["overall"]) >= {
        "recall@5",
        "mrr",
        "ndcg@20",
        "required_fact_pass_rate",
        "insufficient_evidence_pass_rate",
    }
    assert set(report["derived"]) == {
        "mandatory_requirement_coverage@1",
        "mandatory_requirement_coverage@5",
        "support_decision_consistency_rate",
        "answerable_abstention_rate",
        "unsupported_answer_rate",
        "partial_overlap_false_positive_rate",
        "required_code_group_pass_rate",
    }
    assert [row["case_id"] for row in report["evidence_results"]] == [
        case["case_id"] for case in cases
    ]
    assert report["derived"]["support_decision_consistency_rate"] == 1.0
    assert report["derived"]["partial_overlap_false_positive_rate"] == 0.0
    assert report["derived"]["required_code_group_pass_rate"] == 1.0
