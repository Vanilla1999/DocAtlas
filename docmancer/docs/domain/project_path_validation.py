"""Typed project-path validation shared by read and mutation boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal


ProjectPathReason = Literal[
    "project_path_not_found", "project_path_not_directory", "project_path_inaccessible",
]


class ProjectPathValidationError(ValueError):
    def __init__(self, reason_code: ProjectPathReason, path: Path):
        self.reason_code = reason_code
        self.path = path
        super().__init__(f"{reason_code}: {path}")


@dataclass(frozen=True, slots=True)
class ValidatedProjectPath:
    path: Path
    exists: bool = True
    is_directory: bool = True
    accessible: bool = True

    @property
    def value(self) -> str:
        return str(self.path)


def validate_project_path(project_path: str | Path) -> ValidatedProjectPath:
    """Resolve a project path without creating it or touching an index."""

    raw = Path(project_path).expanduser()
    # strict=False avoids a FileNotFoundError before we can return a typed reason.
    resolved = raw.resolve(strict=False)
    if not resolved.exists():
        raise ProjectPathValidationError("project_path_not_found", resolved)
    if not resolved.is_dir():
        raise ProjectPathValidationError("project_path_not_directory", resolved)
    try:
        # access() covers execute/traversal while scandir proves the directory is readable.
        if not os.access(resolved, os.R_OK | os.X_OK):
            raise PermissionError
        with os.scandir(resolved) as iterator:
            next(iterator, None)
    except (OSError, PermissionError):
        raise ProjectPathValidationError("project_path_inaccessible", resolved) from None
    return ValidatedProjectPath(path=resolved)


__all__ = [
    "ProjectPathReason", "ProjectPathValidationError", "ValidatedProjectPath",
    "validate_project_path",
]
