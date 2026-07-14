from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


TASK33C_PILOT_CONDITIONS = (
    "repo_only_strict_offline",
    "docatlas_tool_recommended",
    "docatlas_bounded_direct",
    "docatlas_bounded_subagent",
)
TASK33C_PILOT_TASK_ID = "decisive_nbo_cross_module_gate_large_001"
TASK33C_REQUIRED_EVIDENCE_CATEGORIES = ("project_docs",)


def build_task33c_pilot_plan(task_id: str) -> dict[str, Any]:
    if task_id != TASK33C_PILOT_TASK_ID:
        raise ValueError(f"Task 33C pilot task is frozen to {TASK33C_PILOT_TASK_ID}")
    return {
        "schema_version": 1,
        "status": "engineering_pilot_not_product_decision",
        "task_id": task_id,
        "repeats": 1,
        "conditions": list(TASK33C_PILOT_CONDITIONS),
        "capability_flag": "isolated_worker",
        "retrieval_call_budget": 1,
        "isolated_worker_attempt_budget": 1,
        "packet_token_budget": 1_500,
        "packet_hard_ceiling": 2_000,
        "required_evidence_categories": list(TASK33C_REQUIRED_EVIDENCE_CATEGORIES),
        "required_measurements": [
            "parent_input_tokens",
            "parent_output_tokens",
            "parent_cached_input_tokens",
            "parent_uncached_input_tokens",
            "worker_input_tokens",
            "worker_output_tokens",
            "worker_reasoning_tokens",
            "raw_retrieval_tokens",
            "serialized_packet_tokens",
            "retrieval_calls",
            "time_to_first_edit",
            "total_latency",
            "hidden_correctness",
        ],
        "claims": {
            "may_claim_product_improvement": False,
            "may_claim_system_token_savings_without_complete_worker_usage": False,
        },
    }


def write_task33c_pilot_plan(output_dir: Path, task_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "task33c_pilot_plan.json"
    path.write_text(json.dumps(build_task33c_pilot_plan(task_id), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def evaluate_task33c_pilot_completeness(results: list[dict[str, Any]]) -> dict[str, Any]:
    cells = {
        str(result.get("condition_id")): result
        for result in results
        if result.get("task_id") == TASK33C_PILOT_TASK_ID and result.get("repeat") == 0
    }
    missing_cells = sorted(set(TASK33C_PILOT_CONDITIONS) - set(cells))
    errors: list[str] = [f"missing_cell:{condition}" for condition in missing_cells]
    for condition in TASK33C_PILOT_CONDITIONS:
        result = cells.get(condition)
        if result is None:
            continue
        if result.get("status") in {"runner_unavailable", "runner_failed", "condition_setup_failed", "timeout"}:
            errors.append(f"{condition}:infrastructure_status:{result.get('status')}")
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        for field in ("input_tokens", "output_tokens"):
            value = metrics.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{condition}:missing_{field}")
        if not _finite_nonnegative(metrics.get("total_latency")):
            errors.append(f"{condition}:missing_total_latency")
        if not _finite_nonnegative(metrics.get("time_to_first_edit")):
            errors.append(f"{condition}:missing_time_to_first_edit")
        if condition in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
            retrieval_calls = metrics.get("delivery_retrieval_calls")
            if isinstance(retrieval_calls, bool) or retrieval_calls != 1:
                errors.append(f"{condition}:invalid_retrieval_call_count")
            if metrics.get("action_packet_status") == "insufficient_evidence":
                errors.append(f"{condition}:insufficient_evidence")
            if not metrics.get("evidence_fingerprint"):
                errors.append(f"{condition}:missing_evidence_fingerprint")
        if condition == "docatlas_bounded_subagent":
            for field in ("worker_input_tokens", "worker_output_tokens", "system_total_tokens"):
                value = metrics.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(f"{condition}:missing_{field}")
    bounded_fingerprints = {
        cells[condition].get("metrics", {}).get("evidence_fingerprint")
        for condition in ("docatlas_bounded_direct", "docatlas_bounded_subagent")
        if condition in cells
    }
    bounded_fingerprints.discard(None)
    if len(bounded_fingerprints) != 1:
        errors.append("bounded_lanes_evidence_fingerprint_mismatch")
    return {
        "schema_version": 1,
        "decision": "ENGINEERING_PILOT_COMPLETE" if not errors else "INCONCLUSIVE",
        "complete": not errors,
        "errors": sorted(set(errors)),
        "evidence_fingerprint": next(iter(bounded_fingerprints), None),
    }


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )
