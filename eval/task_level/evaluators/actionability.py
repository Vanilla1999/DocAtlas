from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.schemas import TaskSpec
from eval.task_level.task33_pilot import TASK33C_PILOT_TASK_ID


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
    match_all_symbols: bool = False


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
    if task_id == "real_project_nbo_permission_002":
        return [
            ContractRequirement(task_id, "location_always_deferred", "Do not request Permission.locationAlways during browser/scan preflight.", "project_doc", True, ["Permission.locationAlways", "permissionsToRequestAgain"], ["docs/permission-location.md", "lib/modules/permission/domain/services/permission_service.dart"]),
            ContractRequirement(task_id, "permission_service_layer", "Keep deferred location policy in PermissionService, not presentation providers.", "project_doc", True, ["PermissionService"], ["lib/modules/permission/ARCHITECTURE.md", "lib/modules/permission/domain/services/permission_service.dart"]),
            ContractRequirement(task_id, "pinned_permission_handler_api", "Use the pinned permission_handler 11.4.0 Permission API.", "library_doc", True, ["permission_handler", "11.4.0", "Permission.locationAlways"], ["pubspec.lock"]),
            ContractRequirement(task_id, "generated_files_untouched", "Do not edit generated Riverpod/Freezed files for this service-policy change.", "project_doc", True, [".g.dart", ".freezed.dart"], ["lib/modules/permission/ARCHITECTURE.md"]),
        ]
    if task_id == "real_project_nbo_generated_source_001":
        return [
            ContractRequirement(task_id, "source_model_helper", "Add isCritical to the PermissionInfo source model.", "project_doc", True, ["PermissionInfo", "isCritical"], ["docs/generated-source.md", "lib/modules/permission/data/models/permission_info.dart"]),
            ContractRequirement(task_id, "critical_permission_set", "Classify only camera, phone, foreground location, and background location as critical.", "project_doc", True, ["Permission.camera", "Permission.phone", "Permission.location", "Permission.locationAlways"], ["docs/generated-source.md"]),
            ContractRequirement(task_id, "generated_files_untouched", "Do not hand-edit generated Freezed/Riverpod files.", "project_doc", True, [".g.dart", ".freezed.dart"], ["docs/generated-source.md", "lib/modules/permission/ARCHITECTURE.md"]),
            ContractRequirement(task_id, "pinned_permission_handler_api", "Use the pinned permission_handler 11.4.0 Permission enum.", "library_doc", True, ["permission_handler", "11.4.0", "Permission.locationAlways"], ["pubspec.lock"]),
        ]
    if task_id == "real_project_nbo_distributed_permission_policy_001":
        return [
            ContractRequirement(task_id, "service_owns_policy", "PermissionService owns browser/scan preflight policy.", "project_doc", True, ["PermissionService", "requiredForPreflight"], ["lib/modules/permission/ARCHITECTURE.md", "lib/modules/permission/application/permission_service.dart"]),
            ContractRequirement(task_id, "provider_delegates", "Presentation provider delegates and does not encode platform policy.", "project_doc", True, ["PermissionProvider", "requiredForPreflight"], ["lib/modules/permission/ARCHITECTURE.md", "lib/modules/permission/presentation/permission_provider.dart"]),
            ContractRequirement(task_id, "android_13_notification", "Android 13+ notification permission is required for notification-dependent scan/browser flows.", "project_doc", True, ["Permission.notification", "sdkInt >= 33"], ["docs/permission-notifications.md"]),
            ContractRequirement(task_id, "location_always_deferred", "Background location remains deferred from browser/scan preflight.", "project_doc", True, ["Permission.locationAlways"], ["docs/browser-scan-preflight.md", "lib/modules/permission/ARCHITECTURE.md"]),
            ContractRequirement(task_id, "pinned_permission_handler", "Use pinned permission_handler 11.4.0 API and avoid media permission substitutes.", "library_doc", True, ["permission_handler", "11.4.0", "Permission.notification"], ["pubspec.lock", "docs/permission-notifications.md"]),
        ]
    if task_id == "real_project_nbo_cross_module_permission_contract_001":
        return [
            ContractRequirement(task_id, "permission_module_canonical", "Permission module owns canonical permission interpretation.", "project_doc", True, ["PermissionService", "evaluatePreflight"], ["docs/permission-architecture.md", "lib/modules/permission/application/permission_service.dart"]),
            ContractRequirement(task_id, "browser_scan_shared_contract", "Browser and scan flows share the same permission contract.", "project_doc", True, ["BrowserPermissionGate", "ScanPermissionGate"], ["README.md", "docs/browser-flow.md", "docs/scan-flow.md"]),
            ContractRequirement(task_id, "no_flow_duplicate_policy", "Flow gates must not duplicate permission policy.", "project_doc", True, ["evaluatePreflight"], ["docs/permission-architecture.md"]),
            ContractRequirement(task_id, "generated_files_untouched", "Generated permission result files must not be edited.", "project_doc", True, [".freezed.dart", ".g.dart"], ["docs/generated-files.md"]),
        ]
    if task_id == TASK33C_PILOT_TASK_ID:
        return [
            ContractRequirement(
                task_id,
                "shared_entry_decision",
                "PermissionService.evaluateFlowEntry owns the canonical flow-entry decision.",
                "project_doc",
                True,
                ["PermissionService", "evaluateFlowEntry", "PermissionDecision"],
                [
                    "docs/permission-architecture.md",
                    "lib/modules/permission/application/permission_service.dart",
                ],
                match_all_symbols=True,
            ),
            ContractRequirement(
                task_id,
                "browser_gate_delegates",
                "BrowserPermissionGate delegates flow entry to PermissionService.evaluateFlowEntry.",
                "project_doc",
                True,
                ["BrowserPermissionGate", "evaluateFlowEntry"],
                [
                    "docs/browser-flow.md",
                    "lib/modules/browser/application/browser_permission_gate.dart",
                ],
                match_all_symbols=True,
            ),
            ContractRequirement(
                task_id,
                "scan_gate_delegates",
                "ScanPermissionGate delegates flow entry to PermissionService.evaluateFlowEntry.",
                "project_doc",
                True,
                ["ScanPermissionGate", "evaluateFlowEntry"],
                [
                    "docs/scan-flow.md",
                    "lib/modules/scan/application/scan_permission_gate.dart",
                ],
                match_all_symbols=True,
            ),
            ContractRequirement(
                task_id,
                "offline_sync_uses_shared_gate",
                "OfflineSyncGate uses PermissionService.evaluateFlowEntry before accepting queued work.",
                "project_doc",
                True,
                ["OfflineSyncGate", "evaluateFlowEntry"],
                [
                    "docs/offline-sync.md",
                    "lib/modules/sync/application/offline_sync_gate.dart",
                ],
                match_all_symbols=True,
            ),
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
    if requirement.match_all_symbols:
        return bool(requirement.expected_symbols) and all(
            symbol and symbol in text for symbol in requirement.expected_symbols
        )
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
