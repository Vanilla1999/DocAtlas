#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from eval.agent_developer_v1.p1_closure import (
    CURRENT_IDS, REQUIRED_GATES, derive_from_paths, load_json, sha256_json, verify_closure,
)
from scripts.run_p1_agent_truth_closure_gate import ROOT, REPO_ROOT, input_arguments, report_inputs

_CONTEXT: dict = {}
_BASELINE: dict | None = None


def _report() -> dict:
    global _BASELINE
    if _BASELINE is None:
        _BASELINE = derive_from_paths(**_CONTEXT)
        verify_closure(_BASELINE, **_CONTEXT, require_quality=False)
    return deepcopy(_BASELINE)


def _expect_error(fragment: str, payload: dict, *, context: dict | None = None) -> None:
    # Integrity mode prevents a pre-existing quality failure from killing a
    # forged-output mutant. The exact mutation must fail recomputation.
    try:
        verify_closure(payload, **(context or _CONTEXT), require_quality=False)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def _changed_input(name: str, change) -> None:
    baseline = _report()
    original = next(row for row in baseline["scorecard"] if row["id"] == name.replace("p1_", "P1."))
    assert original["integrity_valid"] is True, "mutation needs a valid observed report baseline"
    source = load_json(_CONTEXT["current_paths"][name])
    change(source)
    with TemporaryDirectory(prefix="docatlas-closure-control-") as temporary:
        path = Path(temporary) / (name + ".json")
        path.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
        paths = {**_CONTEXT["current_paths"], name: path}
        context = {**_CONTEXT, "current_paths": paths}
        changed = derive_from_paths(**context)
        verify_closure(changed, **context, require_quality=False)
        row = next(row for row in changed["scorecard"] if row["id"] == original["id"])
        assert row["integrity_valid"] is False and row["quality_passed"] is False
        assert row["error"]["stage"] == name + "_current_verifier"
        assert changed["passed"] is False
        # An unchanged green-looking closure cannot describe the mutated input.
        _expect_error("differs from current", baseline, context=context)


def test_exact_non_positive_closure() -> None:
    report = _report()
    assert report["passed"] is all(value is True for value in report["checks"].values())
    assert report["execution_status"] == ("PASS" if report["passed"] else "FAIL")
    assert report["outcome"] == "AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN"
    assert report["product_maturity"] == "Beta"
    assert [row["id"] for row in report["scorecard"]] == [
        "P1.1", "P1.2", "P1.3", "P1.4", "P1.5", "P1.6",
    ]
    assert all(row["execution_status"] == "HISTORICAL_CONTEXT" for row in report["scorecard"][:3])
    assert report["scorecard"][0]["facts"]["current_installed_transport_proven"] is False
    assert report["checks"]["historical_archive_guards"] is True
    assert report["checks"]["installed_harness_identities"] is True
    assert all(row["integrity_valid"] is True for row in report["scorecard"][3:])
    assert report["checks"]["current_runtime_consistency"] is True
    # A controlled failed step creates a honest failing baseline even after
    # all product gates eventually turn green; that failure cannot be hidden.
    outcomes = deepcopy(_CONTEXT["gate_outcomes"])
    healthy = next(name for name in REQUIRED_GATES if outcomes["outcomes"].get(name) == "success")
    outcomes["outcomes"][healthy] = "failure"
    context = {**_CONTEXT, "gate_outcomes": outcomes}
    failed = derive_from_paths(**context)
    verify_closure(failed, **context, require_quality=False)
    assert failed["passed"] is False
    forged = deepcopy(failed)
    forged["passed"], forged["execution_status"] = True, "PASS"
    _expect_error("differs from current", forged, context=context)
    try:
        verify_closure(failed, **context)
    except ValueError as exc:
        assert "current closure failed" in str(exc)
    else:
        raise AssertionError("quality mode accepted a failed required gate")


def test_autonomous_and_stable_overclaim_fail_closed() -> None:
    for key in ("autonomous_agent_truth_proven", "stable_claim_allowed",
                "installed_client_delivery_proven", "p1_work_items_complete"):
        report = _report()
        report["claim_boundary"][key] = True
        _expect_error("overclaims " + key, report)
    for index, name in enumerate(CURRENT_IDS, start=3):
        baseline = _report()
        assert baseline["scorecard"][index]["integrity_valid"] is True
        for field, value in (("summary", {}), ("case_checks", [])):
            changed = deepcopy(baseline)
            changed["scorecard"][index][field] = value
            _expect_error("differs from current", changed)
        _changed_input(name, lambda value: value.update(code_commit="0" * 40))
        _changed_input(name, lambda value: value["summary"].clear())
        historical_protocol = {
            "p1_4": "paraphrase-proofability-report-v1",
            "p1_5": "mixed-evidence-provenance-report-v1",
            "p1_6": "evidence-is-data-report-v1",
        }[name]
        _changed_input(name, lambda value, protocol=historical_protocol: value.update(protocol=protocol, schema_version=1))


def test_missing_work_item_and_runtime_change_fail_closed() -> None:
    report = _report()
    report["scorecard"].pop()
    _expect_error("incomplete or reordered", report)
    report = _report()
    report["decision"]["accepted_production_changes"] = ["scope_inference"]
    _expect_error("accepted an unproven production change", report)
    for name in CURRENT_IDS:
        runtime_key = "public_delivery_runtime" if name == "p1_6" else "runtime"
        def forge_runtime(value, key=runtime_key):
            runtime = value["source_identities"][key]
            runtime["files"][0]["sha256"] = "0" * 64
            runtime["sha256"] = sha256_json(runtime["files"])
        _changed_input(name, forge_runtime)
    baseline = _report()
    assert baseline["checks"]["current_report_inventory"] is True
    paths = dict(_CONTEXT["current_paths"])
    del paths["p1_4"]
    context = {**_CONTEXT, "current_paths": paths}
    missing = derive_from_paths(**context)
    verify_closure(missing, **context, require_quality=False)
    assert missing["checks"]["current_report_inventory"] is False and missing["passed"] is False
    _expect_error("differs from current", baseline, context=context)
    assert baseline["checks"]["required_gate_inventory"] is True
    assert baseline["checks"]["required_gate_checkout"] is True
    healthy = next(name for name, state in _CONTEXT["gate_outcomes"]["outcomes"].items() if state == "success")
    for state in (None, "skipped", "failure", "cancelled", {}, "invented"):
        outcomes = deepcopy(_CONTEXT["gate_outcomes"])
        if state is None:
            del outcomes["outcomes"][healthy]
        else:
            outcomes["outcomes"][healthy] = state
        context = {**_CONTEXT, "gate_outcomes": outcomes}
        changed = derive_from_paths(**context)
        verify_closure(changed, **context, require_quality=False)
        row = next(row for row in changed["required_gates"]["outcomes"] if row["id"] == healthy)
        assert row["passed"] is False and changed["passed"] is False
        _expect_error("differs from current", baseline, context=context)

    receipt = deepcopy(_CONTEXT["gate_outcomes"])
    receipt["code_commit"] = "0" * 40
    context = {**_CONTEXT, "gate_outcomes": receipt}
    changed = derive_from_paths(**context)
    verify_closure(changed, **context, require_quality=False)
    assert changed["checks"]["required_gate_checkout"] is False and changed["passed"] is False
    _expect_error("differs from current", baseline, context=context)


def test_maturity_and_path_leak_fail_closed() -> None:
    report = _report()
    report["product_maturity"] = "Stable"
    _expect_error("improperly promotes", report)
    report = _report()
    report["scorecard"][0]["decision"] = "read /home/user/private"
    _expect_error("absolute local path", report)
    report = _report()
    report["code_commit"] = "0" * 40
    _expect_error("differs from current", report)


def main(argv: list[str] | None = None) -> int:
    global _CONTEXT, _BASELINE
    parser = argparse.ArgumentParser(description="Verify current closure integrity controls")
    input_arguments(parser)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    paths, outcomes = report_inputs(args)
    _CONTEXT = dict(repo_root=REPO_ROOT, root=ROOT, current_paths=paths, gate_outcomes=outcomes)
    _BASELINE = None
    try:
        baseline = _report()
        required_input_checks = (
            "historical_archive_guards", "installed_harness_identities",
            "current_report_inventory", "current_report_integrity", "current_runtime_consistency",
            "required_gate_checkout", "required_gate_inventory",
        )
        missing = [name for name in required_input_checks if baseline["checks"][name] is not True]
        if missing:
            print("P1 closure self-test: FAIL; current input proof unavailable: " + ", ".join(missing))
            print("Use the three current runner outputs and --gates from the same closure workflow checkout.")
            return 1
    except Exception as exc:
        print(f"P1 closure self-test: FAIL; input error ({type(exc).__name__}: {exc})")
        return 1
    checks = (
        test_exact_non_positive_closure,
        test_autonomous_and_stable_overclaim_fail_closed,
        test_missing_work_item_and_runtime_change_fail_closed,
        test_maturity_and_path_leak_fail_closed,
    )
    for check in checks:
        try:
            check()
        except Exception as exc:
            print(f"FAIL: {check.__name__} ({type(exc).__name__}: {exc})")
            return 1
        print(f"PASS: {check.__name__}")
    if args.report:
        try:
            verify_closure(load_json(args.report), **_CONTEXT, require_quality=False)
        except Exception as exc:
            print(f"P1 closure report integrity: FAIL ({type(exc).__name__}: {exc})")
            return 1
        print("PASS: current closure report integrity (quality verdict unchanged)")
    print(f"P1 closure self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
