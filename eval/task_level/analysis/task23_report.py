from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

from eval.task_level.analysis.task23_decision import apply_protocol_amendment, evaluate_predeclared_rule


def _metric(row: dict[str, Any], name: str) -> Any:
    metrics = row.get("metrics")
    return metrics.get(name) if isinstance(metrics, dict) else None


def _median(values: list[Any]) -> float | int | None:
    numbers = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return median(numbers) if numbers else None


def build_task23_report(
    rows: list[dict[str, Any]],
    *,
    protocol: dict[str, Any],
    amendment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective = apply_protocol_amendment(protocol, amendment) if amendment else protocol
    task_ids = [task["task_id"] for task in effective["tasks"]]
    conditions = list(effective["conditions"])
    repeats = int(effective["repeats_per_task_condition"])
    expected_cells = {(task_id, condition, repeat) for task_id in task_ids for condition in conditions for repeat in range(repeats)}
    actual_cells = [
        (row.get("task_id"), row.get("condition_id"), row.get("repeat"))
        for row in rows
        if row.get("task_id") in task_ids and row.get("condition_id") in conditions
    ]
    counts = Counter(actual_cells)
    missing = sorted(expected_cells - set(actual_cells))
    duplicates = sorted(cell for cell, count in counts.items() if count != 1)
    selected_rows = [
        row for row in rows
        if row.get("task_id") in task_ids and row.get("condition_id") in conditions
    ]
    integrity_ok = not missing and not duplicates and len(selected_rows) == len(expected_cells)

    decision_rows = []
    for row in selected_rows:
        normalized = dict(row)
        normalized["total_tokens"] = _metric(row, "total_tokens")
        normalized["wall_time_seconds"] = _metric(row, "wall_time_seconds")
        decision_rows.append(normalized)
    decision = evaluate_predeclared_rule(decision_rows, protocol=effective)
    if not integrity_ok:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).append("incomplete_full_condition_matrix")

    condition_summaries: dict[str, Any] = {}
    failure_taxonomy: dict[str, Any] = {}
    for condition in conditions:
        condition_rows = [row for row in selected_rows if row.get("condition_id") == condition]
        condition_summaries[condition] = {
            "runs": len(condition_rows),
            "resolved": sum(bool(row.get("resolved")) for row in condition_rows),
            "resolved_rate": mean(bool(row.get("resolved")) for row in condition_rows) if condition_rows else None,
            "median_total_tokens": _median([_metric(row, "total_tokens") for row in condition_rows]),
            "median_wall_time_seconds": _median([_metric(row, "wall_time_seconds") for row in condition_rows]),
            "median_tool_output_tokens_estimate": _median([_metric(row, "tool_output_tokens_estimate") for row in condition_rows]),
            "median_condition_setup_wall_time_seconds": _median([_metric(row, "condition_setup_wall_time_seconds") for row in condition_rows]),
            "median_required_evidence_recall": _median([_metric(row, "required_evidence_recall") for row in condition_rows]),
            "median_first_required_evidence_rank": _median([_metric(row, "first_required_evidence_rank") for row in condition_rows]),
            "median_audited_external_context_tokens": _median([_metric(row, "audited_external_context_tokens") for row in condition_rows]),
            "policy_violations": sum(not bool(row.get("policy_clean")) for row in condition_rows),
        }
        failure_taxonomy[condition] = dict(sorted(Counter(
            str(row.get("status") or "unknown")
            for row in condition_rows
            if not row.get("resolved")
        ).items()))

    return {
        "schema_version": "task23-report-1",
        "protocol_id": effective.get("protocol_id"),
        "amendment_id": effective.get("amendment_id"),
        "artifact_integrity": {
            "ok": integrity_ok,
            "expected_runs": len(expected_cells),
            "actual_runs": len(selected_rows),
            "missing_cells": [list(cell) for cell in missing],
            "duplicate_cells": [list(cell) for cell in duplicates],
        },
        "conditions": condition_summaries,
        "failure_taxonomy": failure_taxonomy,
        "decision": decision,
        "scientific_limitation": amendment.get("scientific_limitation") if amendment else None,
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen Task 23 decision report")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--amendment", type=Path)
    args = parser.parse_args()
    report = build_task23_report(
        _load_jsonl(args.run_dir / "runs.jsonl"),
        protocol=_load_json(args.protocol),
        amendment=_load_json(args.amendment) if args.amendment else None,
    )
    output = args.run_dir / "task23_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
