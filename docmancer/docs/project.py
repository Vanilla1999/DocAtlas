from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from docmancer.docs.models import ProjectMetadata


class ProjectMetadataReader:
    def read(self, project_path: str | Path) -> ProjectMetadata:
        root = Path(project_path).expanduser().resolve()
        warnings: list[str] = []
        flutter_version, flutter_channel = self._read_fvmrc(root / ".fvmrc", warnings)
        packages = self._read_pubspec_lock(root / "pubspec.lock", warnings)
        direct_dependencies = self._read_pubspec_yaml(root / "pubspec.yaml", warnings)
        return ProjectMetadata(
            project_path=str(root),
            flutter_version=flutter_version,
            flutter_channel=flutter_channel,
            dart_version=None,
            packages=packages,
            direct_dependencies=direct_dependencies,
            warnings=warnings,
        )

    def _read_fvmrc(self, path: Path, warnings: list[str]) -> tuple[str | None, str | None]:
        if not path.exists():
            warnings.append(".fvmrc not found.")
            return None, None
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            warnings.append(f"Could not read .fvmrc: {exc}")
            return None, None
        if not raw:
            warnings.append(".fvmrc is empty.")
            return None, None

        value: str | None = None
        channel: str | None = None
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                warnings.append(f"Could not parse .fvmrc JSON: {exc}")
                return None, None
            if isinstance(data, dict):
                raw_value = data.get("flutter") or data.get("flutterSdkVersion") or data.get("version")
                raw_channel = data.get("channel")
                value = str(raw_value).strip() if raw_value else None
                channel = str(raw_channel).strip().lower() if raw_channel else None
        else:
            value = raw

        if value:
            lowered = value.lower()
            if lowered in {"stable", "beta", "dev", "master", "main"}:
                channel = "main" if lowered in {"master", "main"} else lowered
                return None, channel
            return value, channel
        return None, channel

    def _read_pubspec_lock(self, path: Path, warnings: list[str]) -> dict[str, str]:
        if not path.exists():
            warnings.append("pubspec.lock not found.")
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            warnings.append(f"Could not parse pubspec.lock: {exc}")
            return {}
        packages = data.get("packages")
        if not isinstance(packages, dict):
            warnings.append("pubspec.lock has no packages map.")
            return {}
        result: dict[str, str] = {}
        for name, entry in packages.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                continue
            version = entry.get("version")
            if isinstance(version, str) and version.strip():
                result[name] = version.strip()
        return result

    def _read_pubspec_yaml(self, path: Path, warnings: list[str]) -> list[str]:
        if not path.exists():
            warnings.append("pubspec.yaml not found.")
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            warnings.append(f"Could not parse pubspec.yaml: {exc}")
            return []
        names: list[str] = []
        for section in ("dependencies", "dev_dependencies"):
            values: Any = data.get(section)
            if isinstance(values, dict):
                names.extend(name for name in values if isinstance(name, str))
        return sorted(set(names))
