from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.core.product_identity import (
    PRIMARY_CONFIG_NAME,
    resolve_home,
)


@dataclass(frozen=True)
class ResolvedConfig:
    config: DocmancerConfig
    source: str
    path: Path | None

    @property
    def identity(self) -> str:
        payload = self.config.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def resolve_config(
    *,
    explicit_path: str | Path | None = None,
    project_path: str | Path | None = None,
    cwd: str | Path | None = None,
    user_config_path: str | Path | None = None,
) -> ResolvedConfig:
    """Resolve configuration without creating or modifying config files.

    Discovery recognizes only the current ``docatlas.yaml`` identity.
    """

    if explicit_path is not None:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"explicit config path is not a file: {path}")
        return ResolvedConfig(DocmancerConfig.from_yaml(path), "explicit", path)

    candidates: list[tuple[str, Path]] = []
    if project_path is not None:
        project = Path(project_path).expanduser().resolve()
        candidates.append(("project_local", project / PRIMARY_CONFIG_NAME))
    current = Path(cwd or Path.cwd()).expanduser().resolve()
    candidates.append(("cwd", current / PRIMARY_CONFIG_NAME))
    if user_config_path is not None:
        user_path = Path(user_config_path).expanduser().resolve()
        candidates.append(("user", user_path))
    else:
        home_resolution = resolve_home()
        candidates.append(("user", home_resolution.path / PRIMARY_CONFIG_NAME))

    seen: set[Path] = set()
    for source, path in candidates:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return ResolvedConfig(DocmancerConfig.from_yaml(path), source, path)
    return ResolvedConfig(DocmancerConfig(), "defaults", None)


def resolve_mcp_config(*, explicit_path: str | Path | None = None) -> ResolvedConfig:
    """Local MCP host configuration only: never discover project/CWD settings.

    The fresh default is separate from the legacy user database. A host override
    is still subject to MemberStoragePolicy and cannot adopt an existing store.
    """
    home = resolve_home().path
    path = Path(explicit_path) if explicit_path is not None else home / "mcp-members" / PRIMARY_CONFIG_NAME
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("MCP host configuration requires an absolute literal path")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise PermissionError("MCP host configuration cannot use symlinks")
    if explicit_path is not None and not path.is_file():
        raise ValueError("explicit MCP host config does not exist")
    config = DocmancerConfig.from_yaml(path) if path.is_file() else DocmancerConfig()
    if "db_path" not in config.index.model_fields_set and not os.environ.get("DOCATLAS_INDEX_DB_PATH"):
        config.index.db_path = str(home / "mcp-members" / "members.db")
    from docmancer.core.member_storage_policy import MemberStoragePolicy
    policy = MemberStoragePolicy(home, Path(config.index.db_path), path if path.is_file() else None)
    policy.validate()
    if config.index.provider != "sqlite" or config.retrieval.default_mode != "lexical":
        raise PermissionError("local MCP member storage requires SQLite lexical configuration")
    # Extraction is never published by member preparation. Any service-derived
    # storage remains within the same trusted namespace.
    config.index.extracted_dir = str(policy.db_path.parent / "extracted")
    return ResolvedConfig(config, "mcp_host", path if path.is_file() else None)


__all__ = ["ResolvedConfig", "resolve_config", "resolve_mcp_config"]
