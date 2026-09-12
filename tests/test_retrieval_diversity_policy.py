from __future__ import annotations

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.retrieval.dispatch import RetrievalDispatcher


def _chunk(source: str, label: str, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        chunk_index=rank,
        text=label,
        score=max(0.0, 1.0 - rank * 0.01),
        metadata={},
    )


def _dispatcher() -> RetrievalDispatcher:
    config = DocmancerConfig()
    config.retrieval.max_sections_per_source = 2
    return RetrievalDispatcher(store=object(), config=config)  # type: ignore[arg-type]


def test_soft_source_cap_backfills_unused_global_slots() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1),
        _chunk("docs/a.md", "A2", 2),
        _chunk("docs/a.md", "A3", 3),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=3)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "A3"]


def test_soft_source_cap_never_displaces_first_candidate_from_other_source() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1),
        _chunk("docs/a.md", "A2", 2),
        _chunk("docs/a.md", "A3", 3),
        _chunk("docs/b.md", "B1", 4),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=3)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "B1"]


def test_soft_source_cap_preserves_rank_order_within_preferred_and_overflow_phases() -> None:
    dispatcher = _dispatcher()
    ranked = [
        _chunk("docs/a.md", "A1", 1),
        _chunk("docs/a.md", "A2", 2),
        _chunk("docs/a.md", "A3", 3),
        _chunk("docs/b.md", "B1", 4),
        _chunk("docs/a.md", "A4", 5),
    ]

    selected = dispatcher._limit_sections_per_source(ranked, limit=5)

    assert [chunk.text for chunk in selected] == ["A1", "A2", "B1", "A3", "A4"]
