from __future__ import annotations

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.retrieval.dispatch import RetrievalDispatcher


def _chunk(
    source: str,
    label: str,
    rank: int,
    *,
    parent: str,
    lines: tuple[int, int],
) -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        chunk_index=rank,
        text=label,
        score=max(0.0, 1.0 - rank * 0.01),
        metadata={
            "parent_logical_id": parent,
            "line_span": list(lines),
        },
    )


def _dispatcher() -> RetrievalDispatcher:
    config = DocmancerConfig()
    config.retrieval.max_sections_per_source = 2
    return RetrievalDispatcher(store=object(), config=config)  # type: ignore[arg-type]


def test_structural_overflow_backfills_same_parent_when_global_slot_unused() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1, parent="intro", lines=(48, 50)),
        _chunk("docs/a.md", "A2", 2, parent="examples", lines=(100, 104)),
        _chunk("docs/a.md", "A3", 3, parent="intro", lines=(51, 55)),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=3)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "A3"]


def test_distant_overflow_without_shared_parent_is_not_backfilled() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1, parent="intro", lines=(9, 13)),
        _chunk("docs/a.md", "A2", 2, parent="conversion", lines=(95, 97)),
        _chunk("docs/a.md", "A3", 3, parent="config", lines=(399, 403)),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=3)

    assert [chunk.text for chunk in selected] == ["A1", "A2"]


def test_structural_overflow_never_displaces_first_candidate_from_other_source() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1, parent="intro", lines=(48, 50)),
        _chunk("docs/a.md", "A2", 2, parent="examples", lines=(100, 104)),
        _chunk("docs/a.md", "A3", 3, parent="intro", lines=(51, 55)),
        _chunk("docs/b.md", "B1", 4, parent="other", lines=(1, 5)),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=3)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "B1"]


def test_structural_overflow_is_bounded_to_one_per_source() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1, parent="intro", lines=(48, 50)),
        _chunk("docs/a.md", "A2", 2, parent="examples", lines=(100, 104)),
        _chunk("docs/a.md", "A3", 3, parent="intro", lines=(51, 55)),
        _chunk("docs/a.md", "A4", 4, parent="intro", lines=(56, 60)),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=4)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "A3"]
