"""Static Maven/Gradle dependency evidence reader.

The adapter never executes Maven or Gradle. A declared version is retained as
intent; only a dependency lock is treated as selected-version evidence.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from docmancer.docs.models import DependencyObservation


def read_java_project(
    root: Path, warnings: list[str]
) -> tuple[dict[str, str], list[str], list[DependencyObservation]]:
    pom = root / "pom.xml"
    gradle_files = [root / "build.gradle", root / "build.gradle.kts"]
    lock = root / "gradle.lockfile"
    if not pom.exists() and not lock.exists() and not any(path.exists() for path in gradle_files):
        return {}, [], []

    declared = _read_pom(pom, warnings)
    for path in gradle_files:
        declared.update(_read_gradle_declarations(path, warnings))
    locked = _read_gradle_lock(lock, warnings)
    packages: dict[str, str] = {}
    observations: list[DependencyObservation] = []
    names = sorted(set(declared) | set(locked))
    for coordinate in names:
        group, artifact = coordinate.split(":", 1)
        declaration = declared.get(coordinate)
        locked_version = locked.get(coordinate)
        resolved = locked_version
        if resolved:
            packages[f"maven:{coordinate}"] = resolved
        observations.append(DependencyObservation(
            ecosystem="maven",
            package_name=coordinate,
            dependency_group=(declaration or ("dependencies", None))[0],
            specifier_kind="exact" if locked_version else "declared",
            specifier_raw=(declaration or ("dependencies", None))[1],
            resolved_version=resolved,
            version_source="gradle.lockfile_exact" if resolved else "build_declaration_unresolved",
            source_kind="registry",
            warnings=[] if resolved else [
                f"{group}:{artifact}: build declaration is not proof of the resolved dependency version."
            ],
        ))
    if declared and not lock.exists():
        warnings.append(
            "Java dependency lock not found; pom.xml/build.gradle versions are declared intent, not resolved evidence."
        )
    return packages, sorted(declared), observations


def _read_pom(path: Path, warnings: list[str]) -> dict[str, tuple[str, str | None]]:
    if not path.exists():
        return {}
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as exc:
        warnings.append(f"Could not parse pom.xml: {exc}")
        return {}
    properties: dict[str, str] = {}
    props = next((node for node in root if _tag(node) == "properties"), None)
    if props is not None:
        properties = {_tag(child): (child.text or "").strip() for child in props}
    result: dict[str, tuple[str, str | None]] = {}
    # Only root dependencies are direct. dependencyManagement and plugin
    # dependencies are deliberately excluded from the direct-dependency list.
    for dependencies in (node for node in root if _tag(node) == "dependencies"):
        for dependency in dependencies:
            if _tag(dependency) != "dependency":
                continue
            values = {_tag(child): (child.text or "").strip() for child in dependency}
            group, artifact = values.get("groupId"), values.get("artifactId")
            if not group or not artifact:
                continue
            version = values.get("version")
            if version and version.startswith("${") and version.endswith("}"):
                version = properties.get(version[2:-1], version)
            scope = values.get("scope") or "dependencies"
            result[f"{group}:{artifact}"] = (scope, version)
    return result


def _read_gradle_declarations(path: Path, warnings: list[str]) -> dict[str, tuple[str, str | None]]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read {path.name}: {exc}")
        return {}
    result: dict[str, tuple[str, str | None]] = {}
    pattern = re.compile(
        r"\b(implementation|api|compileOnly|runtimeOnly|testImplementation)\s*\(?\s*[\"']"
        r"([^:\"']+):([^:\"']+):([^\"']+)[\"']"
    )
    for match in pattern.finditer(text):
        configuration, group, artifact, version = match.groups()
        result[f"{group}:{artifact}"] = (configuration, version.strip())
    return result


def _read_gradle_lock(path: Path, warnings: list[str]) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"Could not read gradle.lockfile: {exc}")
        return {}
    result: dict[str, str] = {}
    for line in lines:
        raw = line.split("#", 1)[0].strip()
        match = re.match(r"^([^:=\s]+):([^:=\s]+):([^=\s]+)=", raw)
        if match:
            group, artifact, version = match.groups()
            result[f"{group}:{artifact}"] = version
    return result


def _tag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]
