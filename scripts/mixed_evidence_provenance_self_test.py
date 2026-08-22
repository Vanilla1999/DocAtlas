#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.mixed_provenance import (
    derive_from_paths,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "mixed_provenance_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        model_path=REPO_ROOT / "docmancer" / "docs" / "domain" / "evidence_models.py",
    )


def _expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_report(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def test_exact_claim_local_assignments() -> None:
    report = _report()
    verify_report(report)
    assert report["summary"]["matched_cases"] == 7
    assert report["summary"]["advisory_assignments"] == []
    assert report["decision"]["claim_local_provenance"] == "accepted"


def test_wrong_assignment_source_fails_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if item["answer_supported"])
    row["assignment_sources"] = ["https://advisory.example/forged"]
    _expect_error("assignment-source mismatch", report)


def test_false_support_fails_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if not item["expected_supported"])
    row["answer_supported"] = True
    _expect_error("support mismatch", report)


def test_claim_and_path_leak_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["production_runtime_changed"] = True
    _expect_error("overclaims", report)

    report = _report()
    report["cases"][0]["selected_sources"] = ["/home/user/private.md"]
    _expect_error("absolute local path", report)


def main() -> int:
    checks = (
        test_exact_claim_local_assignments,
        test_wrong_assignment_source_fails_closed,
        test_false_support_fails_closed,
        test_claim_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.5 self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
