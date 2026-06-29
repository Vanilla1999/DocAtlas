from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.task_level.conditions import CONDITIONS
from eval.task_level.patch_constraints_pilot import (
    PATCH_CONSTRAINTS_INJECTED_CONDITION,
    PATCH_CONSTRAINTS_WORKFLOW_CONDITION,
    TARGETED_PILOT_CONDITIONS,
    build_targeted_pilot_plan,
    select_targeted_pilot_tasks,
    write_targeted_pilot_dry_run,
)
from eval.task_level.analysis.cost_accuracy import NormalizedRun, compute_paired_deltas
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import DependencySpec, TaskSpec


def _task(task_id: str, *, status: str = "accepted", differentiating: bool = True, role: str = "candidate") -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        task_type="real",
        suite="differentiation",
        repo=f"fixture://{task_id}",
        base_commit="fixture-base",
        issue_text="Fix shared permission policy without touching generated files.",
        language="dart",
        ecosystem="dart",
        dependencies=(DependencySpec("permission_handler", "11.4.0"),),
        setup_command="python3 -c 'print(ready)'",
        test_command="pytest tests/test_policy.py",
        expected_symbols=("PermissionService", "Permission.notification"),
        expected_project_docs=("README.md", "docs/permission-architecture.md", "pubspec.lock"),
        role=role,
        differentiating=differentiating,
        selection_status=status,
        docatlas_relevance=("project_docs", "architecture_constraint", "generated_file_constraint"),
    )


def test_patch_constraints_workflow_condition_is_registered():
    assert PATCH_CONSTRAINTS_WORKFLOW_CONDITION in CONDITIONS
    policy = CONDITIONS[PATCH_CONSTRAINTS_WORKFLOW_CONDITION].tool_policy
    assert policy.allow_docatlas is True
    assert policy.inject_patch_constraints is False
    assert policy.recommend_docatlas_before_edit is True


def test_patch_constraints_injected_condition_keeps_harness_injection():
    policy = CONDITIONS[PATCH_CONSTRAINTS_INJECTED_CONDITION].tool_policy
    assert policy.allow_docatlas is True
    assert policy.inject_patch_constraints is True


def test_select_targeted_pilot_tasks_uses_accepted_differentiating_subset():
    tasks = [
        _task("accepted_a"),
        _task("smoke_a", status="rejected_too_easy", role="smoke"),
        _task("candidate_a", status="not_screened"),
        _task("accepted_not_diff", differentiating=False),
    ]

    selected = select_targeted_pilot_tasks(tasks)

    assert [task.task_id for task in selected] == ["accepted_a"]


def test_select_targeted_pilot_tasks_can_use_frozen_accepted_pool(tmp_path: Path):
    accepted_pool = tmp_path / "accepted_pool.json"
    accepted_pool.write_text(json.dumps([
        {"task_id": "screened_b", "status": "accepted_differentiating"},
    ]), encoding="utf-8")
    tasks = [_task("legacy_a"), _task("screened_b", status="candidate")]

    selected = select_targeted_pilot_tasks(tasks, accepted_pool_path=accepted_pool)
    plan = build_targeted_pilot_plan(
        selected,
        repeats=1,
        task_selection_source="screening_results",
        screening_metadata={"accepted_pool_size": 1, "rejected_counts": {"rejected_too_easy": 3}},
    )

    assert [task.task_id for task in selected] == ["screened_b"]
    assert plan["task_selection_source"] == "screening_results"
    assert plan["accepted_pool_size"] == 1
    assert plan["rejected_counts"] == {"rejected_too_easy": 3}


def test_select_targeted_pilot_tasks_fails_fast_on_missing_pool_task_id(tmp_path: Path):
    accepted_pool = tmp_path / "accepted_pool.json"
    accepted_pool.write_text(json.dumps([
        {"task_id": "missing_task", "status": "accepted_differentiating"},
    ]), encoding="utf-8")

    with pytest.raises(ValueError, match="missing_task"):
        select_targeted_pilot_tasks([_task("legacy_a")], accepted_pool_path=accepted_pool)


def test_build_targeted_pilot_plan_records_constraints_workflow_protocol():
    plan = build_targeted_pilot_plan([_task("accepted_a")], repeats=2)

    assert plan["conditions"] == list(TARGETED_PILOT_CONDITIONS)
    assert plan["repeats"] == 2
    assert plan["research_question"].startswith("Does DocAtlas patch-constraints workflow")
    assert plan["tasks"][0]["visible_source_coverage"] is True
    assert plan["task_selection_source"] == "legacy_manifest"
    assert "one repair pass" in "\n".join(plan["protocol"])
    assert "Not broad superiority evidence" in plan["status"]


def test_write_targeted_pilot_dry_run_persists_artifact_contract(tmp_path: Path):
    run_dir = tmp_path / "run"
    plan = build_targeted_pilot_plan([_task("accepted_a")], repeats=1)

    rows = write_targeted_pilot_dry_run(run_dir, plan)

    assert len(rows) == 3
    assert (run_dir / "targeted_pilot_plan.json").exists()
    assert (run_dir / "targeted_pilot_protocol.md").exists()
    assert (run_dir / "runs.jsonl").exists()
    row = json.loads((run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "dry_run_targeted_pilot_not_causal"
    assert "constraint_violations_after_patch" in row
    assert "manual_review_unknowns" in row
    assert row["artifact_contract"]["must_persist"] == [
        "constraints.json",
        "constraints.md",
        "validation.json",
        "changed_files.json",
        "patch.diff",
        "result.json",
    ]
    assert {json.loads(line)["condition_id"] for line in (run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()} == set(TARGETED_PILOT_CONDITIONS)


def test_pairwise_targets_include_patch_constraints_conditions():
    records = [
        NormalizedRun(run_id="r", run_family="pilot", task_id="t", condition_id="repo_only_strict_offline", repeat=0, resolved=False, constraint_violations_after_patch=2),
        NormalizedRun(run_id="r", run_family="pilot", task_id="t", condition_id="docatlas_patch_constraints_workflow", repeat=0, resolved=True, constraint_violations_after_patch=1),
        NormalizedRun(run_id="r", run_family="pilot", task_id="t", condition_id="docatlas_patch_constraints_injected", repeat=0, resolved=True, constraint_violations_after_patch=0),
    ]

    deltas = compute_paired_deltas(records)

    assert "docatlas_patch_constraints_workflow - repo_only_strict_offline" in deltas
    assert "docatlas_patch_constraints_injected - repo_only_strict_offline" in deltas
    assert deltas["docatlas_patch_constraints_injected - repo_only_strict_offline"]["constraint_violation_delta_median"] == -2.0


def test_targeted_pilot_plan_avoids_broad_claims():
    plan = build_targeted_pilot_plan([_task("accepted_a")], repeats=1)
    text = json.dumps(plan).lower()

    assert "not broad superiority evidence" in text
    assert "beats repo-only" not in text
    assert "beats context7" not in text
    assert "proves correctness" not in text


def test_main_manifest_has_targeted_pilot_subset():
    selected = select_targeted_pilot_tasks(load_tasks())

    assert selected
    assert all(task.selection_status == "accepted" and task.differentiating for task in selected)
