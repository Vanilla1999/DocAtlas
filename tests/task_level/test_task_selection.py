from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH
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


def test_rich_screening_rejects_repo_only_solved_all_repeats():
    result = _screening(repo_only_resolved=2, repo_only_hidden_passed=2)

    assert result.status == "rejected_too_easy"
    assert not result.selected_for_targeted_pilot


def test_rich_screening_rejects_hidden_only_and_missing_visible_source():
    assert _screening(hidden_oracle_only=True).status == "rejected_hidden_only"
    assert _screening(visible_source_coverage=False).status == "rejected_insufficient_visible_source"


def test_rich_screening_rejects_invalid_or_missing_constraint_angle():
    assert _screening(fairness_clean=False, policy_clean=False).status == "rejected_invalid"
    assert _screening(constraint_angle="", task_class="other").status == "rejected_no_constraint_angle"


def test_rich_screening_accepts_only_clean_differentiating_candidates():
    result = _screening(task_id="accepted", task_class="generated_file_trap", constraint_angle="visible generated-file rule")

    assert result.status == "accepted_differentiating"
    assert result.selected_for_targeted_pilot
    assert result.reason
    assert result.task_class == "generated_file_trap"


def test_rich_screening_marks_ambiguous_partial_results_for_manual_review():
    result = _screening(task_id="partial", repo_only_resolved=1, repo_only_hidden_passed=1)

    assert result.status == "needs_manual_review"
    assert result.requires_manual_review
    assert not result.selected_for_targeted_pilot


def test_screening_artifacts_split_accepted_and_rejected_pools(tmp_path: Path):
    accepted = _screening(task_id="accepted", repo_only_repeats=1, repo_only_public_passed=1, task_class="dependency_version_contract", constraint_angle="visible dependency contract")
    rejected = _screening(task_id="easy", repo_only_repeats=1, repo_only_resolved=1, repo_only_public_passed=1, repo_only_hidden_passed=1, task_class="dependency_version_contract", constraint_angle="visible dependency contract")

    payload = write_screening_artifacts(tmp_path, [accepted, rejected])

    assert payload["accepted_differentiating_count"] == 1
    assert json.loads((tmp_path / "accepted_pool.json").read_text(encoding="utf-8"))[0]["task_id"] == "accepted"
    assert json.loads((tmp_path / "rejected_pool.json").read_text(encoding="utf-8"))[0]["task_id"] == "easy"
    report = (tmp_path / "screening_report.md").read_text(encoding="utf-8")
    assert "rejected-too-easy tasks are not promoted" in report
    assert "must not use DocAtlas outcome" in report
