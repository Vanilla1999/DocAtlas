from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.analysis.cost_accuracy import (
    NormalizedRun,
    compute_condition_metrics,
    compute_context_utilization,
    compute_paired_deltas,
    detect_policy_positive_cases,
    parse_run_directory,
    summarize_cost_accuracy,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    *,
    run_id: str = "pilot_001",
    task_id: str = "task_a",
    condition_id: str = "repo_only_strict_offline",
    repeat: int = 0,
    resolved: bool = False,
    hidden: bool = False,
    policy_clean: bool = True,
    network_attempts: int = 0,
    input_tokens=None,
    output_tokens=None,
    wall_time_seconds=None,
    docatlas_calls: int = 0,
    context_used: bool = False,
    checklist_used: bool = False,
    forbidden_changes: list[str] | None = None,
    constraint_violations_after_patch=None,
    unknown_count=None,
    constraint_used=False,
) -> dict:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "condition_id": condition_id,
        "repeat": repeat,
        "status": "completed",
        "resolved": resolved,
        "public_tests_passed": True,
        "hidden_tests_passed": hidden,
        "policy_clean": policy_clean,
        "policy": {"network_attempts": network_attempts},
        "metrics": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "wall_time_seconds": wall_time_seconds,
            "agent_docatlas_calls": docatlas_calls,
            "harness_docatlas_calls": 0,
        },
        "docatlas": {
            "agent_calls": docatlas_calls,
            "harness_calls": 0,
            "context_used": context_used,
            "fallback_used": False,
            "docatlas_retrieval_status": "success" if context_used else None,
            "vector_indexing_timed_out": False,
        },
        "actionability": {"action_checklist_used": checklist_used},
        "contract": {
            "behavioral_contract_score": 1.0 if resolved else 0.0,
            "project_convention_score": 0.5,
            "version_contract_score": None,
            "generated_file_contract_score": None,
        },
        "forbidden_changes": forbidden_changes or [],
        "constraint_validation": {"violated": constraint_violations_after_patch, "unknown": unknown_count},
        "constraint_violations_after_patch": constraint_violations_after_patch,
        "unknown_count": unknown_count,
        "constraint_used": constraint_used,
    }



























