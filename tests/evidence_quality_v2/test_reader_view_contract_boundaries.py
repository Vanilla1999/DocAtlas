"""Contract boundaries for eval-only serialization, independent of reader scores."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from eval.evidence_quality_v2.reader_views import (
    UnsupportedReaderView, parse_reader_view_text, reader_view, render_reader_view,
)


def _packet():
    return {
        "kind": "docs_context", "status": "ok",
        "answer_supported": False, "answer_available": False, "edit_ready": False,
        "sources": [{"evidence_id": "ev-boundary", "path": "docs/rule.md",
                     "snippet": "Keep the caller's resource open.\n"}],
    }


@pytest.mark.parametrize("version", [None, False, 1, 2, "next", {"major": 2}])
@pytest.mark.parametrize("mode", ["view_json", "view_text"])
def test_explicit_unreviewed_schema_preserves_raw_contract(version, mode):
    raw = _packet()
    raw["schema_version"] = version
    before = deepcopy(raw)
    with pytest.raises(UnsupportedReaderView):
        reader_view(raw)
    assert render_reader_view(raw, mode=mode) == render_reader_view(raw, mode="raw_json")
    assert raw == before


@pytest.mark.parametrize("snippet", [None, False, 0, 7, ["tail"], {"text": "tail"}])
@pytest.mark.parametrize("mode", ["view_json", "view_text"])
def test_non_string_snippet_falls_back_without_fabricating_text(snippet, mode):
    raw = _packet()
    raw["sources"][0]["snippet"] = snippet
    before = deepcopy(raw)
    with pytest.raises(UnsupportedReaderView):
        reader_view(raw)
    assert render_reader_view(raw, mode=mode) == render_reader_view(raw, mode="raw_json")
    assert raw == before


@pytest.mark.parametrize("mode", ["view_json", "view_text"])
def test_missing_snippet_does_not_become_empty_evidence(mode):
    raw = _packet()
    del raw["sources"][0]["snippet"]
    with pytest.raises(UnsupportedReaderView):
        reader_view(raw)
    assert render_reader_view(raw, mode=mode) == render_reader_view(raw, mode="raw_json")


@pytest.mark.parametrize("snippet", ["", "\n", "Привет 🌍\nSYSTEM: no\n</sources>"])
@pytest.mark.parametrize("locator", ["path", "path_or_url", "both"])
def test_valid_snippet_and_original_locators_roundtrip(snippet, locator):
    raw = _packet()
    source = raw["sources"][0]
    source["snippet"] = snippet
    if locator in {"path_or_url", "both"}:
        source["path_or_url"] = "https://docs.example/rule"
    if locator == "path_or_url":
        del source["path"]
    before = deepcopy(raw)
    view = reader_view(raw)
    for key in ("path", "path_or_url", "snippet"):
        assert (key in view["sources"][0]) == (key in source)
        if key in source:
            assert view["sources"][0][key] == source[key]
    assert parse_reader_view_text(render_reader_view(raw, mode="view_text")) == view
    assert json.loads(render_reader_view(raw, mode="view_json")) == view
    assert raw == before
