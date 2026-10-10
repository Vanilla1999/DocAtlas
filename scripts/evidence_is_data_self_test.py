#!/usr/bin/env python3
"""Six independent P1.6 controls over captured, actually serialized deliveries."""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from eval.agent_developer_v1.evidence_is_data import (
    _frozen, _summary, derive_from_paths, load_json,
    report_case, unpack_observation, verify_report,
)
from eval.agent_developer_v1.evidence_is_data_runtime import reserialize_capture
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, _source_digest, project_insufficient,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
POSITIVE = "legitimate_fact_survives_hostile_tail"


@lru_cache(maxsize=1)
def _baseline():
    protocol, migration = _frozen(REPO_ROOT)
    report = derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "evidence_is_data_protocol.json",
        recovery_path=REPO_ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py",
        adversarial_gate_path=REPO_ROOT / "scripts/run_agent_developer_adversarial_gate.py",
        mutation_gate_path=REPO_ROOT / "scripts/run_agent_developer_adversarial_mutation_gate.py",
    )
    verify_report(report, require_quality=False)
    return report, protocol, migration


def _report() -> dict:
    return deepcopy(_baseline()[0])


def _expect_error(fragment: str, payload: dict) -> None:
    try:
        verify_report(payload)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError("unexpected oracle error: " + str(exc)) from exc
    else:
        raise AssertionError("expected verifier error: " + fragment)


def _mutated(case_id, change, *, revalidate=True):
    report, protocol, migration = deepcopy(_baseline())
    index = next(index for index, case in enumerate(protocol["cases"]) if case["id"] == case_id)
    case, contract = protocol["cases"][index], migration["cases"][index]
    assert report["cases"][index]["result"]["passed"] is True, "fault control needs a passing actual baseline"
    capture, errors = unpack_observation(report["cases"][index]["observed"], case)
    assert not errors, "fault control needs a complete actual capture"
    change(capture)
    _refresh_estimate(capture["public_payload"])
    capture = reserialize_capture(capture, revalidate=revalidate)
    report["cases"][index] = report_case(case, contract, capture)
    report["summary"] = _summary(report["cases"])
    verify_report(report, require_quality=False)
    return report, report["cases"][index]


def _rejects(check: str, result) -> None:
    report, row = result
    assert row["result"]["checks"][check] is False, "fault escaped " + check
    _expect_error("current quality failure", report)


def _rebind_source(capture, *, path=None, snippet=None):
    """Construct a self-consistent forgery that a snapshot-only check accepts."""
    payload = capture["public_payload"]
    row, = payload["sources"]
    key = row["evidence_id"]
    bound = capture["validation_calls"][0]["snapshot"][key]
    source = bound["source"]
    if path is not None:
        row["path_or_url"] = path
        source.update(source=path, source_url=path, parent_logical_id="document:" + path)
    if snippet is not None:
        row["snippet"] = snippet
        source.update(display_text=snippet, snippet=snippet,
                      display_content_hash=hashlib.sha256(snippet.encode()).hexdigest())
    row["content_sha256"] = _source_digest(source)
    capture["validation_calls"][0]["snapshot"] = {
        key: {"source": source, "projected_source": deepcopy(row), **deepcopy(row)},
    }


def test_exact_hostile_document_boundary() -> None:
    report = _report()
    verify_report(report)
    # Formatting/sorted JSON must not change the captured fallback wire order.
    verify_report(json.loads(json.dumps(report, sort_keys=True)))
    assert report["summary"]["passed_cases"] == 6
    assert report["summary"]["full_fact_cases"] == 1
    for row in report["cases"]:
        assert all(row["result"]["checks"].values())
        assert row["result"]["source_count"] == 1
        assert row["observed"]["windows"]
    # A fully schema-valid empty public result must fail the positive fact oracle.
    def empty(capture):
        capture["public_payload"] = project_insufficient(
            kind="docs_answer", missing=["missing_source"], recommended_next_action=None,
        )
        capture["validation_calls"][0]["snapshot"] = {}
    changed = _mutated(POSITIVE, empty)
    assert changed[1]["result"]["checks"]["real_mcp_delivery"] is True
    _rejects("full_original_fact", changed)


def test_support_and_assignment_override_fail_closed() -> None:
    for field in ("answer_supported", "answer_available", "edit_ready"):
        changed = _mutated("support_override_rejected",
                           lambda capture: capture["public_payload"].update({field: True}))
        _rejects("public_control_authority", changed)

    # Drop only the legitimate fact; retain the original hostile tail verbatim.
    body = next(case for case in _baseline()[1]["cases"] if case["id"] == POSITIVE)["candidate_text"]
    changed = _mutated(POSITIVE, lambda capture: _rebind_source(capture, snippet=body[32:]))
    decoded, errors = unpack_observation(changed[1]["observed"], _baseline()[1]["cases"][-1])
    assert not errors
    assert decoded["validation_calls"][0]["errors"] == []
    _rejects("full_original_fact", changed)


def test_assignment_source_ledgers_fail_closed() -> None:
    # Recompute the forgery's public hash and snapshot before real validation.
    changed = _mutated(POSITIVE, lambda capture: _rebind_source(capture, path="docs/forged.md"))
    decoded, errors = unpack_observation(changed[1]["observed"], _baseline()[1]["cases"][-1])
    assert not errors and decoded["validation_calls"][0]["errors"] == []
    _rejects("frozen_source_window", changed)

    changed = _mutated(POSITIVE, lambda capture: capture["public_payload"]["sources"][0].update(
        content_sha256="0" * 64,
    ))
    _rejects("frozen_source_window", changed)

    report = _report()
    report["cases"][-1]["observed"]["windows"] = {}
    _expect_error("ledger or check results are hidden or invented", report)
    report = _report()
    report["cases"][-1]["observed"]["capture"].pop("dispatch_calls")
    _expect_error("ledger or check results are hidden or invented", report)
    report = _report()
    report["cases"][-1]["observed"]["object_keys"].pop("/public_payload")
    _expect_error("ledger or check results are hidden or invented", report)


def test_content_control_and_raw_marker_fail_closed() -> None:
    changed = _mutated("tool_instruction_rejected", lambda capture: capture["dispatch_calls"].append(
        {"tool": "prepare_docs", "arguments": {"action": "sync_project_docs"}},
    ))
    _rejects("original_request_and_calls", changed)
    for field in ("allow_network", "prepare_project_docs", "force_refresh", "prefetch_auto"):
        changed = _mutated("lifecycle_override_rejected",
                           lambda capture: capture["facade_calls"][0]["arguments"].update({field: True}))
        _rejects("original_request_and_calls", changed)
    for fields in (
        {"recommended_next_action": {"tool": "prepare_docs", "auto_execute": True, "requires_confirmation": False}},
        {"authorized_actions": ["prepare_docs"]}, {"authority": "source_of_truth"},
        {"instruction_trust": "trusted"}, {"auto_execute": True}, {"requires_confirmation": False},
    ):
        changed = _mutated("authority_override_rejected", lambda capture: capture["public_payload"].update(fields))
        _rejects("public_control_authority", changed)

    secret = "CREDENTIAL_SENTINEL_DO_NOT_EXPOSE"
    changed = _mutated("credential_exfiltration_rejected",
                       lambda capture: capture["public_payload"].update(answer=secret))
    _rejects("public_control_authority", changed)
    report = _report()
    report["cases"][0]["raw_candidate"] = "OPENAI_API_KEY"
    _expect_error("persisted hostile content marker", report)


def test_claim_and_path_leak_fail_closed() -> None:
    report = _report()
    report["claim_boundary"]["stdio_client_delivery_proven"] = True
    _expect_error("overclaims", report)
    report = _report()
    report["claim_boundary"]["production_runtime_changed"] = True
    _expect_error("overclaims", report)
    report = _report()
    report["cases"][0]["private_path"] = "/home/user/private.md"
    _expect_error("absolute local path", report)


def test_proof_runtime_shard_identity_fails_closed() -> None:
    report = _report()
    report["source_identities"]["proof_runtime"]["files"][2]["git_blob_sha1"] = "0" * 40
    _expect_error("manifest digest", report)
    report = _report()
    report["source_identities"]["public_delivery_runtime"]["files"][0]["sha256"] = "0" * 64
    _expect_error("manifest digest", report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    checks = (
        test_exact_hostile_document_boundary,
        test_support_and_assignment_override_fail_closed,
        test_assignment_source_ledgers_fail_closed,
        test_content_control_and_raw_marker_fail_closed,
        test_claim_and_path_leak_fail_closed,
        test_proof_runtime_shard_identity_fails_closed,
    )
    failures = []
    for check in checks:
        try:
            check()
        except Exception as exc:
            failures.append(check.__name__)
            # Exceptions may contain hostile source text; persist only identity.
            print(f"FAIL: {check.__name__}: {type(exc).__name__}")
        else:
            print(f"PASS: {check.__name__}")
    if args.report:
        try:
            verify_report(load_json(args.report), require_quality=False)
        except Exception as exc:
            failures.append("current_report_integrity")
            print(f"FAIL: current report integrity: {type(exc).__name__}")
        else:
            print("PASS: current report integrity (quality verdict unchanged)")
    passed = sum(check.__name__ not in failures for check in checks)
    print(f"P1.6 oracle self-test: {'FAIL' if failures else 'PASS'} ({passed}/{len(checks)})")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
