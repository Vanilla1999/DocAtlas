"""Explicit host-owned workspace binding; never derive a read target from CWD."""
from __future__ import annotations

import json
import os
from pathlib import Path

from docmancer.docs.application.project_docs_member_transaction import local_project_identity

BINDING_ENV = "DOCATLAS_PROJECT_BINDING"


def make_binding(project: Path, workspace: Path) -> dict[str, str]:
    root = project.resolve(strict=True)
    location = workspace.resolve(strict=True)
    if not root.is_dir() or not location.is_dir():
        raise ValueError("Project and workspace must be existing directories")
    return {"project_path": str(root), "project_id": local_project_identity(root),
            "workspace_path": str(location)}


def configured_binding() -> dict[str, str] | None:
    raw = os.environ.get(BINDING_ENV)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {"project_path", "project_id", "workspace_path"}:
            raise ValueError("Invalid binding fields")
        if not all(isinstance(v, str) and v for v in value.values()):
            raise ValueError("Invalid binding values")
        if not all(Path(value[k]).is_absolute() for k in ("project_path", "workspace_path")):
            raise ValueError("Binding paths must be absolute")
        if make_binding(Path(value["project_path"]), Path(value["workspace_path"])) != value:
            raise ValueError("Binding identity or canonical path changed")
        return value
    except (ValueError, OSError, TypeError) as exc:
        raise ValueError("Invalid DOCATLAS_PROJECT_BINDING; reinstall the project integration") from exc


def bind_read_target(name: str, arguments: dict) -> tuple[dict, dict | None]:
    """Bind only reads. Lifecycle operations still require their explicit target."""
    if name not in {"get_docs_context", "docs_status"}:
        return arguments, None
    binding = configured_binding()
    if binding is None:
        return arguments, None
    path = arguments.get("project_path")
    if isinstance(path, str) and path.strip():
        candidate = Path(path)
        if not candidate.is_absolute() or candidate.resolve() != Path(binding["project_path"]):
            return arguments, {"reason_code": "docs_context_target_mismatch", **binding}
    # Explicit library targets and job status never acquire a project implicitly.
    omitted = path is None or (isinstance(path, str) and not path.strip())
    if omitted and not any(arguments.get(k) for k in ("library", "canonical_id", "job_id")):
        arguments = {**arguments, "project_path": binding["project_path"]}
    return arguments, None
