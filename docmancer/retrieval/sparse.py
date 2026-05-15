"""Sparse retrieval (SPLADE) against a Qdrant collection."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docmancer.embeddings.base import EmbeddingsProvider
    from docmancer.stores.base import VectorHit, VectorStore


def sparse_search(
    *,
    vector_store: "VectorStore",
    provider: "EmbeddingsProvider",
    collection: str,
    query: str,
    limit: int = 20,
    filters: dict | None = None,
) -> list["VectorHit"]:
    sparse = provider.embed_sparse_query(query)
    return vector_store.search(
        collection,
        None,
        limit=limit,
        filters=filters,
        mode="sparse",
        sparse_vector=sparse.as_dict(),
    )
