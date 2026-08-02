"""Shared, read-only Dart package_config source-root resolution."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse


def resolve_dart_package_roots(project_root: str | Path) -> tuple[dict[str, Path], list[str]]:
    """Resolve package names to existing roots without escaping package_config semantics."""

    root = Path(project_root).expanduser().resolve()
    config_path = root / ".dart_tool/package_config.json"
    if not config_path.exists():
        return {}, []
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {}, [f"Could not read Dart package_config.json: {exc}"]
    packages = config.get("packages") if isinstance(config, dict) else None
    if not isinstance(packages, list):
        return {}, ["Dart package_config.json has no packages array."]

    resolved: dict[str, Path] = {}
    warnings: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        root_uri = package.get("rootUri")
        if not isinstance(name, str) or not name.strip() or not isinstance(root_uri, str):
            continue
        package_root = _resolve_root_uri(root_uri, config_path.parent)
        if package_root is None:
            warnings.append(f"Dart package root for {name} uses an unsupported URI: {root_uri}")
            continue
        try:
            package_root = package_root.resolve()
        except OSError:
            warnings.append(f"Dart package root for {name} could not be resolved: {root_uri}")
            continue
        if not package_root.is_dir():
            warnings.append(f"Dart package root for {name} was listed but not found: {root_uri}")
            continue
        resolved.setdefault(name.strip(), package_root)
    return resolved, warnings


def _resolve_root_uri(root_uri: str, config_dir: Path) -> Path | None:
    parsed = urlparse(root_uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    return config_dir / root_uri
