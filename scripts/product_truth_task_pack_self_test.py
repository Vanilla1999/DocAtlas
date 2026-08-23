#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.positive_controls import load_json
from eval.product_truth_v1.task_pack import verify_report


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "task-pack.json"


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

    invented_structural = copy.deepcopy(report)
    row = next(item for item in invented_structural["tasks"] if not item["structurally_complete"])
    row["structurally_complete"] = True
    expect_error("structural completeness hidden or invented", invented_structural)

    invented_valid = copy.deepcopy(report)
    row = invented_valid["tasks"][0]
    row["task_valid"] = True
    invented_valid["summary"]["valid_tasks"] += 1
    expect_error("task validity hidden or invented", invented_valid)

    inflated_capacity = copy.deepcopy(report)
    inflated_capacity["summary"]["structurally_complete_tasks"] += 1
    expect_error("summary mismatch: structurally_complete_tasks", inflated_capacity)

    canary_bypass = copy.deepcopy(report)
    canary_bypass["claim_boundary"]["canary_allowed"] = True
    expect_error("execution authorization mismatch", canary_bypass)

    product_overclaim = copy.deepcopy(report)
    product_overclaim["claim_boundary"]["product_truth_proven"] = True
    expect_error("overclaims Product Truth", product_overclaim)

    cardinality_relaxation = copy.deepcopy(report)
    cardinality_relaxation["requirements"]["minimum_valid_tasks"] = 1
    expect_error("preregistered cardinality changed", cardinality_relaxation)

    print("P2.1C task-pack self-test: PASS (6 fail-closed mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
