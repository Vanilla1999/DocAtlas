from __future__ import annotations

import subprocess
from pathlib import Path

from eval.task_level.fixtures.builder import materialize_fixture, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_PATH) if task.task_id == task_id)


def _apply_gold(workspace: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    patch = Path("eval/task_level/oracles") / f"{task_id}.patch"
    return subprocess.run(["git", "apply", str(patch.resolve())], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_fastapi_fixture_base_fails(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"

    result = materialize_fixture(task, workspace)

    assert result["base_commit"]
    assert (workspace / "src/app/main.py").exists()
    assert "Depends" not in (workspace / "src/app/main.py").read_text(encoding="utf-8")


def test_fastapi_fixture_gold_passes(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    applied = _apply_gold(workspace, task.task_id)

    assert applied.returncode == 0, applied.stderr
    assert "Depends" in (workspace / "src/app/main.py").read_text(encoding="utf-8")


def test_mixed_fixture_base_fails(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    workspace = tmp_path / "workspace"

    materialize_fixture(task, workspace)

    text = (workspace / "src/app/main.py").read_text(encoding="utf-8")

    assert "/internal/admin/status" not in text
    assert "require_admin" not in text


def test_mixed_fixture_gold_passes(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    applied = _apply_gold(workspace, task.task_id)

    text = (workspace / "src/app/main.py").read_text(encoding="utf-8")

    assert applied.returncode == 0, applied.stderr
    assert "/internal/admin/status" in text
    assert "Depends(require_admin)" in text


def test_hidden_tests_not_in_agent_workspace(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"

    materialize_fixture(task, workspace)

    assert not (workspace / "tests/hidden").exists()
    assert workspace_has_no_oracles(workspace)


def test_oracle_not_in_agent_workspace(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    workspace = tmp_path / "workspace"

    materialize_fixture(task, workspace)

    paths = [str(path.relative_to(workspace)) for path in workspace.rglob("*")]

    assert not any("oracle" in path or "gold_patch" in path for path in paths)
