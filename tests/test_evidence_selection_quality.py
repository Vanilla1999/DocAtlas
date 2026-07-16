from __future__ import annotations

from eval.evidence_selection_quality import _task41_baseline_gate, evaluate, load_cases


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


def test_task42_task41_gate_rejects_commit_sha_mismatch():
    published_sha = "9afb20d7aca6c0411b14739781dacceb292cb78f"
    trace_hash = "a" * 64
    config_hash = "b" * 64
    report = {"status": "PASS", "published_commit_sha": published_sha}
    variant = {
        "candidate_trace_hash": trace_hash,
        "retrieval_config_hash": config_hash,
    }
    baseline = {
        "commit_sha": published_sha,
        "task41_candidate_trace_hash": trace_hash,
        "retrieval_config_hash": config_hash,
    }

    assert _task41_baseline_gate(report, variant, baseline)["baseline_match"] is True

    baseline["commit_sha"] = "0" * 40
    gate = _task41_baseline_gate(report, variant, baseline)

    assert gate["commit_sha_match"] is False
    assert gate["baseline_match"] is False
