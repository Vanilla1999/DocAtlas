#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.paraphrase_robustness import (
    derive_from_paths,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _production_planner_path() -> Path:
    candidates = (
        REPO_ROOT / "docmancer" / "docs" / "domain" / "project_answer_contract.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "question_planning.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "question_plan.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "answer_completeness.py",
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RuntimeError("no reviewed production question-planning module exists")
    return existing[0]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "paraphrase_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        planner_path=_production_planner_path(),
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


def test_exact_report_and_family_separation() -> None:
    report = _report()
    verify_report(report)
    assert report["summary"]["case_count"] == 14
    assert {
        "exact_identifier",
        "behavior",
        "requirements",
        "policy",
        "typo",
        "alias",
        "negative_control",
    } == set(report["families"])
    assert report["claim_boundary"]["candidate_discovery_separate_from_support"] is True


def test_negative_false_support_fails_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if item["negative_control"])
    row["answer_supported"] = True
    row["selected_sources"] = ["docs/fake.md"]
    _expect_error("negative control was falsely supported", report)


def test_required_discovery_and_support_fail_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if item["require_discovery"])
    row["candidate_discovered"] = False
    _expect_error("required candidate discovery failed", report)

    report = _report()
    row = next(item for item in report["cases"] if item["require_support"])
    row["answer_supported"] = False
    _expect_error("required support failed", report)


def test_claim_and_path_leak_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["production_runtime_changed"] = True
    _expect_error("overclaims", report)

    report = _report()
    report["cases"][0]["selected_sources"] = ["/home/user/private.md"]
    _expect_error("absolute local path", report)


def main() -> int:
    checks = (
        test_exact_report_and_family_separation,
        test_negative_false_support_fails_closed,
        test_required_discovery_and_support_fail_closed,
        test_claim_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.4 self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
