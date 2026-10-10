from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from docmancer.docs.models import ProjectDocsCandidate, ProjectMetadata
from docmancer.docs.project_docs_catalog import MAX_CATALOG_DOCUMENTS, read_project_docs_catalog


DOC_FILE_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
EXCLUDED_DIR_NAMES = {
    ".git", ".hg", ".svn", ".dart_tool", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".tox", ".venv", "venv", "env", "node_modules", "build",
    "dist", "target", ".next", ".turbo", "coverage", "htmlcov", "__pycache__",
}
# Compatibility labels used by impact diagnostics; these are not read selectors.
ROOT_DOC_FILES = {
    "readme": "root_readme", "architecture": "architecture", "arch": "architecture",
    "changelog": "changelog", "contributing": "contributing", "security": "security",
    "license": "license",
}
DOC_DIRECTORIES = {
    "docs": "docs_dir", "doc": "docs_dir", "wiki": "wiki", "adr": "adr",
    "adrs": "adr", "roadmap": "roadmap", "runbooks": "runbook", "runbook": "runbook",
}


class ProjectMetadataReader:
    """Read literal documentation members, never discover roots, links or modules.

    Scope/role/authority/impact are catalog routing data, not action permission.
    Dependency metadata remains unknown without a separate finite read contract.
    """

    def __init__(self, *, max_docs_hash_bytes: int | None = None):
        self.max_docs_hash_bytes = max_docs_hash_bytes

    def read(self, project_path: str | Path, *, docs_candidate_limit: int | None = None) -> ProjectMetadata:
        root = Path(project_path).expanduser().resolve()
        warnings: list[str] = []
        if not root.exists() or not root.is_dir():
            return ProjectMetadata(project_path=str(root), warnings=[f"Invalid project directory: {root}"])
        catalog = read_project_docs_catalog(root)
        warnings.extend(catalog.warnings)
        candidates = self._catalog_docs(root, catalog.entries, [], warnings, limit=docs_candidate_limit) if catalog.present and catalog.valid else []
        if not catalog.present:
            warnings.append("Local documentation membership unresolved: explicit catalog required; no discovery performed.")
        warnings.append("Dependency/source metadata unresolved: finite documentation membership does not authorize metadata reads.")
        return ProjectMetadata(
            project_path=str(root), docs_candidates=candidates, warnings=warnings,
            docs_catalog_present=catalog.present, docs_catalog_valid=catalog.valid,
            code_files=catalog.code_files if catalog.present and catalog.valid else (),
        )

    def discover_docs(self, project_path: str | Path, warnings: list[str] | None = None,
                      *, limit: int | None = None) -> list[ProjectDocsCandidate]:
        metadata = self.read(project_path, docs_candidate_limit=limit)
        if warnings is not None:
            warnings.extend(metadata.warnings)
        return metadata.docs_candidates

    def _catalog_docs(self, root: Path, entries: list[Any], roots: list[Any],
                      warnings: list[str], *, limit: int | None) -> list[ProjectDocsCandidate]:
        from docmancer.docs.domain.source_boundary import SourceBoundary, finite_local_path

        if roots:
            warnings.append("Root discovery is not finite local membership.")
            return []
        boundary = SourceBoundary.from_project(root)
        output_limit = max(0, min(limit if limit is not None else MAX_CATALOG_DOCUMENTS,
                                  MAX_CATALOG_DOCUMENTS, boundary.max_scanned_files))
        deadline = time.monotonic() + boundary.scan_deadline_seconds
        spent_bytes = 0
        candidates = []
        for entry in entries:
            if len(candidates) >= output_limit or time.monotonic() >= deadline:
                warnings.append(f"Configured project docs discovery truncated at {output_limit} candidates for bounded analysis.")
                break
            path = finite_local_path(root, entry.path, boundary=boundary,
                                     supported_extensions=frozenset(DOC_FILE_EXTENSIONS),
                                     use_configured_extensions=False)
            if path is None:
                warnings.append(f"Selected document excluded by local source boundary: {entry.path}.")
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if spent_bytes + stat.st_size > boundary.max_scanned_bytes:
                warnings.append("Configured project docs discovery truncated by byte budget.")
                break
            spent_bytes += stat.st_size
            candidates.append(ProjectDocsCandidate(
                path=entry.path, reason=entry.role, size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns, content_hash=self._content_hash(path),
                doc_scope=entry.scope, module_id=entry.module_path,
                module_name=Path(entry.module_path).name if entry.module_path else None,
                module_path=entry.module_path,
                module_type="catalog_module" if entry.module_path else None,
                description=entry.description, authority=entry.authority,
                lifecycle_status=entry.status, impact_policy=entry.impact,
                catalog_entry_hash="sha256:" + hashlib.sha256(json.dumps({
                    "path": entry.path, "role": entry.role, "scope": entry.scope,
                    "description": entry.description, "module_path": entry.module_path,
                    "authority": entry.authority, "status": entry.status, "impact": entry.impact,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            ))
        return sorted(candidates, key=lambda item: item.path)

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
