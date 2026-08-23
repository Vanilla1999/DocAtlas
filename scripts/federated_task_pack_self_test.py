#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v2.federated_task_pack import (
    build_report,
    load_json,
    validate_manifest,
    verify_report,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval" / "product_truth_v2" / "federated-task-pack.json"


def expect_error(fragment: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def main() -> int:
    manifest = load_json(MANIFEST)
    validate_manifest(manifest)
    report = build_report(manifest)
    verify_report(report, manifest=manifest)

    short_pack = copy.deepcopy(manifest)
    short_pack["repositories"][0]["tasks"].pop()
    expect_error("exactly eight candidates", lambda: validate_manifest(short_pack))

    duplicate = copy.deepcopy(manifest)
    duplicate["repositories"][1]["tasks"][0]["fix_commit"] = (
        duplicate["repositories"][0]["tasks"][0]["fix_commit"]
    )
    expect_error("duplicate historical fix commit", lambda: validate_manifest(duplicate))

    private_leak = copy.deepcopy(manifest)
    private_leak["repositories"][1]["tasks"][0]["source_path"] = "private/source.py"
    expect_error("private task metadata exceeds", lambda: validate_manifest(private_leak))

    premature_valid = copy.deepcopy(manifest)
    premature_valid["repositories"][2]["tasks"][0]["valid"] = True
    expect_error("marked valid before controls", lambda: validate_manifest(premature_valid))

    attestation_forgery = copy.deepcopy(manifest)
    attestation_forgery["repositories"][0]["worker_attestation"] = "green"
    expect_error("attestation must remain pending", lambda: validate_manifest(attestation_forgery))

    bad_sha = copy.deepcopy(manifest)
    bad_sha["repositories"][0]["tasks"][0]["fix_commit"] = "abc123"
    expect_error("invalid full Git SHA", lambda: validate_manifest(bad_sha))

    canary_claim = copy.deepcopy(manifest)
    canary_claim["claim_boundary"]["canary_authorized"] = True
    expect_error("claim boundary drift", lambda: validate_manifest(canary_claim))

    stable_claim = copy.deepcopy(manifest)
    stable_claim["claim_boundary"]["product_maturity"] = "Stable"
    expect_error("claim boundary drift", lambda: validate_manifest(stable_claim))

    report_claim = copy.deepcopy(report)
    report_claim["decision"]["product_truth_proven"] = True
    expect_error(
        "overclaims product_truth_proven",
        lambda: verify_report(report_claim, manifest=manifest),
    )

    report_digest = copy.deepcopy(report)
    report_digest["manifest_sha256"] = "0" * 64
    expect_error(
        "manifest digest mismatch",
        lambda: verify_report(report_digest, manifest=manifest),
    )

    print("Federated Product Truth candidate-pack self-test: PASS (10 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
