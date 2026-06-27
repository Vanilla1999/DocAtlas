from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eval.task_level.execution import run_artifact_integrity, write_run_progress
from eval.task_level.fixtures.builder import materialize_fixture, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


TASK_ID = "real_project_nbo_001"


def _task():
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == TASK_ID)


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _apply_gold(workspace: Path) -> subprocess.CompletedProcess[str]:
    patch = (Path("eval/task_level/oracles") / f"{TASK_ID}.patch").resolve()
    return subprocess.run(["git", "apply", str(patch)], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_real_project_fixture_base_fails_gold_passes(tmp_path: Path):
    task = _task()
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    base = _run(task.test_command, workspace)
    assert base.returncode != 0
    assert "Permission.notification" not in (workspace / "lib/modules/permission/domain/services/permission_service.dart").read_text(encoding="utf-8")

    applied = _apply_gold(workspace)
    assert applied.returncode == 0, applied.stderr
    public = _run(task.test_command, workspace)
    hidden = _run("pytest tests/hidden", workspace)
    if hidden.returncode != 0:
        # Hidden tests are copied by the harness; copy them here for the direct fixture test.
        source = Path("eval/task_level/hidden_tests") / TASK_ID
        target = workspace / "tests/hidden"
        target.mkdir(parents=True, exist_ok=True)
        for file in source.glob("*.py"):
            (target / file.name).write_text(file.read_text(encoding="utf-8"), encoding="utf-8")
        hidden = _run("pytest tests/hidden", workspace)

    assert public.returncode == 0, public.stdout + public.stderr
    assert hidden.returncode == 0, hidden.stdout + hidden.stderr


def test_real_project_fixture_excludes_secrets(tmp_path: Path):
    workspace = tmp_path / "workspace"
    materialize_fixture(_task(), workspace)

    forbidden_names = {".env", "credentials", "node_modules", ".venv", "build", "dist", "coverage"}
    paths = [path.relative_to(workspace).as_posix() for path in workspace.rglob("*")]

    assert not any(part in forbidden_names for path in paths for part in path.split("/"))
    assert "coderepo.corp" not in (workspace / "pubspec.yaml").read_text(encoding="utf-8")
    assert "coderepo.corp" not in (workspace / "pubspec.lock").read_text(encoding="utf-8")


def test_real_project_fixture_excludes_git_history(tmp_path: Path):
    workspace = tmp_path / "workspace"
    materialize_fixture(_task(), workspace)

    assert (workspace / ".git").exists()
    assert not (workspace / ".git/modules").exists()
    assert workspace_has_no_oracles(workspace)


def test_real_project_artifact_integrity(tmp_path: Path):
    results = [{"task_id": TASK_ID, "condition_id": "repo_only", "repeat": 0, "status": "completed", "resolved": True}]

    write_run_progress(tmp_path, results, total_runs=1, current=None, finished=True)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert status["artifact_integrity"]["ok"] is True
    assert run_artifact_integrity(tmp_path, in_memory_results=1, total_runs=1, finished=True)["ok"] is True
