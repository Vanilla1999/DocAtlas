from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)


def test_injected_context_is_not_counted_as_used_without_patch_signal(tmp_path: Path):
    task = _task("fastapi_depends_001")
    patch = tmp_path / "patch.diff"
    patch.write_text("", encoding="utf-8")
    (tmp_path / "docatlas_response.json").write_text(json.dumps({"context_pack": []}), encoding="utf-8")
    (tmp_path / "injected_context.md").write_text("Depends\nBackgroundTasks\n", encoding="utf-8")

    result = evaluate_docatlas_utilization(
        task=task,
        condition_id="docatlas_context_injected",
        run_output_dir=tmp_path,
        patch_path=patch,
        trajectory_path=None,
        agent_docatlas_calls=0,
    )

    assert result.context_injected
    assert not result.context_used
    assert result.context_used_confidence == "none"


def test_patch_symbol_from_context_counts_as_medium_signal(tmp_path: Path):
    task = _task("fastapi_depends_001")
    patch = tmp_path / "patch.diff"
    patch.write_text("+from fastapi import Depends, BackgroundTasks\n", encoding="utf-8")
    (tmp_path / "docatlas_response.json").write_text(json.dumps({"context_pack": []}), encoding="utf-8")
    (tmp_path / "injected_context.md").write_text("Depends\nBackgroundTasks\n", encoding="utf-8")

    result = evaluate_docatlas_utilization(
        task=task,
        condition_id="docatlas_context_injected",
        run_output_dir=tmp_path,
        patch_path=patch,
        trajectory_path=None,
        agent_docatlas_calls=0,
    )

    assert result.context_used
    assert result.context_used_confidence == "medium"
    assert "Depends" in result.used_symbols
