#!/usr/bin/env python3
"""Measure current P1.5 facts and source provenance without resealing history."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from eval.agent_developer_v1.mixed_provenance import derive_from_paths, verify_report

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "p1.5-current-provenance.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure P1.5 original-question facts and explicit source provenance")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    historical = (ROOT / "results" / "mixed-evidence-provenance.json").resolve()
    if args.output.resolve() == historical:
        parser.error("current fixture evidence must not overwrite the historical P1.5 report")
    report = derive_from_paths(repo_root=REPO_ROOT, protocol_path=ROOT / "mixed_provenance_protocol.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_report(report)
    summary = report["summary"]
    print(f"P1.5 current provenance: {'PASS' if report['passed'] else 'FAIL'}; "
          f"cases={summary['passed_count']}/{summary['case_count']}; "
          f"complete_facts={summary['verified_full_fact_count']}/{summary['required_full_fact_count']}; "
          f"errors={summary['runtime_error_count']}; report={args.output}")
    for row in report["cases"]:
        assessment, observation = row["assessment"], row["observation"]
        if not assessment["passed"]:
            print(f"FAIL {row['id']}: {','.join(assessment['failed_checks'])}")
            before, after = observation.get("state_before") or {}, observation.get("state_after") or {}
            details = {
                "id": row["id"], "source_errors": assessment["source_errors"],
                "preparation_errors": assessment["preparation_errors"],
                "authority_errors": assessment["authority_errors"],
                "missing_full_fact_sources": sorted(set(assessment["required_full_fact_sources"])
                                                    - set(assessment["visible_full_fact_sources"])),
                "state_differences": [{"field": key, "before": before.get(key), "after": after.get(key)}
                                      for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)],
                "generation_before": before.get("generation"), "runtime_error": observation.get("error"),
                "output_cost": assessment["output_cost"],
            }
            print("DIAGNOSTICS " + json.dumps(details, ensure_ascii=False, sort_keys=True))
    if report["source_identities"]["runtime_error"]:
        print(f"FAIL runtime identity: {report['source_identities']['runtime_error']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
