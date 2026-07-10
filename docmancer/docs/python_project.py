"""Python manifest and lockfile adapter for project metadata discovery."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from docmancer.docs.models import DependencyObservation


def read_python_project(
    root: Path,
    warnings: list[str],
) -> tuple[dict[str, str], list[str], list[DependencyObservation]]:
    """Read direct Python dependencies and bind them to uv.lock when present."""

    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"
    uv_lock = root / "uv.lock"
    poetry_lock = root / "poetry.lock"
    pdm_lock = root / "pdm.lock"
    locks = [("uv.lock", uv_lock), ("poetry.lock", poetry_lock), ("pdm.lock", pdm_lock)]
    if not pyproject.exists() and not requirements.exists() and not any(path.exists() for _, path in locks):
        return {}, [], []

    manifest = _read_pyproject_dependencies(pyproject, warnings)
    if not manifest:
        manifest = _read_requirements_dependencies(requirements, warnings)
    selected_lock = next(((name, path) for name, path in locks if path.exists()), (None, None))
    lock_name, lock_path = selected_lock
    locked_versions = _read_toml_lock_versions(lock_path, warnings) if lock_path else {}
    if manifest and not lock_path:
        warnings.append("Python lockfile not found; exact Python dependency versions may be unavailable.")

    packages: dict[str, str] = {}
    observations: list[DependencyObservation] = []
    for name, (group, specifier) in sorted(manifest.items()):
        source_kind = _source_kind(specifier)
        locked_version = locked_versions.get(name)
        resolved = locked_version if source_kind == "registry" else None
        if resolved:
            packages[f"python:{name}"] = resolved
            version_source = f"{lock_name}_exact"
        else:
            exact = _exact_version(specifier)
            resolved = exact if source_kind == "registry" else None
            if resolved:
                packages[f"python:{name}"] = resolved
            version_source = "pyproject.toml_exact" if resolved else "pyproject.toml_range"
        observations.append(DependencyObservation(
            ecosystem="python",
            package_name=name,
            dependency_group=group,
            specifier_kind="exact" if resolved else ("direct_url" if source_kind != "registry" else "range"),
            specifier_raw=specifier,
            resolved_version=resolved,
            version_source=version_source,
            source_kind=source_kind,
            warnings=[] if source_kind == "registry" else [f"{name}: non-registry Python dependency source."],
        ))
    return packages, sorted(manifest), observations


def _read_pyproject_dependencies(path: Path, warnings: list[str]) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"Could not parse pyproject.toml: {exc}")
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, tuple[str, str]] = {}
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    _add_requirements(result, project.get("dependencies"), "dependencies")
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group, values in optional.items():
            _add_requirements(result, values, f"optional:{group}")
    _add_requirements(result, data.get("dependency-groups"), "dev", grouped=True)

    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    _add_poetry_dependencies(result, poetry.get("dependencies"), "dependencies")
    poetry_groups = poetry.get("group")
    if isinstance(poetry_groups, dict):
        for group, values in poetry_groups.items():
            if isinstance(values, dict):
                _add_poetry_dependencies(result, values.get("dependencies"), str(group))
    return result


def _read_requirements_dependencies(path: Path, warnings: list[str]) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"Could not read requirements.txt: {exc}")
        return {}
    result: dict[str, tuple[str, str]] = {}
    _add_requirements(result, lines, "dependencies")
    return result


def _read_toml_lock_versions(path: Path, warnings: list[str]) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"Could not parse uv.lock: {exc}")
        return {}
    versions: dict[str, str] = {}
    for entry in data.get("package", []) if isinstance(data, dict) else []:
        if not isinstance(entry, dict):
            continue
        name, version = entry.get("name"), entry.get("version")
        if isinstance(name, str) and isinstance(version, str) and name.strip() and version.strip():
            versions.setdefault(_normalize_name(name), version.strip())
    return versions


def _add_requirements(
    result: dict[str, tuple[str, str]], values: Any, group: str, *, grouped: bool = False
) -> None:
    if grouped:
        if not isinstance(values, dict):
            return
        for group_name, requirements in values.items():
            _add_requirements(result, requirements, str(group_name))
        return
    if not isinstance(values, list):
        return
    for raw in values:
        if not isinstance(raw, str):
            continue
        requirement = raw.split("#", 1)[0].strip()
        if not requirement or requirement.startswith(("-", "--")):
            continue
        name = _requirement_name(requirement)
        if name:
            result[name] = (group, requirement)


def _add_poetry_dependencies(result: dict[str, tuple[str, str]], values: Any, group: str) -> None:
    if not isinstance(values, dict):
        return
    for name, raw in values.items():
        if not isinstance(name, str) or name.lower() == "python":
            continue
        if isinstance(raw, dict):
            path = raw.get("path")
            if isinstance(path, str) and path.strip():
                result[_normalize_name(name)] = (group, f"{name} @ {path.strip()}")
                continue
            git = raw.get("git")
            if isinstance(git, str) and git.strip():
                reference = git.strip()
                if not reference.startswith("git+"):
                    reference = f"git+{reference}"
                result[_normalize_name(name)] = (group, f"{name} @ {reference}")
                continue
        specifier = _specifier_raw(raw) or ""
        result[_normalize_name(name)] = (group, f"{name}{specifier}" if specifier else name)


def _specifier_raw(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().strip('"')
    if isinstance(value, dict):
        raw = value.get("version")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return str(value).strip() if value is not None else None


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _requirement_name(requirement: str) -> str | None:
    match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]*\])?", requirement)
    return _normalize_name(match.group(1)) if match else None


def _exact_version(specifier: str) -> str | None:
    match = re.search(r"==\s*([A-Za-z0-9][A-Za-z0-9._+!-]*)", specifier)
    return match.group(1) if match else None


def _source_kind(specifier: str) -> str:
    lowered = specifier.lower()
    if " @ git+" in lowered or "git+" in lowered:
        return "git"
    if " @ file:" in lowered or " @ ../" in lowered or " @ ./" in lowered:
        return "path"
    if " @ " in lowered:
        return "url"
    return "registry"
