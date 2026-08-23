#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.positive_controls import load_json, verify_report


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "positive-controls.json"


def expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_report(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def main() -> int:
    report = load_json(REPORT)
    verify_report(report)

    invented_validity = copy.deepcopy(report)
    invented_validity["tasks"][0]["task_valid"] = True
    invented_validity["summary"]["valid_tasks"] += 1
    expect_error("task validity was hidden or invented", invented_validity)

    hidden_gold_failure = copy.deepcopy(report)
    hidden_gold_failure["tasks"][0]["gold_attempts"][1]["passed"] = False
    expect_error("gold reproducibility was hidden or invented", hidden_gold_failure)

    provider_free_promotion = copy.deepcopy(report)
    provider_free_promotion["claim_boundary"][
        "provider_free_run_counts_as_oracle_control"
    ] = True
    expect_error("provider-free oracle substitution", provider_free_promotion)

    product_overclaim = copy.deepcopy(report)
    product_overclaim["claim_boundary"]["product_truth_proven"] = True
    expect_error("overclaims Product Truth", product_overclaim)

    readiness_overclaim = copy.deepcopy(report)
    readiness_overclaim["decision"]["task_pack_ready"] = True
    expect_error("task-pack readiness mismatch", readiness_overclaim)

    print("P2.1B positive-control self-test: PASS (5 fail-closed mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
