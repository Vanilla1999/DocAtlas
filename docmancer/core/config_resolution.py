from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import dataclass
from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.core.product_identity import (
    LEGACY_CONFIG_NAME,
    PRIMARY_CONFIG_NAME,
    resolve_home,
    warn_if_legacy_home,
)


@dataclass(frozen=True)
class ResolvedConfig:
    config: DocmancerConfig
    source: str
    path: Path | None
    legacy_compatibility: bool = False

    @property
    def identity(self) -> str:
        payload = self.config.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def _legacy_config_warning(path: Path) -> None:
    warnings.warn(
        f"Legacy DocAtlas config name {LEGACY_CONFIG_NAME!r} is deprecated at {path}; "
        f"rename it to {PRIMARY_CONFIG_NAME!r} during the 1.x compatibility window.",
        DeprecationWarning,
        stacklevel=3,
    )


def _is_legacy_config_path(path: Path) -> bool:
    return path.name == LEGACY_CONFIG_NAME


def resolve_config(
    *,
    explicit_path: str | Path | None = None,
    project_path: str | Path | None = None,
    cwd: str | Path | None = None,
    user_config_path: str | Path | None = None,
) -> ResolvedConfig:
    """Resolve configuration without creating or modifying config files.

    New discovery prefers ``docatlas.yaml``. The old ``docmancer.yaml`` name is
    accepted only as a compatibility candidate and emits a deprecation warning.
    Global discovery resolves inside the DocAtlas home; it never falls back to
    the legacy ``~/.docmancer`` directory unless ``DOCMANCER_HOME`` was set
    explicitly by the caller.
    """

    if explicit_path is not None:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"explicit config path is not a file: {path}")
        legacy = _is_legacy_config_path(path)
        if legacy:
            _legacy_config_warning(path)
        return ResolvedConfig(
            DocmancerConfig.from_yaml(path),
            "explicit",
            path,
            legacy_compatibility=legacy,
        )

    candidates: list[tuple[str, Path, bool]] = []
    if project_path is not None:
        project = Path(project_path).expanduser().resolve()
        candidates.extend(
            [
                ("project_local", project / PRIMARY_CONFIG_NAME, False),
                ("project_local", project / LEGACY_CONFIG_NAME, True),
            ]
        )
    current = Path(cwd or Path.cwd()).expanduser().resolve()
    candidates.extend(
        [
            ("cwd", current / PRIMARY_CONFIG_NAME, False),
            ("cwd", current / LEGACY_CONFIG_NAME, True),
        ]
    )
    if user_config_path is not None:
        user_path = Path(user_config_path).expanduser().resolve()
        candidates.append(("user", user_path, _is_legacy_config_path(user_path)))
    else:
        home_resolution = resolve_home()
        warn_if_legacy_home(home_resolution)
        candidates.extend(
            [
                ("user", home_resolution.path / PRIMARY_CONFIG_NAME, False),
                ("user", home_resolution.path / LEGACY_CONFIG_NAME, True),
            ]
        )

    seen: set[Path] = set()
    for source, path, legacy in candidates:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            if legacy:
                _legacy_config_warning(path)
            return ResolvedConfig(
                DocmancerConfig.from_yaml(path),
                source,
                path,
                legacy_compatibility=legacy,
            )
    return ResolvedConfig(DocmancerConfig(), "defaults", None)


__all__ = ["ResolvedConfig", "resolve_config"]
