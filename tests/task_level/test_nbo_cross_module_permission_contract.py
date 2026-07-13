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


def test_nbo_cross_module_hidden_requirements_have_visible_sources():
    requirements = requirements_for_task(TASK_ID)

    assert requirements
    assert all(requirement.allowed_for_agent for requirement in requirements)
    assert all(requirement.source_type in {"issue", "project_doc", "code_symbol", "library_doc"} for requirement in requirements)
    assert all(requirement.expected_files for requirement in requirements)

    context = json.loads((Path("eval/task_level/oracles") / f"{TASK_ID}.context.json").read_text(encoding="utf-8"))
    assert all(item["visible_source"] for item in context["hidden_requirements"])


def test_nbo_cross_module_fixture_excludes_secrets(tmp_path: Path):
    workspace = tmp_path / TASK_ID
    materialize_fixture(_task(), workspace)
    paths = [path.relative_to(workspace).as_posix() for path in workspace.rglob("*")]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in workspace.rglob("*") if path.is_file())

    assert not any(part in {".env", "credentials", "node_modules", ".venv", "build", "dist", "coverage"} for path in paths for part in path.split("/"))
    assert "coderepo.corp" not in text
    assert "git@" not in text
    assert workspace_has_no_oracles(workspace)


def test_nbo_cross_module_docs_define_shared_permission_contract():
    architecture = (TEMPLATE / "docs/permission-architecture.md").read_text(encoding="utf-8")
    readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")

    assert "canonical permission result interpretation" in architecture
    assert "Flow-specific gates must not duplicate permission policy" in architecture
    assert "Browser and scan flows must use the shared permission contract" in readme


def test_nbo_cross_module_public_tests_exercise_both_flows():
    public_test = (TEMPLATE / "test/permission_contract_test.dart").read_text(encoding="utf-8")

    assert "BROWSER" in public_test
    assert "SCAN" in public_test
    assert "test_browser_and_scan_block_partial_permission_result" in public_test
    assert "test_allowed_result_still_proceeds_through_shared_contract" in public_test


def test_nbo_cross_module_gold_removes_or_bypasses_duplicate_flow_policy():
    patch = ORACLE.read_text(encoding="utf-8")

    assert "scan_permission_gate.dart" in patch
    assert "-    if (!result.cameraGranted || !result.locationGranted)" in patch
    assert "+    return _permissionService.evaluatePreflight(result) == PermissionDecision.allow;" in patch


def test_nbo_cross_module_gold_does_not_touch_generated_files():
    patch = ORACLE.read_text(encoding="utf-8")

    assert ".freezed.dart" not in patch
    assert ".g.dart" not in patch
    assert "pubspec.yaml" not in patch
    assert "pubspec.lock" not in patch


def test_nbo_cross_module_task_manifest_metadata():
    task = _task()

    assert task.task_type == "real"
    assert task.source_project == "nbo"
    assert task.role == "smoke"
    assert task.differentiating is False
    assert task.selection_status == "rejected_too_easy"
    assert set(task.docatlas_relevance) == {"project_docs", "architecture_constraint", "cross_module_context", "private_local_context", "generated_file_constraint"}


def test_previous_distributed_policy_candidate_marked_rejected_too_easy():
    task = _tasks()[PREVIOUS_TASK_ID]

    assert task.role == "smoke"
    assert task.differentiating is False
    assert task.selection_status == "rejected_too_easy"
