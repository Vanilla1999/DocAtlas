"""Connect SQLite sections to vector store + embeddings provider.

Used by the ingest path to embed and upsert chunks after they are written
to SQLite, and to reconcile drift between SQLite state and the vector
store at the start of an ingest run.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from docmancer.embeddings.base import (
    EmbeddingsCache,
    EmbeddingsProvider,
    content_cache_key,
    embed_with_cache,
)
from docmancer.stores.base import VectorPoint, VectorStore

if TYPE_CHECKING:
    from docmancer.core.config import DocmancerConfig
    from docmancer.core.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    embedded: int
    upserted: int
    skipped_cache: int
    skipped_unchanged: int
    pruned: int = 0


def _embedding_hash(vector: list[float]) -> str:
    """Quick fingerprint to detect drift between cache and store."""
    h = hashlib.sha256()
    # Round to 6 decimal places to stabilise across cache hits.
    for v in vector:
        h.update(f"{v:.6f}".encode("ascii"))
        h.update(b",")
    return h.hexdigest()[:32]


def _payload_for_section(section: dict, *, docset_root: str | None = None) -> dict:
    return {
        "section_id": int(section["section_id"]),
        "source": section["source"],
        "chunk_index": int(section["chunk_index"]),
        "title": section["title"],
        "level": section["level"],
        "source_path": section.get("source_path") or "",
        "source_path_prefix": (section.get("source_path") or "").rsplit("/", 1)[0],
        "document_title": section.get("document_title") or "",
        "document_title_hash": hashlib.sha1(
            (section.get("document_title") or "").encode("utf-8")
        ).hexdigest()[:16],
        "format": section.get("format") or "",
        "anchor": section.get("anchor") or "",
        "content_hash": section.get("content_hash") or "",
        "token_estimate": section.get("token_estimate", 0),
        "docset_root": docset_root or "",
    }


def sync_vector_store(
    *,
    store: "SQLiteStore",
    config: "DocmancerConfig",
    provider: EmbeddingsProvider,
    vector_store: VectorStore,
    collection: str,
    include_sparse: bool = False,
) -> SyncResult:
    """Embed every SQLite section, upsert into the vector store, record state.

    Cache hits are reused; sections whose ``content_hash`` already matches
    the recorded upsert state are skipped entirely. The collection is
    created on the fly if needed.
    """
    sections = store.list_sections_for_embedding()
    cache = EmbeddingsCache(config.embeddings.cache)

    # Ensure the collection exists *before* pruning so we have somewhere to
    # delete from on a totally fresh install with an empty SQLite section table.
    vector_store.ensure_collection(
        collection,
        dimensions=int(config.embeddings.dimensions or provider.dimensions or 768),
        sparse=include_sparse,
    )

    existing = store.list_embedding_upserts(collection)
    current_ids = {int(sec["section_id"]) for sec in sections}

    # Prune: any chunk_id recorded in embedding_upserts but absent from the
    # current sections table belongs to a deleted/recreated source. Delete the
    # vector points and the upsert bookkeeping rows so dense/hybrid retrieval
    # cannot resurrect points that have no SQLite section to hydrate.
    stale_ids = [chunk_id for chunk_id in existing if chunk_id not in current_ids]
    pruned = 0
    if stale_ids:
        try:
            pruned = vector_store.delete_points(collection, stale_ids)
        except NotImplementedError:
            pruned = 0
        store.delete_embedding_upserts(collection, stale_ids)

    if not sections:
        return SyncResult(
            embedded=0, upserted=0, skipped_cache=0, skipped_unchanged=0, pruned=pruned
        )

    pending: list[dict] = []
    skipped_unchanged = 0
    for sec in sections:
        prev = existing.get(int(sec["section_id"]))
        if prev and prev.get("content_hash") == (sec.get("content_hash") or ""):
            skipped_unchanged += 1
            continue
        pending.append(sec)

    if not pending:
        return SyncResult(
            embedded=0,
            upserted=0,
            skipped_cache=0,
            skipped_unchanged=skipped_unchanged,
            pruned=pruned,
        )

    texts = [sec["text"] for sec in pending]
    pre_cache_keys = [
        content_cache_key(provider.name, getattr(provider, "model_name", provider.name), t)
        for t in texts
    ]
    cache_hits_before = sum(1 for k in pre_cache_keys if cache.get(k) is not None)
    vectors = embed_with_cache(
        provider,
        texts,
        cache=cache,
        model=getattr(provider, "model_name", provider.name),
    )

    sparse_vectors: list = []
    if include_sparse:
        try:
            sparse_vectors = provider.embed_sparse(texts)
        except NotImplementedError:
            sparse_vectors = []
            include_sparse = False

    points: list[VectorPoint] = []
    for idx, sec in enumerate(pending):
        sparse_payload = None
        if include_sparse and idx < len(sparse_vectors):
            sparse_payload = sparse_vectors[idx].as_dict()
        # Qdrant accepts unsigned int or UUID-formatted strings as point ids.
        # We reuse the SQLite section id directly so reconciliation is trivial.
        points.append(
            VectorPoint(
                id=int(sec["section_id"]),
                vector=vectors[idx],
                payload=_payload_for_section(sec),
                sparse_vector=sparse_payload,
            )
        )

    bulk = len(points) >= 512
    vector_store.upsert(collection, points, bulk=bulk)

    store.record_embedding_upserts(
        collection,
        [
            {
                "chunk_id": int(sec["section_id"]),
                "content_hash": sec.get("content_hash") or "",
                "embedding_hash": _embedding_hash(vectors[idx]),
                "status": "ok",
            }
            for idx, sec in enumerate(pending)
        ],
    )

    return SyncResult(
        embedded=len(pending) - cache_hits_before,
        upserted=len(points),
        skipped_cache=cache_hits_before,
        skipped_unchanged=skipped_unchanged,
        pruned=pruned,
    )


__all__ = ["sync_vector_store", "SyncResult"]
