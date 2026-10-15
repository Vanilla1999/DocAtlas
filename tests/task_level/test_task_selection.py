from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.runner import load_tasks, write_screening_summary
from eval.task_level.schemas import TASKS_PATH, TaskSpec
from eval.task_level.task_selection import decide_candidate_status, decide_screening_result, write_screening_artifacts


NBO_SMOKE_TASKS = {
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
}

NBO_REJECTED_HARD_TASKS = {
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_cross_module_permission_contract_001",
}

















def _screening(**overrides):
    defaults = dict(
        task_id="task",
        repo_only_repeats=2,
        repo_only_resolved=0,
        repo_only_public_passed=2,
        repo_only_hidden_passed=0,
        policy_clean=True,
        visible_source_coverage=True,
        hidden_oracle_only=False,
        fairness_clean=True,
        constraint_angle="visible architecture contract",
        task_class="architecture_layer_boundary",
        stable_public_hidden_separation=True,
        valid_fixture=True,
    )
    defaults.update(overrides)
    return decide_screening_result(**defaults)

















