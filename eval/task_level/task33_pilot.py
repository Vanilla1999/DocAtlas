from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TASK33C_PILOT_CONDITIONS = (
    "repo_only_strict_offline",
    "docatlas_tool_recommended",
    "docatlas_bounded_direct",
    "docatlas_bounded_subagent",
)
TASK33C_PILOT_TASK_ID = "decisive_nbo_cross_module_gate_large_001"


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
