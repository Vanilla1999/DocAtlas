"""Cargo manifest and lockfile adapter for project metadata discovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docmancer.docs.models import DependencyObservation

__all__ = ["read_cargo_project"]


def read_cargo_project(root: Path, warnings: list[str]) -> tuple[dict[str, str], list[DependencyObservation]]:
    """Read Cargo manifest observations and bind them to Cargo.lock versions."""

    if not (root / "Cargo.toml").exists() and not (root / "Cargo.lock").exists():
        return {}, []
    manifest_observations = _read_cargo_toml(root / "Cargo.toml", warnings)
    lock_versions = _read_cargo_lock(root / "Cargo.lock", warnings)
    packages = {f"rust:{name}": version for name, version in lock_versions.items()}
    observations: list[DependencyObservation] = []
    manifest_by_name = {item.package_name: item for item in manifest_observations}
    for name, version in lock_versions.items():
        manifest = manifest_by_name.get(name)
        observations.append(DependencyObservation(
            ecosystem="rust",
            package_name=name,
            dependency_group=manifest.dependency_group if manifest else "dependencies",
            specifier_kind=manifest.specifier_kind if manifest else "exact",
            specifier_raw=manifest.specifier_raw if manifest else version,
            resolved_version=version,
            version_source="lockfile_exact",
            source_kind=manifest.source_kind if manifest else "registry",
            warnings=[] if (manifest is None or manifest.source_kind == "registry") else [f"{name}: non-registry dependency source."],
        ))
    for item in manifest_observations:
        if item.package_name not in lock_versions:
            observations.append(item)
    return packages, observations


def _read_cargo_lock(path: Path, warnings: list[str]) -> dict[str, str]:
    if not path.exists():
        warnings.append("Cargo.lock not found.")
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read Cargo.lock: {exc}")
        return {}
    result: dict[str, str] = {}
    for block in re.split(r"\n\s*\[\[package\]\]\s*\n", text):
        name_match = re.search(r'^name\s*=\s*"([^"]+)"', block, re.MULTILINE)
        version_match = re.search(r'^version\s*=\s*"([^"]+)"', block, re.MULTILINE)
        if name_match and version_match:
            result[name_match.group(1)] = version_match.group(1)
    return result


def _read_cargo_toml(path: Path, warnings: list[str]) -> list[DependencyObservation]:
    if not path.exists():
        warnings.append("Cargo.toml not found.")
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read Cargo.toml: {exc}")
        return []
    observations: list[DependencyObservation] = []
    current_group: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        section = re.fullmatch(r"\[([^\]]+)\]", line)
        if section:
            name = section.group(1)
            if name in {"dependencies", "dev-dependencies", "build-dependencies"}:
                current_group = name
            else:
                current_group = None
            continue
        if current_group is None or "=" not in line:
            continue
        name, raw_spec = [part.strip() for part in line.split("=", 1)]
        package_name = _cargo_package_name(name, raw_spec)
        specifier_kind = _specifier_kind(raw_spec)
        observations.append(DependencyObservation(
            ecosystem="rust",
            package_name=package_name,
            dependency_group={"dev-dependencies": "dev", "build-dependencies": "build"}.get(current_group, "dependencies"),
            specifier_kind=specifier_kind,
            specifier_raw=_specifier_raw(raw_spec),
            resolved_version=None,
            version_source="manifest_exact" if specifier_kind == "exact" else "manifest_range",
            source_kind=_source_kind(raw_spec),
        ))
    return observations


def _cargo_package_name(name: str, raw_spec: str) -> str:
    package_match = re.search(r'package\s*=\s*"([^"]+)"', raw_spec)
    return package_match.group(1) if package_match else name


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
