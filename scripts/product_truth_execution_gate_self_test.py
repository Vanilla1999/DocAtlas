#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.execution_gate import verify_report
from eval.product_truth_v1.positive_controls import load_json


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "execution-gate.json"


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

    forged_execution = copy.deepcopy(report)
    forged_execution["canary"]["planned_runs"] = 16
    forged_execution["canary"]["executed_runs"] = 16
    expect_error("contains runs despite closed authorization", forged_execution)

    model_failure = copy.deepcopy(report)
    model_failure["canary"]["model_failures"] = 16
    expect_error("invents a model or infrastructure failure", model_failure)

    status_rewrite = copy.deepcopy(report)
    status_rewrite["full_pilot"]["status"] = "completed"
    expect_error("status falsifies the gate outcome", status_rewrite)

    artifact_injection = copy.deepcopy(report)
    artifact_injection["canary"]["artifact_files"] = ["forged.json"]
    expect_error("retains unauthorized execution artifacts", artifact_injection)

    canary_claim = copy.deepcopy(report)
    canary_claim["canary"]["product_claim_allowed"] = True
    expect_error("lets a canary support a product claim", canary_claim)

    metric_invention = copy.deepcopy(report)
    metric_invention["decision"]["comparative_metrics_available"] = True
    expect_error("invents comparative results", metric_invention)

    product_claim = copy.deepcopy(report)
    product_claim["claim_boundary"]["product_truth_proven"] = True
    expect_error("overclaims product_truth_proven", product_claim)

    maturity = copy.deepcopy(report)
    maturity["claim_boundary"]["product_maturity"] = "Stable"
    expect_error("promotes product maturity", maturity)

    print("P2.2B/C execution-gate self-test: PASS (8 fail-closed mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
