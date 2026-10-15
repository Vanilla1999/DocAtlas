from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from eval.task_level.conditions import CONDITIONS, DEFAULT_CONDITIONS
from eval.task_level.execution import _archive_run_attempt, count_jsonl_records, execute_pilot, run_artifact_integrity, serialize_run_results_jsonl, shell_call_metrics, write_run_progress
from eval.task_level.report import bootstrap_delta_ci, write_report
from eval.task_level.runner import _causal_gate_error, load_tasks, run_smoke
from eval.task_level.runners.base import RunnerCapabilities
from eval.task_level.schemas import TASKS_PATH
















def _sample_run_result(index: int) -> dict[str, object]:
    return {
        "run_id": "artifact_test",
        "task_id": f"task_{index // 4}",
        "condition_id": f"condition_{index % 4}",
        "repeat": 0,
        "status": "completed",
        "resolved": index % 2 == 0,
        "public_tests_passed": True,
        "hidden_tests_passed": index % 2 == 0,
        "policy_clean": True,
        "metrics": {"wall_time_seconds": float(index)},
        "docatlas": {"agent_calls": 0, "context_used": False},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
    }








class FailingRunner:
    runner_id = "failing"

    def verify(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            runner_id="failing",
            version="test",
            structured_trajectory=False,
            patch_capture=False,
            tool_isolation=False,
            mcp_isolation=False,
            shell_network_isolation=False,
            token_usage=False,
            independent_process=False,
            verified=False,
        )

    def run(self, request):
        self.calls = getattr(self, "calls", 0) + 1
        raise NotImplementedError("runner unavailable in test")








