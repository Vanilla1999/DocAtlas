from __future__ import annotations

from typing import Any

from docmancer.docs.domain.project_doc_ranking import is_changelog_path, normalize_doc_path


def build_project_answer_outline(*, question: str, intent: Any, context_pack: list[dict[str, Any]]) -> dict[str, Any]:
    recommended: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in context_pack:
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        section = item.get("section") if isinstance(item.get("section"), dict) else {}
        path = item.get("path") or source.get("path")
        heading_path = item.get("heading_path") or section.get("heading_path")
        normalized_path = normalize_doc_path(path)
        if not normalized_path or normalized_path in seen:
            continue
        recommended.append({
            "path": path,
            "title": item.get("title") or source.get("title"),
            "heading_path": heading_path,
            "source_class": item.get("source_class"),
            "freshness": item.get("freshness"),
            "reason": reason_for_source(path=path, heading_path=heading_path),
        })
        seen.add(normalized_path)
        if len(recommended) >= 5:
            break

    warnings = []
    if any(is_changelog_path(item.get("path")) for item in context_pack) and not getattr(intent, "wants_release_history", False):
        warnings.append({
            "code": "changelog_present_for_non_release_query",
            "message": "CHANGELOG.md is present even though the query is not release-history oriented.",
        })

    return {
        "query_intent": getattr(intent, "name", "general"),
        "recommended_reading_order": recommended,
        "coverage": compute_coverage(context_pack=context_pack),
        "warnings": warnings,
    }


def reason_for_source(*, path: str | None, heading_path: str | None) -> str:
    p = normalize_doc_path(path)
    h = (heading_path or "").lower()
    if p.endswith("readme.md"):
        return "Best high-level overview and user-facing workflow source."
    if p.endswith("contributing.md"):
        return "Best code layout and extension-point source."
    if "architecture" in p:
        return "Best internal architecture and pipeline source."
    if "mcp-packs" in p:
        return "Best source for MCP Packs / API action runtime."
    if "mcp" in p or "mcp" in h:
        return "Relevant MCP-specific documentation source."
    if is_changelog_path(p):
        return "Release-history source; useful for changes, not primary architecture."
    return "Selected because it matched the project-doc query."


def compute_coverage(*, context_pack: list[dict[str, Any]]) -> dict[str, bool]:
    text = "\n".join(" ".join(str(item.get(key) or "") for key in ["path", "title", "heading_path", "content"]) for item in context_pack).lower()
    return {
        "high_level_overview": "readme" in text or "overview" in text or "what you get" in text,
        "architecture": "architecture" in text,
        "project_structure": "contributing.md" in text or "project structure" in text or "layout" in text,
        "setup_or_commands": "install" in text or "setup" in text or "doc-atlas " in text or "docmancer " in text,
        "mcp_docs": "docs-serve" in text or "get_project_context" in text or "get_library_docs" in text,
        "mcp_packs": "mcp-packs" in text or "install-pack" in text or "action packs" in text,
        "release_history": "changelog" in text or "breaking" in text or "added" in text,
    }
