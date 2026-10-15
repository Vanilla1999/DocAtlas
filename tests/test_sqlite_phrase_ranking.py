"""A source-local phrase survives inline emphasis without losing its relation."""
from __future__ import annotations

import json

import pytest

from docmancer.core.sqlite_store import SQLiteStore


def _candidate(text: str, query: str = "Aurora does not replace"):
    row = {
        "id": 1, "rank": -1.0, "source": "docs/product.md", "chunk_index": 0,
        "title": "Product boundaries", "text": text, "token_estimate": 80,
        "metadata_json": json.dumps({"authority": "source_of_truth"}),
    }
    terms = set(SQLiteStore._strip_stopwords(query).casefold().split())
    return SQLiteStore._ranking_candidate(row, query, terms)






def test_inline_phrase_bonus_does_not_rewrite_visible_text_or_expand_query_budget(tmp_path):
    from tests.test_sqlite_ranking_truth import _doc, _store

    body = "Aurora does **not** replace:\n\n- a scheduler;\n- an archive;\n- an audit service."
    store = _store(tmp_path, [_doc("docs/product.md", "Product boundaries", body)])
    results = store.query("Aurora does not replace", limit=1, budget=160)
    assert len(results) == 1
    assert body in results[0].text
    assert "**not**" in results[0].text
    assert results[0].metadata["docmancer_tokens"] <= 160
    assert "qualified" not in results[0].metadata["lexical_match"]
