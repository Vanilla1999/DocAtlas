#!/usr/bin/env python3
"""Measure current P1.6 delivery; preserve historical evidence unchanged."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eval.agent_developer_v1.evidence_is_data import (
    derive_from_paths, sha256_json, verify_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results" / "evidence-is-data.current.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="Compatibility flag; current observations are always saved.")
    args = parser.parse_args(argv)
    if args.output.resolve() == (ROOT / "results/evidence-is-data.json").resolve():
        raise SystemExit("The frozen historical P1.6 report cannot be overwritten.")
    derived = derive_from_paths(
        repo_root=REPO_ROOT, protocol_path=ROOT / "evidence_is_data_protocol.json",
        recovery_path=REPO_ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py",
        adversarial_gate_path=REPO_ROOT / "scripts/run_agent_developer_adversarial_gate.py",
        mutation_gate_path=REPO_ROOT / "scripts/run_agent_developer_adversarial_mutation_gate.py",
    )
    # Save failures before verification; no hostile document text is persisted.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(derived, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = True
    try:
        verify_report(derived)
    except ValueError as exc:
        passed = False
        print("VERIFICATION " + json.dumps({
            "error_type": type(exc).__name__,
            "message_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
        }, sort_keys=True))
    summary = derived["summary"]
    print(
        f"P1.6 current public delivery: {'PASS' if passed else 'FAIL'}; "
        f"cases={summary['passed_cases']}/{summary['case_count']}; "
        f"full_facts={summary['full_fact_cases']}/1; errors={summary['runtime_errors']}; "
        f"sha256={sha256_json(derived)}; report={args.output}"
    )
    for row in derived["cases"]:
        result = row["result"]
        print(("PASS " if result["passed"] else "FAIL ") + row["id"] + ": " + ",".join(
            name for name, value in result["checks"].items() if not value
        ))
        print("DIAGNOSTICS " + json.dumps({
            "id": row["id"], "checks": result["checks"], "integrity_errors": result["integrity_errors"],
            "authority_errors": result["authority_errors"], "delivery_errors": result["delivery_errors"],
            "source_count": result["source_count"], "public_utf8_bytes": result["public_utf8_bytes"],
            "reported_estimated_tokens": result["reported_estimated_tokens"], "runtime_error": row["error"],
        }, sort_keys=True))
        if not result["passed"]:
            observed = row["observed"]["capture"]
            print("OBSERVED " + json.dumps({
                "id": row["id"], "public_payload": observed.get("public_payload"),
                "projection_calls": observed.get("projection_calls"),
                "validation_calls": observed.get("validation_calls"),
                "dispatch_calls": observed.get("dispatch_calls"),
                "facade_calls": observed.get("facade_calls"),
            }, sort_keys=True))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
