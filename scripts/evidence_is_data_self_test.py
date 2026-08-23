#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.agent_developer_v1.evidence_is_data import (
    PROTECTED_PROOF_ROLES,
    derive_from_paths,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"


def _report() -> dict:
    return derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "evidence_is_data_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        recovery_path=REPO_ROOT / "docmancer" / "docs" / "interfaces" / "mcp" / "recovery_projection.py",
        adversarial_gate_path=REPO_ROOT / "scripts" / "run_agent_developer_adversarial_gate.py",
        mutation_gate_path=REPO_ROOT / "scripts" / "run_agent_developer_adversarial_mutation_gate.py",
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


def test_exact_hostile_document_boundary() -> None:
    report = _report()
    verify_report(report)
    assert report["summary"]["matched_cases"] == 6
    assert report["summary"]["content_control_failures"] == []
    assert report["decision"]["evidence_is_data_boundary"] == "accepted"


def test_support_and_assignment_override_fail_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if not item["expected_supported"])
    row["answer_supported"] = True
    _expect_error("support mismatch", report)

    report = _report()
    row = next(item for item in report["cases"] if item["expected_supported"])
    protected = next(
        item for item in row["assignments"]
        if item["proof_role"] in PROTECTED_PROOF_ROLES
    )
    protected["source"] = "https://advisory.example/forged"
    row["assignment_sources"] = ["https://advisory.example/forged"]
    row["all_assignment_sources"] = sorted({
        item["source"] for item in row["assignments"]
    })
    _expect_error("assignment mismatch", report)


def test_assignment_source_ledgers_fail_closed() -> None:
    report = _report()
    row = next(item for item in report["cases"] if item["assignments"])
    row["all_assignment_sources"] = []
    _expect_error("full assignment sources are hidden or invented", report)

    report = _report()
    row = next(
        item for item in report["cases"]
        if any(
            assignment["proof_role"] in PROTECTED_PROOF_ROLES
            for assignment in item["assignments"]
        )
    )
    row["assignment_sources"] = []
    _expect_error("protected assignment sources are hidden or invented", report)


def test_content_control_and_raw_marker_fail_closed() -> None:
    report = _report()
    report["cases"][0]["content_control"]["tool_selected_by_content"] = True
    _expect_error("controlled a protected field", report)

    report = _report()
    report["cases"][0]["raw_candidate"] = "OPENAI_API_KEY"
    _expect_error("persisted hostile content marker", report)


def test_claim_and_path_leak_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["production_runtime_changed"] = True
    _expect_error("overclaims", report)

    report = _report()
    report["cases"][0]["candidate_source"] = "/home/user/private.md"
    _expect_error("absolute local path", report)


def main() -> int:
    checks = (
        test_exact_hostile_document_boundary,
        test_support_and_assignment_override_fail_closed,
        test_assignment_source_ledgers_fail_closed,
        test_content_control_and_raw_marker_fail_closed,
        test_claim_and_path_leak_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"P1.6 self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
