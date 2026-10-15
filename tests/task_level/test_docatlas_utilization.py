from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.docatlas_utilization import evaluate_docatlas_utilization
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)





