from __future__ import annotations

from docmancer.core.models import RetrievedChunk
from docmancer.retrieval._dispatch_part02 import _RetrievalDispatcherPart02


class _Store:
    def __init__(self) -> None:
        self.hydrated_ids: list[int] = []

    def fetch_section_filter_metadata(self, section_ids: list[int]) -> list[dict]:
        rows = {
            1: {
                "section_id": 1,
                "source": "docs/current.md",
                "source_class": "project_file",
                "lifecycle_status": "active",
            },
            2: {
                "section_id": 2,
                "source": "docs/history.md",
                "source_class": "project_file",
                "lifecycle_status": "historical",
            },
        }
        return [rows[value] for value in section_ids if value in rows]

    def fetch_sections_by_id(self, section_ids: list[int], *, budget: int) -> list[RetrievedChunk]:
        self.hydrated_ids.extend(section_ids)
        return [
            RetrievedChunk(
                source=f"docs/{value}.md",
                chunk_index=value,
                text=f"section {value}",
                score=1.0,
                metadata={"section_id": value},
            )
            for value in section_ids
        ]


def test_section_ids_are_policy_filtered_before_hydration() -> None:
    dispatcher = _RetrievalDispatcherPart02()
    dispatcher.store = _Store()

    chunks = dispatcher._hydrate_policy_filtered(
        [1, 2],
        budget=500,
        filters={"lifecycle_status": {"in": ["active", "current"]}},
    )

    assert dispatcher.store.hydrated_ids == [1]
    assert [chunk.metadata["section_id"] for chunk in chunks] == [1]


def test_fuse_and_hydrate_never_hydrates_policy_rejected_expansion() -> None:
    dispatcher = _RetrievalDispatcherPart02()
    dispatcher.store = _Store()

    chunks = dispatcher._hydrate_policy_filtered(
        [2, 1],
        budget=500,
        filters={"forbidden_sources": ["docs/history.md"]},
    )

    assert dispatcher.store.hydrated_ids == [1]
    assert [chunk.metadata["section_id"] for chunk in chunks] == [1]
