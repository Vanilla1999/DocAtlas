#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.p1_closure import (
    derive_from_paths,
    verify_closure,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(repo_root=REPO_ROOT, root=ROOT)


def _expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_closure(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def test_exact_non_positive_closure() -> None:
    report = _report()
    verify_closure(report)
    assert report["execution_status"] == "CLOSED"
    assert report["outcome"] == "AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN"
    assert report["product_maturity"] == "Beta"
    assert [row["id"] for row in report["scorecard"]] == [
        "P1.1", "P1.2", "P1.3", "P1.4", "P1.5", "P1.6"
    ]


def test_autonomous_and_stable_overclaim_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["autonomous_agent_truth_proven"] = True
    _expect_error("overclaims autonomous_agent_truth_proven", report)

    report = _report()
    report["claim_boundary"]["stable_claim_allowed"] = True
    _expect_error("overclaims stable_claim_allowed", report)


def test_missing_work_item_and_runtime_change_fail_closed() -> None:
    report = _report()
    report["scorecard"].pop()
    _expect_error("incomplete or reordered", report)

    report = _report()
    report["decision"]["accepted_production_changes"] = ["scope_inference"]
    _expect_error("accepted an unproven production change", report)


def test_maturity_and_path_leak_fail_closed() -> None:
    report = _report()
    report["product_maturity"] = "Stable"
    _expect_error("improperly promotes", report)

    report = _report()
    report["scorecard"][0]["decision"] = "read /home/user/private"
    _expect_error("absolute local path", report)


def main() -> int:
    checks = (
        test_exact_non_positive_closure,
        test_autonomous_and_stable_overclaim_fail_closed,
        test_missing_work_item_and_runtime_change_fail_closed,
        test_maturity_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1 closure self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
