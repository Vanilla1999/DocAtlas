"""Connect SQLite sections to vector store + embeddings provider.

Used by the ingest path to embed and upsert chunks after they are written
to SQLite, and to reconcile drift between SQLite state and the vector
store at the start of an ingest run.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from docmancer.core import index_meta
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
    payload = {
        "section_id": int(section["section_id"]),
        "vector_id": section.get("vector_id") or "",
        "generation_id": section.get("generation_id") or "",
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
        "stable_chunk_id": section.get("stable_chunk_id") or "",
        "parent_logical_id": section.get("parent_logical_id") or "",
        "chunk_schema_version": section.get("chunk_schema_version") or "",
        "chunk_config_hash": section.get("chunk_config_hash") or "",
        "context_schema_version": section.get("context_schema_version") or "",
        "context_config_hash": section.get("context_config_hash") or "",
        "context_content_hash": section.get("context_content_hash") or "",
        "embedding_input_hash": section.get("embedding_input_hash") or "",
        "retrieval_config_hash": section.get("retrieval_config_hash") or "",
        "token_estimate": section.get("token_estimate", 0),
        "docset_root": docset_root or "",
    }
    for key in (
        "library_id", "resolved_version", "version_family", "project_identity",
        "project_path", "module_id", "doc_scope", "source_class", "authority",
        "docs_snapshot_exact", "source_identity", "canonical_url", "source_url",
    ):
        value = section.get(key)
        if value is not None:
            payload[key] = value
    return payload


def sync_vector_store(
    *,
    store: "SQLiteStore",
    config: "DocmancerConfig",
    provider: EmbeddingsProvider,
    vector_store: VectorStore,
    collection: str,
    include_sparse: bool = False,
    section_ids: set[int] | None = None,
    prune_ids: set[int] | None = None,
    generation_id: str | None = None,
    prune_stale: bool = True,
) -> SyncResult:
    """Embed selected SQLite sections, upsert them, and record state.

    With no explicit ids this reconciles the full index. Scoped callers may
    provide ``section_ids`` and ``prune_ids`` so unrelated chunks are neither
    embedded nor deleted. Cache hits and unchanged selected sections are
    skipped. The collection is created on the fly if needed.
    """
    effective_generation_id = generation_id or store.active_generation_id()
    all_sections = store.list_sections_for_embedding(
        generation_id=effective_generation_id
    )
    generation_mode = bool(effective_generation_id)
    sections = (
        all_sections
        if section_ids is None
        else [section for section in all_sections if int(section["section_id"]) in section_ids]
    )
    cache = EmbeddingsCache(config.embeddings.cache)

    # Resolve the real dimension from the live provider rather than trusting
    # the config field. FastEmbed can map a configured model name to a
    # different ONNX artifact at load time; sizing the Qdrant collection from
    # the config hint is the original silent-failure mode.
    if hasattr(provider, "_ensure_dense"):
        try:
            provider._ensure_dense()  # type: ignore[attr-defined]
        except Exception:
            pass
    resolved_dim = int(getattr(provider, "dimensions", 0) or 0)
    if resolved_dim <= 0:
        resolved_dim = int(config.embeddings.dimensions or 768)

    sparse_model = (
        getattr(provider, "sparse_model_name", None)
        if include_sparse
        else None
    )
    want_meta = index_meta.CollectionMeta(
        provider=str(getattr(provider, "name", "unknown")),
        model=str(getattr(provider, "model_name", "")),
        dim=resolved_dim,
        sparse_model=(str(sparse_model) if sparse_model else None),
        created_at=index_meta.now_iso(),
    )
    # Refuse to operate on a collection that was built with a different
    # embedder. Prefer metadata on the Qdrant ownership sentinel, then fall
    # back to the sidecar used by older builds.
    vector_meta = getattr(vector_store, "collection_metadata", lambda _collection: None)(collection)
    if vector_meta:
        have_meta = index_meta.CollectionMeta(
            provider=str(vector_meta.get("provider") or ""),
            model=str(vector_meta.get("model") or ""),
            dim=int(vector_meta.get("dim") or 0),
            sparse_model=(str(vector_meta.get("sparse_model")) if vector_meta.get("sparse_model") else None),
            created_at="",
        )
        if (
            have_meta.provider != want_meta.provider
            or have_meta.model != want_meta.model
            or int(have_meta.dim) != int(want_meta.dim)
            or (have_meta.sparse_model or None) != (want_meta.sparse_model or None)
        ):
            raise index_meta.IndexMismatchError(collection, want_meta, have_meta)
    else:
        have_meta = index_meta.get(collection)
        if have_meta is not None:
            index_meta.assert_match(collection, want_meta)

    # Ensure the collection exists *before* pruning so we have somewhere to
    # delete from on a totally fresh install with an empty SQLite section table.
    vector_store.ensure_collection(
        collection,
        dimensions=resolved_dim,
        sparse=include_sparse,
        options={"docmancer_meta": asdict(want_meta)},
    )
    index_meta.put(collection, want_meta)

    existing = (
        store.list_generation_vector_upserts(collection)
        if generation_mode
        else store.list_embedding_upserts(collection)
    )
    current_ids = {int(sec["section_id"]) for sec in all_sections}
    current_stable_ids = {
        str(sec.get("stable_chunk_id") or "") for sec in all_sections
        if sec.get("stable_chunk_id")
    }

    # Prune: any chunk_id recorded in embedding_upserts but absent from the
    # current sections table belongs to a deleted/recreated source. Delete the
    # vector points and the upsert bookkeeping rows so dense/hybrid retrieval
    # cannot resurrect points that have no SQLite section to hydrate.
    if generation_mode:
        stale_keys = [
            stable_id for stable_id in existing
            if stable_id not in current_stable_ids
        ] if prune_stale else []
        stale_ids = [existing[key]["vector_id"] for key in stale_keys]
    else:
        stale_keys = []
        stale_ids = (
            [chunk_id for chunk_id in existing if chunk_id not in current_ids]
            if prune_ids is None
            else [chunk_id for chunk_id in existing if chunk_id in prune_ids]
        )
    pruned = 0
    if stale_ids:
        try:
            pruned = vector_store.delete_points(collection, stale_ids)
        except NotImplementedError:
            pruned = 0
        if generation_mode:
            store.delete_generation_vector_upserts(collection, stale_keys)
        else:
            store.delete_embedding_upserts(collection, stale_ids)

    if not sections:
        return SyncResult(
            embedded=0, upserted=0, skipped_cache=0, skipped_unchanged=0, pruned=pruned
        )

    pending: list[dict] = []
    carried_records: list[dict] = []
    skipped_unchanged = 0
    for sec in sections:
        lookup_id = (
            str(sec.get("stable_chunk_id") or "")
            if generation_mode else int(sec["section_id"])
        )
        prev = existing.get(lookup_id)
        if prev and prev.get("content_hash") == (sec.get("content_hash") or ""):
            skipped_unchanged += 1
            if generation_mode:
                carried_records.append({
                    "stable_chunk_id": str(sec["stable_chunk_id"]),
                    "vector_id": str(sec["vector_id"]),
                    "content_hash": str(sec.get("content_hash") or ""),
                    "embedding_hash": str(prev.get("embedding_hash") or ""),
                    "status": str(prev.get("status") or "ok"),
                })
            continue
        pending.append(sec)

    if not pending:
        if generation_mode and carried_records:
            store.record_generation_vector_upserts(
                collection, str(effective_generation_id), carried_records
            )
        try:
            count_after = int(vector_store.count(collection))
        except Exception:
            count_after = 0
        expected_total = len(current_stable_ids) if generation_mode else len(current_ids)
        if section_ids is None and expected_total > 0 and count_after < expected_total:
            raise RuntimeError(
                f"vector index {collection!r} is incomplete: expected {expected_total} "
                f"indexed points but the vector store reports {count_after}. Rebuild with "
                f"`doc-atlas ingest <path> --recreate`."
            )
        return SyncResult(
            embedded=0,
            upserted=0,
            skipped_cache=0,
            skipped_unchanged=skipped_unchanged,
            pruned=pruned,
        )

    texts = [sec["text"] for sec in pending]
    cache_identity = [
        "\0".join(
            (
                str(sec.get("chunk_schema_version") or "sqlite-sections-v1"),
                str(sec.get("chunk_config_hash") or "legacy"),
                str(sec.get("context_schema_version") or "legacy"),
                str(sec.get("context_config_hash") or "legacy"),
                sec["text"],
            )
        )
        for sec in pending
    ]
    pre_cache_keys = [
        content_cache_key(provider.name, getattr(provider, "model_name", provider.name), identity)
        for identity in cache_identity
    ]
    cache_hits_before = sum(1 for k in pre_cache_keys if cache.get(k) is not None)
    vectors = embed_with_cache(
        provider,
        texts,
        cache=cache,
        model=getattr(provider, "model_name", provider.name),
        cache_identity=cache_identity,
        progress_callback=lambda done, total: logger.info(
            "embedding sections %d/%d", done, total
        ),
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
                id=(str(sec["vector_id"]) if generation_mode else int(sec["section_id"])),
                vector=vectors[idx],
                payload=_payload_for_section(sec),
                sparse_vector=sparse_payload,
            )
        )

    try:
        count_before = int(vector_store.count(collection))
    except Exception:
        count_before = 0

    bulk = len(points) >= 512
    vector_store.upsert(collection, points, bulk=bulk)

    # Verify upserts actually landed. Bulk gRPC upserts return without
    # waiting; if Qdrant rejected the batch (typically a dimension mismatch
    # against a stale collection) the call still looks like it succeeded.
    # We compare counts and refuse to record bookkeeping for points that
    # never made it. Without this check, ingest reports upserted=N while
    # the collection stays effectively empty.
    try:
        count_after = int(vector_store.count(collection))
    except Exception:
        count_after = count_before
    expected_total = len(current_stable_ids) if generation_mode else len(current_ids)
    if section_ids is None and expected_total > 0 and count_after < max(1, expected_total):
        raise RuntimeError(
            f"vector upsert into {collection!r} did not land: expected {expected_total} "
            f"indexed points but the vector store reports {count_after}. The most common cause is "
            f"a dimension or model mismatch against an existing collection. Rebuild with "
            f"`doc-atlas ingest <path> --recreate` or `doc-atlas clear --keep-config "
            f"--keep-models` to wipe the index."
        )

    records = [
        {
            "chunk_id": int(sec["section_id"]),
            "content_hash": sec.get("content_hash") or "",
            "embedding_hash": _embedding_hash(vectors[idx]),
            "status": "ok",
            "stable_chunk_id": sec.get("stable_chunk_id") or "",
            "vector_id": sec.get("vector_id") or "",
        }
        for idx, sec in enumerate(pending)
    ]
    if generation_mode:
        store.record_generation_vector_upserts(
            collection, str(effective_generation_id), [*carried_records, *records]
        )
    else:
        store.record_embedding_upserts(collection, records)

    return SyncResult(
        embedded=len(pending) - cache_hits_before,
        upserted=len(points),
        skipped_cache=cache_hits_before,
        skipped_unchanged=skipped_unchanged,
        pruned=pruned,
    )


__all__ = ["sync_vector_store", "SyncResult"]
