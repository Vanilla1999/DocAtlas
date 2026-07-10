from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from docmancer.docs.models import DependencyObservation, ProjectDocsCandidate, ProjectMetadata, SOURCE_CLASS_PROJECT_FILE


DOC_FILE_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".dart_tool",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "build",
    "dist",
    "target",
    ".next",
    ".turbo",
    "coverage",
    "htmlcov",
    "__pycache__",
}
ROOT_DOC_FILES = {
    "readme": "root_readme",
    "architecture": "architecture",
    "arch": "architecture",
    "changelog": "changelog",
    "contributing": "contributing",
    "security": "security",
    "license": "license",
}
DOC_DIRECTORIES = {
    "docs": "docs_dir",
    "doc": "docs_dir",
    "wiki": "wiki",
    "adr": "adr",
    "adrs": "adr",
    "roadmap": "roadmap",
    "runbooks": "runbook",
    "runbook": "runbook",
}
MODULE_ROOT_DIRECTORIES = {
    "packages": "package",
    "apps": "app",
    "services": "service",
    "modules": "module",
    "libs": "library",
    "crates": "crate",
    "plugins": "plugin",
    "components": "component",
}
LIB_MODULE_ROOT_DIRECTORIES = {
    "modules": "module",
    "features": "feature",
}


class ProjectMetadataReader:
    def read(self, project_path: str | Path) -> ProjectMetadata:
        root = Path(project_path).expanduser().resolve()
        warnings: list[str] = []
        if not root.exists():
            return ProjectMetadata(project_path=str(root), warnings=[f"Project path not found: {root}"])
        if not root.is_dir():
            return ProjectMetadata(project_path=str(root), warnings=[f"Project path is not a directory: {root}"])
        fvmrc_path = root / ".fvmrc"
        pubspec_lock_path = root / "pubspec.lock"
        pubspec_yaml_path = root / "pubspec.yaml"
        flutter_version, flutter_channel = self._read_fvmrc(fvmrc_path, warnings) if fvmrc_path.exists() else (None, None)
        packages, pub_observations = self._read_pubspec_lock(pubspec_lock_path, warnings) if pubspec_lock_path.exists() else ({}, [])
        direct_dependencies, pub_manifest_observations = self._read_pubspec_yaml(pubspec_yaml_path, warnings) if pubspec_yaml_path.exists() else ([], [])
        cargo_packages, rust_observations = self._read_cargo(root, warnings)
        npm_packages, npm_direct_dependencies, npm_observations = self._read_node(root, warnings)
        docs_candidates = self.discover_docs(root, warnings)
        all_packages = {**packages, **cargo_packages, **npm_packages}
        direct_dependencies = sorted({*direct_dependencies, *npm_direct_dependencies})
        dependencies = [*pub_observations, *pub_manifest_observations, *rust_observations, *npm_observations]
        detected_ecosystems = sorted({item.ecosystem for item in dependencies})
        if flutter_version or flutter_channel or "flutter" in direct_dependencies:
            detected_ecosystems = sorted({*detected_ecosystems, "flutter"})
        return ProjectMetadata(
            project_path=str(root),
            flutter_version=flutter_version,
            flutter_channel=flutter_channel,
            dart_version=None,
            packages=all_packages,
            direct_dependencies=direct_dependencies,
            dependencies=dependencies,
            docs_candidates=docs_candidates,
            detected_ecosystems=detected_ecosystems,
            warnings=warnings,
        )

    def discover_docs(self, project_path: str | Path, warnings: list[str] | None = None) -> list[ProjectDocsCandidate]:
        root = Path(project_path).expanduser().resolve()
        warnings = warnings if warnings is not None else []
        if not root.exists():
            warnings.append(f"Project path not found: {root}")
            return []
        if not root.is_dir():
            warnings.append(f"Project path is not a directory: {root}")
            return []

        candidates: dict[str, ProjectDocsCandidate] = {}
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if child.name in EXCLUDED_DIR_NAMES:
                continue
            if child.is_file() and self._is_root_doc_file(child):
                self._add_candidate(candidates, root, child, self._root_doc_reason(child))
            elif child.is_dir() and child.name.lower() in DOC_DIRECTORIES:
                self._discover_docs_in_dir(candidates, root, child, DOC_DIRECTORIES[child.name.lower()])
            elif child.is_dir() and child.name.lower() in MODULE_ROOT_DIRECTORIES:
                self._discover_module_docs(candidates, root, child, MODULE_ROOT_DIRECTORIES[child.name.lower()])
            elif child.is_dir() and child.name.lower() == "lib":
                self._discover_lib_module_docs(candidates, root, child)
        return sorted(candidates.values(), key=lambda item: item.path)

    def _discover_lib_module_docs(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        lib_directory: Path,
    ) -> None:
        for child in sorted(lib_directory.iterdir(), key=lambda item: item.name.lower()):
            if child.name in EXCLUDED_DIR_NAMES or not child.is_dir():
                continue
            module_type = LIB_MODULE_ROOT_DIRECTORIES.get(child.name.lower())
            if module_type:
                self._discover_module_docs(candidates, root, child, module_type)

    def _discover_module_docs(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        modules_directory: Path,
        module_type: str,
    ) -> None:
        for module_root in sorted(modules_directory.iterdir(), key=lambda item: item.name.lower()):
            if module_root.name in EXCLUDED_DIR_NAMES or not module_root.is_dir():
                continue
            try:
                module_path = module_root.relative_to(root).as_posix()
            except ValueError:
                continue
            module_name = module_root.name
            for child in sorted(module_root.iterdir(), key=lambda item: item.name.lower()):
                if child.name in EXCLUDED_DIR_NAMES:
                    continue
                if child.is_file() and self._is_root_doc_file(child):
                    self._add_candidate(
                        candidates,
                        root,
                        child,
                        self._root_doc_reason(child),
                        doc_scope="module",
                        module_id=module_path,
                        module_name=module_name,
                        module_path=module_path,
                        module_type=module_type,
                    )
                elif child.is_dir() and child.name.lower() in DOC_DIRECTORIES:
                    self._discover_docs_in_dir(
                        candidates,
                        root,
                        child,
                        DOC_DIRECTORIES[child.name.lower()],
                        doc_scope="module",
                        module_id=module_path,
                        module_name=module_name,
                        module_path=module_path,
                        module_type=module_type,
                    )

    def _discover_docs_in_dir(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        directory: Path,
        reason: str,
        *,
        doc_scope: str = "project",
        module_id: str | None = None,
        module_name: str | None = None,
        module_path: str | None = None,
        module_type: str | None = None,
    ) -> None:
        for path in sorted(directory.rglob("*"), key=lambda item: str(item.relative_to(root)).lower()):
            if self._is_excluded_path(path, root):
                continue
            if path.is_file() and self._is_docs_file(path):
                self._add_candidate(
                    candidates,
                    root,
                    path,
                    self._nested_doc_reason(path, reason),
                    doc_scope=doc_scope,
                    module_id=module_id,
                    module_name=module_name,
                    module_path=module_path,
                    module_type=module_type,
                )

    def _add_candidate(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        path: Path,
        reason: str,
        *,
        doc_scope: str = "project",
        module_id: str | None = None,
        module_name: str | None = None,
        module_path: str | None = None,
        module_type: str | None = None,
    ) -> None:
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            return
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            return
        if any(part in EXCLUDED_DIR_NAMES for part in Path(relative).parts):
            return
        try:
            stat = path.stat()
            size_bytes = stat.st_size
            mtime_ns = stat.st_mtime_ns
        except OSError:
            size_bytes = 0
            mtime_ns = None
        candidates[relative] = ProjectDocsCandidate(
            path=relative,
            source_class=SOURCE_CLASS_PROJECT_FILE,
            reason=reason,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            content_hash=self._content_hash(path),
            doc_scope=doc_scope,
            module_id=module_id,
            module_name=module_name,
            module_path=module_path,
            module_type=module_type,
        )

    @staticmethod
    def _content_hash(path: Path) -> str | None:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return None
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _is_docs_file(path: Path) -> bool:
        name = path.name.lower()
        if name in {"license", "copying"}:
            return True
        return path.suffix.lower() in DOC_FILE_EXTENSIONS

    def _is_root_doc_file(self, path: Path) -> bool:
        if not self._is_docs_file(path):
            return False
        stem = path.stem.lower()
        return stem in ROOT_DOC_FILES or stem.startswith("readme")

    @staticmethod
    def _root_doc_reason(path: Path) -> str:
        stem = path.stem.lower()
        if stem.startswith("readme"):
            return "root_readme"
        return ROOT_DOC_FILES.get(stem, "root_doc")

    @staticmethod
    def _nested_doc_reason(path: Path, fallback: str) -> str:
        lower_parts = {part.lower() for part in path.parts}
        stem = path.stem.lower()
        if stem in {"architecture", "arch"} or "architecture" in lower_parts:
            return "architecture"
        if "adr" in lower_parts or "adrs" in lower_parts:
            return "adr"
        return fallback

    @staticmethod
    def _is_excluded_path(path: Path, root: Path) -> bool:
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            return True
        return any(part in EXCLUDED_DIR_NAMES for part in relative_parts)

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

    def _read_pubspec_lock(self, path: Path, warnings: list[str]) -> tuple[dict[str, str], list[DependencyObservation]]:
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

    def _read_pubspec_yaml(self, path: Path, warnings: list[str]) -> tuple[list[str], list[DependencyObservation]]:
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
                    observations.append(DependencyObservation(
                        ecosystem="pub",
                        package_name=name,
                        dependency_group="dev" if section == "dev_dependencies" else "dependencies",
                        specifier_kind=self._specifier_kind(specifier),
                        specifier_raw=self._specifier_raw(specifier),
                        resolved_version=None,
                        version_source="manifest_exact" if self._specifier_kind(specifier) == "exact" else "manifest_range",
                        source_kind=self._source_kind(specifier),
                    ))
        return sorted(set(names)), observations

    def _read_cargo(self, root: Path, warnings: list[str]) -> tuple[dict[str, str], list[DependencyObservation]]:
        if not (root / "Cargo.toml").exists() and not (root / "Cargo.lock").exists():
            return {}, []
        manifest_observations = self._read_cargo_toml(root / "Cargo.toml", warnings)
        lock_versions = self._read_cargo_lock(root / "Cargo.lock", warnings)
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

    def _read_node(
        self,
        root: Path,
        warnings: list[str],
    ) -> tuple[dict[str, str], list[str], list[DependencyObservation]]:
        package_path = root / "package.json"
        lock_names = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
        available_locks = [name for name in lock_names if (root / name).exists()]
        if not package_path.exists() and not available_locks:
            return {}, [], []

        manifest, package_manager = self._read_package_json(package_path, warnings)
        selected_lock = self._select_node_lock(package_manager, available_locks)
        lock_versions: dict[str, str] = {}
        lock_direct: dict[str, tuple[str, str]] = {}
        if selected_lock == "package-lock.json":
            lock_versions, lock_direct = self._read_package_lock(root / selected_lock, warnings)
        elif selected_lock == "pnpm-lock.yaml":
            lock_versions, lock_direct = self._read_pnpm_lock(root / selected_lock, warnings)
        elif selected_lock == "yarn.lock":
            lock_versions = self._read_yarn_lock(root / selected_lock, manifest, warnings)

        if package_path.exists() and not available_locks:
            warnings.append("JavaScript lockfile not found; exact npm dependency versions may be unavailable.")
        if not manifest and lock_direct:
            manifest = {name: (group, specifier) for name, (group, specifier) in lock_direct.items()}

        observations: list[DependencyObservation] = []
        packages: dict[str, str] = {}
        for name, (group, specifier) in manifest.items():
            source_kind = self._node_source_kind(specifier)
            specifier_kind = self._node_specifier_kind(specifier)
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

    @staticmethod
    def _read_package_json(
        path: Path,
        warnings: list[str],
    ) -> tuple[dict[str, tuple[str, str]], str | None]:
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

    @staticmethod
    def _select_node_lock(package_manager: str | None, available: list[str]) -> str | None:
        preferred = {"npm": "package-lock.json", "pnpm": "pnpm-lock.yaml", "yarn": "yarn.lock"}
        manager = (package_manager or "").split("@", 1)[0].lower()
        selected = preferred.get(manager)
        if selected in available:
            return selected
        return next((name for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock") if name in available), None)

    @staticmethod
    def _read_package_lock(
        path: Path,
        warnings: list[str],
    ) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
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

    @staticmethod
    def _read_pnpm_lock(
        path: Path,
        warnings: list[str],
    ) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
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
                normalized = ProjectMetadataReader._normalize_pnpm_version(str(version)) if version is not None else None
                if normalized:
                    versions[name] = normalized
        return versions, direct

    @staticmethod
    def _normalize_pnpm_version(value: str) -> str | None:
        text = value.strip().strip("'\"")
        if not text or text.startswith(("link:", "workspace:", "file:")):
            return None
        text = text.lstrip("/").split("(", 1)[0]
        match = re.search(r"(?:^|[@/])(\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?)$", text)
        if match:
            return match.group(1)
        return text if re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?", text) else None

    @staticmethod
    def _read_yarn_lock(
        path: Path,
        manifest: dict[str, tuple[str, str]],
        warnings: list[str],
    ) -> dict[str, str]:
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
                parsed = ProjectMetadataReader._parse_yarn_selector(selector)
                if parsed:
                    selector_versions[parsed] = version.strip()
        versions: dict[str, str] = {}
        for name, (_, specifier) in manifest.items():
            normalized_specifier = specifier.removeprefix("npm:")
            exact = selector_versions.get((name, specifier)) or selector_versions.get((name, normalized_specifier))
            if exact:
                versions[name] = exact
        return versions

    @staticmethod
    def _parse_yarn_selector(selector: str) -> tuple[str, str] | None:
        separator = selector.find("@", 1 if selector.startswith("@") else 0)
        if separator <= 0:
            return None
        name = selector[:separator]
        specifier = selector[separator + 1:].removeprefix("npm:")
        return (name, specifier) if name and specifier else None

    @staticmethod
    def _node_source_kind(specifier: str) -> str:
        text = specifier.lower()
        if text.startswith(("file:", "link:", "workspace:")):
            return "path"
        if text.startswith(("git:", "git+", "github:", "gitlab:", "bitbucket:")):
            return "git"
        if text.startswith(("http://", "https://")):
            return "url"
        return "registry"

    @staticmethod
    def _node_specifier_kind(specifier: str) -> str:
        source_kind = ProjectMetadataReader._node_source_kind(specifier)
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

    def _read_cargo_lock(self, path: Path, warnings: list[str]) -> dict[str, str]:
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

    def _read_cargo_toml(self, path: Path, warnings: list[str]) -> list[DependencyObservation]:
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
            package_name = self._cargo_package_name(name, raw_spec)
            observations.append(DependencyObservation(
                ecosystem="rust",
                package_name=package_name,
                dependency_group={"dev-dependencies": "dev", "build-dependencies": "build"}.get(current_group, "dependencies"),
                specifier_kind=self._specifier_kind(raw_spec),
                specifier_raw=self._specifier_raw(raw_spec),
                resolved_version=None,
                version_source="manifest_exact" if self._specifier_kind(raw_spec) == "exact" else "manifest_range",
                source_kind=self._source_kind(raw_spec),
            ))
        return observations

    @staticmethod
    def _cargo_package_name(name: str, raw_spec: str) -> str:
        package_match = re.search(r'package\s*=\s*"([^"]+)"', raw_spec)
        return package_match.group(1) if package_match else name

    @staticmethod
    def _specifier_raw(value: Any) -> str | None:
        if isinstance(value, str):
            return value.strip().strip('"')
        if isinstance(value, dict):
            for key in ("version", "path", "git"):
                raw = value.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
        return str(value).strip() if value is not None else None

    @staticmethod
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

    @staticmethod
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
