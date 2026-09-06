"""Contiguous context windows keep short prose subjects and list markers."""
from __future__ import annotations

import pytest

from docmancer.docs.domain.context_windows import _focused_snippet


@pytest.mark.parametrize("limit", [160, 240])
def test_rolling_window_starts_with_a_whole_short_sentence(limit):
    sentences = [
        "The archive is a derived cache of owned records.",
        "Each tenant receives isolated private state and extracted artifacts, so one tenant cannot satisfy another tenant's query.",
        "Original records remain authoritative; the cache can be rebuilt with the documented cleanup process.",
        "The cleanup process coordinates the exclusive lease and the writer barrier.",
    ]
    text = " ".join(sentences)
    snippet, start, end = _focused_snippet(
        text, ("isolated state", "records authoritative"), limit=limit,
    )
    assert snippet and text[start:end] == snippet
    assert len(snippet) <= limit
    assert any(snippet.startswith(sentence) for sentence in sentences)
    assert any(snippet.endswith(sentence) for sentence in sentences)
    assert "Each tenant receives isolated private state" in snippet


@pytest.mark.parametrize("limit", [60, 90, 120])
def test_numbered_list_items_keep_their_marker_and_complete_body(limit):
    rows = [
        "1. Discover current records from disk;",
        "2. Remove orphaned indexed records;",
        "3. Reconcile changed files with stale indexed sections;",
        "4. Report removed and indexed record counts.",
    ]
    text = "\n".join(rows)
    snippet, start, end = _focused_snippet(text, ("stale indexed files",), limit=limit)
    assert snippet and text[start:end] == snippet
    assert len(snippet) <= limit
    assert rows[2] in snippet
    assert all(line in rows for line in snippet.splitlines())


def test_complete_short_source_keeps_exact_text_and_offsets():
    text = "  Each tenant owns its cache. The cache is not shared.\n  "
    snippet, start, end = _focused_snippet(text, ("tenant cache",), limit=160)
    assert snippet == text.strip() == text[start:end]
