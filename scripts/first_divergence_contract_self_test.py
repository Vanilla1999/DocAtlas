#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.agent_developer_v1.first_divergence import (
    derive_from_paths,
    verify_atlas,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _atlas() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        report_path=ROOT / "results" / "model-benchmark.json",
        oracle_path=ROOT / "expected_trajectories.json",
        tasks_path=ROOT / "tasks.json",
    )


def _expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_atlas(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def test_exact_historical_classification() -> None:
    payload = _atlas()
    verify_atlas(payload)
    assert payload["summary"]["failure_class_counts"] == {
        "module_selector_cardinality": 8,
        "retrieval_query_drift": 2,
        "trajectory_order": 1,
    }
    assert payload["claim_boundary"]["autonomous_agent_truth_proven"] is False
    assert payload["decision"]["api_freeze"] is True


def test_missing_task_identity_fails_closed() -> None:
    payload = _atlas()
    payload["tasks"].pop()
    _expect_error("exactly 11 tasks", payload)


def test_classification_drift_fails_closed() -> None:
    payload = _atlas()
    payload["tasks"][0]["first_divergence"]["failure_class"] = "retrieval_query_drift"
    _expect_error("class counts changed", payload)


def test_path_and_claim_overreach_fail_closed() -> None:
    payload = _atlas()
    payload["tasks"][0]["server_side_reason"] = "leaked /home/user/private"
    _expect_error("absolute local path", payload)

    payload = _atlas()
    payload["claim_boundary"]["public_api_change_authorized"] = True
    _expect_error("overclaims", payload)


def main() -> int:
    checks = (
        test_exact_historical_classification,
        test_missing_task_identity_fails_closed,
        test_classification_drift_fails_closed,
        test_path_and_claim_overreach_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.2 first-divergence self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
