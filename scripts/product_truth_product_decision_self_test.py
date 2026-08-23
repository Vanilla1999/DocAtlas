#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.product_decision import verify_report
from eval.product_truth_v1.protocol import load_json


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "product-decision.json"


def expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_report(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def main() -> int:
    report = load_json(REPORT)
    verify_report(report)

    forged_product_truth = copy.deepcopy(report)
    forged_product_truth["outcome"] = "PRODUCT_TRUTH_PROVEN"
    expect_error("falsifies the Product Truth outcome", forged_product_truth)

    forged_product_failure = copy.deepcopy(report)
    forged_product_failure["claim_boundary"]["product_failure_proven"] = True
    expect_error("overclaims product_failure_proven", forged_product_failure)

    forged_experiment = copy.deepcopy(report)
    forged_experiment["claim_boundary"]["comparative_experiment_executed"] = True
    expect_error("invents a comparative experiment", forged_experiment)

    forged_runs = copy.deepcopy(report)
    forged_runs["measured_facts"]["full_pilot_executed_runs"] = 576
    expect_error("measured facts", forged_runs)

    forged_valid_tasks = copy.deepcopy(report)
    forged_valid_tasks["measured_facts"]["valid_tasks"] = 24
    expect_error("measured facts", forged_valid_tasks)

    missing_row = copy.deepcopy(report)
    missing_row["scorecard"].pop()
    expect_error("scorecard is incomplete or reordered", missing_row)

    stable = copy.deepcopy(report)
    stable["product_maturity"] = "Stable"
    expect_error("promotes product maturity", stable)

    expansion = copy.deepcopy(report)
    expansion["claim_boundary"]["p3_conditional_expansion_authorized"] = True
    expect_error("overclaims p3_conditional_expansion_authorized", expansion)

    production_change = copy.deepcopy(report)
    production_change["decision"]["accepted_production_changes"] = [
        "broaden retrieval"
    ]
    expect_error("accepts an unproven production change", production_change)

    weakened_reopening = copy.deepcopy(report)
    weakened_reopening["reopening_conditions"]["minimum_valid_tasks"] = 3
    expect_error("reopening conditions changed", weakened_reopening)

    invalid_source = copy.deepcopy(report)
    invalid_source["source_reports"]["task_pack"]["git_blob_sha1"] = "not-a-sha"
    expect_error("source identity invalid", invalid_source)

    path_leak = copy.deepcopy(report)
    path_leak["decision"]["next_step"] = "/home/user/private/task-pack"
    expect_error("absolute local path", path_leak)

    print("P2.3 product-decision self-test: PASS (12 fail-closed mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
