"""Score fusion across retrieval signals.

Implements vanilla Reciprocal Rank Fusion and a weighted variant. Both
operate on candidate lists keyed by an arbitrary id (we use the SQLite
section id), so the same fusion can combine lexical, dense, and sparse
results without caring which produced what.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def reciprocal_rank_fusion(
    candidates: Mapping[str, list[Any]],
    *,
    k_rrf: int = 60,
    id_key: str = "id",
) -> list[tuple[Any, float, dict[str, int]]]:
    """Combine ranked candidate lists with RRF.

    ``candidates`` maps a source name (e.g. "lexical", "dense") to an
    ordered list of hits. Each hit must expose its id via attribute or key
    ``id_key``. Returns ``(id, score, contributions)`` triples sorted by
    score desc, where ``contributions`` maps source -> rank (1-indexed).
    """
    scores: dict[Any, float] = {}
    contributions: dict[Any, dict[str, int]] = {}
    for source, hits in candidates.items():
        for rank, hit in enumerate(hits, start=1):
            hit_id = _id_of(hit, id_key)
            scores[hit_id] = scores.get(hit_id, 0.0) + 1.0 / (k_rrf + rank)
            contributions.setdefault(hit_id, {})[source] = rank
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(hid, score, contributions.get(hid, {})) for hid, score in ordered]


def weighted_rrf(
    candidates: Mapping[str, list[Any]],
    *,
    weights: Mapping[str, float] | None = None,
    k_rrf: int = 60,
    id_key: str = "id",
) -> list[tuple[Any, float, dict[str, int]]]:
    """RRF with per-source weights. Missing weights default to 1.0."""
    weights = weights or {}
    scores: dict[Any, float] = {}
    contributions: dict[Any, dict[str, int]] = {}
    for source, hits in candidates.items():
        w = float(weights.get(source, 1.0))
        for rank, hit in enumerate(hits, start=1):
            hit_id = _id_of(hit, id_key)
            scores[hit_id] = scores.get(hit_id, 0.0) + w / (k_rrf + rank)
            contributions.setdefault(hit_id, {})[source] = rank
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(hid, score, contributions.get(hid, {})) for hid, score in ordered]


def _id_of(hit: Any, id_key: str) -> Any:
    if isinstance(hit, Mapping):
        return hit[id_key]
    return getattr(hit, id_key)
