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


@pytest.mark.parametrize("emphasis", ["not", "**not**", "*not*", "_not_", "`not`"])
def test_whole_relation_phrase_gets_existing_boost_across_inline_emphasis(emphasis):
    candidate = _candidate(f"Aurora does {emphasis} replace:\n\n- a scheduler;\n- an archive.")
    assert dict(candidate.feature_contributions)["leading_exact_phrase_boost"] == 2.0


@pytest.mark.parametrize("text", [
    "Aurora does replace a scheduler.",
    "Other tooling does not replace Aurora.",
    "Aurora does not currently replace a scheduler.",
    "Aurora does. Not replace is a separate example.",
    "Aurora does\n\nnot replace.",
    "Aurora does not replacement analysis.",
])
def test_phrase_boost_does_not_drop_negation_order_or_statement_boundaries(text):
    assert "leading_exact_phrase_boost" not in dict(_candidate(text).feature_contributions)


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
