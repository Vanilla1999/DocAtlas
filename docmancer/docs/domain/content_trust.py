from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

_SCOPED_POLICY_FILENAMES = {"agents.md", "claude.md"}


def annotate_context_pack(
    context_pack: list[dict[str, Any]],
    *,
    repository_root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotated: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for source_item in context_pack:
        item = dict(source_item)
        path = str(item.get("path") or item.get("source") or "")
        scope = str(item.get("doc_scope") or item.get("origin_lane") or "unknown")
        policy_scope = _policy_scope(path, repository_root=repository_root) if scope == "project" else None
        policy_file = policy_scope is not None
        item["source_provenance"] = {
            "owner": "configured_repository" if scope == "project" else "external_source",
            "origin_lane": item.get("origin_lane"),
        }
        item["version_exactness"] = item.get("docs_exactness") or item.get("version_binding") or "not_applicable"
        item["repository_authority"] = "scoped_repository_document" if policy_file else (
            "ordinary_repository_document" if scope == "project" else "not_applicable"
        )
        # Filename/scope establish attribution, never authenticated instructions.
        # Overwrite caller-supplied trust even for canonical policy-file quotes.
        item["instruction_trust"] = "untrusted_data"
        item["content_boundary"] = {
            "role": "cited_document_data",
            "schema": "docmancer-document-data-v1",
            "executable_policy": False,
        }
        item["document_data"] = {
            "schema": "docmancer-document-data-v1",
            "instruction_trust": item["instruction_trust"],
            "content": item.get("content") if "content" in item else item.get("snippet"),
        }
        item["authority_root"] = str(Path(repository_root).resolve()) if policy_file and repository_root else None
        item["policy_scope"] = str(policy_scope) if policy_scope is not None else None
        item["scope_verified"] = bool(policy_file)
        annotated.append(item)
    return annotated, warnings


def source_trust_dimensions(
    *, path: str, scope: str, version_exactness: str | None = None, repository_root: str | Path | None = None,
) -> dict[str, Any]:
    policy_scope = _policy_scope(path, repository_root=repository_root) if scope == "project" else None
    policy_file = policy_scope is not None
    return {
        "source_provenance": {
            "owner": "configured_repository" if scope == "project" else "external_source",
        },
        "version_exactness": version_exactness or "not_applicable",
        "repository_authority": "scoped_repository_document" if policy_file else (
            "ordinary_repository_document" if scope == "project" else "not_applicable"
        ),
        "instruction_trust": "untrusted_data",
        "authority_root": str(Path(repository_root).resolve()) if policy_file and repository_root else None,
        "policy_scope": str(policy_scope) if policy_scope is not None else None,
        "scope_verified": bool(policy_file),
    }


def _is_policy_file(path: str, *, repository_root: str | Path | None) -> bool:
    return _policy_scope(path, repository_root=repository_root) is not None


def _policy_scope(path: str, *, repository_root: str | Path | None) -> Path | None:
    if repository_root is None:
        return None
    root = Path(repository_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    normalized = PurePosixPath(relative.as_posix().lower())
    if normalized.name in _SCOPED_POLICY_FILENAMES:
        return resolved.parent
    if normalized.as_posix() == ".cursorrules":
        return root
    if normalized.as_posix() == ".github/copilot-instructions.md":
        return root
    return None
