"""Dart package root resolution without an implicit metadata/source read grant."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def resolve_dart_package_roots(project_root: str | Path) -> tuple[dict[str, Path], list[str]]:
    """Return unresolved without probes: this API has no finite dependency read contract.

    A project path, selected docs, or selected code files do not authorize reading
    package_config metadata or following its rootUri entries to imported sources.
    Empty output is explicitly unknown, not certification of absent dependencies.
    """
    return {}, [
        "Dart package roots unresolved: no explicit finite dependency metadata/source "
        "read contract; no package_config or imported source roots were inspected."
    ]


def _resolve_root_uri(root_uri: str, config_dir: Path) -> Path | None:
    parsed = urlparse(root_uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    return config_dir / root_uri
