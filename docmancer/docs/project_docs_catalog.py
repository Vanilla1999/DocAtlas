"""Explicit, reviewable catalog of project-owned documentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from yaml.constructor import ConstructorError


CATALOG_FILENAME = "docatlas.project-docs.yaml"
SUPPORTED_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
MAX_CATALOG_DOCUMENTS = 500
MAX_CATALOG_ROOTS = 100
MAX_CATALOG_BYTES = 1024 * 1024
MAX_DESCRIPTION_CHARACTERS = 512
ROLES = {
    "overview", "project_architecture", "module_architecture", "runbook",
    "adr", "api_contract", "development", "operations", "roadmap", "other",
}
AUTHORITIES = {"source_of_truth", "supporting", "historical", "generated"}
STATUSES = {"active", "completed", "superseded"}
IMPACT_POLICIES = {"track", "search_only"}
TOP_LEVEL_FIELDS = ("schema_version", "documents", "roots")
DOCUMENT_FIELDS = (
    "path", "role", "scope", "description", "module_path", "authority", "status", "impact",
)
ROOT_FIELDS = ("path", "scope", "module_path", "authority", "status", "index")


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class ProjectDocCatalogEntry:
    path: str
    role: str
    scope: str
    description: str
    module_path: str | None = None
    authority: str = "supporting"
    status: str = "active"
    impact: str = "track"


@dataclass(frozen=True)
class ProjectDocCatalogRoot:
    path: str
    scope: str = "project"
    module_path: str | None = None
    authority: str = "supporting"
    status: str = "active"
    index: str | None = None


@dataclass(frozen=True)
class ProjectDocCatalog:
    present: bool
    valid: bool = True
    path: str | None = None
    entries: list[ProjectDocCatalogEntry] = field(default_factory=list)
    roots: list[ProjectDocCatalogRoot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def read_project_docs_catalog(root: Path) -> ProjectDocCatalog:
    catalog_path = root / CATALOG_FILENAME
    if catalog_path.is_symlink():
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog must not be a symlink."])
    if not catalog_path.exists():
        return ProjectDocCatalog(present=False)
    if not catalog_path.is_file():
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog must be a regular file."])
    try:
        if catalog_path.stat().st_size > MAX_CATALOG_BYTES:
            return ProjectDocCatalog(
                True, False, CATALOG_FILENAME,
                warnings=[f"Project docs catalog exceeds the {MAX_CATALOG_BYTES}-byte limit."],
            )
        data = yaml.load(
            catalog_path.read_text(encoding="utf-8"),
            Loader=_UniqueKeySafeLoader,
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=[f"Could not read project docs catalog: {exc}"])
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data.get("schema_version") != 1
    ):
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog schema_version must be 1."])
    unknown_top_level_fields = sorted(
        str(field_name) for field_name in data if field_name not in TOP_LEVEL_FIELDS
    )
    if unknown_top_level_fields:
        return ProjectDocCatalog(
            True,
            False,
            CATALOG_FILENAME,
            warnings=[f"Project docs catalog has unknown fields: {', '.join(unknown_top_level_fields)}."],
        )
    raw_roots = data.get("roots", [])
    raw_documents = data.get("documents", [] if "roots" in data else None)
    if not isinstance(raw_documents, list):
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog documents must be a list."])
    if not isinstance(raw_roots, list):
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog roots must be a list."])
    warnings: list[str] = []
    entries: list[ProjectDocCatalogEntry] = []
    roots: list[ProjectDocCatalogRoot] = []
    seen: set[str] = set()
    if len(raw_documents) > MAX_CATALOG_DOCUMENTS:
        return ProjectDocCatalog(
            True, False, CATALOG_FILENAME,
            warnings=[f"Project docs catalog exceeds the {MAX_CATALOG_DOCUMENTS}-document limit."],
        )
    if len(raw_roots) > MAX_CATALOG_ROOTS:
        return ProjectDocCatalog(
            True, False, CATALOG_FILENAME,
            warnings=[f"Project docs catalog exceeds the {MAX_CATALOG_ROOTS}-root limit."],
        )
    for index, raw in enumerate(raw_documents[:MAX_CATALOG_DOCUMENTS]):
        entry, error = _validated_entry(root, raw)
        if error:
            warnings.append(f"Catalog documents[{index}]: {error}")
            continue
        assert entry is not None
        if entry.path in seen:
            warnings.append(f"Catalog documents[{index}]: duplicate path {entry.path!r}.")
            continue
        seen.add(entry.path)
        entries.append(entry)
    seen_roots: set[str] = set()
    for index, raw in enumerate(raw_roots[:MAX_CATALOG_ROOTS]):
        catalog_root, error = _validated_root(root, raw)
        if error:
            warnings.append(f"Catalog roots[{index}]: {error}")
            continue
        assert catalog_root is not None
        if catalog_root.path in seen_roots:
            warnings.append(f"Catalog roots[{index}]: duplicate path {catalog_root.path!r}.")
            continue
        seen_roots.add(catalog_root.path)
        roots.append(catalog_root)
    if warnings:
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=warnings)
    return ProjectDocCatalog(True, True, CATALOG_FILENAME, entries, roots, [])


def _validated_root(root: Path, raw: Any) -> tuple[ProjectDocCatalogRoot | None, str | None]:
    if not isinstance(raw, dict):
        return None, "entry must be a mapping."
    unknown_fields = sorted(str(field_name) for field_name in raw if field_name not in ROOT_FIELDS)
    if unknown_fields:
        return None, f"unknown fields: {', '.join(unknown_fields)}."
    for field_name in ROOT_FIELDS:
        if field_name in raw and raw[field_name] is not None and not isinstance(raw[field_name], str):
            return None, f"{field_name} must be a string."
    relative, error = _safe_relative_path(str(raw.get("path") or ""), field_name="path")
    if error:
        return None, error
    assert relative is not None
    scope = str(raw.get("scope") or "project")
    module_path, module_error = _optional_module_path(str(raw.get("module_path") or ""))
    if module_error:
        return None, module_error
    authority = str(raw.get("authority") or "supporting")
    status = str(raw.get("status") or "active")
    raw_index = str(raw.get("index") or "")
    index, index_error = _safe_relative_path(raw_index, field_name="index", optional=True)
    if index_error:
        return None, index_error
    if scope not in {"project", "module"}:
        return None, f"invalid scope {scope!r}."
    if scope == "module" and not module_path:
        return None, "module scope requires module_path."
    if scope == "project" and module_path:
        return None, "project scope must not declare module_path."
    if authority not in AUTHORITIES or status not in STATUSES:
        return None, "invalid authority or status."
    pure = PurePosixPath(relative)
    candidate = root / Path(*pure.parts)
    if _has_symlink_component(root, pure) or not candidate.is_dir():
        return None, "path must reference an existing non-symlinked directory."
    if module_path:
        module_pure = PurePosixPath(module_path)
        module_candidate = root / Path(*module_pure.parts)
        if _has_symlink_component(root, module_pure) or not module_candidate.is_dir():
            return None, "module_path must reference an existing non-symlinked directory."
    if index:
        index_pure = PurePosixPath(index)
        index_path = candidate / Path(*index_pure.parts)
        relative_to_repo = PurePosixPath(relative) / index_pure
        if _has_symlink_component(root, relative_to_repo) or not index_path.is_file():
            return None, "index must reference an existing non-symlinked file within the configured root."
        if index_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return None, "index uses an unsupported project documentation format."
    return ProjectDocCatalogRoot(relative, scope, module_path, authority, status, index), None


def _safe_relative_path(
    raw: str,
    *,
    field_name: str,
    optional: bool = False,
) -> tuple[str | None, str | None]:
    value = raw.replace("\\", "/")
    if not value and optional:
        return None, None
    if value.startswith("/"):
        return None, f"{field_name} must stay within its configured root."
    relative = value.strip("/")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts or (pure.parts and pure.parts[0].endswith(":")):
        return None, f"{field_name} must stay within its configured root."
    return pure.as_posix(), None


def _optional_module_path(raw: str) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    return _safe_relative_path(raw, field_name="module_path")


def _validated_entry(root: Path, raw: Any) -> tuple[ProjectDocCatalogEntry | None, str | None]:
    if not isinstance(raw, dict):
        return None, "entry must be a mapping."
    unknown_fields = sorted(str(field_name) for field_name in raw if field_name not in DOCUMENT_FIELDS)
    if unknown_fields:
        return None, f"unknown fields: {', '.join(unknown_fields)}."
    for field_name in DOCUMENT_FIELDS:
        if field_name in raw and raw[field_name] is not None and not isinstance(raw[field_name], str):
            return None, f"{field_name} must be a string."
    raw_path = str(raw.get("path") or "").replace("\\", "/")
    if raw_path.startswith("/"):
        return None, "path must stay within the repository."
    relative = raw_path.strip("/")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts or (pure.parts and pure.parts[0].endswith(":")):
        return None, "path must stay within the repository."
    relative = pure.as_posix()
    role = str(raw.get("role") or "")
    scope = str(raw.get("scope") or "project")
    description = str(raw.get("description") or "").strip()
    raw_module_path = str(raw.get("module_path") or "").replace("\\", "/")
    if raw_module_path.startswith("/"):
        return None, "module_path must stay within the repository."
    module_path = raw_module_path.strip("/") or None
    authority = str(raw.get("authority") or "supporting")
    status = str(raw.get("status") or "active")
    impact = str(raw.get("impact") or "track")
    if role not in ROLES:
        return None, f"invalid role {role!r}."
    if scope not in {"project", "module"}:
        return None, f"invalid scope {scope!r}."
    if scope == "module" and not module_path:
        return None, "module scope requires module_path."
    if scope == "project" and module_path:
        return None, "project scope must not declare module_path."
    if module_path and (PurePosixPath(module_path).is_absolute() or ".." in PurePosixPath(module_path).parts):
        return None, "module_path must stay within the repository."
    if module_path:
        module_path = PurePosixPath(module_path).as_posix()
    if scope == "module":
        module_pure = PurePosixPath(module_path or "")
        module_candidate = root / Path(*module_pure.parts)
        if _has_symlink_component(root, module_pure) or not module_candidate.is_dir():
            return None, "module_path must reference an existing non-symlinked directory."
    if not description or len(description) > MAX_DESCRIPTION_CHARACTERS:
        return None, f"description must contain 1..{MAX_DESCRIPTION_CHARACTERS} characters."
    if "\n" in description or "\r" in description:
        return None, "description must be a single line."
    if authority not in AUTHORITIES or status not in STATUSES or impact not in IMPACT_POLICIES:
        return None, "invalid authority, status, or impact policy."
    if role == "module_architecture" and scope != "module":
        return None, "module_architecture requires module scope."
    if role in {"overview", "project_architecture"} and scope != "project":
        return None, f"{role} requires project scope."
    if status != "active" and impact != "search_only":
        return None, "completed or superseded documents must use impact: search_only."
    if authority in {"historical", "generated"} and impact != "search_only":
        return None, f"{authority} documents must use impact: search_only."
    candidate_path = root / Path(*pure.parts)
    if _has_symlink_component(root, pure):
        return None, "path and its parent directories must not be symlinks."
    resolved = candidate_path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "path resolves outside the repository."
    if not resolved.is_file():
        return None, "path must reference an existing regular file."
    if resolved.suffix.lower() not in SUPPORTED_EXTENSIONS and resolved.name.lower() not in {"license", "copying"}:
        return None, "unsupported project documentation format."
    return ProjectDocCatalogEntry(relative, role, scope, description, module_path, authority, status, impact), None


def _has_symlink_component(root: Path, relative: PurePosixPath) -> bool:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False
