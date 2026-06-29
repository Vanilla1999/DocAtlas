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


def test_contract_evaluator_separates_behavior_and_form_fastapi(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "src/app").mkdir(parents=True)
    (workspace / "src/app/main.py").write_text(
        "from typing import Annotated\n"
        "from fastapi import BackgroundTasks, Depends, Header, HTTPException\n"
        "def verify_token(x_token: Annotated[str | None, Header()] = None):\n"
        "    raise HTTPException(status_code=401)\n"
        "TokenDependency = Annotated[str, Depends(verify_token)]\n"
        "def read_user(user_id: int, background_tasks: BackgroundTasks, _token: TokenDependency):\n"
        "    background_tasks.add_task(lambda: None)\n"
        "    return {'user_id': user_id, 'status': 'ok'}\n",
        encoding="utf-8",
    )
    patch = tmp_path / "patch.diff"
    patch.write_text("", encoding="utf-8")

    result = evaluate_contract(_task("fastapi_depends_001"), workspace, patch)

    assert result.behavioral_contract_score == 1.0
    assert result.form_contract_score < 1.0
    assert "dependency_function_require_token" in result.missing_requirements


def test_contract_evaluator_separates_behavior_and_form_mixed(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "src/app").mkdir(parents=True)
    (workspace / "src/app/main.py").write_text(
        "from fastapi import Depends, FastAPI\n"
        "from .security import require_admin\n"
        "from .errors import error_envelope\n"
        "app = FastAPI()\n"
        "@app.exception_handler(403)\n"
        "async def forbidden_handler(request, exc):\n"
        "    return error_envelope('forbidden', 'admin access required', 403)\n"
        "@app.get('/internal/admin/status')\n"
        "def admin_status(_admin: str = Depends(require_admin)):\n"
        "    return {'admin': 'ok'}\n",
        encoding="utf-8",
    )
    (workspace / "src/app/security.py").write_text("def require_admin(): pass\n", encoding="utf-8")
    patch = tmp_path / "patch.diff"
    patch.write_text("", encoding="utf-8")

    result = evaluate_contract(_task("mixed_fastapi_project_001"), workspace, patch)

    assert result.behavioral_contract_score == 1.0
    assert result.form_contract_score < 1.0
    assert "route_parameter_admin" in result.missing_requirements


def test_contract_evaluator_accepts_documented_dependency_exception_envelope_handler(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "src/app").mkdir(parents=True)
    (workspace / "src/app/main.py").write_text(
        "from typing import Annotated\n"
        "from fastapi import Depends, FastAPI\n"
        "from .security import require_admin\n"
        "from .errors import error_envelope\n"
        "app = FastAPI()\n"
        "@app.exception_handler(403)\n"
        "async def forbidden_handler(request, exc):\n"
        "    return error_envelope('forbidden', 'admin access required', 403)\n"
        "@app.get('/internal/admin/status')\n"
        "def admin_status(admin: Annotated[str, Depends(require_admin)]):\n"
        "    return {'admin': 'ok'}\n",
        encoding="utf-8",
    )
    (workspace / "src/app/security.py").write_text("def require_admin(): pass\n", encoding="utf-8")
    patch = tmp_path / "patch.diff"
    patch.write_text("", encoding="utf-8")

    result = evaluate_contract(_task("mixed_fastapi_project_001"), workspace, patch)

    assert result.form_contract_score == 1.0
    assert "dependency_exception_envelope_handler" in result.satisfied_requirements


def test_contract_form_requirements_are_marked_discoverable():
    fastapi = {req.requirement_id: req for req in requirements_for_task("fastapi_depends_001")}
    mixed = {req.requirement_id: req for req in requirements_for_task("mixed_fastapi_project_001")}

    assert fastapi["dependency_name_require_token"].source_type == "project_doc"
    assert "docs/auth.md" in fastapi["dependency_name_require_token"].expected_files
    assert fastapi["route_param_token"].allowed_for_agent is True
    assert mixed["annotated_admin_param"].source_type == "project_doc"
    assert "docs/security.md" in mixed["annotated_admin_param"].expected_files
    assert mixed["dependency_raised_403"].source_type == "project_doc"
