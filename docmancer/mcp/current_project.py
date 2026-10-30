"""Connection-local project routing selected by the host, never by query text."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Any


class ProjectBindingError(ValueError):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(message)


@dataclass(frozen=True)
class CurrentProject:
    root: Path
    device: int
    inode: int

    @classmethod
    def select(cls, value: str | Path) -> CurrentProject:
        root = Path(value)
        if not root.is_absolute() or ".." in root.parts or str(root) != str(value):
            raise ProjectBindingError("docs_context_target_invalid", "Host project root must be a literal absolute directory.")
        info = cls._directory(root)
        return cls(root, info.st_dev, info.st_ino)

    @staticmethod
    def _directory(root: Path) -> os.stat_result:
        # Do not follow a renamed project or a symlink into a different tree.
        # No directory listing, repository discovery or storage initialization.
        try:
            for path in (*reversed(root.parents), root):
                info = path.lstat()
                if not stat.S_ISDIR(info.st_mode):
                    raise OSError("project ancestors must be plain directories")
            if not os.access(root, os.R_OK | os.X_OK):
                raise OSError("project is not readable")
            return info
        except OSError as exc:
            raise ProjectBindingError("docs_context_target_unavailable", "Host-selected project is unavailable; reconnect with the selected project.") from exc

    def validate(self) -> None:
        info = self._directory(self.root)
        if (info.st_dev, info.st_ino) != (self.device, self.inode):
            raise ProjectBindingError("docs_context_target_changed", "Host-selected project directory changed; reconnect before continuing.")

    def arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Fill omitted routing only; selection never grants lifecycle consent."""
        args = dict(arguments)
        explicit = args.get("project_path")
        project_read = name == "get_docs_context" and not args.get("library")
        project_status = name == "docs_status" and args.get("action") == "project"
        project_prepare = name == "prepare_docs" and args.get("action") in {
            "sync_project_docs", "discover_project_docs", "prefetch_project_dependency_docs",
        }
        if explicit is None and not (project_read or project_status or project_prepare):
            return args
        self.validate()
        if explicit is not None and explicit != str(self.root):
            raise ProjectBindingError(
                "docs_context_target_conflict",
                "project_path differs from the host-selected project. Omit it for this project or reconnect to select another project.",
            )
        if project_read or project_status or project_prepare:
            args["project_path"] = str(self.root)
        # Missing scope means the whole selected repository, not only its
        # top-level documents. An explicit module still narrows the request.
        if project_read and args.get("scope") is None and not args.get("module_path"):
            args["scope"] = "all"
        return args
