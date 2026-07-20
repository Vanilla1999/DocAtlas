from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.task_level.schemas import TaskSpec


@dataclass(frozen=True)
class ContractEvaluation:
    behavioral_contract_score: float
    form_contract_score: float
    project_convention_score: float
    version_contract_score: float | None = None
    satisfied_requirements: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "behavioral_contract_score": self.behavioral_contract_score,
            "form_contract_score": self.form_contract_score,
            "project_convention_score": self.project_convention_score,
            "version_contract_score": self.version_contract_score,
            "satisfied_requirements": self.satisfied_requirements,
            "missing_requirements": self.missing_requirements,
        }


def evaluate_contract(task: TaskSpec, workspace: Path, patch_path: Path) -> ContractEvaluation:
    patch_text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
    files = _read_workspace_files(workspace)
    combined = "\n".join(files.values()) + "\n" + patch_text
    if task.task_id == "fastapi_depends_001":
        return _evaluate_fastapi(combined)
    if task.task_id == "mixed_fastapi_project_001":
        return _evaluate_mixed(combined)
    if task.task_id == "real_project_nbo_001":
        return _evaluate_nbo_permissions(combined, patch_text, files.get("lib/modules/permission/domain/services/permission_service.dart", ""))
    if task.task_id == "real_project_nbo_permission_002":
        return _evaluate_nbo_location_deferred(combined, patch_text, files.get("lib/modules/permission/domain/services/permission_service.dart", ""))
    if task.task_id == "real_project_nbo_generated_source_001":
        return _evaluate_nbo_generated_source(combined, patch_text, files.get("lib/modules/permission/data/models/permission_info.dart", ""))
    if task.task_id == "real_project_nbo_distributed_permission_policy_001":
        return _evaluate_nbo_distributed_permission_policy(combined, patch_text, files.get("lib/modules/permission/application/permission_service.dart", ""))
    if task.task_id == "real_project_nbo_cross_module_permission_contract_001":
        return _evaluate_nbo_cross_module_permission_contract(combined, patch_text, files)
    if task.task_id == "decisive_nbo_cross_module_gate_large_001":
        return _evaluate_task33_cross_module_gate(patch_text, files)
    return ContractEvaluation(0.0, 0.0, 0.0, missing_requirements=["contract_not_defined"])


def _evaluate_fastapi(text: str) -> ContractEvaluation:
    behavioral_checks = {
        "uses_background_tasks": "BackgroundTasks" in text and "add_task" in text,
        "uses_header_token": "X-Token" in text or "Header" in text,
        "raises_401": "401" in text or "HTTP_401_UNAUTHORIZED" in text,
        "preserves_response_shape": "status" in text and "ok" in text and "user_id" in text,
    }
    form_checks = {
        "dependency_function_require_token": re.search(r"def\s+require_token\s*\(", text) is not None,
        "route_parameter_token": re.search(r"def\s+read_user\s*\([^)]*\btoken\s*:", text, re.S) is not None,
        "uses_annotated_depends": "Annotated" in text and "Depends" in text,
    }
    project_checks = {
        "shared_dependency_not_inline_only": "Depends" in text and "secret-token" not in _route_body(text, "read_user"),
        "failed_auth_no_audit_signal": "AUDIT_EVENTS == []" in text or "add_task" in text,
    }
    return _scores(behavioral_checks, form_checks, project_checks)


def _evaluate_mixed(text: str) -> ContractEvaluation:
    behavioral_checks = {
        "admin_route_exists": "/internal/admin/status" in text,
        "admin_success_shape": "admin" in text and "ok" in text,
        "error_envelope_shape": "forbidden" in text and "admin access required" in text and "error" in text,
    }
    form_checks = {
        "route_parameter_admin": re.search(r"def\s+admin_status\s*\([^)]*\badmin\s*:", text, re.S) is not None,
        "annotated_depends_require_admin": "Annotated" in text and "Depends(require_admin)" in text,
        "dependency_exception_envelope_handler": "exception_handler(" in text and "error_envelope" in text,
    }
    project_checks = {
        "uses_require_admin": "require_admin" in text and "Depends(require_admin)" in text,
        "no_duplicate_admin_auth": "X-Admin-Token" not in _route_body(text, "admin_status") and "admin-secret" not in _route_body(text, "admin_status"),
        "uses_error_envelope": "error_envelope" in text,
        "route_in_main": "src/app/main.py" in text or "/internal/admin/status" in text,
    }
    return _scores(behavioral_checks, form_checks, project_checks)


def _scores(behavioral: dict[str, bool], form: dict[str, bool], project: dict[str, bool]) -> ContractEvaluation:
    satisfied = [key for group in (behavioral, form, project) for key, value in group.items() if value]
    missing = [key for group in (behavioral, form, project) for key, value in group.items() if not value]
    return ContractEvaluation(
        behavioral_contract_score=_ratio(behavioral),
        form_contract_score=_ratio(form),
        project_convention_score=_ratio(project),
        satisfied_requirements=satisfied,
        missing_requirements=missing,
    )


def _evaluate_nbo_permissions(text: str, patch_text: str, service_text: str) -> ContractEvaluation:
    service_patch = _patch_file_body(patch_text, "lib/modules/permission/domain/services/permission_service.dart")
    code_text = service_patch or service_text or text
    behavioral_checks = {
        "adds_notification_permission": "Permission.notification" in text,
        "android_13_block_adds_notification": _android_13_adds_notification(code_text),
        "request_flow_uses_permissions_to_request": "permissionsToRequest" in text and "permsToRequestFirst" in text,
    }
    form_checks = {
        "permission_info_model_reused": "PermissionInfo" in text and "Permission.notification" in text,
        "notification_permission_named_field": "permissionNotification" in text,
        "does_not_request_location_always_in_first_batch": "Permission.locationAlways" in text and "permissionInfo.permission == Permission.locationAlways" in text,
    }
    project_checks = {
        "change_lives_in_permission_service": "Permission.notification" in service_patch,
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
        "notifier_flow_untouched": "permission_notifier.dart" not in patch_text and "requestPermission" not in patch_text,
    }
    version_checks = {
        "pinned_permission_handler_11_4_0_visible": 'permission_handler' in text and 'version: "11.4.0"' in text,
        "uses_permission_handler_11_notification_api": "Permission.notification" in text,
        "avoids_unrequested_media_permission_api": "Permission.photos" not in code_text and "Permission.videos" not in code_text and "Permission.audio" not in code_text,
    }
    satisfied = [key for group in (behavioral_checks, form_checks, project_checks, version_checks) for key, value in group.items() if value]
    missing = [key for group in (behavioral_checks, form_checks, project_checks, version_checks) for key, value in group.items() if not value]
    return ContractEvaluation(
        behavioral_contract_score=_ratio(behavioral_checks),
        form_contract_score=_ratio(form_checks),
        project_convention_score=_ratio(project_checks),
        version_contract_score=_ratio(version_checks),
        satisfied_requirements=satisfied,
        missing_requirements=missing,
    )


def _evaluate_nbo_location_deferred(text: str, patch_text: str, service_text: str) -> ContractEvaluation:
    service_patch = _patch_file_body(patch_text, "lib/modules/permission/domain/services/permission_service.dart")
    code_text = service_patch or service_text or text
    behavioral_checks = {
        "does_not_request_location_always_in_preflight": "Permission.locationAlways.request()" not in text,
        "reports_location_always_again": "permissionsToRequestAgain.add(permissionLocationAlways)" in text or "permissionsToRequestAgain.add(locationAlwaysInfo)" in text,
        "checks_foreground_location_status": "Permission.location.status" in text,
    }
    form_checks = {
        "keeps_location_always_out_of_first_batch": "p.permission != Permission.locationAlways" in text,
        "uses_existing_permission_location_always_info": "permissionLocationAlways" in text,
        "does_not_add_media_permissions": "Permission.photos" not in code_text and "Permission.videos" not in code_text and "Permission.audio" not in code_text,
    }
    project_checks = {
        "change_lives_in_permission_service": "Permission.locationAlways.request()" in service_patch or "permissionsToRequestAgain.add(permissionLocationAlways)" in service_patch,
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
        "notifier_flow_untouched": "permission_notifier.dart" not in patch_text,
    }
    version_checks = {
        "pinned_permission_handler_11_4_0_visible": 'permission_handler' in text and 'version: "11.4.0"' in text,
        "uses_permission_handler_11_location_api": "Permission.locationAlways" in text and "Permission.location.status" in text,
        "avoids_latest_media_permission_trap": "Permission.photos" not in code_text and "Permission.videos" not in code_text and "Permission.audio" not in code_text,
    }
    return _scores_with_version(behavioral_checks, form_checks, project_checks, version_checks)


def _evaluate_nbo_generated_source(text: str, patch_text: str, model_text: str) -> ContractEvaluation:
    model_patch = _patch_file_body(patch_text, "lib/modules/permission/data/models/permission_info.dart")
    code_text = model_text or text
    getter_body = code_text.split("bool get isCritical", 1)[-1] if "bool get isCritical" in code_text else ""
    behavioral_checks = {
        "adds_is_critical_getter": "bool get isCritical" in code_text,
        "critical_permissions_included": all(token in getter_body for token in ("Permission.camera", "Permission.phone", "Permission.location", "Permission.locationAlways")),
        "noncritical_media_permissions_excluded": all(token not in getter_body for token in ("Permission.photos", "Permission.videos", "Permission.audio")),
    }
    form_checks = {
        "model_extension_or_member": "extension PermissionInfoCritical" in code_text or "bool get isCritical" in model_patch,
        "uses_permission_info_source_model": "class PermissionInfo" in code_text and "permission_info.dart" in patch_text,
        "generated_stub_not_used_for_helper": "isCritical" not in _patch_file_body(patch_text, "lib/modules/permission/data/models/permission_info.freezed.dart"),
    }
    project_checks = {
        "change_lives_in_source_model": "bool get isCritical" in model_patch,
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
        "service_layer_untouched": "permission_service.dart" not in patch_text,
    }
    version_checks = {
        "pinned_permission_handler_11_4_0_visible": 'permission_handler' in text and 'version: "11.4.0"' in text,
        "uses_permission_handler_permission_enum": "Permission.locationAlways" in code_text,
        "avoids_latest_media_permission_trap": all(token not in getter_body for token in ("Permission.photos", "Permission.videos", "Permission.audio")),
    }
    return _scores_with_version(behavioral_checks, form_checks, project_checks, version_checks)


def _evaluate_nbo_distributed_permission_policy(text: str, patch_text: str, service_text: str) -> ContractEvaluation:
    service_patch = _patch_file_body(patch_text, "lib/modules/permission/application/permission_service.dart")
    code_text = service_text or text
    preflight = _method_body(code_text, "requiredForPreflight")
    behavioral_checks = {
        "android_13_notification_permission": "sdkInt >= 33" in preflight and "notificationPermission" in preflight and "Permission.notification" in code_text,
        "android_below_13_not_default_notification": "Permission.notification" not in preflight.split("sdkInt >= 33", 1)[0],
        "location_always_deferred": "Permission.locationAlways" not in preflight and "permission == Permission.locationAlways" in code_text,
    }
    form_checks = {
        "service_method_used": "requiredForPreflight(PermissionFlow flow, int sdkInt)" in code_text,
        "shared_policy_no_flow_branch": all(token not in preflight for token in ("flow == PermissionFlow.browser", "flow == PermissionFlow.scan", "switch (flow)")),
        "uses_permission_info": "PermissionInfo" in preflight and "notificationPermission" in code_text,
    }
    project_checks = {
        "change_lives_in_service": "Permission.notification" in service_patch,
        "provider_untouched": "permission_provider.dart" not in patch_text,
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
    }
    version_checks = {
        "pinned_permission_handler_11_4_0_visible": "permission_handler" in text and 'version: "11.4.0"' in text,
        "uses_notification_not_media": "Permission.notification" in code_text and all(token not in code_text for token in ("Permission.photos", "Permission.videos", "Permission.audio")),
        "dependency_files_untouched": "pubspec.yaml" not in patch_text and "pubspec.lock" not in patch_text,
    }
    return _scores_with_version(behavioral_checks, form_checks, project_checks, version_checks)


def _evaluate_nbo_cross_module_permission_contract(text: str, patch_text: str, files: dict[str, str]) -> ContractEvaluation:
    service_text = files.get("lib/modules/permission/application/permission_service.dart", "")
    browser_text = files.get("lib/modules/browser/application/browser_permission_gate.dart", "")
    scan_text = files.get("lib/modules/scan/application/scan_permission_gate.dart", "")
    flow_text = browser_text + "\n" + scan_text
    behavioral_checks = {
        "browser_uses_shared_contract": "evaluatePreflight(result) == PermissionDecision.allow" in browser_text,
        "scan_uses_shared_contract": "evaluatePreflight(result) == PermissionDecision.allow" in scan_text,
        "shared_contract_blocks_partial": "result.hasAnyMissingPermission" in service_text and "PermissionDecision.block" in service_text,
    }
    form_checks = {
        "permission_service_canonical_method": "PermissionDecision evaluatePreflight" in service_text,
        "both_gates_have_service_dependency": "PermissionService _permissionService" in browser_text and "PermissionService _permissionService" in scan_text,
        "no_duplicate_flow_interpretation": all(token not in flow_text for token in ("cameraGranted ||", "locationGranted ||", "notificationGranted ||", "hasAnyMissingPermission")),
    }
    project_checks = {
        "scan_gate_fixed_to_delegate": "scan_permission_gate.dart" in patch_text and "evaluatePreflight(result)" in _patch_file_body(patch_text, "lib/modules/scan/application/scan_permission_gate.dart"),
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
        "dependency_files_untouched": "pubspec.yaml" not in patch_text and "pubspec.lock" not in patch_text,
    }
    version_checks = {
        "pinned_permission_handler_11_4_0_visible": "permission_handler" in text and 'version: "11.4.0"' in text,
        "no_dependency_version_change": "pubspec.yaml" not in patch_text and "pubspec.lock" not in patch_text,
        "source_model_not_generated_model": "permission_result.freezed.dart" not in patch_text,
    }
    return _scores_with_version(behavioral_checks, form_checks, project_checks, version_checks)


_DART_NON_CODE = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|//[^\n]*|/\*[\s\S]*?\*/"
)
_TASK33_ENTRY_RECEIVER = r"(?:_permissionService|this\._permissionService)"
_TASK33_METHOD_RETURN_TYPES = {
    "canAcceptQueuedWork": "bool",
    "canEnter": "bool",
    "evaluateFlowEntry": "PermissionDecision",
}


def _evaluate_task33_cross_module_gate(
    patch_text: str,
    files: dict[str, str],
) -> ContractEvaluation:
    service = _strip_dart_non_code(files.get("lib/modules/permission/application/permission_service.dart", ""))
    browser = _strip_dart_non_code(files.get("lib/modules/browser/application/browser_permission_gate.dart", ""))
    scan = _strip_dart_non_code(files.get("lib/modules/scan/application/scan_permission_gate.dart", ""))
    sync = _strip_dart_non_code(files.get("lib/modules/sync/application/offline_sync_gate.dart", ""))
    entry = _task33_method_body(service, "PermissionService", "evaluateFlowEntry")
    browser_entry = _task33_method_body(browser, "BrowserPermissionGate", "canEnter")
    scan_entry = _task33_method_body(scan, "ScanPermissionGate", "canEnter")
    sync_entry = _task33_method_body(sync, "OfflineSyncGate", "canAcceptQueuedWork")
    behavioral_checks = {
        "shared_entry_decision": _task33_blocks_missing_immediate(entry),
        "browser_gate_delegates": _task33_delegates_and_requires_allow(
            browser_entry,
            required_fallback=True,
        ),
        "scan_gate_delegates": _task33_delegates_and_requires_allow(scan_entry),
        "offline_sync_uses_shared_gate": _task33_delegates_and_requires_allow(
            sync_entry,
            required_fallback=False,
        ),
    }
    form_checks = {
        "shared_service_dependencies": all(
            _task33_has_permission_service_field(source, class_name)
            for source, class_name in (
                (browser, "BrowserPermissionGate"),
                (scan, "ScanPermissionGate"),
                (sync, "OfflineSyncGate"),
            )
        ),
        "flow_entry_methods_present": all((entry, browser_entry, scan_entry, sync_entry)),
        "no_duplicate_flow_interpretation": all(
            token not in "\n".join((browser, scan, sync))
            for token in (
                "cameraGranted ||",
                "locationGranted ||",
                "nearbyGranted ||",
                "notificationGranted ||",
                "hasMissingImmediatePermission",
                "hasPartialImmediateGrant",
                "decision != PermissionDecision.block",
            )
        ),
    }
    project_checks = {
        "generated_files_untouched": ".g.dart" not in patch_text and ".freezed.dart" not in patch_text,
        "dependency_files_untouched": "pubspec.yaml" not in patch_text and "pubspec.lock" not in patch_text,
    }
    return _scores(behavioral_checks, form_checks, project_checks)


def _task33_delegates_and_requires_allow(
    source: str,
    *,
    required_fallback: bool | None = None,
) -> bool:
    if required_fallback is None:
        call_args = (
            r"\(\s*result\s*"
            r"(?:,\s*allowOfflineFallback\s*:\s*false\s*,?)?\s*\)"
        )
    else:
        fallback = "true" if required_fallback else "false"
        call_args = (
            r"\(\s*result\s*,\s*allowOfflineFallback\s*:\s*"
            + fallback
            + r"\s*,?\s*\)"
        )
    direct = re.fullmatch(
        rf"\s*return\s+{_TASK33_ENTRY_RECEIVER}\.evaluateFlowEntry\s*"
        + call_args
        + r"\s*==\s*PermissionDecision\.allow\s*;\s*",
        source,
    )
    assigned = re.fullmatch(
        r"\s*final\s+(?:PermissionDecision\s+)?(\w+)\s*=\s*"
        rf"{_TASK33_ENTRY_RECEIVER}\.evaluateFlowEntry\s*"
        + call_args
        + r"\s*;\s*return\s+\1\s*==\s*PermissionDecision\.allow\s*;\s*",
        source,
    )
    return direct is not None or assigned is not None


def _task33_blocks_missing_immediate(source: str) -> bool:
    return re.match(
        r"\s*if\s*\(\s*result\.hasMissingImmediatePermission\s*\)\s*"
        r"\{\s*return\s+PermissionDecision\.block\s*;\s*\}",
        source,
    ) is not None


def _task33_method_body(text: str, class_name: str, method: str) -> str:
    class_body = _task33_class_body(text, class_name)
    if not class_body:
        return ""
    return_type = _TASK33_METHOD_RETURN_TYPES[method]
    match = re.search(
        rf"(?m)^[ \t]*{re.escape(return_type)}[ \t]+"
        rf"{re.escape(method)}\s*\([\s\S]*?\)\s*(\{{)",
        class_body,
    )
    if match is None:
        return ""
    body_start = match.end(1)
    depth = 1
    for index in range(body_start, len(class_body)):
        if class_body[index] == "{":
            depth += 1
        elif class_body[index] == "}":
            depth -= 1
            if depth == 0:
                return class_body[body_start:index]
    return ""


def _task33_class_body(text: str, class_name: str) -> str:
    match = re.search(rf"\bclass\s+{re.escape(class_name)}\b[^{{]*(\{{)", text)
    if match is None:
        return ""
    body_start = match.end(1)
    depth = 1
    for index in range(body_start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[body_start:index]
    return ""


def _task33_has_permission_service_field(text: str, class_name: str) -> bool:
    return re.search(
        r"(?m)^[ \t]*(?:(?:late|final)\s+)*PermissionService[ \t]+"
        r"_permissionService\s*;",
        _task33_class_body(text, class_name),
    ) is not None


def _strip_dart_non_code(text: str) -> str:
    masked = list(text)
    index = 0
    while index < len(text):
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            for position in range(index, end):
                masked[position] = " "
            index = end
            continue
        if text.startswith("/*", index):
            depth = 1
            end = index + 2
            while end < len(text) and depth:
                if text.startswith("/*", end):
                    depth += 1
                    end += 2
                elif text.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            for position in range(index, end):
                if masked[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        if text[index] in {"'", '"'}:
            quote = text[index]
            delimiter = quote * 3 if text.startswith(quote * 3, index) else quote
            end = index + len(delimiter)
            while end < len(text):
                if text.startswith(delimiter, end):
                    end += len(delimiter)
                    break
                end += 2 if len(delimiter) == 1 and text[end] == "\\" else 1
            for position in range(index, min(end, len(text))):
                if masked[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        index += 1
    return "".join(masked)


def _scores_with_version(behavioral: dict[str, bool], form: dict[str, bool], project: dict[str, bool], version: dict[str, bool]) -> ContractEvaluation:
    satisfied = [key for group in (behavioral, form, project, version) for key, value in group.items() if value]
    missing = [key for group in (behavioral, form, project, version) for key, value in group.items() if not value]
    return ContractEvaluation(
        behavioral_contract_score=_ratio(behavioral),
        form_contract_score=_ratio(form),
        project_convention_score=_ratio(project),
        version_contract_score=_ratio(version),
        satisfied_requirements=satisfied,
        missing_requirements=missing,
    )


def _ratio(checks: dict[str, bool]) -> float:
    return round(sum(checks.values()) / len(checks), 4) if checks else 0.0


def _read_workspace_files(workspace: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in ("src/**/*.py", "tests/*.py", "test/*.dart", "docs/*.md", "README.md", "lib/**/*.dart", "pubspec.yaml", "pubspec.lock"):
        for path in workspace.glob(pattern):
            if path.is_file():
                try:
                    files[path.relative_to(workspace).as_posix()] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
    return files


def _route_body(text: str, function_name: str) -> str:
    match = re.search(rf"def\s+{function_name}\s*\([^)]*\).*?(?=\n\ndef\s|\n\n@app|\Z)", text, re.S)
    return match.group(0) if match else ""


def _patch_file_body(patch_text: str, file_path: str) -> str:
    match = re.search(rf"diff --git a/{re.escape(file_path)} b/{re.escape(file_path)}\n(.*?)(?=\ndiff --git |\Z)", patch_text, re.S)
    return match.group(1) if match else ""


def _method_body(text: str, method_name: str) -> str:
    match = re.search(rf"{method_name}\([^)]*\) \{{([\s\S]*?)\n  \}}", text)
    return match.group(1) if match else ""


def _android_13_adds_notification(text: str) -> bool:
    return re.search(
        r"sdkInt\s*>=\s*33[\s\S]*?Permission\.notification[\s\S]*?permissionsToRequest\.add\(\s*permissionNotification\s*\)",
        text,
    ) is not None
