from __future__ import annotations

from types import SimpleNamespace

from docmancer.stores.qdrant_store import QdrantStore
from docmancer.stores.base import VectorPoint


class _FakeClient:
    def __init__(self, raw_count: int) -> None:
        self.raw_count = raw_count

    def count(self, *, collection_name: str, exact: bool):
        assert collection_name == "docs"
        assert exact is True
        return SimpleNamespace(count=self.raw_count)


class _FakeRetrieveClient:
    def __init__(self, payload):
        self.payload = payload

    def retrieve(self, *, collection_name: str, ids: list, with_payload: bool, with_vectors: bool):
        assert collection_name == "docs"
        assert ids == [0]
        assert with_payload is True
        assert with_vectors is False
        return [SimpleNamespace(payload=self.payload)]


def test_count_excludes_ownership_sentinel_for_owned_collection():
    store = object.__new__(QdrantStore)
    store._client = _FakeClient(raw_count=10)
    store._is_owned = lambda collection: collection == "docs"  # type: ignore[method-assign]

    assert store.count("docs") == 9


def test_count_does_not_subtract_for_foreign_collection():
    store = object.__new__(QdrantStore)
    store._client = _FakeClient(raw_count=10)
    store._is_owned = lambda collection: False  # type: ignore[method-assign]

    assert store.count("docs") == 10


def test_collection_metadata_reads_ownership_sentinel_payload():
    store = object.__new__(QdrantStore)
    store._client = _FakeRetrieveClient(
        {
            "_docmancer_owned": True,
            "_docmancer_embedder_provider": "fastembed",
            "_docmancer_embedder_model": "BAAI/bge-base-en-v1.5",
            "_docmancer_embedder_dim": 768,
            "_docmancer_sparse_model": "prithivida/Splade_PP_en_v1",
        }
    )

    meta = store.collection_metadata("docs")

    assert meta == {
        "provider": "fastembed",
        "model": "BAAI/bge-base-en-v1.5",
        "dim": 768,
        "sparse_model": "prithivida/Splade_PP_en_v1",
    }


class _FakeUploadClient:
    def __init__(self) -> None:
        self.calls = []

    def upload_points(self, **kwargs):
        self.calls.append(kwargs)


def test_bulk_upsert_uses_bounded_waited_upload_batches():
    client = _FakeUploadClient()
    store = object.__new__(QdrantStore)
    store.options = {
        "upload_batch_size": 999,
        "upload_parallel": 99,
        "upload_max_retries": 99,
    }
    store._qm = SimpleNamespace(
        PointStruct=lambda **kwargs: SimpleNamespace(**kwargs),
        SparseVector=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    store._bulk_client = lambda: client  # type: ignore[method-assign]
    store._client = object()

    store.upsert(
        "docs",
        [VectorPoint(id=1, vector=[1.0, 0.0], payload={"source": "one"})],
        bulk=True,
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["collection_name"] == "docs"
    assert call["batch_size"] == 256
    assert call["parallel"] == 8
    assert call["max_retries"] == 10
    assert call["wait"] is True
