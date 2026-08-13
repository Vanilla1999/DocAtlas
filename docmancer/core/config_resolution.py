from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from docmancer.core.config import DocmancerConfig


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
    """Resolve configuration without creating or modifying config files."""

    if explicit_path is not None:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"explicit config path is not a file: {path}")
        return ResolvedConfig(DocmancerConfig.from_yaml(path), "explicit", path)

    candidates: list[tuple[str, Path]] = []
    if project_path is not None:
        candidates.append(
            ("project_local", Path(project_path).expanduser().resolve() / "docmancer.yaml")
        )
    candidates.append(("cwd", Path(cwd or Path.cwd()).expanduser().resolve() / "docmancer.yaml"))
    user_path = Path(user_config_path).expanduser() if user_config_path else Path.home() / ".docmancer" / "docmancer.yaml"
    candidates.append(("user", user_path.resolve()))
    seen: set[Path] = set()
    for source, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return ResolvedConfig(DocmancerConfig.from_yaml(path), source, path)
    return ResolvedConfig(DocmancerConfig(), "defaults", None)


__all__ = ["ResolvedConfig", "resolve_config"]
