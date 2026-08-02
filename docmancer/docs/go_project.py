"""Read-only Go module metadata adapter."""

from __future__ import annotations

import re
from pathlib import Path

from docmancer.docs.models import DependencyObservation

__all__ = ["read_go_project"]


def read_go_project(
    root: Path, warnings: list[str]
) -> tuple[dict[str, str], list[DependencyObservation], dict[str, Path]]:
    """Read Go requirements without executing the Go toolchain or using the network."""

    module_roots = _workspace_module_roots(root, warnings)
    if not module_roots and (root / "go.mod").exists():
        module_roots = [root]
    if not module_roots:
        return {}, [], {}

    vendor_versions = _read_vendor_modules(root / "vendor/modules.txt", warnings)
    packages: dict[str, str] = {}
    observations: list[DependencyObservation] = []
    source_roots: dict[str, Path] = {}
    seen: set[tuple[str, str | None, str]] = set()
    for module_root in module_roots[:100]:
        requirements, replacements = _read_go_mod(module_root / "go.mod", warnings)
        for name, requested, indirect in requirements:
            replacement = replacements.get(name)
            source_kind = "registry"
            resolved = vendor_versions.get(name)
            version_source = "vendor_modules_exact" if resolved else "go_mod_requirement"
            item_warnings: list[str] = []
            if replacement:
                replacement_path, replacement_version = replacement
                local = _local_replacement(module_root, replacement_path)
                if local is not None:
                    source_kind = "path"
                    source_roots[f"go:{name}"] = local
                    resolved = None
                    version_source = "go_mod_local_replace"
                    item_warnings.append(f"{name}: local replace cannot be bound to public module docs exactly.")
                else:
                    source_kind = "remote_replace"
                    resolved = replacement_version if replacement_version in vendor_versions.values() else None
                    version_source = "go_mod_remote_replace"
                    item_warnings.append(f"{name}: remote replace requires explicit documentation-source confirmation.")
            key = (name, requested, source_kind)
            if key in seen:
                continue
            seen.add(key)
            if resolved and source_kind == "registry":
                packages[f"go:{name}"] = resolved
            observations.append(DependencyObservation(
                ecosystem="go",
                package_name=name,
                workspace_member=str(module_root.relative_to(root)) if module_root != root else None,
                dependency_group="indirect" if indirect else "dependencies",
                specifier_kind="exact" if _canonical_go_version(requested) else "unknown",
                specifier_raw=requested,
                resolved_version=resolved,
                version_source=version_source,
                source_kind=source_kind,
                warnings=item_warnings + ([] if resolved else [
                    f"{name}: go.mod records a minimum requirement; run a controlled `go list -m` or vendor the graph for an exact selected version."
                ] if source_kind == "registry" else []),
            ))
    return packages, observations, source_roots


def _workspace_module_roots(root: Path, warnings: list[str]) -> list[Path]:
    path = root / "go.work"
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read go.work: {exc}")
        return []
    uses: list[str] = []
    in_use = False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if line == "use (":
            in_use = True
            continue
        if in_use and line == ")":
            in_use = False
            continue
        if line.startswith("use "):
            uses.append(line[4:].strip().strip('"'))
        elif in_use and line:
            uses.append(line.strip('"'))
    result: list[Path] = []
    for value in uses:
        candidate = (root / value).resolve()
        if candidate.is_dir() and (candidate / "go.mod").exists():
            result.append(candidate)
        else:
            warnings.append(f"Go workspace module was listed but not found: {value}")
    return list(dict.fromkeys(result))


def _read_go_mod(
    path: Path, warnings: list[str]
) -> tuple[list[tuple[str, str, bool]], dict[str, tuple[str, str | None]]]:
    if not path.exists():
        return [], {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read {path.name}: {exc}")
        return [], {}
    requirements: list[tuple[str, str, bool]] = []
    replacements: dict[str, tuple[str, str | None]] = {}
    section: str | None = None
    for raw in text.splitlines():
        indirect = "// indirect" in raw
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"(require|replace)\s*\(", line)
        if match:
            section = match.group(1)
            continue
        if line == ")":
            section = None
            continue
        directive = section
        value = line
        if section is None:
            match = re.match(r"(require|replace)\s+(.+)", line)
            if not match:
                continue
            directive, value = match.groups()
        if directive == "require":
            parts = value.split()
            if len(parts) >= 2:
                requirements.append((parts[0].strip('"'), parts[1].strip('"'), indirect))
        elif directive == "replace" and "=>" in value:
            left, right = [part.strip() for part in value.split("=>", 1)]
            left_parts = left.split()
            right_parts = right.split()
            if left_parts and right_parts:
                replacements[left_parts[0].strip('"')] = (
                    right_parts[0].strip('"'),
                    right_parts[1].strip('"') if len(right_parts) > 1 else None,
                )
    return requirements, replacements


def _read_vendor_modules(path: Path, warnings: list[str]) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read vendor/modules.txt: {exc}")
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^#\s+(\S+)\s+(v\S+)", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _local_replacement(module_root: Path, value: str) -> Path | None:
    if not value.startswith(("./", "../")):
        return None
    candidate = (module_root / value).resolve()
    return candidate if candidate.is_dir() else None


def _canonical_go_version(value: str) -> bool:
    return bool(re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", value))
