"""Pub manifest and lockfile adapter for project metadata discovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from docmancer.docs.models import DependencyObservation

__all__ = ["read_pub_project"]


def read_pub_project(
    root: Path,
    warnings: list[str],
) -> tuple[dict[str, str], list[str], list[DependencyObservation]]:
    """Read Pub manifest observations and bind them to pubspec.lock versions."""

    lock_path = root / "pubspec.lock"
    manifest_path = root / "pubspec.yaml"
    packages, lock_observations = _read_pubspec_lock(lock_path, warnings) if lock_path.exists() else ({}, [])
    direct_dependencies, manifest_observations = (
        _read_pubspec_yaml(manifest_path, warnings) if manifest_path.exists() else ([], [])
    )
    return packages, direct_dependencies, [*lock_observations, *manifest_observations]


def _read_pubspec_lock(path: Path, warnings: list[str]) -> tuple[dict[str, str], list[DependencyObservation]]:
    if not path.exists():
        warnings.append("pubspec.lock not found.")
        return {}, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        warnings.append(f"Could not parse pubspec.lock: {exc}")
        return {}, []
    packages = data.get("packages")
    if not isinstance(packages, dict):
        warnings.append("pubspec.lock has no packages map.")
        return {}, []
    result: dict[str, str] = {}
    observations: list[DependencyObservation] = []
    for name, entry in packages.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        version = entry.get("version")
        if isinstance(version, str) and version.strip():
            result[name] = version.strip()
            dependency = str(entry.get("dependency") or "").lower()
            group = "dev" if "dev" in dependency else "dependencies"
            source = str(entry.get("source") or "hosted").lower()
            observations.append(DependencyObservation(
                ecosystem="pub",
                package_name=name,
                dependency_group=group,
                specifier_kind="exact",
                specifier_raw=version.strip(),
                resolved_version=version.strip(),
                version_source="lockfile_exact",
                source_kind="registry" if source == "hosted" else source,
            ))
    return result, observations


def _read_pubspec_yaml(path: Path, warnings: list[str]) -> tuple[list[str], list[DependencyObservation]]:
    if not path.exists():
        warnings.append("pubspec.yaml not found.")
        return [], []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        warnings.append(f"Could not parse pubspec.yaml: {exc}")
        return [], []
    names: list[str] = []
    observations: list[DependencyObservation] = []
    for section in ("dependencies", "dev_dependencies"):
        values: Any = data.get(section)
        if isinstance(values, dict):
            for name, specifier in values.items():
                if not isinstance(name, str):
                    continue
                names.append(name)
                specifier_kind = _specifier_kind(specifier)
                observations.append(DependencyObservation(
                    ecosystem="pub",
                    package_name=name,
                    dependency_group="dev" if section == "dev_dependencies" else "dependencies",
                    specifier_kind=specifier_kind,
                    specifier_raw=_specifier_raw(specifier),
                    resolved_version=None,
                    version_source="manifest_exact" if specifier_kind == "exact" else "manifest_range",
                    source_kind=_source_kind(specifier),
                ))
    return sorted(set(names)), observations


def _specifier_raw(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().strip('"')
    if isinstance(value, dict):
        for key in ("version", "path", "git"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return str(value).strip() if value is not None else None


def _source_kind(value: Any) -> str:
    raw = value if isinstance(value, dict) else {}
    if isinstance(raw, dict):
        if "path" in raw:
            return "path"
        if "git" in raw:
            return "git"
    text = str(value).strip()
    if text.startswith("path") or "path =" in text:
        return "path"
    if text.startswith("git") or "git =" in text:
        return "git"
    return "registry"


def _specifier_kind(value: Any) -> str:
    if isinstance(value, dict):
        if "path" in value:
            return "path"
        if "git" in value:
            return "git"
        raw = value.get("version")
    else:
        raw = value
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    text = raw.strip().strip('"')
    if text.startswith("{") and "path =" in text:
        return "path"
    if text.startswith("{") and "git =" in text:
        return "git"
    version_match = re.search(r'version\s*=\s*"([^"]+)"', text)
    if version_match:
        text = version_match.group(1)
    if re.fullmatch(r"=?\d+(?:\.\d+)*(?:[-+][A-Za-z0-9_.-]+)?", text):
        return "exact"
    if text.startswith(">="):
        return "minimum"
    if text.startswith(("^", "~", ">", "<", "*")) or any(marker in text for marker in (" ", ",", "||")):
        return "range"
    return "unknown"
