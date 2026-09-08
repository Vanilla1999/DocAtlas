"""Each accepted expansion is retained; table subjects cannot become suffixes."""
from copy import deepcopy
import hashlib

import pytest

from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.context_windows import _focused_snippet, _include_complete_table_row
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def _growing_span(monkeypatch):
    prefix = "ALPHA_KEY stores disk backups.\n"
    retained = "ALPHA_KEY controls cache state."
    suffix = "\nALPHA_KEY accepts optional tuning parameters for local memory buffers."
    raw = prefix + retained + suffix
    first = prefix + retained
    replacement = retained + suffix
    def focus(text, queries, *, limit):
        assert text == raw
        snippet = first if limit == 160 else replacement
        start = raw.index(snippet)
        return snippet, start, start + len(snippet)
    monkeypatch.setattr(projection, "_focused_snippet", focus)
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(evidence_id="ev-grow", path_or_url=source["path"], snippet=retained,
                  content_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                  line_start=12, line_end=12,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"],
                      "exact_terms": ["ALPHA_KEY"], "qualified": True,
                  }})
    return source, raw, first


def test_later_expansion_preserves_the_latest_accepted_exact_span(monkeypatch):
    source, raw, first = _growing_span(monkeypatch)
    original = deepcopy(source)
    expanded = projection._expand_selected_snippets([source],
        projection_inputs={"ev-grow": (raw, ("ALPHA_KEY",), 11)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800)[0]
    assert first in expanded["snippet"]  # Must retain what round 160 already accepted.
    assert expanded["snippet"] == raw
    assert (expanded["line_start"], expanded["line_end"]) == (11, 13)
    assert expanded["content_sha256"] == original["content_sha256"]
    assert source == original
    assert "query-original" not in expanded["retrieval_query_matches"]


def test_failed_budget_expansion_keeps_the_original_exact_span(monkeypatch):
    source, raw, _ = _growing_span(monkeypatch)
    result = projection._expand_selected_snippets([source],
        projection_inputs={"ev-grow": (raw, ("ALPHA_KEY",), 11)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=1)
    assert result == [source]


@pytest.mark.parametrize("subject", ["disabled", "archived", "module-only", "not approved"])
def test_no_table_subject_is_dropped_to_gain_a_keyword(subject):
    text = f"| {subject} | " + "alpha context " * 8 + "|\n| beta | enabled |"
    start, end = _include_complete_table_row(text, 35, len(text),
        terms={"alpha", "enabled"}, limit=len(text) - 35)
    assert text[start:end] == "| beta | enabled |"
    snippet, left, right = _focused_snippet(text, ("alpha context enabled",), limit=90)
    assert snippet == text[left:right]
    assert len(snippet) <= 90
    assert all(line in text.splitlines() for line in snippet.splitlines())


def test_public_table_span_and_hash_stay_bound_to_the_original_source():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    table = "| State | ALPHA_KEY |\n| --- | --- |\n| disabled | ALPHA_KEY never writes |\n| active | ALPHA_KEY writes |"
    source.update(content=table, line_start=20, retrieval_query_ids=["query-lookup-1"],
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"], "exact_terms": ["ALPHA_KEY"],
                  }})
    retrieval["context_pack"] = [source]
    retrieval["documentation_query_plan"]["queries"] = [
        {"query_id": "query-original", "text": "Explain ALPHA_KEY states.", "origin": "original"},
        {"query_id": "query-lookup-1", "text": "ALPHA_KEY", "origin": "host_lookup"},
    ]
    payload, snapshot = projection.project_docs_context(retrieval=retrieval)
    assert payload["sources"]
    for row in payload["sources"]:
        snippet = row["snippet"]
        assert snippet in table
        assert all(line in table.splitlines() for line in snippet.splitlines())
        start = table.index(snippet)
        assert row["line_start"] == 20 + table[:start].count("\n")
        assert row["line_end"] == row["line_start"] + snippet.count("\n")
        assert snapshot[row["evidence_id"]]["projected_source"] == row
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
