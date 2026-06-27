from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.schemas import TaskSpec


SourceType = Literal["issue", "project_doc", "code_symbol", "library_doc", "hidden_test"]


@dataclass(frozen=True)
class ContractRequirement:
    task_id: str
    requirement_id: str
    description: str
    source_type: SourceType
    allowed_for_agent: bool
    expected_symbols: list[str] = field(default_factory=list)
    expected_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActionabilityEvaluation:
    task_id: str
    condition_id: str
    checklist_items: list[dict[str, Any]]
    critical_contract_recall: float
    critical_contract_salience: float
    action_checklist_precision: float
    action_checklist_used: bool
    patch_contract_satisfaction: dict[str, Any]
    hidden_only_requirements_excluded: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def requirements_for_task(task_id: str) -> list[ContractRequirement]:
    if task_id == "fastapi_depends_001":
        return [
            ContractRequirement(task_id, "reject_missing_x_token", "Reject missing X-Token with HTTP 401.", "project_doc", True, ["X-Token", "HTTPException"], ["README.md", "docs/auth.md", "src/app/main.py"]),
            ContractRequirement(task_id, "shared_dependency", "Use a shared FastAPI dependency for token auth.", "project_doc", True, ["Depends"], ["docs/auth.md", "src/app/main.py"]),
            ContractRequirement(task_id, "background_audit", "Queue audit with BackgroundTasks only after success.", "project_doc", True, ["BackgroundTasks"], ["src/app/main.py"]),
            ContractRequirement(task_id, "dependency_name_require_token", "Dependency function is named require_token.", "project_doc", True, ["require_token"], ["docs/auth.md", "src/app/main.py"]),
            ContractRequirement(task_id, "route_param_token", "Route dependency parameter is named token.", "project_doc", True, ["token"], ["docs/auth.md", "src/app/main.py"]),
        ]
    if task_id == "mixed_fastapi_project_001":
        return [
            ContractRequirement(task_id, "use_require_admin", "Use shared require_admin dependency.", "project_doc", True, ["require_admin"], ["docs/security.md", "src/app/security.py"]),
            ContractRequirement(task_id, "route_in_main", "Place internal admin route in src/app/main.py.", "project_doc", True, [], ["src/app/main.py"]),
            ContractRequirement(task_id, "error_envelope", "Use documented forbidden error envelope.", "project_doc", True, ["error_envelope"], ["docs/api-errors.md", "src/app/errors.py"]),
            ContractRequirement(task_id, "dependency_raised_403", "Handle dependency-raised HTTPException 403 with the envelope path.", "project_doc", True, ["HTTPException", "error_envelope"], ["docs/api-errors.md", "src/app/security.py", "src/app/main.py"]),
            ContractRequirement(task_id, "annotated_admin_param", "Use admin: Annotated[str, Depends(require_admin)].", "project_doc", True, ["Annotated", "Depends", "require_admin", "admin"], ["docs/security.md", "src/app/main.py"]),
        ]
    if task_id == "real_project_nbo_001":
        return [
            ContractRequirement(task_id, "notification_permission", "Add Android 13+ notification permission support.", "project_doc", True, ["Permission.notification"], ["docs/permission-notifications.md", "lib/modules/permission/domain/services/permission_service.dart"]),
            ContractRequirement(task_id, "permission_service_layer", "Put permission checks in PermissionService, not presentation providers.", "project_doc", True, ["PermissionService", "permissionsToRequest"], ["lib/modules/permission/ARCHITECTURE.md", "lib/modules/permission/domain/services/permission_service.dart"]),
            ContractRequirement(task_id, "pinned_permission_handler_api", "Use the pinned permission_handler 11.4.0 API.", "library_doc", True, ["permission_handler", "11.4.0", "Permission.notification"], ["pubspec.lock"]),
            ContractRequirement(task_id, "generated_files_untouched", "Do not edit generated Riverpod/Freezed files for this hand-written service change.", "project_doc", True, [".g.dart", ".freezed.dart"], ["lib/modules/permission/ARCHITECTURE.md"]),
        ]
    return []


def evaluate_actionability(
    *,
    task: TaskSpec,
    condition_id: str,
    run_output_dir: Path,
    patch_path: Path,
    trajectory_path: Path | None,
    contract: ContractEvaluation,
) -> ActionabilityEvaluation:
    items = _load_checklist(run_output_dir / "action_checklist.json")
    requirements = requirements_for_task(task.task_id)
    allowed = [req for req in requirements if req.allowed_for_agent]
    hidden = [req.requirement_id for req in requirements if not req.allowed_for_agent]

    item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items)
    recalled = [req for req in allowed if _requirement_in_text(req, item_text)]
    top_item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items[:3])
    salient = [req for req in recalled if _requirement_in_text(req, top_item_text)]
    precise = [item for item in items if _item_has_visible_source(item)]
    used_count = _checklist_used_count(items, patch_path, trajectory_path)
    warnings: list[str] = []
    if not items and condition_id.startswith("docatlas_action_checklist"):
        warnings.append("checklist_condition_without_items")

    result = ActionabilityEvaluation(
        task_id=task.task_id,
        condition_id=condition_id,
        checklist_items=items,
        critical_contract_recall=round(len(recalled) / len(allowed), 4) if allowed else 0.0,
        critical_contract_salience=round(len(salient) / len(allowed), 4) if allowed else 0.0,
        action_checklist_precision=round(len(precise) / len(items), 4) if items else 0.0,
        action_checklist_used=used_count > 0,
        patch_contract_satisfaction=contract.to_json(),
        hidden_only_requirements_excluded=hidden,
        warnings=warnings,
    )
    (run_output_dir / "actionability_evaluation.json").write_text(json.dumps(result.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    return result


def _load_checklist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _requirement_in_text(requirement: ContractRequirement, text: str) -> bool:
    if any(symbol and symbol in text for symbol in requirement.expected_symbols):
        return True
    return any(path and path in text for path in requirement.expected_files)


def _item_has_visible_source(item: dict[str, Any]) -> bool:
    source_type = item.get("evidence_type")
    source = str(item.get("source") or "")
    return source_type in {"issue", "project_doc", "code_symbol", "library_doc"} and "hidden" not in source.lower()


def _checklist_used_count(items: list[dict[str, Any]], patch_path: Path, trajectory_path: Path | None) -> int:
    patch_text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
    trajectory_text = trajectory_path.read_text(encoding="utf-8") if trajectory_path and trajectory_path.exists() else ""
    used = 0
    for item in items:
        symbols = [str(symbol) for symbol in item.get("symbols", [])]
        files = [str(file) for file in item.get("files", [])]
        if any(symbol and symbol in patch_text for symbol in symbols):
            used += 1
        elif any(file and file in trajectory_text for file in files):
            used += 1
        elif str(item.get("source") or "") in trajectory_text:
            used += 1
    return used
