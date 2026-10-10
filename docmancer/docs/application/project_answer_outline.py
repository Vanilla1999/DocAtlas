from __future__ import annotations

from typing import Any

from docmancer.docs.domain.project_doc_ranking import normalize_doc_path


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
            "reason": "Selected cited source; topic coverage is not inferred.",
        })
        seen.add(normalized_path)
        if len(recommended) >= 5:
            break

    return {
        "query_intent": getattr(intent, "name", "general"),
        "recommended_reading_order": recommended,
        "coverage": {},
        "warnings": [],
    }
