from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.conditions import CONDITIONS, DEFAULT_CONDITIONS
from eval.task_level.report import bootstrap_delta_ci
from eval.task_level.runner import load_tasks, run_smoke
from eval.task_level.schemas import TASKS_PATH


def test_manifest_has_required_pilot_shape():
    tasks = load_tasks(TASKS_PATH)

    assert len(tasks) == 8
    assert sum(1 for task in tasks if task.suite == "comparable") == 5
    assert sum(1 for task in tasks if task.suite == "differentiation") == 3
    assert {task.task_type for task in tasks} == {"curated"}


def test_conditions_encode_tool_isolation():
    assert not CONDITIONS["repo_only"].tool_policy.allow_docatlas
    assert not CONDITIONS["repo_only"].tool_policy.allow_context7
    assert CONDITIONS["context7"].tool_policy.allow_context7
    assert not CONDITIONS["context7"].tool_policy.allow_docatlas
    assert CONDITIONS["docatlas_evidence_first"].tool_policy.allow_docatlas
    assert CONDITIONS["docatlas_evidence_first"].tool_policy.docatlas_response_style == "evidence-first"
    assert CONDITIONS["docatlas_snippet_first"].tool_policy.docatlas_response_style == "snippet-first"
    assert CONDITIONS["docatlas_tool_recommended"].tool_policy.recommend_docatlas_before_edit
    assert not CONDITIONS["docatlas_tool_recommended"].tool_policy.require_docatlas_call_before_edit


def test_smoke_results_are_explicitly_not_causal(tmp_path: Path):
    tasks = load_tasks(TASKS_PATH)
    results = run_smoke(tasks, list(DEFAULT_CONDITIONS), repeats=1, run_dir=tmp_path)

    assert results
    assert {result["status"] for result in results} == {"smoke_not_causal"}
    assert not any(result["resolved"] for result in results)


def test_bootstrap_delta_ci_is_paired_and_directional():
    ci = bootstrap_delta_ci([True, True, False, True], [True, False, False, False])
    assert ci is not None
    observed, low, high = ci
    assert observed == 0.5
    assert low <= observed <= high
