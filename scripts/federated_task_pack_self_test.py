#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.product_truth_v2.federated_task_pack import (
    build_report,
    load_json,
    validate_manifest,
    verify_report,
)


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
    duplicate["repositories"][1]["tasks"][0]["fix_commit"] = duplicate["repositories"][0]["tasks"][0]["fix_commit"]
    expect_error("duplicate historical fix commit", lambda: validate_manifest(duplicate))

    private_repo = next(repo for repo in manifest["repositories"] if repo["visibility"] == "private")
    private_index = manifest["repositories"].index(private_repo)
    private_leak = copy.deepcopy(manifest)
    private_leak["repositories"][private_index]["tasks"][0]["source_path"] = "private/source.py"
    expect_error("private task metadata exceeds", lambda: validate_manifest(private_leak))

    stale_repository = copy.deepcopy(manifest)
    stale_repository["repositories"][1].update(
        id="smart_glass",
        repository="Vanilla1999/smart_glass",
    )
    expect_error("repository identity/order drift", lambda: validate_manifest(stale_repository))

    premature_valid = copy.deepcopy(manifest)
    premature_valid["repositories"][0]["tasks"][0]["valid"] = True
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

    oracle_claim = copy.deepcopy(manifest)
    oracle_claim["claim_boundary"]["real_model_oracle_authorized"] = True
    expect_error("claim boundary drift", lambda: validate_manifest(oracle_claim))

    stable_claim = copy.deepcopy(manifest)
    stable_claim["claim_boundary"]["product_maturity"] = "Stable"
    expect_error("claim boundary drift", lambda: validate_manifest(stable_claim))

    report_claim = copy.deepcopy(report)
    report_claim["decision"]["product_truth_proven"] = True
    expect_error("overclaims product_truth_proven", lambda: verify_report(report_claim, manifest=manifest))

    isolation_claim = copy.deepcopy(report)
    isolation_claim["isolation"]["network_access_forbidden"] = False
    expect_error("isolation contract drift", lambda: verify_report(isolation_claim, manifest=manifest))

    report_digest = copy.deepcopy(report)
    report_digest["manifest_sha256"] = "0" * 64
    expect_error("manifest digest mismatch", lambda: verify_report(report_digest, manifest=manifest))

    print("Federated Product Truth candidate-pack self-test: PASS (13 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
