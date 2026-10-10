#!/usr/bin/env python3
"""Verify frozen Legacy facts separately from honest production query lineage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.project_context_quality.legacy_fact_acceptance import (
    FACT_METRIC, ORACLE_SCHEMA, PROTOCOL_PATH, summarize_legacy_facts,
)
from scripts.run_project_context_quality_v2_gate import load_acceptance_lock

_CONTRACT_PATH = "eval/project_context_quality/legacy_fact_acceptance_crosswalk.json"


def _contract_errors(floor: dict[str, Any]) -> list[str]:
    raw = (ROOT / _CONTRACT_PATH).read_bytes()
    contract = json.loads(raw)
    current = contract.get("current_acceptance") or {}
    historical_minimum = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))["thresholds"]["original_query_coverage_min"]
    if not (
        floor.get("schema_version") == "legacy-source-fact-acceptance-v2"
        and floor.get("acceptance_metric") == FACT_METRIC
        and floor.get("positive_case_count") == current.get("denominator") == 15
        and floor.get("contract_path") == _CONTRACT_PATH
        and floor.get("contract_sha256") == hashlib.sha256(raw).hexdigest()
        and floor.get("raw_original_query_coverage") == "telemetry_with_no_lookup_transfer"
        and contract.get("schema_version") == "legacy-original-case-fact-acceptance-crosswalk-v1"
        and current.get("schema_version") == ORACLE_SCHEMA and current.get("metric") == FACT_METRIC
        and type(floor.get("original_query_coverage_min")) is int
        and floor["original_query_coverage_min"] == current.get("minimum") == historical_minimum == 12
    ):
        return ["legacy_versioned_fact_acceptance_contract"]
    return []


def verify_legacy_lineage_floor(
    report: dict[str, Any], lock: dict[str, Any] | None = None, *, source_root: Path = ROOT,
) -> list[str]:
    lock = lock or load_acceptance_lock()
    floor = lock["legacy_lineage_floor"]
    failures = _contract_errors(floor)
    if failures:
        return failures
    summary = summarize_legacy_facts(report, source_root=source_root)
    failures.extend(summary["errors"])
    metrics = report.get("metrics") or {}
    value = metrics.get(FACT_METRIC)
    if type(value) is not int or value != summary[FACT_METRIC]:
        failures.append(f"legacy_fact_rollup: claimed {value!r}, recomputed {summary[FACT_METRIC]}")
    claimed = json.dumps(report.get("legacy_fact_acceptance"), ensure_ascii=False, sort_keys=True)
    if claimed != json.dumps(summary, ensure_ascii=False, sort_keys=True):
        failures.append("legacy_fact_receipt_rollup does not match independently verified case evidence")
    raw_original = metrics.get("original_query_covered_count")
    if type(raw_original) is not int or raw_original != summary["raw_original_query_covered_count"]:
        failures.append("legacy_raw_original_rollup does not match bound literal query credit")
    if summary[FACT_METRIC] < floor["original_query_coverage_min"]:
        failures.append(
            f"legacy_fact_floor: full frozen facts visible for {summary[FACT_METRIC]}/15 "
            f"original cases; minimum {floor['original_query_coverage_min']}/15"
        )
    for metric in floor["hard_zero_metrics"]:
        if type(metrics.get(metric)) is not int or metrics[metric] != 0:
            failures.append(f"legacy hard-safety metric {metric} must remain zero, got {metrics.get(metric)!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify source-bound frozen Legacy facts, safety and honest original-query telemetry")
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures = verify_legacy_lineage_floor(report)
    if failures:
        print("Legacy source-fact compatibility floor: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "Legacy source-fact compatibility floor: PASS; "
        f"facts={report['metrics'][FACT_METRIC]}/15; "
        f"raw original={report['metrics']['original_query_covered_count']}/15; hard safety unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
