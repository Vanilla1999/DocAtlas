from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from eval.task_level.fixtures.builder import materialize_fixture, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


REAL_TASK_IDS = (
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
)


def _tasks():
    loaded = {task.task_id: task for task in load_tasks(TASKS_PATH)}
    return [loaded[task_id] for task_id in REAL_TASK_IDS]


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


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


def test_real_project_fixtures_exclude_secrets_and_git_history(tmp_path: Path):
    forbidden_names = {".env", "credentials", "node_modules", ".venv", "build", "dist", "coverage"}

    for task in _tasks():
        workspace = tmp_path / task.task_id
        materialize_fixture(task, workspace)
        paths = [path.relative_to(workspace).as_posix() for path in workspace.rglob("*")]

        assert not any(part in forbidden_names for path in paths for part in path.split("/")), task.task_id
        assert not (workspace / ".git/modules").exists()
        assert workspace_has_no_oracles(workspace)
        assert "coderepo.corp" not in (workspace / "pubspec.yaml").read_text(encoding="utf-8")
        assert "coderepo.corp" not in (workspace / "pubspec.lock").read_text(encoding="utf-8")


def test_real_project_suite_expected_runs_are_persisted(tmp_path: Path):
    from eval.task_level.execution import count_jsonl_records, write_run_progress

    conditions = ("repo_only_strict_offline", "repo_only_web_audited", "docatlas_tool_recommended", "docatlas_action_checklist_injected")
    results = [
        {
            "task_id": task_id,
            "condition_id": condition,
            "repeat": 0,
            "status": "completed",
            "resolved": False,
            "public_tests_passed": False,
            "hidden_tests_passed": False,
            "policy_clean": True,
            "docatlas": {"agent_calls": 0, "context_used": False},
            "actionability": {"checklist_items": [], "action_checklist_used": False},
        }
        for task_id in REAL_TASK_IDS
        for condition in conditions
    ]

    write_run_progress(tmp_path, results, total_runs=12, current=None, finished=True)

    assert count_jsonl_records(tmp_path / "runs.jsonl") == 12
