from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

from eval.task_level.analysis.task23_decision import apply_protocol_amendment, evaluate_predeclared_rule, validate_protocol_amendment_artifacts
from eval.task_level.execution import is_infrastructure_failure


def _metric(row: dict[str, Any], name: str) -> Any:
    metrics = row.get("metrics")
    return metrics.get(name) if isinstance(metrics, dict) else None


def _median(values: list[Any]) -> float | int | None:
    numbers = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return median(numbers) if numbers else None


def _failure_reason(row: dict[str, Any]) -> str:
    if is_infrastructure_failure(row):
        status = str(row.get("status") or "")
        return status if status in {"runner_unavailable", "runner_failed", "condition_setup_failed", "timeout"} else "runner_output_missing"
    if not row.get("policy_clean"):
        return "policy_violation"
    if not row.get("compile_success"):
        return "compile_failed"
    if not row.get("public_tests_passed"):
        return "public_tests_failed"
    if not row.get("hidden_tests_passed"):
        return "hidden_tests_failed"
    return str(row.get("status") or "unknown")


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
    infrastructure_failed_runs = sum(is_infrastructure_failure(row) for row in selected_rows)
    if infrastructure_failed_runs:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).extend(sorted({
            _failure_reason(row) for row in selected_rows if is_infrastructure_failure(row)
        }))
        decision["reasons"] = list(dict.fromkeys(decision["reasons"]))

    condition_summaries: dict[str, Any] = {}
    failure_taxonomy: dict[str, Any] = {}
    for condition in conditions:
        condition_rows = [row for row in selected_rows if row.get("condition_id") == condition]
        valid_rows = [row for row in condition_rows if not is_infrastructure_failure(row)]
        full_coverage = len(valid_rows) == len(condition_rows)
        condition_summaries[condition] = {
            "runs": len(condition_rows),
            "metric_valid_runs": len(valid_rows),
            "infrastructure_failed_runs": len(condition_rows) - len(valid_rows),
            "metric_coverage_ratio": len(valid_rows) / len(condition_rows) if condition_rows else None,
            "descriptive_metrics_scope": "valid_runner_outputs_only",
            "resolved": sum(bool(row.get("resolved")) for row in valid_rows),
            "resolved_rate": mean(bool(row.get("resolved")) for row in valid_rows) if valid_rows and full_coverage else None,
            "diagnostic_resolved_rate_valid_runs": mean(bool(row.get("resolved")) for row in valid_rows) if valid_rows else None,
            "compile_success_rate": mean(bool(row.get("compile_success")) for row in valid_rows) if valid_rows else None,
            "public_tests_passed_rate": mean(bool(row.get("public_tests_passed")) for row in valid_rows) if valid_rows else None,
            "hidden_tests_passed_rate": mean(bool(row.get("hidden_tests_passed")) for row in valid_rows) if valid_rows else None,
            "median_total_tokens": _median([_metric(row, "total_tokens") for row in valid_rows]),
            "median_input_tokens": _median([_metric(row, "input_tokens") for row in valid_rows]),
            "median_output_tokens": _median([_metric(row, "output_tokens") for row in valid_rows]),
            "median_wall_time_seconds": _median([_metric(row, "wall_time_seconds") for row in valid_rows]),
            "median_tool_output_tokens_estimate": _median([_metric(row, "tool_output_tokens_estimate") for row in valid_rows]),
            "median_condition_setup_wall_time_seconds": _median([_metric(row, "condition_setup_wall_time_seconds") for row in valid_rows]),
            "median_required_evidence_recall": _median([_metric(row, "required_evidence_recall") for row in valid_rows]),
            "median_useful_context_ratio": _median([_metric(row, "required_evidence_recall") for row in valid_rows]),
            "median_first_required_evidence_rank": _median([_metric(row, "first_required_evidence_rank") for row in valid_rows]),
            "median_audited_external_context_tokens": _median([_metric(row, "audited_external_context_tokens") for row in valid_rows]),
            "policy_violations": sum(not bool(row.get("policy_clean")) for row in condition_rows),
        }
        failure_taxonomy[condition] = dict(sorted(Counter(
            _failure_reason(row) for row in condition_rows if not row.get("resolved")
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
        "runtime_integrity": {
            "ok": integrity_ok and infrastructure_failed_runs == 0,
            "valid_runs": len(selected_rows) - infrastructure_failed_runs,
            "infrastructure_failed_runs": infrastructure_failed_runs,
        },
        "conditions": condition_summaries,
        "failure_taxonomy": failure_taxonomy,
        "decision": decision,
        "screening_exclusions": [{
            "excluded_task_id": amendment.get("excluded_task_id"),
            "excluded_screening_status": amendment.get("excluded_screening_status"),
            "replacement_task_id": amendment.get("replacement_task", {}).get("task_id"),
            "screening_run_id": amendment.get("screening_run_id"),
            "screening_results_sha256": amendment.get("screening_results_sha256"),
            "replacement_screening_run_id": amendment.get("replacement_screening_run_id"),
        }] if amendment else [],
        "scientific_limitation": amendment.get("scientific_limitation") if amendment else None,
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _retry_provenance(run_dir: Path) -> dict[str, Any]:
    cells: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for attempt_dir in sorted(run_dir.glob("*/*/repeat_*/attempts/attempt_*")):
        repeat_dir = attempt_dir.parents[1]
        key = (
            repeat_dir.parents[1].name,
            repeat_dir.parent.name,
            int(repeat_dir.name.removeprefix("repeat_")),
        )
        result = _load_json(attempt_dir / "result.json")
        status = result.get("status")
        if status is None and (attempt_dir / "runner_error.json").exists():
            status = "runner_unavailable"
        cells.setdefault(key, []).append({
            "attempt": int(attempt_dir.name.removeprefix("attempt_")),
            "status": status,
        })
    summaries = [
        {
            "task_id": task_id,
            "condition_id": condition_id,
            "repeat": repeat,
            "attempts": sorted(attempts, key=lambda item: item["attempt"]),
        }
        for (task_id, condition_id, repeat), attempts in sorted(cells.items())
    ]
    canonical = json.dumps(summaries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "selection_rule": "infrastructure_failures_only",
        "retried_cells": len(summaries),
        "total_retry_attempts": sum(len(cell["attempts"]) for cell in summaries),
        "retry_attempts_sha256": hashlib.sha256(canonical).hexdigest(),
        "cells": summaries,
    }


def _source_artifact_hashes(
    runs_path: Path,
    protocol_path: Path,
    amendment_path: Path | None,
    replacement_screening_path: Path | None = None,
) -> dict[str, str]:
    hashes = {
        "runs_jsonl_sha256": hashlib.sha256(runs_path.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
    }
    if amendment_path is not None:
        hashes["amendment_sha256"] = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    if replacement_screening_path is not None:
        hashes["replacement_screening_sha256"] = hashlib.sha256(replacement_screening_path.read_bytes()).hexdigest()
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen Task 23 decision report")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--amendment", type=Path)
    parser.add_argument("--replacement-screening", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    amendment = _load_json(args.amendment) if args.amendment else None
    if amendment is not None:
        screening_path = args.protocol.parent / f"{amendment['screening_run_id']}.json"
        validate_protocol_amendment_artifacts(
            amendment,
            args.protocol.read_bytes(),
            screening_path.read_bytes(),
        )
    report = build_task23_report(
        _load_jsonl(args.run_dir / "runs.jsonl"),
        protocol=_load_json(args.protocol),
        amendment=amendment,
    )
    if args.replacement_screening is not None:
        replacement_screening = _load_json(args.replacement_screening)
        report["replacement_screening"] = {
            "run_id": replacement_screening.get("run_id"),
            "results": replacement_screening.get("results"),
        }
        if report["screening_exclusions"]:
            report["screening_exclusions"][0]["replacement_screening_run_id"] = replacement_screening.get("run_id")
    retry_provenance = _retry_provenance(args.run_dir)
    if retry_provenance["retried_cells"]:
        report["retry_provenance"] = retry_provenance
    report["source_artifacts"] = _source_artifact_hashes(
        args.run_dir / "runs.jsonl",
        args.protocol,
        args.amendment,
        args.replacement_screening,
    )
    output = args.output or args.run_dir / "task23_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
