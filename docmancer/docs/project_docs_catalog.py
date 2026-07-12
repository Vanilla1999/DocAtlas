"""Explicit, reviewable catalog of project-owned documentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


CATALOG_FILENAME = "docatlas.project-docs.yaml"
SUPPORTED_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
MAX_CATALOG_DOCUMENTS = 500
MAX_CATALOG_BYTES = 1024 * 1024
MAX_DESCRIPTION_CHARACTERS = 512
ROLES = {
    "overview", "project_architecture", "module_architecture", "runbook",
    "adr", "api_contract", "development", "operations", "roadmap", "other",
}
AUTHORITIES = {"source_of_truth", "supporting", "historical", "generated"}
STATUSES = {"active", "completed", "superseded"}
IMPACT_POLICIES = {"track", "search_only"}
TOP_LEVEL_FIELDS = ("schema_version", "documents")
DOCUMENT_FIELDS = (
    "path", "role", "scope", "description", "module_path", "authority", "status", "impact",
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
class ProjectDocCatalog:
    present: bool
    valid: bool = True
    path: str | None = None
    entries: list[ProjectDocCatalogEntry] = field(default_factory=list)
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
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=[f"Could not read project docs catalog: {exc}"])
    if not isinstance(data, dict) or data.get("schema_version") != 1:
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
    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list):
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=["Project docs catalog documents must be a list."])
    warnings: list[str] = []
    entries: list[ProjectDocCatalogEntry] = []
    seen: set[str] = set()
    if len(raw_documents) > MAX_CATALOG_DOCUMENTS:
        return ProjectDocCatalog(
            True, False, CATALOG_FILENAME,
            warnings=[f"Project docs catalog exceeds the {MAX_CATALOG_DOCUMENTS}-document limit."],
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
    if warnings:
        return ProjectDocCatalog(True, False, CATALOG_FILENAME, warnings=warnings)
    return ProjectDocCatalog(True, True, CATALOG_FILENAME, entries, [])


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
