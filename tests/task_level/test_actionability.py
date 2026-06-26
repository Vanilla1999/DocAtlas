from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.schemas import TaskSpec


def _task(task_id: str = "mixed_fastapi_project_001") -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        task_type="curated",
        suite="differentiation",
        repo="fixture://test",
        base_commit="fixture-base",
        issue_text="Add internal admin endpoint using project docs.",
        language="python",
        ecosystem="python",
        dependencies=(),
        setup_command="",
        test_command="pytest",
    )


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "src/app").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / "src/app/security.py").write_text(
        "from fastapi import HTTPException\n\n"
        "def require_admin():\n"
        "    raise HTTPException(status_code=403)\n",
        encoding="utf-8",
    )
    (workspace / "src/app/errors.py").write_text("def error_envelope():\n    pass\n", encoding="utf-8")
    (workspace / "docs/security.md").write_text(
        "All internal admin routes must live in `src/app/main.py` and use the shared `require_admin` dependency from `app.security`.",
        encoding="utf-8",
    )
    (workspace / "docs/api-errors.md").write_text(
        '{"error": {"code": "forbidden", "message": "admin access required"}}',
        encoding="utf-8",
    )
    (workspace / "README.md").write_text("Internal API fixture", encoding="utf-8")
    return workspace


def test_checklist_excludes_hidden_only_requirements(tmp_path: Path):
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Use require_admin for admin route.",
        docatlas_response={"context_pack": [{"content": "require_admin error envelope"}]},
        workspace=workspace,
    )

    text = "\n".join(item.text for item in items)
    assert "require_admin" in text
    assert "Annotated[str, Depends(require_admin)]" not in text
    assert "parameter named admin" not in text


def test_checklist_item_has_visible_source(tmp_path: Path):
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Use require_admin.",
        docatlas_response={"context_pack": [{"content": "require_admin"}]},
        workspace=workspace,
    )

    assert items
    assert all("hidden" not in item.source.lower() for item in items)
    assert all(item.evidence_type in {"code_symbol", "project_doc", "library_doc", "issue"} for item in items)


def test_checklist_extracts_existing_project_symbol(tmp_path: Path):
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Add admin route.",
        docatlas_response={"context_pack": [{"content": "Use require_admin from docs/security.md"}]},
        workspace=workspace,
    )

    assert any("require_admin" in item.symbols for item in items)
    assert any(item.source == "src/app/security.py" for item in items)


def test_checklist_surfaces_project_doc_constraint(tmp_path: Path):
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Add admin route.",
        docatlas_response={"context_pack": [{"content": "project security"}]},
        workspace=workspace,
    )

    assert any(item.source == "docs/security.md" and "src/app/main.py" in item.text for item in items)


def test_checklist_does_not_invent_parameter_name(tmp_path: Path):
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Use dependency injection.",
        docatlas_response={"context_pack": [{"content": "Depends require_admin"}]},
        workspace=workspace,
    )

    assert not any("admin:" in item.text for item in items)


def test_checklist_usage_detects_patch_symbol(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = _workspace(tmp_path)
    items = build_action_checklist(
        task_id="mixed_fastapi_project_001",
        issue_text="Use require_admin.",
        docatlas_response={"context_pack": [{"content": "require_admin"}]},
        workspace=workspace,
    )
    save_action_checklist(items, run_dir)
    patch = run_dir / "patch.diff"
    patch.write_text("+from .security import require_admin\n+Depends(require_admin)\n", encoding="utf-8")
    trajectory = run_dir / "trajectory.normalized.json"
    trajectory.write_text("[]", encoding="utf-8")

    result = evaluate_actionability(
        task=_task(),
        condition_id="docatlas_action_checklist_injected",
        run_output_dir=run_dir,
        patch_path=patch,
        trajectory_path=trajectory,
        contract=ContractEvaluation(1.0, 0.5, 0.75),
    )

    assert result.action_checklist_used is True
    assert "annotated_admin_param" in result.hidden_only_requirements_excluded


def test_actionability_report_marks_missing_contracts(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "action_checklist.json").write_text(json.dumps([]), encoding="utf-8")
    patch = run_dir / "patch.diff"
    patch.write_text("", encoding="utf-8")

    result = evaluate_actionability(
        task=_task("fastapi_depends_001"),
        condition_id="repo_only",
        run_output_dir=run_dir,
        patch_path=patch,
        trajectory_path=None,
        contract=ContractEvaluation(0.25, 0.0, 0.0, missing_requirements=["dependency_function_require_token"]),
    )

    assert result.critical_contract_recall == 0.0
    assert "dependency_name_require_token" in result.hidden_only_requirements_excluded
