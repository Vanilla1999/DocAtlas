"""Step-4 research pool pruning stays opt-in, dictionary-free and section-whole."""
from __future__ import annotations

import pytest

from docmancer.docs.application import experimental_pool_pruning as pruning
from docmancer.docs.application import joint_context_selection as selection


def _row(path: str, section: str, snippet: str) -> dict:
    return {"path_or_url": path, "section": section, "snippet": snippet}


def test_otsu_keeps_the_upper_class_and_never_splits_equal_scores():
    assert pruning.otsu_upper([9.0, 8.0, 1.0, 0.5]) == 2
    assert pruning.otsu_upper([5.0]) == 1
    assert pruning.otsu_upper([]) == 0
    assert pruning.otsu_upper([3.0, 3.0, 3.0]) == 3


def test_sections_are_numbered_by_path_and_heading_in_pool_order():
    rows = [_row("a.md", "A", "x"), _row("b.md", "A", "y"), _row("a.md", "A", "z"), _row("a.md", "B", "w")]
    assert pruning.section_units(rows) == [0, 1, 0, 2]


def test_body_mode_keeps_whole_sections_both_body_views_agree_on():
    rows = [
        _row("guide.md", "Guide > Index cleanup", "Run the cleanup command to prune the index safely."),
        _row("guide.md", "Guide > Unrelated", "Colors and fonts of the theme."),
        _row("guide.md", "Guide > Index cleanup", "Back up first."),
        _row("other.md", "Other > Release", "Release notes for version two."),
        _row("other.md", "Other > Theme", "Dark mode and light mode."),
    ]
    queries = {"query-original": {"text": "How do I prune the index safely?"}}
    lexical = {"query-original": [9.0, 0.0, 0.0, 0.5, 0.0]}
    kept, receipt = pruning.prune_rows("body", rows, lexical, queries)
    # The second window of the matched section has no query word and stays.
    assert kept == [0, 2]
    assert receipt["candidate_rows"] == 5 and receipt["kept_rows"] == 2 and receipt["kept_sections"] == 1


def test_heading_alone_cannot_keep_a_section_in_vote_mode():
    rows = [
        _row("a.md", "Docs > Logging off and on", "Set the variable in the server environment."),
        _row("a.md", "Docs > Cache", "Logging writes diagnostics to stderr when tracing is on."),
        _row("b.md", "Docs > Theme", "Colors."),
        _row("b.md", "Docs > Fonts", "Typefaces."),
    ]
    queries = {"query-original": {"text": "logging off"}}
    lexical = {"query-original": [0.0, 4.0, 0.0, 0.0]}
    views = pruning.views(rows, lexical, queries)
    assert 0 in views["heading"] and 0 not in views["body_words"]
    vote, _ = pruning.prune_rows("vote", rows, lexical, queries)
    heading, _ = pruning.prune_rows("heading", rows, lexical, queries)
    assert 0 in heading and 0 not in vote and 1 in vote


def test_character_views_match_inflections_without_a_dictionary():
    rows = [_row("a.md", "Настройка окружения", "Переменная задаётся в окружении сервера."),
            _row("a.md", "Цвета", "Тёмная тема.")]
    queries = {"query-original": {"text": "окружение сервера"}}
    views = pruning.views(rows, {"query-original": [0.0, 0.0]}, queries)
    assert views["heading"] == {0} and views["body_chars"] == {0}


def test_no_kept_section_falls_back_to_the_whole_pool():
    rows = [_row("a.md", "A", "alpha"), _row("b.md", "B", "beta")]
    kept, receipt = pruning.prune_rows("body", rows, {"query-original": [0.0, 0.0]},
                                       {"query-original": {"text": "zzzz"}})
    assert kept == [0, 1] and receipt["fallback"] == "no_section_kept"


def test_pool_prune_flag_is_off_by_default_and_validated(monkeypatch):
    name = "DOCATLAS_EXPERIMENT_POOL_PRUNE"
    monkeypatch.delenv(name, raising=False)
    assert selection._experiment(name) == "off"
    for mode in pruning.MODES:
        monkeypatch.setenv(name, mode)
        assert selection._experiment(name) == mode
    monkeypatch.setenv(name, "top50")
    with pytest.raises(ValueError, match=name):
        selection._experiment(name)
    with pytest.raises(ValueError, match="unknown pool pruning mode"):
        pruning.kept_sections("top50", {"heading": set(), "body_words": set(), "body_chars": set()})
