#!/usr/bin/env python3
"""Blocking acceptance wrapper around the independent V2 quality evaluator."""
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

from eval.project_context_quality_v2_protocol import run_live

LOCK_PATH = ROOT / "eval/project_context_quality_v2/acceptance.lock.json"
V2_PROTOCOL_LOCK = ROOT / "eval/project_context_quality_v2/protocol.lock.json"
LEGACY_PROTOCOL_LOCK = ROOT / "eval/project_context_quality/protocol.lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fraction(value: Any, *, name: str) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not a fraction")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    if type(numerator) is not int or type(denominator) is not int or numerator < 0 or denominator < 0:
        raise ValueError(f"{name} has invalid fraction values")
    return numerator, denominator


def load_acceptance_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "project-context-quality-v2-acceptance-v1":
        raise ValueError("unsupported V2 acceptance lock")
    expected = {
        "v2_protocol_lock_sha256": _sha256(V2_PROTOCOL_LOCK),
        "legacy_protocol_lock_sha256": _sha256(LEGACY_PROTOCOL_LOCK),
    }
    for key, digest in expected.items():
        if lock.get(key) != digest:
            raise ValueError(f"{key} does not bind the current frozen protocol")
    return lock


def verify_v2_acceptance(report: dict[str, Any], lock: dict[str, Any] | None = None) -> list[str]:
    lock = lock or load_acceptance_lock()
    failures: list[str] = []
    if report.get("schema_version") != "project-context-quality-v2-result-2":
        return ["unexpected V2 report schema"]
    if report.get("run_mode") != "live_self_host":
        failures.append("V2 acceptance requires live_self_host mode")
    validation = report.get("validation") or {}
    if validation.get("case_count") != 25:
        failures.append("V2 acceptance requires the complete 25-case frozen corpus")
    lanes = report.get("lanes") or {}
    for lane, thresholds in lock["lanes"].items():
        metrics = (lanes.get(lane) or {}).get("metrics") or {}
        for metric, threshold in thresholds.items():
            try:
                numerator, denominator = _fraction(metrics.get(metric), name=f"{lane}.{metric}")
            except ValueError as exc:
                failures.append(str(exc))
                continue
            if denominator != threshold["denominator"]:
                failures.append(
                    f"{lane}.{metric} denominator changed: {denominator} != {threshold['denominator']}"
                )
                continue
            if "minimum" in threshold and numerator < threshold["minimum"]:
                failures.append(
                    f"{lane}.{metric} below acceptance: {numerator}/{denominator} < "
                    f"{threshold['minimum']}/{denominator}"
                )
            if "maximum" in threshold and numerator > threshold["maximum"]:
                failures.append(
                    f"{lane}.{metric} above acceptance: {numerator}/{denominator} > "
                    f"{threshold['maximum']}/{denominator}"
                )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or verify blocking project-context V2 acceptance")
    parser.add_argument("--report", type=Path, help="verify an existing V2 live report instead of executing retrieval")
    parser.add_argument("--output", type=Path, help="write the live report for artifact retention")
    args = parser.parse_args(argv)
    report = (
        json.loads(args.report.read_text(encoding="utf-8"))
        if args.report else run_live()
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = verify_v2_acceptance(report)
    if failures:
        print("V2 project-context acceptance: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    natural = report["lanes"]["natural"]["metrics"]
    exposed = report["lanes"]["exposed_paraphrases"]["metrics"]
    print(
        "V2 project-context acceptance: PASS; "
        f"natural={natural['semantic_usefulness']['numerator']}/15; "
        f"paraphrases={exposed['semantic_usefulness']['numerator']}/5; "
        "false_full=0; safety/budgets=25/25"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
