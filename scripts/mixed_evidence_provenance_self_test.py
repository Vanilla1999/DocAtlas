#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.mixed_provenance import (
    derive_from_paths,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _production_evidence_model_path() -> Path:
    candidates = (
        REPO_ROOT / "docmancer" / "docs" / "domain" / "evidence_models.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "evidence.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "models.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "answer_completeness.py",
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RuntimeError("no reviewed production evidence-model module exists")
    return existing[0]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "mixed_provenance_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        model_path=_production_evidence_model_path(),
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


def test_provenance_gap_is_retained_but_not_hidden() -> None:
    report = _report()
    row = next(item for item in report["cases"] if item["answer_supported"])
    row["assignment_sources"] = ["https://advisory.example/forged"]
    report["summary"]["mismatches"] = [row["id"]]
    report["summary"]["advisory_assignments"] = [
        {"case_id": row["id"], "source": "https://advisory.example/forged"}
    ]
    report["decision"]["claim_local_provenance"] = "rejected"
    verify_report(report)

    report["summary"]["mismatches"] = []
    _expect_error("provenance mismatches are hidden or invented", report)


def test_support_gap_is_retained_but_not_hidden() -> None:
    report = _report()
    row = next(item for item in report["cases"] if not item["expected_supported"])
    row["answer_supported"] = True
    report["summary"]["mismatches"] = [row["id"]]
    report["decision"]["claim_local_provenance"] = "rejected"
    verify_report(report)

    report["summary"]["mismatches"] = []
    _expect_error("provenance mismatches are hidden or invented", report)


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
        test_provenance_gap_is_retained_but_not_hidden,
        test_support_gap_is_retained_but_not_hidden,
        test_claim_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.5 self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
