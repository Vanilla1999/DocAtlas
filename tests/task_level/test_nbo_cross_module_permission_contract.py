from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from eval.task_level.evaluators.actionability import requirements_for_task
from eval.task_level.fixtures.builder import materialize_fixture, run_local_test_command, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


TASK_ID = "real_project_nbo_cross_module_permission_contract_001"
PREVIOUS_TASK_ID = "real_project_nbo_distributed_permission_policy_001"
TEMPLATE = Path("eval/task_level/fixtures/templates") / TASK_ID
ORACLE = Path("eval/task_level/oracles") / f"{TASK_ID}.patch"
HIDDEN = Path("eval/task_level/hidden_tests") / TASK_ID


def _tasks():
    return {task.task_id: task for task in load_tasks(TASKS_PATH)}


def _task():
    return _tasks()[TASK_ID]


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return run_local_test_command(command, cwd)


def test_nbo_cross_module_fixture_base_fails_gold_passes(tmp_path: Path):
    workspace = tmp_path / TASK_ID
    task = _task()
    materialize_fixture(task, workspace)

    base = _run(task.test_command, workspace)
    assert base.returncode != 0

    applied = subprocess.run(["git", "apply", str(ORACLE.resolve())], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert applied.returncode == 0, applied.stderr

    public = _run(task.test_command, workspace)
    assert public.returncode == 0, public.stdout + public.stderr

    shutil.copytree(HIDDEN, workspace / "tests/hidden")
    hidden = _run("pytest tests/hidden", workspace)
    assert hidden.returncode == 0, hidden.stdout + hidden.stderr















