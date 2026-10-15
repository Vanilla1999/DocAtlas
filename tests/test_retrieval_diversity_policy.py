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







