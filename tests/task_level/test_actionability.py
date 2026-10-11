from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from eval.task_level.context.action_checklist import build_action_checklist, save_action_checklist
from eval.task_level.evaluators.actionability import evaluate_actionability, requirements_for_task
from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.runner import load_tasks
from eval.task_level.schemas import TASKS_PATH, TaskSpec
from eval.task_level.task33_pilot import TASK33C_PILOT_TASK_ID, TASK33C_REQUIRED_TARGET_PATHS


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
    assert result.hidden_only_requirements_excluded == []




def _evaluate_task33_checklist_text(tmp_path: Path, text: str):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "action_checklist.json").write_text(
        json.dumps(
            [{
                "text": text,
                "source": "docs/permission-architecture.md",
                "evidence_type": "project_doc",
                "symbols": [],
                "files": [],
            }]
        ),
        encoding="utf-8",
    )
    patch = run_dir / "patch.diff"
    patch.write_text("", encoding="utf-8")
    return evaluate_actionability(
        task=_task(TASK33C_PILOT_TASK_ID),
        condition_id="docatlas_action_checklist",
        run_output_dir=run_dir,
        patch_path=patch,
        trajectory_path=None,
        contract=ContractEvaluation(1.0, 1.0, 1.0),
    )





