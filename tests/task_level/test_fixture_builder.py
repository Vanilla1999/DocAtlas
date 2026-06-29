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


def test_fastapi_require_token_convention_is_visible(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    auth_doc = (workspace / "docs/auth.md").read_text(encoding="utf-8")

    assert "require_token" in auth_doc
    assert "route as `token`" in auth_doc
    assert "X-Token" in auth_doc


def test_fastapi_gold_still_passes_after_recalibration(tmp_path: Path):
    task = _task("fastapi_depends_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    applied = _apply_gold(workspace, task.task_id)
    text = (workspace / "src/app/main.py").read_text(encoding="utf-8")

    assert applied.returncode == 0, applied.stderr
    assert "def require_token" in text
    assert "token: Annotated[str, Depends(require_token)]" in text


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


def test_mixed_admin_dependency_convention_is_visible(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    security_doc = (workspace / "docs/security.md").read_text(encoding="utf-8")

    assert "route parameter named `admin`" in security_doc
    assert "admin: Annotated[str, Depends(require_admin)]" in security_doc


def test_mixed_error_envelope_dependency_exception_convention_is_visible(tmp_path: Path):
    task = _task("mixed_fastapi_project_001")
    workspace = tmp_path / "workspace"
    materialize_fixture(task, workspace)

    errors_doc = (workspace / "docs/api-errors.md").read_text(encoding="utf-8")

    assert "Dependency-raised `HTTPException`" in errors_doc
    assert "project error-envelope handler" in errors_doc


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


def test_hidden_requirements_have_visible_sources():
    requirements = requirements_for_task("fastapi_depends_001") + requirements_for_task("mixed_fastapi_project_001")
    strict_requirements = {
        "dependency_name_require_token",
        "route_param_token",
        "annotated_admin_param",
        "dependency_raised_403",
    }

    strict = [req for req in requirements if req.requirement_id in strict_requirements]

    assert strict
    assert all(req.allowed_for_agent for req in strict)
    assert all(req.source_type in {"project_doc", "code_symbol", "issue", "library_doc"} for req in strict)
    assert all(any(path.startswith("docs/") or path.startswith("src/") or path == "README.md" for path in req.expected_files) for req in strict)


def test_oracle_only_requirements_are_not_left_unmarked():
    requirements = requirements_for_task("fastapi_depends_001") + requirements_for_task("mixed_fastapi_project_001")

    assert all(req.allowed_for_agent or req.source_type == "hidden_test" for req in requirements)
    assert not [req.requirement_id for req in requirements if req.source_type == "hidden_test"]
