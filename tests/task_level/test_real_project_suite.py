from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from eval.task_level.fixtures.builder import materialize_fixture, run_local_test_command, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


REAL_TASK_IDS = (
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_cross_module_permission_contract_001",
)


def _tasks():
    loaded = {task.task_id: task for task in load_tasks(TASKS_PATH)}
    return [loaded[task_id] for task_id in REAL_TASK_IDS]


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return run_local_test_command(command, cwd)


def test_real_project_fixtures_base_fail_gold_pass(tmp_path: Path):
    for task in _tasks():
        workspace = tmp_path / task.task_id
        materialize_fixture(task, workspace)

        base = _run(task.test_command, workspace)
        assert base.returncode != 0, task.task_id

        patch = (Path("eval/task_level/oracles") / f"{task.task_id}.patch").resolve()
        applied = subprocess.run(["git", "apply", str(patch)], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        assert applied.returncode == 0, applied.stderr

        public = _run(task.test_command, workspace)
        assert public.returncode == 0, task.task_id + public.stdout + public.stderr

        source = Path("eval/task_level/hidden_tests") / task.task_id
        target = workspace / "tests/hidden"
        shutil.copytree(source, target)
        hidden = _run("pytest tests/hidden", workspace)
        assert hidden.returncode == 0, task.task_id + hidden.stdout + hidden.stderr







