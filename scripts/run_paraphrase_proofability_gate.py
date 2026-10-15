#!/usr/bin/env python3
"""Measure current P1.4 fixture reads without resealing historical evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from eval.agent_developer_v1.paraphrase_robustness import derive_from_paths, verify_report

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "p1.4-current-retrieval.json"


def failure_diagnostics(row: dict) -> dict:
    """Bounded console view of the full saved observation; no verdict changes."""
    observation = row["observation"]
    assessment = row["assessment"]
    before = observation.get("state_before") or {}
    after = observation.get("state_after") or {}
    expected_documents = {row["candidate_source"]: row["candidate_text_sha256"]}
    differences = []
    for field in ("generation", "store_sha256", "catalog_sha256", "document_sha256"):
        if before.get(field) != after.get(field):
            differences.append({"field": field, "before": before.get(field), "after": after.get(field)})
    state_types = {
        field: type(before.get(field)).__name__
        for field in ("generation", "store_sha256", "catalog_sha256", "document_sha256")
    }
    return {
        "id": row["id"],
        "source_errors": assessment["source_errors"][:12],
        "authority_errors": assessment["authority_errors"][:12],
        "read_only": {
            "state_equal": before == after,
            "before_types": state_types,
            "generation_before": before.get("generation"),
            "generation_after": after.get("generation"),
            "expected_document_sha256": expected_documents,
            "document_sha256_before": before.get("document_sha256"),
            "differences": differences,
        },
        "output_cost": assessment["output_cost"],
        "pipeline_diagnostics": observation.get("pipeline_diagnostics"),
        "service_requests": observation.get("service_requests"),
        "preparation": observation.get("preparation"),
        "runtime_error": observation.get("error"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure P1.4 original-question source facts and provenance")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    historical = (ROOT / "results" / "paraphrase-proofability.json").resolve()
    if args.output.resolve() == historical:
        parser.error("current fixture evidence must not overwrite the historical P1.4 report")
    report = derive_from_paths(repo_root=REPO_ROOT, protocol_path=ROOT / "paraphrase_protocol.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve every observed row before verifying or failing the current gate.
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_report(report)
    summary = report["summary"]
    print(f"P1.4 current retrieval: {'PASS' if report['passed'] else 'FAIL'}; "
          f"cases={summary['passed_count']}/{summary['case_count']}; "
          f"discovery={summary['required_discovery_passed']}/{summary['required_discovery']}; "
          f"complete_fact={summary['required_complete_fact_passed']}/{summary['required_complete_fact']}; "
          f"errors={summary['runtime_error_count']}; report={args.output}")
    for row in report["cases"]:
        diagnostics = failure_diagnostics(row)
        print("READ_STATE " + json.dumps({
            "id": row["id"],
            "read_only_check": row["assessment"]["checks"]["read_only"],
            "state_equal": diagnostics["read_only"]["state_equal"],
            "changed_fields": [item["field"] for item in diagnostics["read_only"]["differences"]],
        }, sort_keys=True))
        if not row["assessment"]["passed"]:
            print(f"FAIL {row['id']}: {','.join(row['assessment']['failed_checks'])}")
            print("DIAGNOSTICS " + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if report["source_identities"]["runtime_error"]:
        print(f"FAIL runtime identity: {report['source_identities']['runtime_error']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
