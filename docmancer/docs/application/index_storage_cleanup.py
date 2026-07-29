from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from typing import Any

from docmancer.core.storage_topology import StorageTopologyResolver


@dataclass(frozen=True)
class IndexCleanupPlan:
    scope: str
    config_source: str
    storage_root: str
    db_path: str
    extracted_dir: str
    plan: list[str]


class IndexStorageCleanup:
    """Plan and apply a narrowly scoped cleanup of derived Docmancer index data."""

    _SCOPES = {"project-local", "global"}

    def preview(
        self,
        *,
        scope: str,
        project_path: str | None = None,
        global_config: Any | None = None,
        global_config_source: str = "global_config",
    ) -> IndexCleanupPlan:
        if scope not in self._SCOPES:
            raise ValueError("scope must be exactly 'project-local' or 'global'")
        if scope == "project-local":
            if not project_path or not project_path.strip():
                raise ValueError("project_path is required for project-local cleanup")
            topology = StorageTopologyResolver().resolve(project_path)
            if topology.config_source != "project_local":
                raise ValueError("project_path must resolve to a project-local Docmancer config")
            root = (topology.project_path / ".docmancer").resolve()
            config = topology.config
            config_source = topology.config_source
        else:
            if project_path:
                raise ValueError("project_path is not allowed for global cleanup")
            if global_config is None:
                raise ValueError("a resolved global Docmancer config is required for global cleanup")
            root = (Path.home() / ".docmancer").resolve()
            config = global_config
            config_source = global_config_source

        db_path = Path(config.index.db_path).expanduser().resolve()
        extracted_value = config.index.extracted_dir
        extracted_dir = (
            Path(extracted_value).expanduser().resolve()
            if extracted_value
            else (db_path.parent / "extracted").resolve()
        )
        for target in (db_path, extracted_dir):
            if not target.is_relative_to(root):
                raise ValueError(f"refusing cleanup target outside resolved Docmancer storage root: {target}")
        return IndexCleanupPlan(
            scope=scope,
            config_source=config_source,
            storage_root=str(root),
            db_path=str(db_path),
            extracted_dir=str(extracted_dir),
            plan=[str(db_path), str(extracted_dir)],
        )

    def apply(self, plan: IndexCleanupPlan) -> dict[str, Any]:
        root = Path(plan.storage_root).resolve()
        removed: list[str] = []
        for value in plan.plan:
            target = Path(value).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"refusing cleanup target outside resolved Docmancer storage root: {target}")
            if not target.exists() and not target.is_symlink():
                continue
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(value)
        return {**asdict(plan), "status": "applied", "removed": removed}

    @staticmethod
    def payload(plan: IndexCleanupPlan, *, status: str = "preview") -> dict[str, Any]:
        return {**asdict(plan), "status": status}
