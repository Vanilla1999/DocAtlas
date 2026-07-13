from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any
from uuid import uuid4

from eval.task_level.analysis.task23_decision import apply_protocol_amendment, evaluate_predeclared_rule, validate_protocol_amendment_artifacts
from eval.task_level.evaluators.task_contract import evaluation_contract_registry_sha256, evaluation_contract_sha256, load_task_evaluation_contracts
from eval.task_level.execution import is_infrastructure_failure


TASK33_EVALUATION_CONTRACTS = load_task_evaluation_contracts()


def _metric(row: dict[str, Any], name: str) -> Any:
    metrics = row.get("metrics")
    return metrics.get(name) if isinstance(metrics, dict) else None


def _median(values: list[Any]) -> float | int | None:
    numbers = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return median(numbers) if numbers else None


def _failure_reason(row: dict[str, Any], required_contract_task_ids: set[str] | None = None) -> str:
    if is_infrastructure_failure(row):
        status = str(row.get("status") or "")
        return status if status in {"runner_unavailable", "runner_failed", "condition_setup_failed", "timeout"} else "runner_output_missing"
    if not row.get("policy_clean"):
        return "policy_violation"
    if required_contract_task_ids and _row_requires_contract(row, required_contract_task_ids) and not _row_has_valid_contract(row):
        return "evaluation_contract_invalid"
    evaluation_contract = row.get("evaluation_contract")
    if isinstance(evaluation_contract, dict) and evaluation_contract.get("status") == "invalid":
        return "evaluation_contract_invalid"
    compile_status = row.get("compile_status")
    if compile_status == "failed":
        return "compile_failed"
    if compile_status not in {"passed", "not_applicable"} and not row.get("compile_success"):
        return "compile_gate_unknown"
    if not row.get("public_tests_passed"):
        return "public_tests_failed"
    if not row.get("hidden_tests_passed"):
        return "hidden_tests_failed"
    return str(row.get("status") or "unknown")


def _matrix_cell(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    task_id = row.get("task_id")
    condition_id = row.get("condition_id")
    repeat = row.get("repeat")
    return (
        task_id if isinstance(task_id, str) else f"<invalid task_id:{task_id!r}>",
        condition_id if isinstance(condition_id, str) else f"<invalid condition_id:{condition_id!r}>",
        repeat if type(repeat) is int else f"<invalid repeat:{repeat!r}>",
    )


def _valid_budget(row: dict[str, Any]) -> dict[str, Any] | None:
    budget = row.get("budget")
    metrics = row.get("metrics")
    if not isinstance(budget, dict) or not isinstance(metrics, dict):
        return None
    max_input = budget.get("max_input_tokens")
    max_output = budget.get("max_output_tokens")
    max_turns = budget.get("max_turns")
    input_tokens = metrics.get("input_tokens")
    output_tokens = metrics.get("output_tokens")
    input_exceeded = budget.get("input_tokens_exceeded")
    output_exceeded = budget.get("output_tokens_exceeded")
    numeric_values = (max_input, max_output, max_turns, input_tokens, output_tokens)
    if any(not isinstance(value, int) or isinstance(value, bool) for value in numeric_values):
        return None
    if max_input <= 0 or max_output <= 0 or max_turns <= 0 or input_tokens < 0 or output_tokens < 0:
        return None
    if not isinstance(input_exceeded, bool) or not isinstance(output_exceeded, bool):
        return None
    if input_exceeded != (input_tokens > max_input) or output_exceeded != (output_tokens > max_output):
        return None
    return budget


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
    actual_cells = [_matrix_cell(row) for row in rows]
    counts = Counter(actual_cells)
    missing = sorted(expected_cells - set(actual_cells))
    duplicates = sorted((cell for cell, count in counts.items() if count != 1), key=repr)
    unexpected = sorted((cell for cell in counts if cell not in expected_cells), key=repr)
    selected_rows = [
        row for row in rows
        if _matrix_cell(row) in expected_cells
    ]
    integrity_ok = not missing and not duplicates and not unexpected and len(rows) == len(expected_cells)

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
    budget_rows = [row for row in selected_rows if not is_infrastructure_failure(row)]
    valid_budgets = [_valid_budget(row) for row in budget_rows]
    budget_known_runs = sum(budget is not None for budget in valid_budgets)
    budget_unknown_runs = len(budget_rows) - budget_known_runs
    input_budget_exceeded_runs = sum(bool(budget and budget["input_tokens_exceeded"]) for budget in valid_budgets)
    output_budget_exceeded_runs = sum(bool(budget and budget["output_tokens_exceeded"]) for budget in valid_budgets)
    max_turns_unenforced_runs = sum(
        not isinstance(row.get("budget"), dict)
        or row["budget"].get("max_turns_enforced_by_runner") is not True
        for row in budget_rows
    )
    if budget_unknown_runs:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).append("missing_or_invalid_budget_metrics")
        decision["reasons"] = list(dict.fromkeys(decision["reasons"]))
    if input_budget_exceeded_runs or output_budget_exceeded_runs:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).append("declared_token_budget_exceeded")
        decision["reasons"] = list(dict.fromkeys(decision["reasons"]))
    if max_turns_unenforced_runs:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).append("max_turn_budget_not_enforced")
        decision["reasons"] = list(dict.fromkeys(decision["reasons"]))
    required_contract_task_ids = (
        set(task_ids)
        if effective.get("protocol_id") == "task23-real-project-value-token-001"
        else set()
    )
    evaluation_contract_integrity = _evaluation_contract_integrity(selected_rows, required_contract_task_ids)
    if not evaluation_contract_integrity["ok"]:
        decision["decision"] = "INCONCLUSIVE"
        decision.setdefault("reasons", []).append("missing_or_invalid_evaluation_contract")
        decision["reasons"] = list(dict.fromkeys(decision["reasons"]))

    condition_summaries: dict[str, Any] = {}
    failure_taxonomy: dict[str, Any] = {}
    for condition in conditions:
        condition_rows = [row for row in selected_rows if row.get("condition_id") == condition]
        valid_rows = [row for row in condition_rows if not is_infrastructure_failure(row)]
        condition_budgets = [_valid_budget(row) for row in valid_rows]
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
            "compile_success_rate": _compile_success_rate(valid_rows),
            "compile_not_applicable_runs": sum(row.get("compile_status") == "not_applicable" for row in valid_rows),
            "public_tests_passed_rate": mean(bool(row.get("public_tests_passed")) for row in valid_rows) if valid_rows else None,
            "hidden_tests_passed_rate": mean(bool(row.get("hidden_tests_passed")) for row in valid_rows) if valid_rows else None,
            "median_total_tokens": _median([_metric(row, "total_tokens") for row in valid_rows]),
            "median_input_tokens": _median([_metric(row, "input_tokens") for row in valid_rows]),
            "median_output_tokens": _median([_metric(row, "output_tokens") for row in valid_rows]),
            "median_wall_time_seconds": _median([_metric(row, "wall_time_seconds") for row in valid_rows]),
            "median_tool_output_tokens_estimate": _median([_metric(row, "tool_output_tokens_estimate") for row in valid_rows]),
            "median_condition_setup_wall_time_seconds": _median([_metric(row, "condition_setup_wall_time_seconds") for row in valid_rows]),
            "median_required_evidence_recall": _median([_metric(row, "required_evidence_recall") for row in valid_rows]),
            "median_useful_context_ratio": None,
            "useful_context_ratio_method": "not_measured_without_chunk_usage_attribution",
            "median_docs_output_evidence_coverage": _median([_metric(row, "docs_output_evidence_coverage") for row in valid_rows]),
            "median_first_required_evidence_rank": _median([_metric(row, "first_required_evidence_rank") for row in valid_rows]),
            "median_audited_external_context_tokens": _median([_metric(row, "audited_external_context_tokens") for row in valid_rows]),
            "policy_violations": sum(not bool(row.get("policy_clean")) for row in condition_rows),
            "budget_known_runs": sum(budget is not None for budget in condition_budgets),
            "budget_unknown_runs": sum(budget is None for budget in condition_budgets),
            "input_budget_exceeded_runs": sum(bool(budget and budget["input_tokens_exceeded"]) for budget in condition_budgets),
            "output_budget_exceeded_runs": sum(bool(budget and budget["output_tokens_exceeded"]) for budget in condition_budgets),
            "max_turns_unenforced_runs": sum(
                not isinstance(row.get("budget"), dict)
                or row["budget"].get("max_turns_enforced_by_runner") is not True
                for row in valid_rows
            ),
            "evaluation_contract_invalid_runs": sum(
                _row_requires_contract(row, required_contract_task_ids) and not _row_has_valid_contract(row)
                for row in valid_rows
            ),
        }
        failure_taxonomy[condition] = dict(sorted(Counter(
            _failure_reason(row, required_contract_task_ids) for row in condition_rows if not row.get("resolved")
        ).items()))

    return {
        "schema_version": "task23-report-1",
        "protocol_id": effective.get("protocol_id"),
        "amendment_id": effective.get("amendment_id"),
        "artifact_integrity": {
            "ok": integrity_ok,
            "expected_runs": len(expected_cells),
            "actual_runs": len(rows),
            "missing_cells": [list(cell) for cell in missing],
            "duplicate_cells": [list(cell) for cell in duplicates],
            "unexpected_cells": [list(cell) for cell in unexpected],
        },
        "runtime_integrity": {
            "ok": integrity_ok and infrastructure_failed_runs == 0,
            "valid_runs": len(selected_rows) - infrastructure_failed_runs,
            "infrastructure_failed_runs": infrastructure_failed_runs,
        },
        "budget_integrity": {
            "ok": (
                budget_unknown_runs == 0
                and input_budget_exceeded_runs == 0
                and output_budget_exceeded_runs == 0
                and max_turns_unenforced_runs == 0
            ),
            "expected_runs": len(budget_rows),
            "known_runs": budget_known_runs,
            "unknown_runs": budget_unknown_runs,
            "input_budget_exceeded_runs": input_budget_exceeded_runs,
            "output_budget_exceeded_runs": output_budget_exceeded_runs,
            "max_turns_unenforced_runs": max_turns_unenforced_runs,
        },
        "evaluation_contract_integrity": evaluation_contract_integrity,
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


def _compile_success_rate(rows: list[dict[str, Any]]) -> float | None:
    applicable = [row for row in rows if row.get("compile_status") != "not_applicable"]
    return mean(bool(row.get("compile_success")) for row in applicable) if applicable else None


def _row_requires_contract(row: dict[str, Any], required_task_ids: set[str]) -> bool:
    return row.get("task_id") in required_task_ids


def _row_has_valid_contract(row: dict[str, Any]) -> bool:
    task_id = row.get("task_id")
    expected = TASK33_EVALUATION_CONTRACTS.get(task_id)
    evidence = row.get("evaluation_contract")
    if expected is None:
        return False
    identity = evidence.get("artifact_identity") if isinstance(evidence, dict) else None
    return (
        isinstance(evidence, dict)
        and evidence.get("status") == "valid"
        and evidence.get("patch_contract_id") == expected.patch_contract_id
        and evidence.get("contract_sha256") == evaluation_contract_sha256(expected)
        and evidence.get("registry_sha256") == evaluation_contract_registry_sha256()
        and isinstance(identity, dict)
        and identity.get("fixture_hash_algorithm") == "sha256-length-prefixed-v2"
        and identity.get("fixture_sha256") == expected.fixture_sha256
        and identity.get("protocol_fixture_hash_algorithm") == "sha256-concat-v1"
        and identity.get("protocol_fixture_sha256") == expected.protocol_fixture_sha256
        and identity.get("oracle_sha256") == expected.oracle_sha256
        and identity.get("hidden_tests_sha256") == expected.hidden_tests_sha256
        and identity.get("external_context_sha256") == expected.external_context_sha256
    )


def _evaluation_contract_integrity(rows: list[dict[str, Any]], required_task_ids: set[str]) -> dict[str, Any]:
    missing_registry_task_ids = required_task_ids - set(TASK33_EVALUATION_CONTRACTS)
    required = [row for row in rows if _row_requires_contract(row, required_task_ids)]
    invalid = [
        [row.get("task_id"), row.get("condition_id"), row.get("repeat")]
        for row in required
        if not _row_has_valid_contract(row)
    ]
    return {
        "ok": not invalid and not missing_registry_task_ids,
        "required_runs": len(required),
        "valid_runs": len(required) - len(invalid),
        "invalid_cells": invalid,
        "registry_sha256": evaluation_contract_registry_sha256(),
        "missing_registry_task_ids": sorted(missing_registry_task_ids),
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


_LOCAL_PATH = re.compile(
    r"(?:/(?:home|tmp|workspace|root|Users|private|etc)/|/var/folders/|(?<![A-Za-z0-9_])[A-Za-z]:\\|\\\\[A-Za-z0-9._$-]+\\[A-Za-z0-9._$-]+)",
    re.IGNORECASE,
)
_CREDENTIAL_LIKE = re.compile(
    r"(?:(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{8,}|Bearer\s+(?!<redacted>)[^\s]+|https?://[^\s/@]+:[^\s/@]+@)",
    re.IGNORECASE,
)


def _assert_sanitized(value: Any, *, location: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "patch" and isinstance(item, str):
                _assert_patch_sanitized(item, location=f"{location}.{key}")
            else:
                _assert_sanitized(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_sanitized(item, location=f"{location}[{index}]")
    elif isinstance(value, str) and (_LOCAL_PATH.search(value) or _CREDENTIAL_LIKE.search(value)):
        raise ValueError(f"Unsanitized path or credential-like value in {location}")


def _assert_patch_sanitized(patch: str, *, location: str) -> None:
    if _CREDENTIAL_LIKE.search(patch):
        raise ValueError(f"Credential-like value in {location}")
    for line in patch.splitlines():
        if line.startswith(("diff --git ", "--- ", "+++ ")) and _LOCAL_PATH.search(line):
            raise ValueError(f"Unsanitized diff header path in {location}")


def write_sanitized_run_bundle(
    rows: list[dict[str, Any]],
    run_dir: Path,
    output: Path,
    *,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist rescorable per-cell evidence, failing closed on missing or unsafe artifacts."""
    sanitized: list[dict[str, Any]] = []
    task_metadata = {
        str(task.get("task_id")): task
        for task in (protocol or {}).get("tasks", [])
        if isinstance(task, dict)
    }
    ordered_rows = sorted(rows, key=lambda row: (str(row.get("task_id")), str(row.get("condition_id")), int(row.get("repeat") or 0)))
    for row in ordered_rows:
        task_id = str(row.get("task_id") or "")
        condition_id = str(row.get("condition_id") or "")
        repeat = int(row.get("repeat") or 0)
        cell_dir = run_dir / task_id / condition_id / f"repeat_{repeat}"
        patch_path = cell_dir / "patch.diff"
        trajectory_path = cell_dir / "trajectory.normalized.json"
        infrastructure_failure = is_infrastructure_failure(row)
        patch = _read_text_strict(patch_path) if patch_path.exists() else ""
        if row.get("status") == "completed" and not patch.strip():
            raise ValueError(f"Completed cell has no patch: {task_id}/{condition_id}/repeat_{repeat}")
        if not infrastructure_failure and not trajectory_path.exists():
            raise ValueError(f"Valid runner cell has no normalized trajectory: {task_id}/{condition_id}/repeat_{repeat}")
        trajectory = _load_json_list_strict(trajectory_path) if trajectory_path.exists() else []
        task = task_metadata.get(task_id, {})
        if protocol is not None:
            missing_identifiers = [
                name for name in ("fixture_hash", "oracle_sha256", "external_context_sha256")
                if not task.get(name)
            ]
            if missing_identifiers:
                raise ValueError(
                    f"Missing immutable task identifiers for {task_id}: {', '.join(missing_identifiers)}"
                )
        payload = {
            "schema_version": "task23-sanitized-run-1",
            "task_id": task_id,
            "condition_id": condition_id,
            "repeat": repeat,
            "status": row.get("status"),
            "resolved": row.get("resolved"),
            "compile_success": row.get("compile_success"),
            "public_tests_passed": row.get("public_tests_passed"),
            "hidden_tests_passed": row.get("hidden_tests_passed"),
            "policy_clean": row.get("policy_clean"),
            "model": row.get("model"),
            "runner_id": row.get("runner_id"),
            "runner_version": row.get("runner_version"),
            "changed_files": row.get("changed_files") or [],
            "forbidden_changes": row.get("forbidden_changes") or [],
            "metrics": row.get("metrics") or {},
            "policy": row.get("policy") or {},
            "docatlas": row.get("docatlas") or {},
            "contract": row.get("contract") or {},
            "actionability": row.get("actionability") or {},
            "budget": row.get("budget") or {},
            "evaluation_contract": row.get("evaluation_contract") or {},
            "token_attribution": row.get("token_attribution") or {},
            "fixture_hash": task.get("fixture_hash"),
            "oracle_sha256": task.get("oracle_sha256"),
            "external_context_sha256": task.get("external_context_sha256"),
            "artifact_presence": {
                "patch": bool(patch),
                "trajectory": trajectory_path.exists(),
                "infrastructure_failure": infrastructure_failure,
            },
            "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
            "patch": patch,
            "trajectory": trajectory,
        }
        _assert_sanitized(payload, location=f"{task_id}/{condition_id}/repeat_{repeat}")
        sanitized.append(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in sanitized),
        encoding="utf-8",
    )
    return {
        "schema_version": "task23-sanitized-run-1",
        "rows_expected": len(rows),
        "rows_written": len(sanitized),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "integrity_ok": len(sanitized) == len(rows),
    }


def _read_text_strict(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json_list_strict(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Expected a JSON array of objects: {path}")
    return value


def _publish_report_artifacts(
    report: dict[str, Any],
    rows: list[dict[str, Any]],
    run_dir: Path,
    output: Path,
    sanitized_bundle: Path,
    *,
    protocol: dict[str, Any],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    staged_output = output.with_name(f".{output.name}.{token}.tmp")
    staged_bundle = sanitized_bundle.with_name(f".{sanitized_bundle.name}.{token}.tmp")
    try:
        report["sanitized_bundle_integrity"] = write_sanitized_run_bundle(
            rows,
            run_dir,
            staged_bundle,
            protocol=protocol,
        )
        staged_bundle_sha256 = hashlib.sha256(staged_bundle.read_bytes()).hexdigest()
        report.setdefault("source_artifacts", {})["sanitized_runs_sha256"] = staged_bundle_sha256
        report["sanitized_bundle_integrity"]["sha256"] = staged_bundle_sha256
        report["sanitized_bundle_integrity"]["path"] = sanitized_bundle.name

        if sanitized_bundle.exists():
            published_sha256 = hashlib.sha256(sanitized_bundle.read_bytes()).hexdigest()
            if published_sha256 != staged_bundle_sha256:
                raise FileExistsError(
                    f"Refusing to overwrite immutable sanitized bundle: {sanitized_bundle}"
                )
        else:
            staged_bundle.replace(sanitized_bundle)

        staged_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged_output.replace(output)
    finally:
        staged_output.unlink(missing_ok=True)
        staged_bundle.unlink(missing_ok=True)


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
    sanitized_bundle_path: Path | None = None,
) -> dict[str, str]:
    hashes = {
        "runs_jsonl_sha256": hashlib.sha256(runs_path.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
    }
    if amendment_path is not None:
        hashes["amendment_sha256"] = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    if replacement_screening_path is not None:
        hashes["replacement_screening_sha256"] = hashlib.sha256(replacement_screening_path.read_bytes()).hexdigest()
    if sanitized_bundle_path is not None:
        hashes["sanitized_runs_sha256"] = hashlib.sha256(sanitized_bundle_path.read_bytes()).hexdigest()
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
    rows = _load_jsonl(args.run_dir / "runs.jsonl")
    protocol = _load_json(args.protocol)
    effective_protocol = apply_protocol_amendment(protocol, amendment) if amendment else protocol
    report = build_task23_report(
        rows,
        protocol=protocol,
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
    output = args.output or args.run_dir / "task23_report.json"
    bundle_path = output.with_name(output.stem + "_runs.sanitized.jsonl")
    report["source_artifacts"] = _source_artifact_hashes(
        args.run_dir / "runs.jsonl",
        args.protocol,
        args.amendment,
        args.replacement_screening,
    )
    _publish_report_artifacts(
        report,
        rows,
        args.run_dir,
        output,
        bundle_path,
        protocol=effective_protocol,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
