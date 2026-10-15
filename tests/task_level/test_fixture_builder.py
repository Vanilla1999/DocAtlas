from __future__ import annotations

import subprocess
from pathlib import Path

from eval.task_level.fixtures.builder import materialize_fixture, workspace_has_no_oracles
from eval.task_level.evaluators.actionability import requirements_for_task
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)


def _apply_gold(workspace: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    patch = Path("eval/task_level/oracles") / f"{task_id}.patch"
    return subprocess.run(["git", "apply", str(patch.resolve())], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)























