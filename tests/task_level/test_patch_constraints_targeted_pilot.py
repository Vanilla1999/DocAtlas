from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.conditions import CONDITIONS
from eval.task_level.patch_constraints_pilot import (
    PATCH_CONSTRAINTS_WORKFLOW_CONDITION,
    TARGETED_PILOT_CONDITIONS,
    build_targeted_pilot_plan,
    select_targeted_pilot_tasks,
    write_targeted_pilot_dry_run,
)
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
    assert policy.inject_patch_constraints is True
    assert policy.allow_docatlas is True


def test_select_targeted_pilot_tasks_uses_accepted_differentiating_subset():
    tasks = [
        _task("accepted_a"),
        _task("smoke_a", status="rejected_too_easy", role="smoke"),
        _task("candidate_a", status="not_screened"),
        _task("accepted_not_diff", differentiating=False),
    ]

    selected = select_targeted_pilot_tasks(tasks)

    assert [task.task_id for task in selected] == ["accepted_a"]


def test_build_targeted_pilot_plan_records_constraints_workflow_protocol():
    plan = build_targeted_pilot_plan([_task("accepted_a")], repeats=2)

    assert plan["conditions"] == list(TARGETED_PILOT_CONDITIONS)
    assert plan["repeats"] == 2
    assert plan["research_question"].startswith("Does DocAtlas patch-constraints workflow")
    assert plan["tasks"][0]["visible_source_coverage"] is True
    assert "one repair pass" in "\n".join(plan["protocol"])
    assert "Not broad superiority evidence" in plan["status"]


def test_write_targeted_pilot_dry_run_persists_artifact_contract(tmp_path: Path):
    run_dir = tmp_path / "run"
    plan = build_targeted_pilot_plan([_task("accepted_a")], repeats=1)

    rows = write_targeted_pilot_dry_run(run_dir, plan)

    assert len(rows) == 2
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


def test_main_manifest_has_targeted_pilot_subset():
    selected = select_targeted_pilot_tasks(load_tasks())

    assert selected
    assert all(task.selection_status == "accepted" and task.differentiating for task in selected)
