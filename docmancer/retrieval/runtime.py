"""Runtime construction for retrieval paths shared by CLI and public docs APIs.

Lexical retrieval must stay dependency-free.  Dense, sparse, and hybrid
retrieval resolve the same embeddings provider, vector backend, and active
generation collection that vector ingest uses.
"""
from __future__ import annotations

from typing import Any

from .dispatch import HybridRetrievalError, RetrievalDispatcher


VECTOR_MODES = frozenset({"dense", "sparse", "hybrid"})


def effective_retrieval_mode(config: Any, mode: str | None = None) -> str:
    configured = getattr(getattr(config, "retrieval", None), "default_mode", None)
    return str(mode or configured or "lexical").lower()


def dispatcher_for_agent(agent: Any, *, mode: str | None = None) -> RetrievalDispatcher:
    """Build a dispatcher for an agent without touching vector dependencies in lexical mode."""

    config = agent.config
    effective_mode = effective_retrieval_mode(config, mode)
    if effective_mode not in VECTOR_MODES:
        return RetrievalDispatcher(store=agent.store, config=config)

    try:
        from docmancer.embeddings import get_embeddings_provider
        from docmancer.runtime.qdrant_manager import ensure_running
        from docmancer.stores.base import get_vector_store

        vector_config = config.vector_store
        generation_info = agent.store.generation_info() or {}
        persisted_backend = str(generation_info.get("vector_backend") or "").strip().lower()
        if persisted_backend:
            vector_config = vector_config.model_copy(update={"provider": persisted_backend})
        if vector_config.provider == "qdrant" and not vector_config.url:
            resolution = ensure_running()
            if persisted_backend == "qdrant" and (resolution.fallback or not resolution.url):
                raise RuntimeError(
                    "active generation requires qdrant, but its managed backend is unavailable"
                )
            if resolution.fallback or not resolution.url:
                vector_config = vector_config.model_copy(update={"provider": "sqlite-vec"})
            else:
                vector_config = vector_config.model_copy(update={"url": resolution.url})

        vector_store = get_vector_store(
            vector_config,
            embeddings_dim=config.embeddings.dimensions,
        )
        provider = get_embeddings_provider(config.embeddings)
        persisted_identity = str(generation_info.get("vector_backend_identity") or "")
        if not persisted_identity:
            raise RuntimeError(
                "unverified_backend_identity: full vector rebuild required"
            )
        if persisted_identity != vector_store.backend_identity():
            raise RuntimeError("active generation vector backend identity mismatch")
        collection = agent._vector_collection_name()
    except Exception as exc:
        raise HybridRetrievalError(
            {"vector_runtime": f"{type(exc).__name__}: {exc}"}
        ) from exc

    return RetrievalDispatcher(
        store=agent.store,
        config=config,
        vector_store=vector_store,
        provider=provider,
        collection=collection,
    )


__all__ = ["VECTOR_MODES", "dispatcher_for_agent", "effective_retrieval_mode"]
