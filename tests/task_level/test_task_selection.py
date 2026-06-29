from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH
from eval.task_level.task_selection import decide_candidate_status


NBO_SMOKE_TASKS = {
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
}

NBO_REJECTED_HARD_TASKS = {
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_cross_module_permission_contract_001",
}


def test_existing_nbo_tasks_marked_smoke_not_differentiating():
    tasks = {task.task_id: task for task in load_tasks(TASKS_PATH)}

    for task_id in NBO_SMOKE_TASKS:
        task = tasks[task_id]
        assert task.source_project == "nbo"
        assert task.role == "smoke"
        assert task.differentiating is False
        assert task.selection_status == "rejected_too_easy"
        assert task.selection_reason == "repo_only_strict_offline resolved in pilot; useful as regression/smoke, not proof-of-value"


def test_rejected_too_easy_tasks_do_not_count_as_differentiating():
    tasks = {task.task_id: task for task in load_tasks(TASKS_PATH)}

    for task_id in NBO_REJECTED_HARD_TASKS:
        task = tasks[task_id]
        assert task.source_project == "nbo"
        assert task.role == "smoke"
        assert task.differentiating is False
        assert task.selection_status == "rejected_too_easy"
        assert task.selection_reason == (
            "repo_only_strict_offline resolved 2/2 during screening; useful as regression/smoke, not proof-of-value"
        )


def test_task_selection_rejects_repo_only_2_of_2():
    status = decide_candidate_status(repo_only_repeats=2, repo_only_resolved=2, fairness_clean=True, hidden_oracle_only=False)

    assert status == "rejected_too_easy"


def test_task_selection_accepts_repo_only_partial_or_zero():
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=1, fairness_clean=True, hidden_oracle_only=False) == "accepted"
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=0, fairness_clean=True, hidden_oracle_only=False) == "accepted"


def test_screening_accepts_candidate_only_if_repo_only_not_2_of_2():
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=2, fairness_clean=True, hidden_oracle_only=False) == "rejected_too_easy"
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=1, fairness_clean=True, hidden_oracle_only=False) == "accepted"


def test_task_selection_rejects_unfair_candidates():
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=0, fairness_clean=False, hidden_oracle_only=False) == "rejected_unfair"
    assert decide_candidate_status(repo_only_repeats=2, repo_only_resolved=0, fairness_clean=True, hidden_oracle_only=True) == "rejected_unfair"


def test_task_selection_summary_schema():
    summary = json.loads(Path("eval/task_level/results/task_selection/summary.json").read_text(encoding="utf-8"))

    assert len(summary) >= 4
    for candidate in summary:
        assert candidate["source_project"] == "nbo"
        assert candidate["candidate_status"] in {"designed", "implemented", "accepted", "rejected_too_easy", "rejected_unfair", "needs_redesign"}
        assert isinstance(candidate["docatlas_relevance"], list)
        assert candidate["repo_only_screening"]["repeats"] == 2
        assert set(candidate["fairness"]) == {"reviewed", "clean", "hidden_oracle_only"}
        assert candidate["decision_reason"]
        assert candidate["next_action"]
