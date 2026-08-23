#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.comparative import _verify_matrix, build_matrix
from eval.product_truth_v1.comparative_contract import verify_report
from eval.product_truth_v1.positive_controls import load_json, load_tasks


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "comparative-harness.json"


def expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_report(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def verify_synthetic_matrix(report: dict) -> None:
    tasks = load_tasks(ROOT / "eval" / "task_level" / "tasks.jsonl")
    ids = (
        "decisive_docmancer_vector_timeout_fallback_001",
        "real_project_help_chat_linearizable_module_lifecycle_001",
    )
    selected = [
        {
            "task_id": task_id,
            "source_project": tasks[task_id].source_project or tasks[task_id].repo,
            "fixture_hash": str(index) * 64,
        }
        for index, task_id in enumerate(ids, start=1)
    ]
    runs = build_matrix(
        selected_tasks=selected,
        task_specs=tasks,
        model_snapshots=("model-snapshot-a", "model-snapshot-b"),
        repeats=1,
        conditions=report["conditions"],
        seed="docatlas-product-truth-v1:synthetic-control",
    )
    assert len(runs) == 16
    _verify_matrix(runs, conditions=report["conditions"], expected_blocks=4)


def main() -> int:
    report = load_json(REPORT)
    verify_report(report)
    verify_synthetic_matrix(report)

    authorization_bypass = copy.deepcopy(report)
    authorization_bypass["authorization"]["canary_authorized"] = True
    expect_error("authorization mismatch", authorization_bypass)

    run_injection = copy.deepcopy(report)
    run_injection["plans"]["canary"]["runs"] = [{"run_id": "forged"}]
    expect_error("planned-run count mismatch", run_injection)

    condition_drift = copy.deepcopy(report)
    condition_drift["conditions"][0]["docatlas"] = True
    expect_error("condition capability drift", condition_drift)

    randomization_drift = copy.deepcopy(report)
    randomization_drift["randomization"]["seed"] = "post-hoc"
    expect_error("randomization contract mismatch", randomization_drift)

    canary_claim = copy.deepcopy(report)
    canary_claim["claim_boundary"]["canary_product_claim_allowed"] = True
    expect_error("canary support a product claim", canary_claim)

    product_claim = copy.deepcopy(report)
    product_claim["claim_boundary"]["product_truth_proven"] = True
    expect_error("overclaims Product Truth", product_claim)

    cardinality_drift = copy.deepcopy(report)
    cardinality_drift["plans"]["full_pilot"]["minimum_scored_runs"] = 1
    expect_error("pilot cardinality changed", cardinality_drift)

    print("P2.2A comparative self-test: PASS (synthetic 16-cell matrix + 7 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
