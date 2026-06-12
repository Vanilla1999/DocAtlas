from __future__ import annotations

from pathlib import Path
from typing import Any


def partition_project_doc_state(
    candidates: list[dict[str, Any]],
    indexed_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_by_path = {item.get("path"): item for item in candidates if item.get("path")}
    indexed_by_path = {item.get("path"): item for item in indexed_sources if item.get("path")}
    current: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for path, indexed in indexed_by_path.items():
        candidate = candidate_by_path.get(path)
        if not candidate:
            ignored.append({
                **indexed,
                "stale": True,
                "reason": "indexed_source_not_discovered",
                "meaning": "This source exists in the index, but current project-doc discovery did not select it as a candidate.",
                "recommended_next_action": "Link it from docs/INDEX.md or root docs, move it under a discovered docs location, adjust discovery, or refresh/remove obsolete index entries.",
            })
            continue
        stale_reasons: list[str] = []
        if candidate.get("content_hash") != indexed.get("content_hash"):
            stale_reasons.append("content_hash_changed")
        if candidate.get("mtime_ns") != indexed.get("mtime_ns"):
            stale_reasons.append("mtime_changed")
        merged = {**indexed, "candidate": candidate, "stale": bool(stale_reasons)}
        if stale_reasons:
            merged["stale_reasons"] = stale_reasons
            merged["current_content_hash"] = candidate.get("content_hash")
            merged["current_mtime_ns"] = candidate.get("mtime_ns")
            stale.append(merged)
        else:
            current.append(merged)
    return current, stale, ignored


def has_high_level_project_overview(candidates: list[dict[str, Any]]) -> bool:
    for candidate in candidates:
        reason = str(candidate.get("reason") or "")
        path = Path(str(candidate.get("path") or ""))
        stem = path.stem.lower()
        parts = {part.lower() for part in path.parts}
        if reason in {"root_readme", "architecture"}:
            return True
        if stem in {"overview", "introduction", "intro", "index", "readme"}:
            return True
        if "overview" in parts or "architecture" in parts:
            return True
    return False


def create_project_docs_next_action(root: Path, query: str | None = None, *, reason: str | None = None) -> dict[str, Any]:
    get_project_docs_args = {"project_path": str(root)}
    if query:
        get_project_docs_args["query"] = query
    return {
        "action": "create_reviewable_project_doc",
        "requires_confirmation": True,
        "preferred_path": "ARCHITECTURE.md",
        "suggested_paths": ["ARCHITECTURE.md", "README.md", "docs/architecture.md"],
        "reason": reason or "No official project docs files were discovered. Ask the user before creating a reviewable architecture doc in the repository.",
        "agent_guidance": "If the user approves, inspect the codebase, create ARCHITECTURE.md as a normal reviewable file, then call inspect_project_docs and ingest_project_docs before answering repo-specific architecture questions.",
        "after": [
            {"tool": "inspect_project_docs", "requires_confirmation": False, "arguments_patch": {"project_path": str(root)}},
            {"tool": "ingest_project_docs", "requires_confirmation": False, "arguments_patch": {"project_path": str(root)}},
            {"tool": "get_project_docs", "requires_confirmation": False, "arguments_patch": get_project_docs_args},
        ],
    }


def project_docs_structured_next_action(
    *,
    reason_code: str,
    root: Path,
    query: str | None = None,
) -> tuple[dict[str, Any], bool, str | None, dict[str, Any], str, str | None]:
    project_args = {"project_path": str(root)}
    ingest_args = {"project_path": str(root), "skip_known": False, "with_vectors": True}
    if reason_code == "project_docs_stale":
        return ({"type": "ingest_project_docs", "tool": "ingest_project_docs"}, False, None, ingest_args, "Indexed project documentation is stale. Call ingest_project_docs before answering project-level questions.", None)
    if reason_code == "project_docs_found_not_indexed":
        return ({"type": "ingest_project_docs", "tool": "ingest_project_docs"}, False, None, ingest_args, "Project documentation files were found but are not indexed. Call ingest_project_docs before answering project-level questions.", None)
    if reason_code in {"no_project_docs", "architecture_doc_creation_recommended"}:
        agent_message = "No reviewable project docs were found. Ask the user whether to create ARCHITECTURE.md as a repository file, then inspect and ingest it after creation."
        user_message = "Project documentation was not found. Create ARCHITECTURE.md as a reviewable file?"
        if reason_code == "architecture_doc_creation_recommended":
            agent_message = "Project docs exist, but no high-level architecture or overview document was found. Ask the user before creating ARCHITECTURE.md as a repository file, then inspect and ingest it after creation."
            user_message = "I could not find a high-level project architecture document. Do you want me to inspect the repository and create ARCHITECTURE.md as a reviewable file?"
        return ({"type": "ask_user_to_create_project_doc", "suggested_file": "ARCHITECTURE.md", "handled_by": "coding_agent"}, True, "repo_write", project_args, agent_message, user_message)
    get_context_args = {"project_path": str(root)}
    if query:
        get_context_args["question"] = query
    return ({"type": "get_project_context", "tool": "get_project_context"}, False, None, get_context_args, "Project documentation is indexed and ready. Use get_project_context or get_project_docs for repo-specific questions.", None)
