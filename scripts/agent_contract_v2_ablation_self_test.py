#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.contract_v2_ablation import (
    conservative_module_inference,
    derive_from_paths,
    verify_ablation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        public_tasks_path=ROOT / "tasks.json",
        oracle_path=ROOT / "expected_trajectories.json",
        atlas_path=ROOT / "results" / "first-divergence-atlas.json",
    )


def _expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_ablation(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def test_unique_module_inference_is_conservative() -> None:
    assert conservative_module_inference(
        "packages/orders/src/submission.py",
        ["packages/orders"],
    ) == "packages/orders"
    assert conservative_module_inference(
        "packages/orders/src/submission.py",
        ["packages", "packages/orders"],
    ) is None
    assert conservative_module_inference(
        "../packages/orders/src/submission.py",
        ["packages/orders"],
    ) is None


def test_exact_ablation_decisions() -> None:
    report = _report()
    verify_ablation(report)
    inference = next(
        row for row in report["variants"]
        if row["id"] == "conservative_server_owned_scope_inference"
    )
    assert inference["first_divergences_prevented_counterfactually"] == 8
    assert report["decision"]["accepted_production_changes"] == []


def test_unproven_inference_promotion_fails_closed() -> None:
    report = _report()
    inference = next(
        row for row in report["variants"]
        if row["id"] == "conservative_server_owned_scope_inference"
    )
    inference["decision"] = "accepted"
    _expect_error("promoted without fresh evidence", report)


def test_public_change_and_path_leak_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["production_api_changed"] = True
    _expect_error("overclaims", report)

    report = _report()
    report["variants"][0]["reason"] = "read /home/user/private"
    _expect_error("absolute local path", report)


def main() -> int:
    checks = (
        test_unique_module_inference_is_conservative,
        test_exact_ablation_decisions,
        test_unproven_inference_promotion_fails_closed,
        test_public_change_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.3 ablation self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
