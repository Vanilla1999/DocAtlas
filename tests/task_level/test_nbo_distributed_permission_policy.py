from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from eval.task_level.evaluators.actionability import requirements_for_task
from eval.task_level.fixtures.builder import materialize_fixture, workspace_has_no_oracles
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH


TASK_ID = "real_project_nbo_distributed_permission_policy_001"
TEMPLATE = Path("eval/task_level/fixtures/templates") / TASK_ID
ORACLE = Path("eval/task_level/oracles") / f"{TASK_ID}.patch"
HIDDEN = Path("eval/task_level/hidden_tests") / TASK_ID


def _task():
    return {task.task_id: task for task in load_tasks(TASKS_PATH)}[TASK_ID]


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_nbo_distributed_fixture_base_fails_gold_passes(tmp_path: Path):
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


def test_nbo_distributed_hidden_requirements_have_visible_sources():
    requirements = requirements_for_task(TASK_ID)

    assert requirements
    assert all(requirement.allowed_for_agent for requirement in requirements)
    assert all(requirement.source_type in {"issue", "project_doc", "code_symbol", "library_doc"} for requirement in requirements)
    assert all(requirement.expected_files for requirement in requirements)

    context = json.loads((Path("eval/task_level/oracles") / f"{TASK_ID}.context.json").read_text(encoding="utf-8"))
    assert all(item["visible_source"] for item in context["hidden_requirements"])


def test_nbo_distributed_fixture_excludes_secrets(tmp_path: Path):
    workspace = tmp_path / TASK_ID
    materialize_fixture(_task(), workspace)
    paths = [path.relative_to(workspace).as_posix() for path in workspace.rglob("*")]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in workspace.rglob("*") if path.is_file())

    assert not any(part in {".env", "credentials", "node_modules", ".venv", "build", "dist", "coverage"} for path in paths for part in path.split("/"))
    assert "coderepo.corp" not in text
    assert "git@" not in text
    assert workspace_has_no_oracles(workspace)


def test_nbo_distributed_docs_include_browser_scan_preflight_policy():
    text = (TEMPLATE / "docs/browser-scan-preflight.md").read_text(encoding="utf-8")

    assert "shared `PermissionService` policy" in text
    assert "Background location remains deferred" in text
    assert "Both browser and scan" in text


def test_nbo_distributed_docs_include_android13_notification_policy():
    text = (TEMPLATE / "docs/permission-notifications.md").read_text(encoding="utf-8")

    assert "Android 13" in text
    assert "Permission.notification" in text
    assert "Permission.photos" in text
    assert "Permission.videos" in text
    assert "Permission.audio" in text


def test_nbo_distributed_gold_does_not_touch_provider_or_generated_files():
    patch = ORACLE.read_text(encoding="utf-8")

    assert "lib/modules/permission/application/permission_service.dart" in patch
    assert "permission_provider.dart" not in patch
    assert ".freezed.dart" not in patch
    assert ".g.dart" not in patch
    assert "pubspec.yaml" not in patch
    assert "pubspec.lock" not in patch


def test_nbo_distributed_task_manifest_metadata():
    task = _task()

    assert task.task_type == "real"
    assert task.source_project == "nbo"
    assert task.role == "rejected"
    assert task.differentiating is False
    assert task.selection_status == "rejected_too_easy"
    assert set(task.docatlas_relevance) == {"project_docs", "pinned_dependency", "architecture_constraint", "private_local_context"}
