"""Small serialization helpers for model-visible projections."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def bounded_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = (
        "tool", "type", "action", "handled_by", "arguments_patch", "question",
        "requires_confirmation", "confirmation_reason", "reason", "observations",
        "security_scope", "decision_options", "agent_question", "query_terms",
        "suggested_doc_paths", "suggested_symbols", "suggested_layers",
        "repeat_docs_context",
    )
    result = {
        key: deepcopy(value[key])
        for key in allowed
        if value.get(key) not in (None, {}, [])
    }
    result["auto_execute"] = False
    return result


def cited_patch_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[Any] = [
        payload.get("acceptance_conditions"),
        payload.get("invariants"),
        payload.get("forbidden_changes"),
        payload.get("implementation_guidance"),
        (payload.get("targets") or {}).get("likely_files"),
        (payload.get("targets") or {}).get("symbols"),
        *((payload.get("checks") or {}).values()),
    ]
    return [
        item
        for value in values
        if isinstance(value, list)
        for item in value
        if isinstance(item, dict) and item.get("provenance") != "user_request"
    ]


__all__ = ["bounded_action", "cited_patch_items"]
