"""Mechanical local read bindings. None of these checks authorize an action."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from docmancer.docs.project import ProjectMetadataReader


def document_binding(root: Path, path: str) -> dict[str, str] | None:
    if not isinstance(path, str):
        return None
    try:
        metadata = ProjectMetadataReader().read(root)
    except (OSError, ValueError):
        return None
    for candidate in metadata.docs_candidates:
        if candidate.path == path and candidate.content_hash and candidate.catalog_entry_hash:
            return {
                "project_path": metadata.project_path, "path": path,
                "content_hash": candidate.content_hash,
                "catalog_entry_hash": candidate.catalog_entry_hash,
            }
    return None


def finite_doc_reference(item: dict[str, Any]) -> bool:
    """Check an existing source reference against actual current local membership."""
    path = item.get("source")
    for ref in item.get("source_refs") or []:
        if not isinstance(ref, dict) or ref.get("path") != path:
            continue
        binding = ref.get("local_read_binding")
        if not isinstance(binding, dict) or not isinstance(binding.get("project_path"), str):
            continue
        actual = document_binding(Path(binding["project_path"]), path)
        if actual is not None and binding == actual:
            return True
    return False
