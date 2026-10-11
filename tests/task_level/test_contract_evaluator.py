from __future__ import annotations

from pathlib import Path

from eval.task_level.evaluators.contract import evaluate_contract
from eval.task_level.evaluators.actionability import requirements_for_task
from eval.task_level.schemas import TaskSpec


def _task(task_id: str) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        task_type="curated",
        suite="differentiation",
        repo="fixture://test",
        base_commit="fixture-base",
        issue_text="Issue",
        language="python",
        ecosystem="python",
        dependencies=(),
        setup_command="",
        test_command="pytest",
    )







