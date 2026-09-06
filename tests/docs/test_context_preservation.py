"""Regression checks for source identity and lossless context presentation."""
from docmancer.docs.application.docs_context_projection import _expand_selected_snippets
from docmancer.docs.domain.context_windows import _include_complete_table_row
from docmancer.docs.domain.query_terms import documentation_technical_anchors
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def _expand(raw, retained):
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(evidence_id="ev-retained", path_or_url=source["path"], snippet=retained,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"],
                      "exact_terms": ["ALPHA_KEY"], "qualified": True,
                  }})
    return _expand_selected_snippets([source],
        projection_inputs={"ev-retained": (raw, ("ALPHA_KEY",), 1)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800)[0]


def test_expansion_keeps_descriptive_fact_without_normative_keywords():
    retained = "ALPHA_KEY stores a disk backup."
    raw = ("ALPHA_KEY uses memory buffers to process incoming requests.\n\n"
           + "Unrelated background explanation. " * 25 + "\n\n" + retained)
    result = _expand(raw, retained)
    assert retained in result["snippet"]
    assert result["snippet"] in raw


def test_expansion_does_not_relocate_ambiguous_duplicate_passage():
    retained = "ALPHA_KEY stores a disk backup."
    raw = retained + " Another storage mode. " * 25 + retained
    assert _expand(raw, retained)["snippet"] == retained


def test_table_window_never_omits_subject_even_to_gain_a_term():
    text = "| disabled | " + "alpha context " * 5 + "|\n| beta | enabled |"
    start, end = _include_complete_table_row(text, 30, len(text),
        terms={"alpha", "enabled"}, limit=len(text) - 30)
    assert text[start:end] == "| beta | enabled |"


def test_table_window_retains_whole_row_when_it_fits():
    text = "| disabled | alpha context |\n| beta | enabled |"
    start, end = _include_complete_table_row(text, 15, len(text),
        terms={"alpha", "enabled"}, limit=len(text))
    assert text[start:end] == text


def test_oversized_table_row_is_not_returned_as_a_suffix():
    text = "| archived | " + "alpha context " * 30 + "|"
    start, end = _include_complete_table_row(text, len(text) - 90, len(text),
        terms={"alpha"}, limit=90)
    assert text[start:end] == ""


def test_filename_does_not_introduce_a_standalone_identifier():
    assert documentation_technical_anchors("Read CONTRIBUTING.md before testing") == ("CONTRIBUTING.md",)


def test_embedded_filename_parts_do_not_exhaust_the_anchor_budget():
    anchors = documentation_technical_anchors("Read docs/API_GUIDE.md and explain CACHE_MODE")
    assert "API_GUIDE" not in anchors
    assert "API_GUIDE.md" not in anchors
    assert "docs/API_GUIDE.md" in anchors
    assert "CACHE_MODE" in anchors


def test_separately_requested_identifier_is_not_lost_with_filename_part():
    anchors = documentation_technical_anchors("Compare CONTRIBUTING.md with CONTRIBUTING")
    assert set(anchors) == {"CONTRIBUTING.md", "CONTRIBUTING"}


def test_anchor_extraction_preserves_flags_and_exact_symbols():
    anchors = documentation_technical_anchors("Explain `Cache.refresh` and --no-vectors with CACHE_MODE")
    assert {"Cache.refresh", "--no-vectors", "CACHE_MODE"} <= set(anchors)
