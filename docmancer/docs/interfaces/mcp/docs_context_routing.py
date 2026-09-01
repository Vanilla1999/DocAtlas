"""Input normalization and safe routing for retrieval-only docs context."""

from __future__ import annotations

import math
from typing import Any

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS,
    canonical_projection_bytes,
)
from docmancer.docs.interfaces.mcp.recovery_projection import (
    is_operational_recovery_action,
)


def normalize_lookup_queries(value: Any) -> tuple[tuple[str, ...], str | None]:
    if value in (None, []):
        return (), None
    if not isinstance(value, list) or len(value) > 5:
        return (), "lookup_queries must be an array of at most five strings"
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        query = str(item).strip() if isinstance(item, str) else ""
        key = query.casefold()
        if not query or len(query) > 500:
            return (), "lookup_queries must contain non-empty strings of at most 500 characters"
        if key in seen:
            return (), "lookup_queries must not contain duplicates"
        seen.add(key)
        result.append(query)
    return tuple(result), None


def tuple_value(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,) if value not in (None, "") else ()


def refresh_projection_estimate(payload: dict[str, Any]) -> None:
    for _ in range(4):
        estimate = max(1, math.ceil(len(canonical_projection_bytes(payload)) / 4))
        if payload.get("estimated_tokens") == estimate:
            return
        payload["estimated_tokens"] = estimate


def docs_context_fallback_allowed(
    *, raw: dict[str, Any], args: dict[str, Any], recovery: Any,
) -> bool:
    return bool(
        args.get("project_path")
        and not args.get("library")
        and not args.get("libraries")
        and str(raw.get("mode_selected") or "") == "project"
        and str(raw.get("status") or "") in {"success", "partial_success"}
        and not raw.get("requires_confirmation")
        and not raw.get("hard_stop")
        and not is_operational_recovery_action(recovery)
    )


def maybe_project_docs_context(
    *, projection: dict[str, Any], snapshot: dict[str, dict[str, Any]],
    raw: dict[str, Any], args: dict[str, Any], recovery: Any, output_budget: int,
    allow_fallback: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if (
        not allow_fallback
        or projection.get("status") != "insufficient_evidence"
        or not docs_context_fallback_allowed(raw=raw, args=args, recovery=recovery)
    ):
        return projection, snapshot
    context_projection, context_snapshot = project_docs_context(
        retrieval=raw, max_tokens=min(DOCS_CONTEXT_MAX_TOKENS, output_budget),
    )
    if context_projection.get("status") in {"ok", "truncated"}:
        return context_projection, context_snapshot
    return projection, snapshot
