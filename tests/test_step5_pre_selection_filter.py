"""Step-5 research: the pool filter runs in front of both selectors, MiniLM included."""
from __future__ import annotations

import pytest

from docmancer.docs.application import experimental_candidate_selection as candidates
from docmancer.docs.application import experimental_pool_pruning as pruning
from docmancer.docs.application import joint_context_selection as joint
from docmancer.docs.application import section_compression as compression

QUESTION = "How do I prune the index safely?"


def _pool():
    rows = [
        {"evidence_id": "e1", "path_or_url": "guide.md", "section": "Guide > Index cleanup",
         "snippet": "Run the cleanup command to prune the index safely."},
        {"evidence_id": "e2", "path_or_url": "guide.md", "section": "Guide > Unrelated",
         "snippet": "Colors and fonts of the theme."},
        {"evidence_id": "e3", "path_or_url": "guide.md", "section": "Guide > Index cleanup",
         "snippet": "Back up first."},
        {"evidence_id": "e4", "path_or_url": "other.md", "section": "Other > Release",
         "snippet": "Release notes for version two."},
        {"evidence_id": "e5", "path_or_url": "other.md", "section": "Other > Theme",
         "snippet": "Dark mode and light mode."},
    ]
    scores = [9.0, 0.0, 0.0, 0.5, 0.0]
    snapshot = {row["evidence_id"]: {"source": {"retrieval_query_matches": {
        "query-original": {"lexical_score": score}}}} for row, score in zip(rows, scores)}
    retrieval = {"documentation_query_plan": {"original_question": QUESTION, "queries": [
        {"query_id": "query-original", "origin": "original", "relation": "direct", "text": QUESTION}]}}
    return {"kind": "docs_context", "sources": rows}, snapshot, retrieval


def test_filter_is_off_by_default_and_returns_the_same_payload(monkeypatch):
    monkeypatch.delenv(pruning.ENVIRONMENT, raising=False)
    payload, snapshot, _ = _pool()
    result, receipt = pruning.prune_checked_pool(payload, snapshot, {"query-original": {"text": QUESTION}})
    assert result is payload and receipt is None


def test_filter_keeps_whole_sections_and_leaves_the_input_untouched(monkeypatch):
    monkeypatch.setenv(pruning.ENVIRONMENT, "body")
    payload, snapshot, _ = _pool()
    result, receipt = pruning.prune_checked_pool(payload, snapshot, {"query-original": {"text": QUESTION}})
    assert [row["evidence_id"] for row in result["sources"]] == ["e1", "e3"]
    assert len(payload["sources"]) == 5
    assert receipt["candidate_rows"] == 5 and receipt["kept_rows"] == 2 and receipt["kept_sections"] == 1


def test_unknown_mode_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv(pruning.ENVIRONMENT, "top50")
    with pytest.raises(ValueError, match=pruning.ENVIRONMENT):
        pruning.pool_prune_mode()


@pytest.mark.parametrize("mode, expected", [("off", ["e1", "e2", "e3", "e4", "e5"]), ("body", ["e1", "e3"])])
def test_minilm_selector_scores_only_the_kept_sections(monkeypatch, tmp_path, mode, expected):
    monkeypatch.setenv(pruning.ENVIRONMENT, mode)
    monkeypatch.setenv("DOCATLAS_MINILM_MODEL_DIR", str(tmp_path))
    monkeypatch.delenv("DOCATLAS_CONTEXT_COMPRESSION", raising=False)
    monkeypatch.setattr(candidates, "native_rank_selection_active", lambda: True)
    seen = []

    class Stop(Exception):
        pass

    def sections(rows, snapshot):
        seen.extend(row["evidence_id"] for row in rows)
        raise Stop

    monkeypatch.setattr(compression, "_sections", sections)
    payload, snapshot, retrieval = _pool()
    with pytest.raises(Stop):
        compression.select_sections(payload, snapshot, retrieval, QUESTION)
    assert seen == expected
    diagnostics = retrieval.get("retrieval_diagnostics") or {}
    assert ("pool_pruning" in diagnostics) is (mode != "off")


def test_joint_selector_uses_the_same_filter():
    assert joint.prune_checked_pool is pruning.prune_checked_pool


def test_own_heading_mode_ignores_titles_shared_by_sibling_sections():
    rows = [
        {"path_or_url": "a.md", "section": "Index cleanup guide > Colors", "snippet": "Theme colors."},
        {"path_or_url": "a.md", "section": "Index cleanup guide > Steps", "snippet": "Open the theme panel."},
        {"path_or_url": "b.md", "section": "Reference > Index cleanup", "snippet": "Run the command."},
        {"path_or_url": "b.md", "section": "Reference > Fonts", "snippet": "Typefaces."},
        {"path_or_url": "c.md", "section": "Release notes", "snippet": "Version two."},
    ]
    queries = {"query-original": {"text": "index cleanup"}}
    lexical = {"query-original": [0.0] * len(rows)}
    assert pruning.views(rows, lexical, queries)["heading"] == {0, 1, 2}
    assert pruning.views(rows, lexical, queries, own_heading=True)["heading"] == {2}
    assert pruning.prune_rows("own_heading_or_body", rows, lexical, queries)[0] == [2]
    assert pruning.prune_rows("heading_or_body", rows, lexical, queries)[0] == [0, 1, 2]
