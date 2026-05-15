from __future__ import annotations

from types import SimpleNamespace

from docmancer.stores.qdrant_store import QdrantStore


class _FakeClient:
    def __init__(self, raw_count: int) -> None:
        self.raw_count = raw_count

    def count(self, *, collection_name: str, exact: bool):
        assert collection_name == "docs"
        assert exact is True
        return SimpleNamespace(count=self.raw_count)


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
