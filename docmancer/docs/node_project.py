"""Node manifest and lockfile adapter for project metadata discovery."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from docmancer.docs.models import DependencyObservation


def read_node_project(
    root: Path,
    warnings: list[str],
) -> tuple[dict[str, str], list[str], list[DependencyObservation]]:
    """Read direct Node dependencies and bind them to the selected lockfile."""

    package_path = root / "package.json"
    lock_names = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    available_locks = [name for name in lock_names if (root / name).exists()]
    if not package_path.exists() and not available_locks:
        return {}, [], []

    manifest, package_manager = _read_package_json(package_path, warnings)
    selected_lock = _select_lock(package_manager, available_locks)
    lock_versions: dict[str, str] = {}
    lock_direct: dict[str, tuple[str, str]] = {}
    if selected_lock == "package-lock.json":
        lock_versions, lock_direct = _read_package_lock(root / selected_lock, warnings)
    elif selected_lock == "pnpm-lock.yaml":
        lock_versions, lock_direct = _read_pnpm_lock(root / selected_lock, warnings)
    elif selected_lock == "yarn.lock":
        lock_versions = _read_yarn_lock(root / selected_lock, manifest, warnings)

    if package_path.exists() and not available_locks:
        warnings.append("JavaScript lockfile not found; exact npm dependency versions may be unavailable.")
    if not manifest and lock_direct:
        manifest = {name: (group, specifier) for name, (group, specifier) in lock_direct.items()}

    observations: list[DependencyObservation] = []
    packages: dict[str, str] = {}
    for name, (group, specifier) in manifest.items():
        source_kind = _source_kind(specifier)
        specifier_kind = _specifier_kind(specifier)
        locked_version = lock_versions.get(name)
        resolved = locked_version
        if locked_version and source_kind == "registry":
            packages[f"npm:{name}"] = resolved
        elif specifier_kind == "exact" and source_kind == "registry":
            resolved = specifier.lstrip("=v")
            packages[f"npm:{name}"] = resolved
        version_source = (
            f"{selected_lock}_exact"
            if locked_version
            else ("package.json_exact" if resolved else "package.json_range")
        )
        observations.append(DependencyObservation(
            ecosystem="npm",
            package_name=name,
            dependency_group=group,
            specifier_kind=specifier_kind,
            specifier_raw=specifier,
            resolved_version=resolved,
            version_source=version_source,
            source_kind=source_kind,
            warnings=[] if source_kind == "registry" else [f"{name}: non-registry npm dependency source."],
        ))
    return packages, sorted(manifest), observations


def _read_package_json(path: Path, warnings: list[str]) -> tuple[dict[str, tuple[str, str]], str | None]:
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not parse package.json: {exc}")
        return {}, None
    if not isinstance(data, dict):
        warnings.append("package.json root must be an object.")
        return {}, None
    observations: dict[str, tuple[str, str]] = {}
    groups = {
        "dependencies": "dependencies",
        "devDependencies": "dev",
        "optionalDependencies": "optional",
        "peerDependencies": "peer",
    }
    for section, group in groups.items():
        values = data.get(section)
        if not isinstance(values, dict):
            continue
        for name, specifier in values.items():
            if isinstance(name, str) and isinstance(specifier, str) and specifier.strip():
                observations[name] = (group, specifier.strip())
    package_manager = data.get("packageManager")
    return observations, package_manager.strip() if isinstance(package_manager, str) else None


def _select_lock(package_manager: str | None, available: list[str]) -> str | None:
    preferred = {"npm": "package-lock.json", "pnpm": "pnpm-lock.yaml", "yarn": "yarn.lock"}
    manager = (package_manager or "").split("@", 1)[0].lower()
    selected = preferred.get(manager)
    if selected in available:
        return selected
    return next((name for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock") if name in available), None)


def _read_package_lock(path: Path, warnings: list[str]) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not parse package-lock.json: {exc}")
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    versions: dict[str, str] = {}
    direct: dict[str, tuple[str, str]] = {}
    packages = data.get("packages")
    if isinstance(packages, dict):
        root_entry = packages.get("")
        if isinstance(root_entry, dict):
            for section, group in (("dependencies", "dependencies"), ("devDependencies", "dev"), ("optionalDependencies", "optional")):
                values = root_entry.get(section)
                if isinstance(values, dict):
                    for name, specifier in values.items():
                        if isinstance(name, str) and isinstance(specifier, str):
                            direct[name] = (group, specifier)
        for name in direct:
            entry = packages.get(f"node_modules/{name}")
            version = entry.get("version") if isinstance(entry, dict) and not entry.get("link") else None
            if isinstance(version, str) and version.strip():
                versions[name] = version.strip()
    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        for name, entry in dependencies.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                continue
            version = entry.get("version")
            if isinstance(version, str) and version.strip():
                versions.setdefault(name, version.strip())
                direct.setdefault(name, ("dependencies", version.strip()))
    return versions, direct


def _read_pnpm_lock(path: Path, warnings: list[str]) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        warnings.append(f"Could not parse pnpm-lock.yaml: {exc}")
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    importers = data.get("importers")
    root = importers.get(".") if isinstance(importers, dict) else data
    if not isinstance(root, dict):
        return {}, {}
    versions: dict[str, str] = {}
    direct: dict[str, tuple[str, str]] = {}
    for section, group in (("dependencies", "dependencies"), ("devDependencies", "dev"), ("optionalDependencies", "optional")):
        values = root.get(section)
        if not isinstance(values, dict):
            continue
        for name, entry in values.items():
            if not isinstance(name, str):
                continue
            if isinstance(entry, dict):
                specifier = entry.get("specifier")
                version = entry.get("version")
            else:
                specifier = entry
                version = entry
            raw_specifier = str(specifier).strip() if specifier is not None else ""
            direct[name] = (group, raw_specifier)
            normalized = _normalize_pnpm_version(str(version)) if version is not None else None
            if normalized:
                versions[name] = normalized
    return versions, direct


def _normalize_pnpm_version(value: str) -> str | None:
    text = value.strip().strip("'\"")
    if not text or text.startswith(("link:", "workspace:", "file:")):
        return None
    text = text.lstrip("/").split("(", 1)[0]
    match = re.search(r"(?:^|[@/])(\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?)$", text)
    if match:
        return match.group(1)
    return text if re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?", text) else None


def _read_yarn_lock(path: Path, manifest: dict[str, tuple[str, str]], warnings: list[str]) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read yarn.lock: {exc}")
        return {}
    selector_versions: dict[tuple[str, str], str] = {}
    for match in re.finditer(r'(?ms)^([^\s#][^\n]*):\n(?:(?:[ \t]+.*\n)*?)[ \t]+version[: ]+["\']?([^"\'\s]+)', text):
        header, version = match.groups()
        for raw_selector in header.split(","):
            selector = raw_selector.strip().strip("'\"")
            parsed = _parse_yarn_selector(selector)
            if parsed:
                selector_versions[parsed] = version.strip()
    versions: dict[str, str] = {}
    for name, (_, specifier) in manifest.items():
        normalized_specifier = specifier.removeprefix("npm:")
        exact = selector_versions.get((name, specifier)) or selector_versions.get((name, normalized_specifier))
        if exact:
            versions[name] = exact
    return versions


def _parse_yarn_selector(selector: str) -> tuple[str, str] | None:
    separator = selector.find("@", 1 if selector.startswith("@") else 0)
    if separator <= 0:
        return None
    name = selector[:separator]
    specifier = selector[separator + 1:].removeprefix("npm:")
    return (name, specifier) if name and specifier else None


def _source_kind(specifier: str) -> str:
    text = specifier.lower()
    if text.startswith(("file:", "link:", "workspace:")):
        return "path"
    if text.startswith(("git:", "git+", "github:", "gitlab:", "bitbucket:")):
        return "git"
    if text.startswith(("http://", "https://")):
        return "url"
    return "registry"


def _specifier_kind(specifier: str) -> str:
    source_kind = _source_kind(specifier)
    if source_kind != "registry":
        return source_kind
    if specifier.startswith("npm:"):
        return "alias"
    text = specifier.strip()
    exact = r"=?v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
    if re.fullmatch(exact, text):
        return "exact"
    if (
        re.fullmatch(r"\d+(?:\.\d+)?", text)
        or re.search(r"(?:^|\.)[xX*](?:\.|$)", text)
        or text.startswith(("^", "~", ">", "<", "*", "||"))
        or any(marker in text for marker in (" ", ",", "||"))
    ):
        return "range"
    return "tag"
