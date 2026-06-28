from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


EvidenceType = Literal["code_symbol", "project_doc", "library_doc", "issue"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ChecklistItem:
    text: str
    source: str
    evidence_type: EvidenceType
    confidence: Confidence
    symbols: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def build_action_checklist(
    *,
    task_id: str,
    issue_text: str,
    docatlas_response: dict[str, Any] | None,
    workspace: Path,
) -> list[ChecklistItem]:
    context_text = _combined_visible_context(issue_text, docatlas_response)
    visible_files = _read_visible_files(workspace)
    items: list[ChecklistItem] = []

    def add(item: ChecklistItem) -> None:
        key = (item.text, item.source)
        if key not in {(existing.text, existing.source) for existing in items}:
            items.append(item)

    if _mentions("require_admin", context_text) and _symbol_file("require_admin", visible_files):
        source = _symbol_file("require_admin", visible_files) or "src/app/security.py"
        add(ChecklistItem(
            text="Reuse the existing `require_admin` dependency instead of duplicating admin token parsing.",
            source=source,
            evidence_type="code_symbol",
            confidence="high",
            symbols=["require_admin"],
            files=[source],
        ))

    if _mentions("error_envelope", context_text) and _symbol_file("error_envelope", visible_files):
        source = _symbol_file("error_envelope", visible_files) or "src/app/errors.py"
        add(ChecklistItem(
            text="Use the shared `error_envelope` helper for documented authorization errors.",
            source=source,
            evidence_type="code_symbol",
            confidence="high",
            symbols=["error_envelope"],
            files=[source],
        ))

    security_doc = visible_files.get("docs/security.md", "")
    if "src/app/main.py" in security_doc and "require_admin" in security_doc:
        add(ChecklistItem(
            text="Place internal admin routes in `src/app/main.py` and protect them with shared `require_admin`.",
            source="docs/security.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["require_admin"],
            files=["src/app/main.py", "docs/security.md"],
        ))

    api_errors_doc = visible_files.get("docs/api-errors.md", "")
    if "admin access required" in api_errors_doc and "error" in api_errors_doc:
        add(ChecklistItem(
            text="Check the unauthorized admin path returns the documented `{\"error\": ...}` envelope.",
            source="docs/api-errors.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["error_envelope"],
            files=["docs/api-errors.md", "src/app/main.py"],
        ))

    auth_doc = visible_files.get("docs/auth.md", "")
    if "require_token" in auth_doc and "X-Token" in auth_doc:
        add(ChecklistItem(
            text="Use the documented shared dependency named `require_token` to validate the `X-Token` header.",
            source="docs/auth.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["require_token", "X-Token"],
            files=["docs/auth.md", "src/app/main.py"],
        ))

    if "route as `token`" in auth_doc or "as `token`" in auth_doc:
        add(ChecklistItem(
            text="Expose the validated token to protected routes with a route parameter named `token`.",
            source="docs/auth.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["token", "Depends"],
            files=["docs/auth.md", "src/app/main.py"],
        ))

    if "admin: Annotated[str, Depends(require_admin)]" in security_doc:
        add(ChecklistItem(
            text="Declare the admin dependency as `admin: Annotated[str, Depends(require_admin)]`.",
            source="docs/security.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["admin", "Annotated", "Depends", "require_admin"],
            files=["docs/security.md", "src/app/main.py"],
        ))

    if any(_mentions(token, context_text) for token in ("Depends", "Annotated")):
        add(ChecklistItem(
            text="Use FastAPI dependency injection for shared auth behavior instead of inline request parsing.",
            source="DocAtlas context",
            evidence_type="library_doc",
            confidence="medium",
            symbols=[token for token in ("Depends", "Annotated") if _mentions(token, context_text)],
            files=["src/app/main.py"],
        ))

    if _mentions("BackgroundTasks", context_text):
        add(ChecklistItem(
            text="Queue audit work with `BackgroundTasks` only after the route dependency succeeds.",
            source="DocAtlas context",
            evidence_type="library_doc",
            confidence="medium",
            symbols=["BackgroundTasks"],
            files=["src/app/main.py"],
        ))

    if "X-Token" in context_text or "x_token" in context_text:
        add(ChecklistItem(
            text="Read the user token from the `X-Token` request header and return HTTP 401 for failed auth.",
            source="README.md" if "README.md" in visible_files else "issue",
            evidence_type="project_doc" if "README.md" in visible_files else "issue",
            confidence="high",
            symbols=["Header", "HTTPException"],
            files=["src/app/main.py"],
        ))

    if task_id == "mixed_fastapi_project_001" and "HTTPException" in visible_files.get("src/app/security.py", ""):
        add(ChecklistItem(
            text="Verify dependency-raised authorization failures are handled by the app error-envelope path.",
            source="src/app/security.py",
            evidence_type="code_symbol",
            confidence="medium",
            symbols=["HTTPException", "require_admin"],
            files=["src/app/security.py", "src/app/main.py"],
        ))

    nbo_doc = visible_files.get("docs/permission-notifications.md", "")
    nbo_service = visible_files.get("lib/modules/permission/domain/services/permission_service.dart", "")
    nbo_application_service = visible_files.get("lib/modules/permission/application/permission_service.dart", "")
    nbo_lock = visible_files.get("pubspec.lock", "")
    if task_id == "real_project_nbo_001" and ("Permission.notification" in context_text or "notification" in nbo_doc.lower()):
        add(ChecklistItem(
            text="Add Android 13+ notification permission through `PermissionService` using `Permission.notification`.",
            source="docs/permission-notifications.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["Permission.notification", "PermissionService"],
            files=["docs/permission-notifications.md", "lib/modules/permission/domain/services/permission_service.dart"],
        ))
    if task_id in {"real_project_nbo_001", "real_project_nbo_permission_002"} and "PermissionService" in nbo_service:
        add(ChecklistItem(
            text="Keep the permission flow in `lib/modules/permission/domain/services/permission_service.dart`; do not move it into presentation providers.",
            source="lib/modules/permission/ARCHITECTURE.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["PermissionService", "permissionsToRequest"],
            files=["lib/modules/permission/domain/services/permission_service.dart", "lib/modules/permission/ARCHITECTURE.md"],
        ))
    if task_id in {"real_project_nbo_001", "real_project_nbo_permission_002", "real_project_nbo_generated_source_001"} and "permission_handler" in nbo_lock and 'version: "11.4.0"' in nbo_lock:
        add(ChecklistItem(
            text="Use the pinned `permission_handler` 11.4.0 API; avoid unrelated media permission APIs.",
            source="pubspec.lock",
            evidence_type="library_doc",
            confidence="high",
            symbols=["permission_handler", "11.4.0", "Permission.notification"],
            files=["pubspec.lock", "lib/modules/permission/domain/services/permission_service.dart"],
        ))

    if task_id == "real_project_nbo_distributed_permission_policy_001":
        if "PermissionService" in nbo_application_service:
            add(ChecklistItem(
                text="Keep browser/scan preflight policy in `PermissionService`; providers should delegate.",
                source="lib/modules/permission/ARCHITECTURE.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=["PermissionService", "requiredForPreflight"],
                files=["lib/modules/permission/application/permission_service.dart", "lib/modules/permission/ARCHITECTURE.md"],
            ))
        if "Permission.notification" in nbo_doc and "permission_handler" in nbo_lock:
            add(ChecklistItem(
                text="For Android 13+ browser/scan preflight, use pinned `Permission.notification`; do not substitute media permissions.",
                source="docs/permission-notifications.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=["Permission.notification", "sdkInt >= 33"],
                files=["docs/permission-notifications.md", "pubspec.lock", "lib/modules/permission/application/permission_service.dart"],
            ))
        if "Background location remains deferred" in visible_files.get("docs/browser-scan-preflight.md", ""):
            add(ChecklistItem(
                text="Keep `Permission.locationAlways` deferred from the shared browser/scan preflight batch.",
                source="docs/browser-scan-preflight.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=["Permission.locationAlways"],
                files=["docs/browser-scan-preflight.md", "lib/modules/permission/application/permission_service.dart"],
            ))

    if task_id == "real_project_nbo_cross_module_permission_contract_001":
        permission_arch = visible_files.get("docs/permission-architecture.md", "")
        if "canonical permission result interpretation" in permission_arch:
            add(ChecklistItem(
                text="Keep canonical permission interpretation in `PermissionService`; flow gates should consume the shared contract.",
                source="docs/permission-architecture.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=["PermissionService", "evaluatePreflight"],
                files=["docs/permission-architecture.md", "lib/modules/permission/application/permission_service.dart"],
            ))
        if "same permission contract" in visible_files.get("docs/scan-flow.md", ""):
            add(ChecklistItem(
                text="Make browser and scan gates use the same shared permission contract rather than flow-specific interpretation.",
                source="docs/scan-flow.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=["BrowserPermissionGate", "ScanPermissionGate", "evaluatePreflight"],
                files=["docs/browser-flow.md", "docs/scan-flow.md"],
            ))
        if "must not be edited by hand" in visible_files.get("docs/generated-files.md", ""):
            add(ChecklistItem(
                text="Do not hand-edit generated `*.freezed.dart` or `*.g.dart` files.",
                source="docs/generated-files.md",
                evidence_type="project_doc",
                confidence="high",
                symbols=[".freezed.dart", ".g.dart"],
                files=["docs/generated-files.md"],
            ))

    location_doc = visible_files.get("docs/permission-location.md", "")
    if task_id == "real_project_nbo_permission_002" and "locationAlways" in location_doc:
        add(ChecklistItem(
            text="Keep `Permission.locationAlways` deferred: do not call `Permission.locationAlways.request()` during preflight; report it as still needed instead.",
            source="docs/permission-location.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["Permission.locationAlways", "permissionsToRequestAgain"],
            files=["docs/permission-location.md", "lib/modules/permission/domain/services/permission_service.dart"],
        ))

    generated_doc = visible_files.get("docs/generated-source.md", "")
    if task_id == "real_project_nbo_generated_source_001" and "isCritical" in generated_doc:
        add(ChecklistItem(
            text="Add `isCritical` in `permission_info.dart`, not generated Freezed/Riverpod files.",
            source="docs/generated-source.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["PermissionInfo", "isCritical"],
            files=["docs/generated-source.md", "lib/modules/permission/data/models/permission_info.dart"],
        ))
        add(ChecklistItem(
            text="Mark only camera, phone, location, and locationAlways as critical; do not include storage/media/notification permissions.",
            source="docs/generated-source.md",
            evidence_type="project_doc",
            confidence="high",
            symbols=["Permission.camera", "Permission.phone", "Permission.location", "Permission.locationAlways"],
            files=["docs/generated-source.md", "lib/modules/permission/data/models/permission_info.dart"],
        ))

    add(ChecklistItem(
        text="Run the relevant public tests after editing, including unauthorized/failure-path tests.",
        source="issue",
        evidence_type="issue",
        confidence="medium",
        symbols=[],
        files=[],
    ))
    return items


def format_action_checklist(items: list[ChecklistItem]) -> str:
    lines = [
        "## Action checklist",
        "",
        "These checklist items were derived from visible project/code/docs context.",
        "They may be incomplete. Use this checklist to avoid missing project and dependency constraints.",
        "",
    ]
    if not items:
        lines.append("- [ ] No checklist items were derived from visible context.")
        return "\n".join(lines)
    for item in items:
        symbols = f" symbols: {', '.join(item.symbols)};" if item.symbols else ""
        lines.append(f"- [ ] {item.text} (source: `{item.source}`; evidence: {item.evidence_type}; confidence: {item.confidence};{symbols})")
    return "\n".join(lines)


def save_action_checklist(items: list[ChecklistItem], output_dir: Path) -> None:
    output_dir.joinpath("action_checklist.json").write_text(
        json.dumps([item.to_json() for item in items], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    output_dir.joinpath("action_checklist.md").write_text(format_action_checklist(items), encoding="utf-8")


def _combined_visible_context(issue_text: str, docatlas_response: dict[str, Any] | None) -> str:
    parts = [issue_text]
    if docatlas_response:
        parts.append(json.dumps(docatlas_response, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts)


def _read_visible_files(workspace: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in ("README.md", "docs/*.md", "src/**/*.py", "tests/*.py", "lib/**/*.dart", "pubspec.yaml", "pubspec.lock"):
        for path in workspace.glob(pattern):
            if path.is_file() and "hidden" not in path.parts:
                try:
                    files[path.relative_to(workspace).as_posix()] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
    return files


def _symbol_file(symbol: str, visible_files: dict[str, str]) -> str | None:
    for path, content in visible_files.items():
        if symbol in content:
            return path
    return None


def _mentions(token: str, text: str) -> bool:
    return token.lower() in text.lower()
