from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from docmancer.docs.domain.project_doc_ranking import (
    project_question_lane,
    project_source_lane,
    rerank_project_doc_chunks,
    source_lane_allowed,
    source_weight_for_intent,
    source_weight_reason,
)
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


@dataclass
class FakeChunk:
    path: str
    heading_path: str
    score: float
    content: str = "content"
    metadata: dict[str, Any] = field(default_factory=dict)
    authority: str | None = None


def fake_chunk(path: str, heading_path: str, score: float, content: str = "content", metadata: dict[str, Any] | None = None) -> FakeChunk:
    return FakeChunk(path=path, heading_path=heading_path, score=score, content=content, metadata=metadata)

