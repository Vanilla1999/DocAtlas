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
        return _evaluate_nbo_permissions(combined, patch_text)
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


def _evaluate_nbo_permissions(text: str, patch_text: str) -> ContractEvaluation:
    service_patch = _patch_file_body(patch_text, "lib/modules/permission/domain/services/permission_service.dart")
    code_text = service_patch or text
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


def _ratio(checks: dict[str, bool]) -> float:
    return round(sum(checks.values()) / len(checks), 4) if checks else 0.0


def _read_workspace_files(workspace: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in ("src/**/*.py", "tests/*.py", "docs/*.md", "README.md", "lib/**/*.dart", "pubspec.yaml", "pubspec.lock"):
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


def _android_13_adds_notification(text: str) -> bool:
    return re.search(
        r"sdkInt\s*>=\s*33[\s\S]*?Permission\.notification[\s\S]*?permissionsToRequest\.add\(\s*permissionNotification\s*\)",
        text,
    ) is not None
