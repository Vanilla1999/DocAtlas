"""Dense retrieval against the configured VectorStore."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docmancer.embeddings.base import EmbeddingsProvider
    from docmancer.stores.base import VectorHit, VectorStore


def dense_search(
    *,
    vector_store: "VectorStore",
    provider: "EmbeddingsProvider",
    collection: str,
    query: str,
    limit: int = 20,
    filters: dict | None = None,
) -> list["VectorHit"]:
    vec = provider.embed_query(query)
    return vector_store.search(
        collection, vec, limit=limit, filters=filters, mode="dense"
    )
