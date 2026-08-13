from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.core.config_resolution import ResolvedConfig, resolve_config


@dataclass(frozen=True)
class StorageTopology:
    project_path: Path
    config: DocmancerConfig
    config_source: str
    config_path: Path | None
    config_identity: str
    library_index_root: Path | None


class StorageTopologyResolver:
    """Resolve the active index configuration from an explicit project path."""

    def __init__(
        self,
        *,
        fallback_config: DocmancerConfig | None = None,
        prefer_fallback: bool = False,
        fallback_source: str = "fallback",
    ):
        self._fallback_config = fallback_config
        self._prefer_fallback = prefer_fallback
        self._fallback_source = fallback_source

    def resolve(self, project_path: str | Path) -> StorageTopology:
        root = Path(project_path).expanduser().resolve()
        local_config = root / "docmancer.yaml"
        if local_config.is_file() and not self._prefer_fallback:
            resolved = resolve_config(project_path=root)
            return StorageTopology(
                project_path=root,
                config=resolved.config,
                config_source=resolved.source,
                config_path=resolved.path,
                config_identity=resolved.identity,
                library_index_root=root / ".docmancer" / "docs-indexes",
            )
        config = (
            self._fallback_config.model_copy(deep=True)
            if self._fallback_config is not None
            else DocmancerConfig()
        )
        resolved = ResolvedConfig(config, self._fallback_source, None)
        return StorageTopology(
            project_path=root,
            config=config,
            config_source=self._fallback_source,
            config_path=None,
            config_identity=resolved.identity,
            library_index_root=None,
        )
