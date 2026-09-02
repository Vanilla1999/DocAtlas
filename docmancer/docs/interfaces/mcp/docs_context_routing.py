"""Input normalization and safe routing for retrieval-only docs context."""

from __future__ import annotations

import math
from typing import Any

from docmancer.docs.application.model_visible_projection import (
    canonical_projection_bytes,
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
