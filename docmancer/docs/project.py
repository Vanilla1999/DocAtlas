from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from docmancer.docs.dart_package_config import resolve_dart_package_roots
from docmancer.docs.ecosystem_adapters import read_project_ecosystems
from docmancer.docs.models import DependencyObservation, ProjectDocsCandidate, ProjectMetadata, SOURCE_CLASS_PROJECT_FILE
from docmancer.docs.project_docs_catalog import (
    MAX_CATALOG_DOCUMENTS,
    ProjectDocCatalogRoot,
    read_project_docs_catalog,
)


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
_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_MAX_INDEX_FILE_BYTES = 256 * 1024
_MAX_INDEX_LINKS_PER_FILE = 200


class ProjectMetadataReader:
    def __init__(self, *, max_docs_hash_bytes: int | None = None):
        self.max_docs_hash_bytes = max_docs_hash_bytes

    def read(self, project_path: str | Path, *, docs_candidate_limit: int | None = None) -> ProjectMetadata:
        root = Path(project_path).expanduser().resolve()
        warnings: list[str] = []
        if not root.exists():
            return ProjectMetadata(project_path=str(root), warnings=[f"Project path not found: {root}"])
        if not root.is_dir():
            return ProjectMetadata(project_path=str(root), warnings=[f"Project path is not a directory: {root}"])
        fvmrc_path = root / ".fvmrc"
        flutter_version, flutter_channel = self._read_fvmrc(fvmrc_path, warnings) if fvmrc_path.exists() else (None, None)
        ecosystem_result = read_project_ecosystems(root, warnings)
        dart_package_roots, dart_root_warnings = resolve_dart_package_roots(root)
        warnings.extend(dart_root_warnings)
        catalog = read_project_docs_catalog(root)
        warnings.extend(catalog.warnings)
        if catalog.present:
            docs_candidates = self._catalog_docs(
                root,
                catalog.entries,
                catalog.roots,
                warnings,
                limit=docs_candidate_limit,
            ) if catalog.valid else []
        else:
            docs_candidates = self.discover_docs(root, warnings, limit=docs_candidate_limit)
        all_packages = dict(ecosystem_result.packages)
        direct_dependencies = list(ecosystem_result.direct_dependencies)
        dependencies = list(ecosystem_result.observations)
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
            dependency_source_roots={
                **{
                    f"pub:{name}": str(path)
                    for name, path in sorted(dart_package_roots.items())
                    if path != root
                },
                **{name: str(path) for name, path in sorted(ecosystem_result.source_roots.items())},
            },
            docs_candidates=docs_candidates,
            detected_ecosystems=detected_ecosystems,
            warnings=warnings,
            docs_catalog_present=catalog.present,
            docs_catalog_valid=catalog.valid,
        )

    def _catalog_docs(
        self,
        root: Path,
        entries: list[Any],
        roots: list[ProjectDocCatalogRoot],
        warnings: list[str],
        *,
        limit: int | None,
    ) -> list[ProjectDocsCandidate]:
        candidates: dict[str, ProjectDocsCandidate] = {}
        output_limit = min(limit, MAX_CATALOG_DOCUMENTS) if limit is not None else MAX_CATALOG_DOCUMENTS
        scan_limit = output_limit + 1
        explicit_paths: list[str] = []
        truncated = False
        for entry in entries:
            if len(explicit_paths) >= output_limit:
                truncated = True
                break
            path = root / entry.path
            try:
                stat = path.stat()
            except OSError:
                continue
            candidates[entry.path] = ProjectDocsCandidate(
                path=entry.path,
                reason=entry.role,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                content_hash=self._content_hash(path),
                doc_scope=entry.scope,
                module_id=entry.module_path,
                module_name=Path(entry.module_path).name if entry.module_path else None,
                module_path=entry.module_path,
                module_type="catalog_module" if entry.module_path else None,
                description=entry.description,
                authority=entry.authority,
                lifecycle_status=entry.status,
                impact_policy=entry.impact,
                catalog_entry_hash="sha256:" + hashlib.sha256(json.dumps({
                    "path": entry.path, "role": entry.role, "scope": entry.scope,
                    "description": entry.description, "module_path": entry.module_path,
                    "authority": entry.authority, "status": entry.status, "impact": entry.impact,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            )
            explicit_paths.append(entry.path)
        if roots and len(explicit_paths) >= output_limit:
            truncated = True
        else:
            for catalog_root in roots:
                if len(candidates) >= scan_limit:
                    truncated = True
                    break
                self._discover_catalog_root(
                    candidates,
                    root,
                    catalog_root,
                    warnings,
                    limit=scan_limit,
                )
        explicit = [candidates[path] for path in explicit_paths]
        explicit_path_set = set(explicit_paths)
        root_candidates = sorted(
            (candidate for path, candidate in candidates.items() if path not in explicit_path_set),
            key=lambda item: item.path,
        )
        remaining = max(0, output_limit - len(explicit))
        if len(root_candidates) > remaining:
            truncated = True
        selected = [*explicit, *root_candidates[:remaining]]
        if truncated:
            warnings.append(
                f"Configured project docs discovery truncated at {output_limit} candidates for bounded analysis."
            )
        return sorted(selected, key=lambda item: item.path)

    def _discover_catalog_root(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        repository_root: Path,
        catalog_root: ProjectDocCatalogRoot,
        warnings: list[str],
        *,
        limit: int | None,
    ) -> None:
        directory = repository_root / catalog_root.path
        module_name = Path(catalog_root.module_path).name if catalog_root.module_path else None
        common = {
            "doc_scope": catalog_root.scope,
            "module_id": catalog_root.module_path,
            "module_name": module_name,
            "module_path": catalog_root.module_path,
            "module_type": "catalog_module" if catalog_root.module_path else None,
            "authority": catalog_root.authority,
            "lifecycle_status": catalog_root.status,
            "impact_policy": (
                "track"
                if catalog_root.status == "active" and catalog_root.authority not in {"historical", "generated"}
                else "search_only"
            ),
            "catalog_entry_hash": self._catalog_root_hash(catalog_root),
        }
        if catalog_root.index:
            self._discover_docs_from_index(
                candidates,
                repository_root,
                directory,
                catalog_root,
                warnings,
                common=common,
                limit=limit,
            )
            return
        self._discover_docs_in_dir(
            candidates,
            repository_root,
            directory,
            "configured_docs_root",
            warnings=warnings,
            limit=limit,
            **common,
        )

    def _discover_docs_from_index(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        repository_root: Path,
        directory: Path,
        catalog_root: ProjectDocCatalogRoot,
        warnings: list[str],
        *,
        common: dict[str, Any],
        limit: int | None,
    ) -> None:
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(relative: str) -> None:
            if limit is not None and len(candidates) >= limit:
                return
            if relative in visiting:
                warnings.append(
                    f"Project docs index loop skipped in {catalog_root.path}: {relative}."
                )
                return
            if relative in visited:
                return
            visiting.add(relative)
            path = directory / Path(*PurePosixPath(relative).parts)
            repository_relative = PurePosixPath(catalog_root.path) / PurePosixPath(relative)
            if self._has_symlink_component(repository_root, repository_relative):
                warnings.append(f"Project docs index target is a symlink and was skipped: {repository_relative.as_posix()}.")
                visiting.remove(relative)
                visited.add(relative)
                return
            if not path.is_file() or not self._is_docs_file(path):
                warnings.append(f"Project docs index target is missing or unsupported: {repository_relative.as_posix()}.")
                visiting.remove(relative)
                visited.add(relative)
                return
            self._add_candidate(
                candidates,
                repository_root,
                path,
                "index" if relative == catalog_root.index else self._nested_doc_reason(path, "configured_docs_index"),
                **common,
            )
            try:
                if path.stat().st_size > _MAX_INDEX_FILE_BYTES:
                    warnings.append(
                        f"Project docs index link scan skipped for oversized file: {repository_relative.as_posix()}."
                    )
                    text = ""
                else:
                    text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                text = ""
            links = _MARKDOWN_LINK_RE.findall(text)
            if len(links) > _MAX_INDEX_LINKS_PER_FILE:
                warnings.append(
                    f"Project docs index links truncated at {_MAX_INDEX_LINKS_PER_FILE} for bounded analysis: "
                    f"{repository_relative.as_posix()}."
                )
            for href in links[:_MAX_INDEX_LINKS_PER_FILE]:
                target, escaped = self._resolve_index_link(relative, href)
                if escaped:
                    warnings.append(
                        f"Project docs index link outside the configured root was skipped: {href}."
                    )
                    continue
                if target is None:
                    continue
                if target in visiting:
                    warnings.append(
                        f"Project docs index loop skipped in {catalog_root.path}: {target}."
                    )
                    continue
                visit(target)
            visiting.remove(relative)
            visited.add(relative)

        assert catalog_root.index is not None
        visit(catalog_root.index)

    @staticmethod
    def _resolve_index_link(source: str, href: str) -> tuple[str | None, bool]:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None, False
        decoded = unquote(parsed.path).replace("\\", "/")
        if decoded.startswith("/"):
            return None, True
        parts = list(PurePosixPath(source).parent.parts)
        for part in PurePosixPath(decoded).parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    return None, True
                parts.pop()
                continue
            parts.append(part)
        if not parts:
            return None, False
        return PurePosixPath(*parts).as_posix(), False

    @staticmethod
    def _catalog_root_hash(catalog_root: ProjectDocCatalogRoot) -> str:
        payload = {
            "path": catalog_root.path,
            "scope": catalog_root.scope,
            "module_path": catalog_root.module_path,
            "authority": catalog_root.authority,
            "status": catalog_root.status,
            "index": catalog_root.index,
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def discover_docs(
        self,
        project_path: str | Path,
        warnings: list[str] | None = None,
        *,
        limit: int | None = None,
    ) -> list[ProjectDocsCandidate]:
        root = Path(project_path).expanduser().resolve()
        warnings = warnings if warnings is not None else []
        if not root.exists():
            warnings.append(f"Project path not found: {root}")
            return []
        if not root.is_dir():
            warnings.append(f"Project path is not a directory: {root}")
            return []

        candidates: dict[str, ProjectDocsCandidate] = {}
        internal_limit = limit + 1 if limit is not None else None
        children = [child for child in sorted(root.iterdir(), key=lambda item: item.name.lower()) if child.name not in EXCLUDED_DIR_NAMES]
        # Preserve the most actionable surfaces under a bounded scan: root
        # authority docs first, then module docs, then broad nested docs trees.
        for child in children:
            if internal_limit is not None and len(candidates) >= internal_limit:
                break
            if child.is_file() and self._is_root_doc_file(child):
                self._add_candidate(candidates, root, child, self._root_doc_reason(child))
        for child in children:
            if internal_limit is not None and len(candidates) >= internal_limit:
                break
            if child.is_dir() and not child.is_symlink() and child.name.lower() in MODULE_ROOT_DIRECTORIES:
                self._discover_module_docs(candidates, root, child, MODULE_ROOT_DIRECTORIES[child.name.lower()], limit=internal_limit)
            elif child.is_dir() and not child.is_symlink() and child.name.lower() == "lib":
                self._discover_lib_module_docs(candidates, root, child, limit=internal_limit)
        for child in children:
            if internal_limit is not None and len(candidates) >= internal_limit:
                break
            if child.is_dir() and not child.is_symlink() and child.name.lower() in DOC_DIRECTORIES:
                self._discover_docs_in_dir(candidates, root, child, DOC_DIRECTORIES[child.name.lower()], limit=internal_limit)
        ordered = sorted(candidates.values(), key=lambda item: item.path)
        if limit is not None and len(ordered) > limit:
            warnings.append(f"Project docs discovery truncated at {limit} candidates for bounded analysis.")
            return ordered[:limit]
        return ordered

    def _discover_lib_module_docs(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        lib_directory: Path,
        *,
        limit: int | None = None,
    ) -> None:
        for child in sorted(lib_directory.iterdir(), key=lambda item: item.name.lower()):
            if limit is not None and len(candidates) >= limit:
                return
            if child.name in EXCLUDED_DIR_NAMES or not child.is_dir() or child.is_symlink():
                continue
            module_type = LIB_MODULE_ROOT_DIRECTORIES.get(child.name.lower())
            if module_type:
                self._discover_module_docs(candidates, root, child, module_type, limit=limit)

    def _discover_module_docs(
        self,
        candidates: dict[str, ProjectDocsCandidate],
        root: Path,
        modules_directory: Path,
        module_type: str,
        *,
        limit: int | None = None,
    ) -> None:
        for module_root in sorted(modules_directory.iterdir(), key=lambda item: item.name.lower()):
            if limit is not None and len(candidates) >= limit:
                return
            if module_root.name in EXCLUDED_DIR_NAMES or not module_root.is_dir() or module_root.is_symlink():
                continue
            try:
                module_path = module_root.relative_to(root).as_posix()
            except ValueError:
                continue
            module_name = module_root.name
            for child in sorted(module_root.iterdir(), key=lambda item: item.name.lower()):
                if limit is not None and len(candidates) >= limit:
                    return
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
                elif child.is_dir() and not child.is_symlink() and child.name.lower() in DOC_DIRECTORIES:
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
                        limit=limit,
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
        authority: str | None = None,
        lifecycle_status: str = "active",
        impact_policy: str = "track",
        catalog_entry_hash: str | None = None,
        warnings: list[str] | None = None,
        limit: int | None = None,
    ) -> None:
        for path in self._iter_docs_tree(directory):
            if limit is not None and len(candidates) >= limit:
                return
            if self._is_excluded_path(path, root):
                continue
            if path.is_symlink():
                if warnings is not None:
                    try:
                        relative = path.relative_to(root).as_posix()
                    except ValueError:
                        relative = str(path)
                    warnings.append(
                        f"Configured project docs symlink was skipped: {relative}."
                    )
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
                    authority=authority,
                    lifecycle_status=lifecycle_status,
                    impact_policy=impact_policy,
                    catalog_entry_hash=catalog_entry_hash,
                )

    def _iter_docs_tree(self, directory: Path):
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            return
        for child in children:
            if child.name in EXCLUDED_DIR_NAMES:
                continue
            yield child
            if child.is_dir() and not child.is_symlink():
                yield from self._iter_docs_tree(child)

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
        authority: str | None = None,
        lifecycle_status: str = "active",
        impact_policy: str = "track",
        catalog_entry_hash: str | None = None,
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
        if relative in candidates:
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
            authority=authority,
            lifecycle_status=lifecycle_status,
            impact_policy=impact_policy,
            catalog_entry_hash=catalog_entry_hash,
        )

    @staticmethod
    def _has_symlink_component(root: Path, relative: PurePosixPath) -> bool:
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    def _content_hash(self, path: Path) -> str | None:
        digest = hashlib.sha256()
        try:
            if self.max_docs_hash_bytes is not None and path.stat().st_size > self.max_docs_hash_bytes:
                return None
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
