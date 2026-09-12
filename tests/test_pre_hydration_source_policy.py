from __future__ import annotations

from types import SimpleNamespace

from docmancer.retrieval.dispatch import RetrievalDispatcher


class _Store:
    def __init__(self, *, metadata_error: bool = False) -> None:
        self.metadata_error = metadata_error
        self.hydrated_ids: list[int] = []

    def adjacent_section_ids(self, section_id: int, *, mode: str = "adjacent") -> list[int]:
        assert section_id == 1
        assert mode == "adjacent"
        return [2]

    def section_filter_metadata_for(self, section_ids: list[int]):
        assert section_ids == [1, 2]
        if self.metadata_error:
            raise RuntimeError("metadata lookup failed")
        return {
            1: {
                "source": "docs/current.md",
                "source_class": "project_file",
                "lifecycle_status": "active",
            },
            2: {
                "source": "docs/history.md",
                "source_class": "project_file",
                "lifecycle_status": "superseded",
            },
        }

    def fetch_sections_by_id(self, section_ids: list[int], *, budget: int):
        self.hydrated_ids = list(section_ids)
        return []


def _dispatcher(store: _Store) -> RetrievalDispatcher:
    dispatcher = object.__new__(RetrievalDispatcher)
    dispatcher.store = store
    dispatcher.config = SimpleNamespace(
        retrieval=SimpleNamespace(
            fusion=SimpleNamespace(method="rrf", rrf_k=60, weights={}),
            max_sections_per_source=None,
        )
    )
    dispatcher._rank_candidate_lists = lambda _candidate_lists: [
        ("safe", 1.0, {"lexical": 1})
    ]
    return dispatcher


def test_adjacent_source_policy_is_enforced_before_text_hydration():
    store = _Store()
    dispatcher = _dispatcher(store)

    dispatcher._fuse_and_hydrate(
        {"lexical": [{"id": "safe", "hydration_id": 1, "score": 1.0}]},
        query="plain words",
        limit=2,
        budget=200,
        expand="adjacent",
        counts={"lexical": 1},
        mode="hybrid",
        filters={
            "source_class": "project_file",
            "lifecycle_status": {"in": ["active", "current"]},
        },
    )

    assert store.hydrated_ids == [1]


def test_pre_hydration_metadata_failure_fails_closed():
    store = _Store(metadata_error=True)
    dispatcher = _dispatcher(store)

    allowed = dispatcher._filter_section_ids_before_hydration(
        [1, 2],
        {"lifecycle_status": {"in": ["active", "current"]}},
    )

    assert allowed == []
    assert store.hydrated_ids == []
