"""Retrieval: lexical (FTS5), dense (Qdrant/SqliteVec), sparse (SPLADE), and hybrid fusion."""
from __future__ import annotations

from .dispatch import RetrievalDispatcher, dispatch_query
from .fusion import reciprocal_rank_fusion, weighted_rrf

__all__ = [
    "RetrievalDispatcher",
    "dispatch_query",
    "reciprocal_rank_fusion",
    "weighted_rrf",
]
