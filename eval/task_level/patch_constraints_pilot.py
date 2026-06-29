from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.task_level.execution import serialize_run_results_jsonl
from eval.task_level.schemas import TaskSpec

BASELINE_CONDITION = "repo_only_strict_offline"
PATCH_CONSTRAINTS_WORKFLOW_CONDITION = "docatlas_patch_constraints_workflow"
TARGETED_PILOT_CONDITIONS = (BASELINE_CONDITION, PATCH_CONSTRAINTS_WORKFLOW_CONDITION)
ARTIFACT_CONTRACT = [
    "constraints.json",
    "constraints.md",
    "validation.json",
    "changed_files.json",
    "patch.diff",
    "result.json",
]


def select_targeted_pilot_tasks(tasks: list[TaskSpec], *, limit: int = 12) -> list[TaskSpec]:
    """Return accepted/differentiating tasks for the patch-constraints pilot."""

    selected = [task for task in tasks if task.selection_status == "accepted" and task.differentiating]
    return selected[:limit]


def task_class(task: TaskSpec) -> str:
    relevance = set(task.docatlas_relevance)
    issue = task.issue_text.lower()
    if "generated" in relevance or "generated" in issue:
        return "generated-file trap"
    if "pinned_dependency" in relevance or "dependency" in issue or "lockfile" in issue:
        return "lockfile/dependency trap"
    if "architecture_constraint" in relevance or "source" in issue or "service" in issue:
        return "source-of-truth ownership"
    if "cross_module_contract" in relevance or "cross-module" in issue or "shared" in issue:
        return "cross-module policy task"
    if "verification" in relevance:
        return "verification/checks required"
    return "architecture/layer boundary"


def expected_constraint_types(task: TaskSpec) -> list[str]:
    relevance = set(task.docatlas_relevance)
    types: list[str] = []
    if "generated_file_constraint" in relevance or "generated" in task.issue_text.lower():
        types.append("generated_file")
    if "pinned_dependency" in relevance or task.dependencies:
        types.append("dependency_version")
    if "architecture_constraint" in relevance or "project_docs" in relevance:
        types.extend(["architecture", "source_of_truth"])
    if "cross_module_contract" in relevance:
        types.append("forbidden_edit")
    return sorted(set(types or ["architecture"]))


def build_targeted_pilot_plan(tasks: list[TaskSpec], *, repeats: int = 1) -> dict[str, Any]:
    return {
        "status": "Exploratory targeted pilot. Not broad superiority evidence.",
        "research_question": "Does DocAtlas patch-constraints workflow reduce high-confidence deterministic project-rule violations compared with repo_only_strict_offline?",
        "primary_success_metric": "fewer deterministic project-rule violations after patch",
        "conditions": list(TARGETED_PILOT_CONDITIONS),
        "repeats": repeats,
        "minimum_meaningful_pilot": "8-12 accepted/differentiating tasks if available; this plan records the available accepted subset.",
        "protocol": [
            "compile constraints before editing",
            "inject compact constraint packet into the agent prompt",
            "agent edits code",
            "collect changed_files and patch_diff",
            "validate patch against constraints",
            "allow exactly one repair pass on deterministic violations",
            "run public tests",
            "run hidden tests only inside eval harness",
            "persist artifacts and metrics",
        ],
        "metrics": [
            "resolved",
            "public_tests_pass",
            "hidden_tests_pass",
            "policy_clean",
            "constraint_violations_after_patch",
            "violation_type",
            "constraint_used",
            "constraint_packet_tokens",
            "input_tokens",
            "output_tokens",
            "wall_time_seconds",
            "unknown_count",
            "manual_review_required",
            "fallback_used",
        ],
        "artifact_contract": {"must_persist": ARTIFACT_CONTRACT},
        "tasks": [_task_plan_row(task) for task in tasks],
        "limitations": _plan_limitations(tasks),
    }


def write_targeted_pilot_dry_run(run_dir: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    run_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for task in plan["tasks"]:
        for repeat in range(int(plan["repeats"])):
            for condition in plan["conditions"]:
                rows.append({
                    "run_id": run_dir.name,
                    "task_id": task["task_id"],
                    "condition_id": condition,
                    "repeat": repeat,
                    "status": "dry_run_targeted_pilot_not_causal",
                    "resolved": False,
                    "public_tests_passed": False,
                    "hidden_tests_passed": False,
                    "policy_clean": False,
                    "constraint_violations_after_patch": None,
                    "violation_types": [],
                    "unknown_count": None,
                    "manual_review_unknowns": None,
                    "manual_review_required": None,
                    "constraint_used": False,
                    "fallback_used": None,
                    "metrics": {
                        "constraint_packet_tokens": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "wall_time_seconds": None,
                    },
                    "artifact_contract": plan["artifact_contract"],
                    "notes": ["Planning/dry-run artifact only; no agent process launched and no causal result claimed."],
                })
    (run_dir / "targeted_pilot_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "targeted_pilot_protocol.md").write_text(format_targeted_pilot_protocol(plan), encoding="utf-8")
    (run_dir / "runs.jsonl").write_text(serialize_run_results_jsonl(rows), encoding="utf-8")
    return rows


def format_targeted_pilot_protocol(plan: dict[str, Any]) -> str:
    lines = [
        "# Patch constraints targeted pilot protocol",
        "",
        f"Status: {plan['status']}",
        "",
        f"Question: {plan['research_question']}",
        "",
        "Conditions:",
        *[f"- {condition}" for condition in plan["conditions"]],
        "",
        "Protocol:",
        *[f"{index}. {step}" for index, step in enumerate(plan["protocol"], start=1)],
        "",
        "Tasks:",
    ]
    for task in plan["tasks"]:
        lines.append(f"- {task['task_id']} — {task['task_class']} — visible_source_coverage={task['visible_source_coverage']}")
    lines.extend([
        "",
        "Limitations:",
        *[f"- {limitation}" for limitation in plan["limitations"]],
    ])
    return "\n".join(lines) + "\n"


def _task_plan_row(task: TaskSpec) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "task_class": task_class(task),
        "accepted": task.selection_status == "accepted",
        "differentiating": task.differentiating,
        "visible_source_coverage": bool(task.expected_project_docs or task.expected_symbols or task.dependencies),
        "expected_constraint_types": expected_constraint_types(task),
        "expected_project_docs": list(task.expected_project_docs),
        "expected_symbols": list(task.expected_symbols),
        "public_tests": list(task.fail_to_pass_tests + task.pass_to_pass_tests),
        "hidden_tests": "eval harness only",
        "public_hidden_separation": "hidden tests/oracles are never injected into production prompt or constraint tools",
    }


def _plan_limitations(tasks: list[TaskSpec]) -> list[str]:
    limitations = [
        "small sample size; do not infer broad superiority",
        "stochastic agent behavior requires repeats before causal claims",
        "constraint_used is correlation, not causal proof",
        "unknown validation results are manual-review signal, not violations",
    ]
    if len(tasks) < 8:
        limitations.append(f"only {len(tasks)} accepted/differentiating tasks are currently available; below the 8-12 task target")
    return limitations
