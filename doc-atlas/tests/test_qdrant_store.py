from __future__ import annotations

import math
import uuid

import pytest

pytest.importorskip("qdrant_client")


def _qdrant_available(url: str = "http://localhost:6333") -> bool:
    try:
        import httpx

        return httpx.get(f"{url}/readyz", timeout=1.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_available(), reason="local Qdrant not running"
)

from docmancer.core.config import VectorStoreConfig  # noqa: E402
from docmancer.stores import VectorPoint, get_vector_store  # noqa: E402
from docmancer.stores.qdrant_store import QdrantStore  # noqa: E402


DIM = 8


def _normalize(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def _store() -> QdrantStore:
    config = VectorStoreConfig(provider="qdrant", url="http://localhost:6333")
    store = get_vector_store(config, embeddings_dim=DIM)
    assert isinstance(store, QdrantStore)
    return store


def _collection_name(prefix: str = "dm_test") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def test_factory_returns_qdrant_store():
    store = _store()
    assert store.health_check() is True


def test_ensure_collection_idempotent():
    store = _store()
    name = _collection_name()
    try:
        store.ensure_collection(name, DIM)
        store.ensure_collection(name, DIM)
        assert store.count(name) == 0
    finally:
        try:
            store.delete_collection(name)
        except Exception:
            pass


def test_upsert_and_search_dense():
    store = _store()
    name = _collection_name()
    try:
        store.ensure_collection(name, DIM)
        points = [
            VectorPoint(
                id=str(uuid.uuid4()),
                vector=_normalize([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                payload={"format": "md", "docset_root": "/a"},
            ),
            VectorPoint(
                id=str(uuid.uuid4()),
                vector=_normalize([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                payload={"format": "pdf", "docset_root": "/b"},
            ),
        ]
        store.upsert(name, points)
        hits = store.search(
            name,
            query_vector=_normalize([1.0, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            limit=2,
        )
        assert hits, "expected at least one search hit"
        # The closest match should be the first point (id of the [1,0,...] vector).
        assert hits[0].id == points[0].id
    finally:
        try:
            store.delete_collection(name)
        except Exception:
            pass


def test_search_with_payload_filter():
    store = _store()
    name = _collection_name()
    try:
        store.ensure_collection(name, DIM)
        a_id = str(uuid.uuid4())
        b_id = str(uuid.uuid4())
        store.upsert(
            name,
            [
                VectorPoint(
                    id=a_id,
                    vector=_normalize([1.0, 0, 0, 0, 0, 0, 0, 0]),
                    payload={"format": "md"},
                ),
                VectorPoint(
                    id=b_id,
                    vector=_normalize([1.0, 0, 0, 0, 0, 0, 0, 0]),
                    payload={"format": "pdf"},
                ),
            ],
        )
        hits = store.search(
            name,
            query_vector=_normalize([1.0, 0, 0, 0, 0, 0, 0, 0]),
            limit=5,
            filters={"format": "pdf"},
        )
        assert hits
        assert all(h.payload.get("format") == "pdf" for h in hits)
        assert any(h.id == b_id for h in hits)
    finally:
        try:
            store.delete_collection(name)
        except Exception:
            pass


def test_count_reports_points():
    store = _store()
    name = _collection_name()
    try:
        store.ensure_collection(name, DIM)
        baseline = store.count(name)
        store.upsert(
            name,
            [
                VectorPoint(
                    id=str(uuid.uuid4()),
                    vector=_normalize([1.0] + [0.0] * (DIM - 1)),
                    payload={},
                )
            ],
        )
        assert store.count(name) == baseline + 1
    finally:
        try:
            store.delete_collection(name)
        except Exception:
            pass


def test_delete_collection_refuses_foreign():
    store = _store()
    name = _collection_name(prefix="dm_foreign")
    # Create the collection directly via the raw client so the docmancer
    # sentinel is absent. delete_collection must refuse.
    qm = store._qm
    store._client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": qm.VectorParams(size=DIM, distance=qm.Distance.COSINE)
        },
    )
    try:
        with pytest.raises(PermissionError):
            store.delete_collection(name)
    finally:
        store._client.delete_collection(collection_name=name)


def test_health_check_true():
    store = _store()
    assert store.health_check() is True


def test_ensure_collection_refuses_foreign_existing():
    """A pre-existing foreign collection must not be claimed by writing the sentinel."""
    store = _store()
    name = _collection_name(prefix="dm_foreign_claim")
    qm = store._qm
    store._client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": qm.VectorParams(size=DIM, distance=qm.Distance.COSINE)
        },
    )
    try:
        with pytest.raises(PermissionError):
            store.ensure_collection(name, DIM)
        # And the collection is still not docmancer-owned afterwards.
        assert store._is_owned(name) is False
    finally:
        store._client.delete_collection(collection_name=name)


def test_delete_points_drops_by_id():
    store = _store()
    name = _collection_name(prefix="dm_prune")
    try:
        store.ensure_collection(name, DIM)
        pid_a = 1001
        pid_b = 1002
        store.upsert(
            name,
            [
                VectorPoint(id=pid_a, vector=_normalize([1.0] + [0.0] * (DIM - 1)), payload={}),
                VectorPoint(id=pid_b, vector=_normalize([0.0, 1.0] + [0.0] * (DIM - 2)), payload={}),
            ],
        )
        # delete_points reports what it removed.
        assert store.delete_points(name, [pid_a]) == 1
        # b is still searchable; a no longer is.
        hits = store.search(name, _normalize([1.0] + [0.0] * (DIM - 1)), limit=5)
        ids = [h.id for h in hits]
        assert str(pid_a) not in ids
    finally:
        try:
            store.delete_collection(name)
        except Exception:
            pass
