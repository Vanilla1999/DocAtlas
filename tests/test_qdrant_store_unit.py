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








class _FakeUploadClient:
    def __init__(self) -> None:
        self.calls = []

    def upload_points(self, **kwargs):
        self.calls.append(kwargs)

