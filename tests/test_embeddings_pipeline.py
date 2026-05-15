"""Integration test for sync_vector_store, focused on prune semantics."""
from __future__ import annotations

import pytest

pytest.importorskip("sqlite_vec")

from docmancer.core.config import DocmancerConfig, VectorStoreConfig
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


def test_sync_prunes_vectors_for_removed_sections(tmp_path):
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
