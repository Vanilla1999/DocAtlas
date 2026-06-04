"""Explain trace schema and builders."""
from __future__ import annotations

import time
from typing import Any

TRACE_SCHEMA_VERSION = 1


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def started_timer() -> float:
    return time.perf_counter()


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def build_explain_trace(
    *,
    query: str,
    selected_mode: str,
    chunks: list[Any],
    limit: int | None,
    budget: int | None,
    expand: str | None,
    contributions: dict[Any, dict[str, int]] | None = None,
    candidate_counts: dict[str, int] | None = None,
    failures: dict[str, str] | None = None,
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    contributions = contributions or {}
    candidate_counts = candidate_counts or {}
    failures = failures or {}
    doc_tokens = 0
    raw_tokens = 0
    if chunks:
        meta = chunks[0].metadata or {}
        doc_tokens = int(meta.get("docmancer_tokens") or 0)
        raw_tokens = int(meta.get("raw_tokens") or 0)
    result_items = []
    for rank, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata or {}
        section_id = meta.get("section_id")
        result_items.append(
            {
                "rank": rank,
                "source": chunk.source,
                "title": meta.get("title"),
                "section_id": section_id,
                "score": float(getattr(chunk, "score", 0.0)),
                "token_estimate": int(meta.get("token_estimate") or 0),
                "fusion_contributions": contributions.get(section_id, {}) if section_id is not None else {},
            }
        )
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "query_normalization": {"original": query, "normalized": normalize_query(query)},
        "selected_mode": selected_mode,
        "routers": {"matched": [], "applied_filters": {}},
        "candidates": {"counts": candidate_counts},
        "fusion": {"contributions": contributions},
        "expansion": {"mode": expand or "none"},
        "packing": {"limit": limit, "budget": budget, "result_count": len(chunks), "docmancer_tokens": doc_tokens, "raw_tokens": raw_tokens},
        "results": result_items,
        "warnings": [],
        "failures": failures,
        "timing": {"total_ms": latency_ms},
    }


def validate_explain_trace(trace: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "query_normalization",
        "selected_mode",
        "routers",
        "candidates",
        "fusion",
        "expansion",
        "packing",
        "warnings",
        "failures",
        "timing",
    ]
    missing = [key for key in required if key not in trace]
    if missing:
        raise ValueError(f"Explain trace missing required keys: {', '.join(missing)}")
    if trace["schema_version"] != TRACE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported trace schema_version: {trace['schema_version']}")
    if "normalized" not in trace["query_normalization"]:
        raise ValueError("Explain trace query_normalization.normalized is required")
