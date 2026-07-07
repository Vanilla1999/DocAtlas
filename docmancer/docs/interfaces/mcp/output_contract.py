from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES = 32_000
DEFAULT_FULL_OUTPUT_MAX_BYTES = 256_000
_TEXT_KEYS = {"content", "snippet", "text", "primary_snippet", "surrounding_context"}
_SUMMARY_KEYS = (
    "path",
    "title",
    "heading_path",
    "source_class",
    "freshness",
    "token_estimate",
    "why_selected",
    "line_start",
    "line_end",
    "score",
    "ranking",
)
_ALLOWED_OUTPUT_MODES = {"answer", "compact", "debug", "full"}


def normalize_output_mode(
    args: dict[str, Any],
    *,
    default: str = "answer",
    details_fallback: bool = False,
    allowed: set[str] | None = None,
) -> str:
    allowed_modes = allowed or _ALLOWED_OUTPUT_MODES
    fallback = "debug" if details_fallback and args.get("details") else default
    mode = str(args.get("output_mode") or fallback).lower()
    return mode if mode in allowed_modes else default


def json_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def paginate_context_items(items: list[Any], *, page: int | None, page_size: int | None) -> dict[str, Any]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(20, int(page_size or 8)))
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    total = len(items)
    return {
        "items": items[start:end],
        "page": safe_page,
        "page_size": safe_page_size,
        "total_items": total,
        "next_page": safe_page + 1 if end < total else None,
    }


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = f" … [truncated {len(value) - limit} chars]"
    return value[: max(0, limit - len(suffix))].rstrip() + suffix, True


def _compact_context_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    compact = {key: item.get(key) for key in _SUMMARY_KEYS if item.get(key) not in (None, [], {})}
    source = item.get("source")
    if isinstance(source, dict):
        for key in ("path", "title", "source_class", "freshness"):
            compact.setdefault(key, source.get(key))
    section = item.get("section")
    if isinstance(section, dict):
        compact.setdefault("heading_path", section.get("heading_path"))
        compact.setdefault("line_start", section.get("line_start"))
        compact.setdefault("line_end", section.get("line_end"))
    for text_key in ("snippet", "primary_snippet"):
        if isinstance(item.get(text_key), str):
            compact[text_key], _ = _truncate_text(item[text_key], 320)
            break
    if any(key in item for key in _TEXT_KEYS):
        compact["content_omitted"] = True
    return {key: value for key, value in compact.items() if value not in (None, [], {})}


def _compact_value(value: Any, *, text_limit: int, list_limit: int, key: str | None, stats: dict[str, int]) -> Any:
    if isinstance(value, str):
        limit = text_limit if key in _TEXT_KEYS else max(text_limit * 2, text_limit)
        compact, truncated = _truncate_text(value, limit)
        if truncated:
            stats["truncated_strings"] += 1
            stats["truncated_chars"] += len(value) - len(compact)
        return compact
    if isinstance(value, list):
        items = value[:list_limit]
        omitted = max(0, len(value) - len(items))
        if omitted:
            stats["omitted_item_count"] += omitted
        return [_compact_value(item, text_limit=text_limit, list_limit=list_limit, key=None, stats=stats) for item in items]
    if isinstance(value, dict):
        return {
            str(k): _compact_value(v, text_limit=text_limit, list_limit=list_limit, key=str(k), stats=stats)
            for k, v in value.items()
        }
    return value


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _append_warning(payload: dict[str, Any], warning: dict[str, str]) -> None:
    warnings = list(payload.get("warnings") or [])
    if warning not in warnings:
        warnings.append(warning)
    payload["warnings"] = warnings


def _section_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"omitted": True, "type": "array", "item_count": len(value)}
    if isinstance(value, dict):
        return {"omitted": True, "type": "object", "key_count": len(value), "keys": list(value)[:12]}
    if isinstance(value, str):
        return {"omitted": True, "type": "string", "char_count": len(value)}
    return {"omitted": True, "type": type(value).__name__}


def _fit_payload(payload: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
    if json_bytes(payload) <= max_bytes:
        return payload
    compact = deepcopy(payload)
    compaction = dict(compact.get("mcp_compaction") or {})
    omitted_sections: list[str] = list(compaction.get("omitted_sections") or [])
    for section in ("diagnostics", "metrics", "snippet_metrics", "project_docs", "dependency_docs", "answer_outline", "trust_contract"):
        if json_bytes(compact) <= max_bytes:
            break
        if compact.get(section) not in (None, [], {}):
            compact[section] = _section_summary(compact[section])
            omitted_sections.append(section)
            compact["mcp_compaction"] = {**compaction, "hard_cap_enforced": True, "omitted_sections": omitted_sections}
    if json_bytes(compact) <= max_bytes:
        return compact
    keep_keys = {
        "status", "tool", "schema_version", "answer_available", "answer_type", "answer_completeness",
        "mode", "reason", "message", "response_style", "primary_snippet", "context_pack", "supporting_snippets",
        "next_actions", "next_action", "arguments_patch", "warnings", "mcp_compaction", "output_mode",
        "full_output_available", "requires_confirmation", "confirmation_reason",
    }
    omitted = [key for key in compact if key not in keep_keys]
    compact = {key: value for key, value in compact.items() if key in keep_keys}
    compact["mcp_compaction"] = {**dict(compact.get("mcp_compaction") or {}), "hard_cap_enforced": True, "omitted_sections": omitted_sections, "omitted_fields": omitted[:40]}
    return compact


def compact_mcp_payload(
    payload: dict[str, Any],
    *,
    max_bytes: int = DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES,
    tool: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    include_sections: list[str] | None = None,
) -> dict[str, Any]:
    if json_bytes(payload) <= max_bytes:
        return payload

    original_bytes = json_bytes(payload)
    compact = deepcopy(payload)
    if include_sections:
        allowed = {"status", "tool", "schema_version", "answer_available", "answer_type", "warnings", "mcp_compaction", *include_sections}
        compact = {key: value for key, value in compact.items() if key in allowed}

    has_context_pack = "context_pack" in compact
    has_supporting_snippets = "supporting_snippets" in compact
    context_items = list(compact.get("context_pack") or [])
    supporting_items = list(compact.get("supporting_snippets") or [])
    selected_page = paginate_context_items(context_items, page=page, page_size=page_size)
    if has_context_pack:
        compact["context_pack"] = [_compact_context_item(item) for item in selected_page["items"]]
    if has_supporting_snippets:
        compact["supporting_snippets"] = [_compact_context_item(item) for item in supporting_items[: max(1, min(3, int(page_size or 3)))] ]

    stats = {"truncated_strings": 0, "truncated_chars": 0, "omitted_item_count": 0}
    compact = _compact_value(compact, text_limit=900, list_limit=8, key=None, stats=stats)
    compact["mcp_compaction"] = {
        "truncated": True,
        "max_bytes": max_bytes,
        "original_bytes_estimate": original_bytes,
        "returned_bytes": json_bytes(compact),
        "omitted_sections": [],
        "omitted_item_count": stats["omitted_item_count"],
        "truncated_strings": stats["truncated_strings"],
        "truncated_chars": stats["truncated_chars"],
        "page": selected_page["page"],
        "page_size": selected_page["page_size"],
        "total_items": selected_page["total_items"],
        "next_page": selected_page["next_page"],
        "guidance": f"Retry with page={selected_page['next_page']}/page_size={selected_page['page_size']} or include_sections=[...]" if selected_page["next_page"] else "Retry with lower page_size/tokens/limit or include_sections=[...]",
    }
    _append_warning(compact, _warning("mcp_compact_output_truncated", f"Compact MCP response was truncated to stay under {max_bytes} bytes."))
    compact = _fit_payload(compact, max_bytes=max_bytes)
    if isinstance(compact.get("mcp_compaction"), dict):
        compact["mcp_compaction"]["returned_bytes"] = json_bytes(compact)
    return compact


def strip_debug_noise(payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(payload)
    payload.pop("diagnostics", None)
    payload.pop("metrics", None)
    payload.pop("snippet_metrics", None)
    return payload


def attach_output_contract(payload: dict[str, Any], *, output_mode: str, max_bytes: int = DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES) -> dict[str, Any]:
    raw_compaction = payload.get("mcp_compaction")
    compaction: dict[str, Any] = raw_compaction if isinstance(raw_compaction, dict) else {}
    truncated = bool(payload.get("response_truncated") or compaction.get("truncated"))
    payload["output_contract"] = {
        "mode": output_mode,
        "complete": not truncated,
        "truncated": truncated,
        "safe_to_use_as_complete_context": not truncated,
        "retry_with": {"page": compaction.get("next_page"), "page_size": compaction.get("page_size")} if truncated else None,
        "max_bytes": max_bytes,
    }
    return payload
