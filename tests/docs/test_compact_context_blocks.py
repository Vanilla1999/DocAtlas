"""Regression cases for intact, source-bound runtime context delivery."""
from __future__ import annotations

import re

import pytest

from docmancer.docs.application.docs_context_projection import (
    _qualified_fragments,
    project_docs_context,
)
from docmancer.docs.application.model_visible_projection import (
    _docs_source,
    _source_digest,
    docs_context_budget_tokens,
    validate_model_visible_projection,
)
from docmancer.docs.domain.context_windows import _focused_snippet
from docmancer.docs.domain.evidence_qualification import _visible_term_present, qualify_evidence


# Original list from the reviewed uv source, not an expected/generated answer.
STRATEGIES = """- `first-match` (default): Search for each package across all indexes, limiting the candidate
  versions to those present in the first index that contains the package, prioritizing the
  `--extra-index-url` indexes over the default index URL.
- `unsafe-first-match`: Search for each package across all indexes, but prefer the first index with
  a compatible version, even if newer versions are available on other indexes.
- `unsafe-best-match`: Search for each package across all indexes, and select the best version from
  the combined set of candidate versions."""


def _retrieval(text: str, question: str, *, start: int = 136):
    query = {"query_id": "query-original", "text": question, "origin": "original"}
    candidate = {
        "source_class": "project_doc", "path": "docs/options.md",
        "heading_path": "Options", "content": text,
        "project_identity": "project:compact-context",
        "line_start": start, "line_end": start + text.count("\n"),
        "char_start": 900, "char_end": 900 + len(text),
        "authority": "source_of_truth", "doc_scope": "project",
        "lifecycle_status": "active", "freshness": "current",
        "index_freshness": "synchronized", "risk_flags": [],
        "retrieval_query_ids": ["query-original"],
        "retrieval_query_matches": {"query-original": {
            "qualified": True, "mode": "and", "query_text": question,
            "query_terms": sorted(set(re.findall(r"[a-zA-Z0-9_.-]{4,}", question.lower()))),
        }},
    }
    return {"question": question, "context_pack": [candidate],
            "documentation_query_plan": {
                "original_question": question, "query_ids": ["query-original"],
                "queries": [query], "required_query_ids": ["query-original"],
                "public_query_ids": ["query-original"],
            }}


def _variants(text: str, question: str):
    retrieval = _retrieval(text, question)
    original = retrieval["context_pack"][0]
    source = _docs_source(original, display_snippet=text)
    source.update({"retrieval_query_matches": original["retrieval_query_matches"],
                   "retrieval_query_ids": original["retrieval_query_ids"],
                   "_qualification_candidate": original,
                   "_expected_project_identity": original["project_identity"],
                   "_independent_query_plan": retrieval["documentation_query_plan"]})
    return _qualified_fragments(
        source, raw_snippet=text, query_ids={"query-original"},
        query_text={"query-original": question}, source_line_start=original["line_start"],
    )


@pytest.mark.parametrize("rename", [False, True], ids=["uv", "synthetic"])
@pytest.mark.parametrize("intro", ["Available strategies:\n\n", "Unrelated introduction. " * 90 + "\n\n"])
def test_three_named_options_survive_as_one_complete_list(rename, intro):
    block = STRATEGIES
    question = "Compare first-match, unsafe-first-match and unsafe-best-match index strategies."
    if rename:
        for old, new in (("unsafe-best-match", "other-high-score"),
                         ("unsafe-first-match", "other-low-score"),
                         ("first-match", "low-score")):
            block = block.replace(old, new)
            question = question.replace(old, new)
    text = intro + block
    retrieval = _retrieval(text, question)
    payload, snapshot = project_docs_context(retrieval=retrieval)
    snippets = [source["snippet"] for source in payload["sources"]]
    assert any(block in snippet for snippet in snippets), snippets
    assert docs_context_budget_tokens(payload) <= 800
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    for source in payload["sources"]:
        offset = text.index(source["snippet"])
        assert source["line_start"] == 136 + text[:offset].count("\n")
        assert source["line_end"] == source["line_start"] + source["snippet"].count("\n")
        assert source["content_sha256"] == _source_digest(retrieval["context_pack"][0])


@pytest.mark.parametrize("name, larger", [
    ("first-match", "unsafe-first-match"),
    ("low-score", "other-low-score"),
    ("Client.open", "AsyncClient.open"),
    ("Client.open", "package.Client.open"),
])
def test_identifier_suffix_is_not_a_distinct_option(name, larger):
    assert not _visible_term_present(name.lower(), larger.lower(), exact=True)
    assert not _visible_term_present(name.lower(), larger.lower(), exact=False)
    assert _visible_term_present(name.lower(), f"Use `{name}`.".lower(), exact=True)
    assert _visible_term_present(name.lower(), f"{name.lower()}.", exact=True)
    result = qualify_evidence(
        {"query_terms": [name.lower(), "export", "identifiers"], "exact_terms": [name.lower()]},
        query_id="query-original", visible_text=f"{larger} can export identifiers.",
    )
    assert not result.qualified
    assert name.lower() in result.trace["missing_exact_terms"]


def test_window_ranking_does_not_reward_identifier_suffix():
    text = "unsafe-first-match is unrelated.\n\nfirst-match is the standalone choice."
    snippet, _, _ = _focused_snippet(text, ("first-match",), limit=40)
    assert "standalone choice" in snippet
    assert "unsafe-first-match" not in snippet


def test_long_complete_block_is_offered_before_budget_decision():
    block = "The export operation preserves original identifiers. " + "Additional context is retained. " * 24
    assert len(block) > 640
    alternatives = _variants(block, "How does the export operation preserve original identifiers?")
    assert any(item["snippet"] == block.rstrip() for item in alternatives)


def test_overbudget_block_is_not_silently_clipped():
    text = "The export operation preserves original identifiers. " + "Additional context is retained. " * 150
    retrieval = _retrieval(text, "How does the export operation preserve original identifiers?")
    payload, _ = project_docs_context(retrieval=retrieval)
    assert not payload.get("sources"), payload
    rejections = retrieval["retrieval_diagnostics"]["docs_context_projection"]["projection_rejections"]
    assert any(item["reason"] == "token_budget" for item in rejections), rejections
    assert docs_context_budget_tokens(payload) <= 800


@pytest.mark.parametrize("text, required", [
    ("| Option | Meaning |\n| --- | --- |\n| export | Preserve original identifiers |", "| Option | Meaning |"),
    ("```python\n" + "# export operation preserves identifiers\n" * 20 + "export()\n```", "```"),
    ("- The export operation preserves original identifiers.\n  Only when the source snapshot is unchanged.",
     "Only when the source snapshot is unchanged."),
])
def test_structural_dependencies_are_not_silently_removed(text, required):
    alternatives = _variants(text, "How does the export operation preserve original identifiers?")
    assert alternatives
    assert any(item["snippet"] == text for item in alternatives)
    assert all(required in item["snippet"] for item in alternatives)
    if text.startswith("```"):
        assert all(item["snippet"].startswith("```python\n") and item["snippet"].endswith("\n```")
                   for item in alternatives)


def test_atomic_alternatives_do_not_widen_ordinary_windows_or_join_sections():
    from docmancer.docs.domain.context_blocks import source_block_alternatives
    from docmancer.docs.domain.context_windows import _projection_limits
    text = "First standalone fact.\n\n" + "Unrelated background. " * 70 + "\n\nLast standalone fact."
    alternatives = source_block_alternatives(text).spans
    assert _projection_limits(text) == (160, 320, 520)
    assert all(not ("First standalone" in text[start:end] and "Last standalone" in text[start:end])
               for start, end in alternatives)
    dependent = "Use this example:\n\n```python\nexport()\n```"
    assert (0, len(dependent)) in source_block_alternatives(dependent).spans


def test_selected_command_cannot_be_replaced_by_topical_operation(monkeypatch):
    from copy import deepcopy
    from docmancer.docs.application import docs_context_projection as projection
    retained = "| `lumen load` | Load local files. |"
    replacement = "| `lumen export` | Export local files after load. |"
    text = retained + "\n\n" + "Unrelated background. " * 40 + "\n\n" + replacement
    question = "Load local files safely"
    variants = _variants(text, question)
    first = next(row for row in variants if row["snippet"] == retained)
    first.update(project_identity="project:compact-context", authority="source_of_truth", scope="project")
    second = deepcopy(first)
    second["snippet"] = replacement
    second["line_start"] = second["line_end"] = 136 + text[:text.index(replacement)].count("\n")
    selected = [first, second]
    # Force the already accepted witness to be followed by an equally qualified
    # alternative, without relying on incidental candidate-order heuristics.
    monkeypatch.setattr(projection, "_qualified_fragments", lambda *args, **kwargs: deepcopy(selected))
    monkeypatch.setattr(projection, "_facet_aware_candidates", lambda candidates, **kwargs: candidates)
    monkeypatch.setattr(projection, "_expand_selected_snippets", lambda sources, **kwargs: sources)
    payload, snapshot = projection.project_docs_context(retrieval=_retrieval(text, question))
    assert [row["snippet"] for row in payload["sources"]] == [retained]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


def test_inline_command_retention_does_not_pin_single_identifier_aliases():
    from docmancer.docs.domain.context_blocks import inline_command_literals
    text = "Use `lumen load` with `--offline`; see `WidgetClient.open` and `optional-alias`."
    assert inline_command_literals(text) == frozenset({"`lumen load`", "`--offline`"})
    assert not inline_command_literals("```python\nWidgetClient.open()\n```")
