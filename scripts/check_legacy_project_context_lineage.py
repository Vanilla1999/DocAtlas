#!/usr/bin/env python3
"""Keep frozen Legacy safety and original-query lineage floors during V2 migration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_project_context_quality_v2_gate import load_acceptance_lock


def verify_legacy_lineage_floor(report: dict[str, Any], lock: dict[str, Any] | None = None) -> list[str]:
    lock = lock or load_acceptance_lock()
    failures: list[str] = []
    if report.get("lane") != "legacy" or report.get("input_mode") != "question_with_lookups":
        return ["legacy lineage floor requires the frozen legacy live lane"]
    metrics = report.get("metrics") or {}
    floor = lock["legacy_lineage_floor"]
    value = metrics.get("original_query_covered_count")
    if type(value) is not int or value < floor["original_query_coverage_min"]:
        failures.append(
            f"original query coverage below frozen floor: {value!r} < {floor['original_query_coverage_min']}"
        )
    for metric in floor["hard_zero_metrics"]:
        if metrics.get(metric) != 0:
            failures.append(f"legacy hard-safety metric {metric} must remain zero, got {metrics.get(metric)!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Legacy lineage/safety floors without using path-specific quality as acceptance")
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures = verify_legacy_lineage_floor(report)
    if failures:
        print("Legacy lineage compatibility floor: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "Legacy lineage compatibility floor: PASS; "
        f"original={report['metrics']['original_query_covered_count']}/15; hard safety unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
