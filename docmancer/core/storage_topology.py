from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docmancer.core.config import DocmancerConfig


@dataclass(frozen=True)
class StorageTopology:
    project_path: Path
    config: DocmancerConfig
    config_source: str
    library_index_root: Path | None


class StorageTopologyResolver:
    """Resolve the active index configuration from an explicit project path."""

    def __init__(self, *, fallback_config: DocmancerConfig | None = None):
        self._fallback_config = fallback_config

    def resolve(self, project_path: str | Path) -> StorageTopology:
        root = Path(project_path).expanduser().resolve()
        local_config = root / "docmancer.yaml"
        if local_config.exists():
            return StorageTopology(
                project_path=root,
                config=DocmancerConfig.from_yaml(local_config),
                config_source="project_local",
                library_index_root=root / ".docmancer" / "docs-indexes",
            )
        config = (
            self._fallback_config.model_copy(deep=True)
            if self._fallback_config is not None
            else DocmancerConfig()
        )
        return StorageTopology(
            project_path=root,
            config=config,
            config_source="fallback",
            library_index_root=None,
        )
