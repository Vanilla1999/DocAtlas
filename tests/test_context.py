"""Tests for context formatting helpers."""

from __future__ import annotations

import pytest

from docmancer.context import build_rag_prompt, format_context
from docmancer.core.models import RetrievedChunk


def _chunk(text: str, source: str = "https://docs.example.com/auth", title: str = "Auth", score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        chunk_index=0,
        text=text,
        score=score,
        metadata={"title": title, "token_estimate": len(text) // 4},
    )



