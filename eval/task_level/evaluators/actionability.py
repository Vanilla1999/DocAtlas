from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)

from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.schemas import TaskSpec
from eval.task_level.task33_pilot import TASK33C_PILOT_TASK_ID


SourceType = Literal["issue", "project_doc", "code_symbol", "library_doc", "hidden_test"]
MetricSource = Literal[
    "model_visible_action_packet",
    "invalid_model_visible_projection",
    "legacy_action_checklist",
]


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
    metric_source: MetricSource = "legacy_action_checklist"
    requirement_recall: float = 0.0
    requirement_precision: float = 0.0
    critical_invariant_recall: float = 0.0
    source_coverage: float = 0.0
    behavioral_scope_coverage: float = 0.0
    citation_fidelity: float = 0.0
    model_visible_omissions: int = 0
    projection_status: str | None = None
    projection_tokens: int | None = None
    projection_omissions: dict[str, int] = field(default_factory=dict)
    mutation_ready: bool | None = None
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
    projection, projection_error = _load_projection(
        run_output_dir / "model_visible_patch_context.json",
        run_output_dir / "model_visible_evidence_snapshot.json",
    )
    requirements = requirements_for_task(task.task_id)
    allowed = [req for req in requirements if req.allowed_for_agent]
    hidden = [req.requirement_id for req in requirements if not req.allowed_for_agent]
    warnings: list[str] = []
    if projection_error is not None:
        warnings.append(f"invalid_model_visible_projection:{projection_error}")

    if projection is not None:
        metrics = _projection_metrics(projection, allowed)
        item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items)
        recalled = [req for req in allowed if _requirement_in_text(req, item_text)]
        top_item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items[:3])
        salient = [req for req in recalled if _requirement_in_text(req, top_item_text)]
        precise = [item for item in items if _item_has_visible_source(item)]
        used_count = _checklist_used_count(items, patch_path, trajectory_path)
        result = ActionabilityEvaluation(
            task_id=task.task_id,
            condition_id=condition_id,
            checklist_items=items,
            critical_contract_recall=(
                round(len(recalled) / len(allowed), 4) if allowed else 0.0
            ),
            critical_contract_salience=(
                round(len(salient) / len(allowed), 4) if allowed else 0.0
            ),
            action_checklist_precision=(
                round(len(precise) / len(items), 4) if items else 0.0
            ),
            action_checklist_used=used_count > 0,
            patch_contract_satisfaction=contract.to_json(),
            hidden_only_requirements_excluded=hidden,
            metric_source="model_visible_action_packet",
            requirement_recall=metrics["requirement_recall"],
            requirement_precision=metrics["requirement_precision"],
            critical_invariant_recall=metrics["critical_invariant_recall"],
            source_coverage=metrics["source_coverage"],
            behavioral_scope_coverage=metrics["behavioral_scope_coverage"],
            citation_fidelity=metrics["citation_fidelity"],
            model_visible_omissions=metrics["model_visible_omissions"],
            projection_status=str(projection.get("status") or "unknown"),
            projection_tokens=_int_or_none(projection.get("estimated_tokens")),
            projection_omissions=metrics["projection_omissions"],
            mutation_ready=(
                bool(projection.get("mutation_ready"))
                if "mutation_ready" in projection else None
            ),
            warnings=warnings,
        )
        if result.projection_status in {"ok", "truncated"} and result.mutation_ready is not True:
            warnings.append("successful_projection_without_mutation_readiness")
            result = ActionabilityEvaluation(**{**result.to_json(), "warnings": warnings})
    elif projection_error is not None:
        result = ActionabilityEvaluation(
            task_id=task.task_id,
            condition_id=condition_id,
            checklist_items=items,
            critical_contract_recall=0.0,
            critical_contract_salience=0.0,
            action_checklist_precision=0.0,
            action_checklist_used=False,
            patch_contract_satisfaction=contract.to_json(),
            hidden_only_requirements_excluded=hidden,
            metric_source="invalid_model_visible_projection",
            projection_status="invalid",
            warnings=warnings,
        )
    else:
        item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items)
        recalled = [req for req in allowed if _requirement_in_text(req, item_text)]
        top_item_text = "\n".join(json.dumps(item, sort_keys=True) for item in items[:3])
        salient = [req for req in recalled if _requirement_in_text(req, top_item_text)]
        precise = [item for item in items if _item_has_visible_source(item)]
        used_count = _checklist_used_count(items, patch_path, trajectory_path)
        if not items and condition_id.startswith("docatlas_action_checklist"):
            warnings.append("checklist_condition_without_items")
        recall = round(len(recalled) / len(allowed), 4) if allowed else 0.0
        precision = round(len(precise) / len(items), 4) if items else 0.0
        salience = round(len(salient) / len(allowed), 4) if allowed else 0.0
        result = ActionabilityEvaluation(
            task_id=task.task_id,
            condition_id=condition_id,
            checklist_items=items,
            critical_contract_recall=recall,
            critical_contract_salience=salience,
            action_checklist_precision=precision,
            action_checklist_used=used_count > 0,
            patch_contract_satisfaction=contract.to_json(),
            hidden_only_requirements_excluded=hidden,
            metric_source="legacy_action_checklist",
            requirement_recall=recall,
            requirement_precision=precision,
            critical_invariant_recall=salience,
            warnings=warnings,
        )

    (run_output_dir / "actionability_evaluation.json").write_text(
        json.dumps(result.to_json(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _load_checklist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _load_projection(
    path: Path,
    snapshot_path: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "artifact_or_snapshot_unreadable"
    if not isinstance(data, dict) or not isinstance(snapshot, dict):
        return None, "artifact_or_snapshot_not_object"
    errors = validate_model_visible_projection(
        data,
        snapshot=snapshot,
        max_tokens=2_000,
    )
    if errors:
        return None, ";".join(errors)
    return data, None


def _projection_metrics(
    projection: dict[str, Any],
    requirements: list[ContractRequirement],
) -> dict[str, Any]:
    invariants = _dict_rows(projection.get("invariants"))
    guidance = _dict_rows(projection.get("implementation_guidance"))
    acceptance = _dict_rows(projection.get("acceptance_conditions"))
    checks = projection.get("checks") if isinstance(projection.get("checks"), dict) else {}
    check_rows = [
        row
        for values in checks.values()
        for row in _dict_rows(values)
    ]
    behavioral_rows = [*invariants, *guidance]
    requirement_rows = [*invariants, *guidance, *acceptance]
    requirement_row_texts = [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in requirement_rows]
    recalled = [
        req for req in requirements
        if any(_requirement_in_text(req, text) for text in requirement_row_texts)
    ]
    matched_rows = [
        text for text in requirement_row_texts
        if any(_requirement_in_text(req, text) for req in requirements)
    ]

    invariant_text = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) for row in invariants
    )
    invariant_recalled = [
        req for req in requirements if _requirement_in_text(req, invariant_text)
    ]

    source_paths = {
        str(row.get("path_or_url") or row.get("path") or "")
        for row in _dict_rows(projection.get("sources"))
    }
    targets = projection.get("targets") if isinstance(projection.get("targets"), dict) else {}
    covered_sources = [
        req for req in requirements
        if any(path in source_paths for path in req.expected_files)
    ]

    source_path_by_id = {
        str(row.get("evidence_id") or ""): str(row.get("path_or_url") or row.get("path") or "")
        for row in _dict_rows(projection.get("sources"))
        if str(row.get("evidence_id") or "")
    }
    valid_source_ids = set(source_path_by_id)
    behavioral_covered: list[ContractRequirement] = []
    all_refs: list[str] = []
    valid_refs: list[str] = []
    for row in [*behavioral_rows, *acceptance, *check_rows]:
        refs = [str(value) for value in row.get("evidence_ids") or [] if str(value)]
        all_refs.extend(refs)
        valid_refs.extend(ref for ref in refs if ref in valid_source_ids)
    for req in requirements:
        for row in behavioral_rows:
            row_text = json.dumps(row, sort_keys=True, ensure_ascii=False)
            refs = [str(value) for value in row.get("evidence_ids") or [] if str(value)]
            expected_sources = set(req.expected_files) & source_paths
            cited_sources = {source_path_by_id[ref] for ref in refs if ref in source_path_by_id}
            if (
                _requirement_in_text(req, row_text)
                and expected_sources
                and cited_sources & expected_sources
            ):
                behavioral_covered.append(req)
                break

    omissions = _normalized_omission_counts(projection.get("omitted_counts"))
    if projection.get("status") == "insufficient_evidence":
        missing = projection.get("missing")
        if isinstance(missing, list):
            omissions["missing"] = len([value for value in missing if str(value).strip()])

    count = len(requirements)
    return {
        "requirement_recall": round(len(recalled) / count, 4) if count else 0.0,
        "requirement_precision": round(len(matched_rows) / len(requirement_rows), 4) if requirement_rows else 0.0,
        "critical_invariant_recall": round(len(invariant_recalled) / count, 4) if count else 0.0,
        "source_coverage": round(len(covered_sources) / count, 4) if count else 0.0,
        "behavioral_scope_coverage": round(len(behavioral_covered) / count, 4) if count else 0.0,
        "citation_fidelity": round(len(valid_refs) / len(all_refs), 4) if all_refs else 0.0,
        "model_visible_omissions": sum(omissions.values()),
        "projection_omissions": omissions,
    }


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _normalized_omission_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(raw, bool):
            count = int(raw)
        elif isinstance(raw, int):
            count = max(0, raw)
        else:
            continue
        if count:
            result[str(key)] = count
    return result


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


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
