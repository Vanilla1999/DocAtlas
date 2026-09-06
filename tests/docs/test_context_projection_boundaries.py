"""Projection must keep source-local text intact without inventing answer proof."""
from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import (
    _focused_snippet,
    project_docs_context,
)
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def test_path_only_projection_uses_the_current_exact_topic_guard():
    retrieval = _host_lookup_context_retrieval()
    question = "In docs/settings.md, explain ALPHA_KEY."
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question=question, explicit_paths=["docs/settings.md"],
                required_query_ids=[], public_query_ids=["query-original", "query-path-1"],
                queries=[
                    {"query_id": "query-original", "text": question, "origin": "original"},
                    {"query_id": "query-path-1", "text": "docs/settings.md", "origin": "exact_path"},
                ])
    source = retrieval["context_pack"][0]
    source.update(path="docs/settings.md", content="ALPHA_KEY enables durable storage.",
                  line_start=11, retrieval_query_matches={}, retrieval_query_ids=[])
    retrieval["context_pack"] = [source]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["context_available"] is True
    assert result["sources"][0]["snippet"] == source["content"]
    assert result["covered_query_ids"] == ["query-path-1"]
    assert result["answer_supported"] is False
    assert result["edit_ready"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_table_windows_never_start_or_end_inside_a_row(limit):
    rows = ["| Stage | Operation |", "| --- | --- |"] + [
        f"| stage-{i} | gateway accepts a bounded request and sends candidates to the next stage; "
        "untrusted input must never authorize edits |" for i in range(14)
    ]
    text = "  \n" + "\n".join(rows) + "\n  "
    snippet, start, end = _focused_snippet(text, ("gateway bounded candidates",), limit=limit)
    assert snippet
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert all(line in rows for line in snippet.splitlines())


def test_oversized_table_row_does_not_drop_its_restriction():
    row = "| gateway | " + "bounded request " * 35 + "; never authorize edits |"
    text = "| Stage | Rule |\n| --- | --- |\n" + row
    snippet, start, end = _focused_snippet(text, ("gateway bounded request",), limit=160)
    # No fabricated short prefix of the oversized atomic row may escape.
    assert row in snippet or "gateway" not in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_prose_window_does_not_start_in_the_middle_of_a_word(limit):
    text = "Prefix " * 25 + "ALPHA_KEY " + "configuration " * 70
    snippet, start, end = _focused_snippet(text, ("ALPHA_KEY configuration",), limit=limit)
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert not start or text[start - 1].isspace()
    assert end == len(text) or text[end].isspace()


def test_stronger_explicit_lookup_precedes_generated_alias_bonus():
    retrieval = _host_lookup_context_retrieval()
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question="Explain the processing path.",
                public_query_ids=["query-original", "query-lookup-1"],
                required_query_ids=[], queries=[
                    {"query_id": "query-original", "text": "Explain the processing path.", "origin": "original"},
                    {"query_id": "query-lookup-1", "text": "gateway request candidates selection", "origin": "host_lookup"},
                    {"query_id": "query-intent-1", "text": "internal policy", "origin": "canonical_intent"},
                ])
    strong, weak = retrieval["context_pack"][:2]
    strong.update(path="docs/strong.md", content="The gateway handles request candidates.",
                  retrieval_query_matches={"query-lookup-1": {"query_text": "gateway request candidates selection"}})
    weak.update(path="docs/weak.md", content="Internal policy describes the gateway request.",
                retrieval_query_matches={
                    "query-lookup-1": {"query_text": "gateway request candidates selection"},
                    "query-intent-1": {"query_text": "internal policy"},
                })
    # The weak generated hit arrives first; input ordering must not decide this.
    retrieval["context_pack"] = [weak, strong]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["sources"][0]["path_or_url"] == "docs/strong.md"
    assert "query-original" not in result["covered_query_ids"]
    assert "query-intent-1" not in result["covered_query_ids"]
    assert result["answer_supported"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


def test_table_focus_prefers_the_row_matching_the_whole_lookup():
    target = "| wire | documentation transport boundary accepts requests |"
    text = ("| Area | Responsibility |\n| --- | --- |\n"
            "| introduction | documentation overview |\n"
            + "\n".join(f"| area-{i} | unrelated processing step |" for i in range(9))
            + "\n" + target + "\n"
            + "\n".join(f"| appendix-{i} | unrelated appendix |" for i in range(9)))
    snippet, start, end = _focused_snippet(text, ("documentation transport boundary",), limit=160)
    assert target in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


def test_snippet_expansion_cannot_replace_an_already_visible_fact():
    from docmancer.docs.application.docs_context_projection import _expand_selected_snippets

    retained = "ALPHA_KEY requires a disk backup."
    raw = ("ALPHA_KEY uses memory buffers to process incoming requests.\n\n"
           + "Unrelated background explanation. " * 25 + "\n\n" + retained)
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(evidence_id="ev-retained", path_or_url=source["path"], snippet=retained,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"],
                      "exact_terms": ["ALPHA_KEY"], "qualified": True,
                  }})
    expanded = _expand_selected_snippets([source],
        projection_inputs={"ev-retained": (raw, ("ALPHA_KEY",), 1)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800)
    assert retained in expanded[0]["snippet"]
    assert expanded[0]["snippet"] in raw
