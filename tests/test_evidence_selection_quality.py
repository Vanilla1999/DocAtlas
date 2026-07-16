from __future__ import annotations

from eval.evidence_selection_quality import evaluate, load_cases


def test_task42_provider_free_cases_are_unique_and_digest_bound():
    cases, digests = load_cases()

    assert len(cases) == 13
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all(len(value) == 64 for value in digests.values())


def test_task42_acceptance_binds_task41_and_beats_legacy_token_cost():
    report = evaluate()

    assert report["correctness_gate"] == "PASS"
    assert report["verdict"] == "PASS"
    assert report["baseline_status"] == "PASS"
    assert report["task41_gate"]["status"] == "PASS"
    assert report["task41_gate"]["baseline_match"] is True
    assert report["token_gate"] == "PASS"
    assert all(
        row["median_selector_budgeted_tokens"] <= row["median_legacy_budgeted_tokens"]
        for row in report["groups"].values()
    )
    assert all(row["passed"] for row in report["results"])
