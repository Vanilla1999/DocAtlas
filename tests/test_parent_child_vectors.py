from __future__ import annotations

import hashlib
import uuid

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.embeddings.base import EmbeddingsProvider
from docmancer.embeddings.pipeline import sync_vector_store
from docmancer.stores.base import VectorHit, VectorPoint, VectorStore


class DeterministicProvider(EmbeddingsProvider):
    name = "task40-test"
    model_name = "sha256-test"
    dimensions = 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [value / 255.0 for value in hashlib.sha256(text.encode()).digest()[:4]]
            for text in texts
        ]

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


class MemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self.points: dict[str, dict[str, VectorPoint]] = {}

    def ensure_collection(
        self,
        name: str,
        dimensions: int,
        *,
        sparse: bool = False,
        options: dict | None = None,
    ) -> None:
        self.points.setdefault(name, {})

    def upsert(
        self, collection: str, points: list[VectorPoint], *, bulk: bool = False
    ) -> None:
        target = self.points.setdefault(collection, {})
        for point in points:
            target[str(point.id)] = point

    def search(
        self,
        collection: str,
        query_vector: list[float] | None,
        *,
        limit: int = 10,
        filters: dict | None = None,
        sparse_vector: dict[int, float] | None = None,
        mode: str = "dense",
    ) -> list[VectorHit]:
        return []

    def count(self, collection: str) -> int:
        return len(self.points.get(collection, {}))

    def delete_points(self, collection: str, ids: list) -> int:
        target = self.points.setdefault(collection, {})
        deleted = 0
        for point_id in ids:
            deleted += int(target.pop(str(point_id), None) is not None)
        return deleted

    def delete_collection(self, collection: str) -> None:
        self.points.pop(collection, None)

    def health_check(self) -> bool:
        return True


def _doc(content: str) -> Document:
    return Document(
        source="docs/guide.md",
        content=content,
        metadata={
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 32,
            "child_hard_max_tokens": 64,
        },
    )


def test_generation_vector_sync_is_stable_incremental_and_prunes(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.embeddings.cache = str(tmp_path / "cache")
    config.embeddings.dimensions = 4
    store = SQLiteStore(tmp_path / "index.db")
    vectors = MemoryVectorStore()
    provider = DeterministicProvider()
    collection = "task40_pc_config"
    before = "# Alpha\n\nunchanged\n\n# Beta\n\nold value\n"

    first = store.add_documents([_doc(before)], activate_generation=False)
    store.set_generation_vector_collection(str(first.generation_id), collection)
    initial = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vectors,
        collection=collection,
        generation_id=first.generation_id,
    )
    store.activate_generation(str(first.generation_id))
    first_rows = store.list_sections_for_embedding(first.generation_id)
    first_ids = {row["stable_chunk_id"] for row in first_rows}
    assert initial.upserted == len(first_ids)
    assert all(str(uuid.UUID(str(row["vector_id"]))) == row["vector_id"] for row in first_rows)

    unchanged = store.add_documents([_doc(before)], activate_generation=False)
    store.set_generation_vector_collection(str(unchanged.generation_id), collection)
    unchanged_sync = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vectors,
        collection=collection,
        generation_id=unchanged.generation_id,
        prune_stale=False,
    )
    assert unchanged_sync.upserted == 0
    assert unchanged_sync.skipped_unchanged == len(first_ids)
    assert {
        row["stable_chunk_id"]
        for row in store.list_sections_for_embedding(unchanged.generation_id)
    } == first_ids
    store.activate_generation(unchanged.generation_id)

    edited = store.add_documents(
        [_doc(before.replace("old value", "new value"))],
        activate_generation=False,
    )
    store.set_generation_vector_collection(str(edited.generation_id), collection)
    edit_sync = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vectors,
        collection=collection,
        generation_id=edited.generation_id,
        prune_stale=False,
    )
    assert edit_sync.upserted == 1
    store.activate_generation(edited.generation_id)
    prune_sync = sync_vector_store(
        store=store,
        config=config,
        provider=provider,
        vector_store=vectors,
        collection=collection,
        generation_id=edited.generation_id,
        prune_stale=True,
    )
    assert prune_sync.upserted == 0
    assert prune_sync.pruned == 1
    assert vectors.count(collection) == len(store.list_sections_for_embedding())
    assert store.index_health(collection)["ok"] is True


def test_generation_vectors_keep_additive_legacy_rows_hydratable(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.embeddings.cache = str(tmp_path / "cache")
    config.embeddings.dimensions = 4
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents([
        Document(source="legacy.txt", content="legacy vector sentinel"),
    ])
    generation = store.add_documents(
        [_doc("# Current\n\ncurrent sentinel\n")],
        activate_generation=False,
    )
    vectors = MemoryVectorStore()
    collection = "task40_mixed"
    store.set_generation_vector_collection(str(generation.generation_id), collection)

    result = sync_vector_store(
        store=store,
        config=config,
        provider=DeterministicProvider(),
        vector_store=vectors,
        collection=collection,
        generation_id=generation.generation_id,
    )
    store.activate_generation(str(generation.generation_id))
    rows = store.list_sections_for_embedding(generation.generation_id)
    legacy = next(row for row in rows if row["source"] == "legacy.txt")

    assert result.upserted == len(rows)
    assert legacy["chunk_schema_version"] == "sqlite-sections-v1"
    hydrated = store.fetch_sections_by_id([legacy["section_id"]], budget=100)
    assert hydrated[0].text == "legacy vector sentinel"
