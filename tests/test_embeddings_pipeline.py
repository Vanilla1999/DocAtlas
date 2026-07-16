"""Integration test for sync_vector_store, focused on prune semantics."""
from __future__ import annotations

import pytest

pytest.importorskip("sqlite_vec")

from docmancer.core.config import DocmancerConfig, VectorStoreConfig
from docmancer.agent import DocmancerAgent
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.embeddings.base import EmbeddingsProvider
from docmancer.embeddings.pipeline import sync_vector_store
from docmancer.stores import get_vector_store


DIM = 4


class StubProvider(EmbeddingsProvider):
    name = "stub"
    model_name = "stub"
    dimensions = DIM
    max_batch_size = 8

    def embed(self, texts):
        # Deterministic hash-derived vectors so re-embedding the same chunk
        # produces the same cache hit.
        out = []
        for t in texts:
            h = abs(hash(t))
            v = [((h >> (i * 8)) & 0xFF) / 255.0 for i in range(DIM)]
            out.append(v)
        return out

    def embed_query(self, query):
        return self.embed([query])[0]


def _config(tmp_path) -> DocmancerConfig:
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.embeddings.cache = str(tmp_path / "cache")
    config.embeddings.dimensions = DIM
    config.vector_store = VectorStoreConfig(
        provider="sqlite-vec",
        options={"db_path": str(tmp_path / "vec.db")},
    )
    return config


def _make_doc(source: str, content: str) -> Document:
    return Document(source=source, content=content, metadata={"format": "markdown"})


def _make_parent_child_doc(source: str, content: str) -> Document:
    return Document(
        source=source,
        content=content,
        metadata={
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 32,
            "child_hard_max_tokens": 64,
        },
    )


def test_sync_prunes_vectors_for_removed_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = _config(tmp_path)
    store = SQLiteStore(config.index.db_path)
    vector_store = get_vector_store(config.vector_store, embeddings_dim=DIM)
    provider = StubProvider()
    collection = "dm_test_prune"

    docs = [
        _make_doc("doc1.md", "# A\n\nfirst section.\n\n# B\n\nsecond section.\n"),
        _make_doc("doc2.md", "# C\n\nthird section.\n"),
    ]
    store.add_documents(docs, recreate=True)

    result = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vector_store,
        collection=collection,
    )
    initial_points = vector_store.count(collection)
    assert initial_points >= 3
    assert result.upserted >= 3
    assert result.pruned == 0

    # Recreate the index with only doc1, dropping every section under doc2.
    # SQLite section ids change too because add_documents(recreate=True) wipes
    # the table — so prune must be keyed on "ids present in upserts but not in
    # current sections", not on hashes alone.
    store.add_documents([_make_doc("doc1.md", "# A\n\nfirst section.\n")], recreate=True)
    result2 = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vector_store,
        collection=collection,
    )
    assert result2.pruned >= 1
    # Every remaining vector point must correspond to a current SQLite section.
    surviving_chunk_ids = {
        int(s["section_id"]) for s in store.list_sections_for_embedding()
    }
    upsert_rows = store.list_embedding_upserts(collection)
    assert set(upsert_rows.keys()).issubset(surviving_chunk_ids)
    # Vector point count never exceeds current section count.
    assert vector_store.count(collection) <= len(surviving_chunk_ids)


def test_scoped_sync_writes_only_requested_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = _config(tmp_path)
    store = SQLiteStore(config.index.db_path)
    vector_store = get_vector_store(config.vector_store, embeddings_dim=DIM)
    provider = StubProvider()
    collection = "dm_test_scoped"
    store.add_documents([
        _make_doc("changed.md", "# Changed\n\nnew content.\n"),
        _make_doc("unrelated.md", "# Unrelated\n\nuntouched content.\n"),
    ])
    changed_ids = set(store.section_ids_for_source("changed.md"))

    result = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vector_store,
        collection=collection,
        section_ids=changed_ids,
        prune_ids=set(),
    )

    assert result.upserted == len(changed_ids)
    assert set(store.list_embedding_upserts(collection)) == changed_ids


def test_real_sqlite_vec_parent_child_incremental_uuid_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = _config(tmp_path)
    store = SQLiteStore(config.index.db_path)
    vector_store = get_vector_store(config.vector_store, embeddings_dim=DIM)
    provider = StubProvider()
    collection = "dm_task40_uuid"
    before = "# Alpha\n\nunchanged\n\n# Beta\n\nold value\n"

    first = store.add_documents(
        [_make_parent_child_doc("guide.md", before)],
        activate_generation=False,
    )
    store.set_generation_vector_collection(str(first.generation_id), collection)
    initial = sync_vector_store(
        store=store, config=config, provider=provider,
        vector_store=vector_store, collection=collection,
        generation_id=first.generation_id,
    )
    store.activate_generation(str(first.generation_id))

    unchanged = store.add_documents(
        [_make_parent_child_doc("guide.md", before)],
        activate_generation=False,
    )
    unchanged_sync = sync_vector_store(
        store=store, config=config, provider=provider,
        vector_store=vector_store, collection=collection,
        generation_id=unchanged.generation_id, prune_stale=False,
    )
    store.activate_generation(str(unchanged.generation_id))
    unchanged_prune = sync_vector_store(
        store=store, config=config, provider=provider,
        vector_store=vector_store, collection=collection,
        generation_id=unchanged.generation_id, prune_stale=True,
    )

    edited = store.add_documents(
        [_make_parent_child_doc("guide.md", before.replace("old value", "new value"))],
        activate_generation=False,
    )
    edited_sync = sync_vector_store(
        store=store, config=config, provider=provider,
        vector_store=vector_store, collection=collection,
        generation_id=edited.generation_id, prune_stale=False,
    )
    store.activate_generation(str(edited.generation_id))
    edited_prune = sync_vector_store(
        store=store, config=config, provider=provider,
        vector_store=vector_store, collection=collection,
        generation_id=edited.generation_id, prune_stale=True,
    )

    assert initial.upserted > 0
    assert unchanged_sync.upserted == 0
    assert unchanged_prune.pruned == 0
    assert edited_sync.upserted == 1
    assert edited_prune.pruned == 1
    assert vector_store.count(collection) == len(store.list_sections_for_embedding())


def test_agent_prunes_exact_chunks_without_embedding_unrelated_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DOCMANCER_AUTO_VECTORS", raising=False)
    config = _config(tmp_path)
    collection = "dm_test_exact_prune"
    config.vector_store = config.vector_store.model_copy(update={"collection": collection})
    store = SQLiteStore(config.index.db_path)
    vector_store = get_vector_store(config.vector_store, embeddings_dim=DIM)
    store.add_documents([
        _make_doc("removed.md", "# Removed\n\nold content.\n"),
        _make_doc("kept.md", "# Kept\n\ncurrent content.\n"),
    ])
    sync_vector_store(
        store=store,
        config=config,
        provider=StubProvider(),
        vector_store=vector_store,
        collection=collection,
    )
    removed_ids = set(store.section_ids_for_source("removed.md"))
    kept_ids = set(store.section_ids_for_source("kept.md"))

    deleted = DocmancerAgent(config=config).prune_vector_chunks(removed_ids)

    assert deleted == len(removed_ids)
    assert set(store.list_embedding_upserts(collection)) == kept_ids
    assert vector_store.count(collection) == len(kept_ids)
