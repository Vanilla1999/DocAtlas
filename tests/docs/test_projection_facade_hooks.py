"""Keep public projection observation hooks effective across the facade/core split."""
from __future__ import annotations

import pytest

from docmancer.docs.application import docs_context_projection as projection


def test_public_selection_hook_is_used_by_projection_core(monkeypatch):
    marker = object()

    def observed_selection(*args, **kwargs):
        del args, kwargs
        return marker

    monkeypatch.setattr(projection, "context_selection_decision", observed_selection)

    assert projection._core.context_selection_decision((), ()) is marker


def test_public_coverage_hook_is_used_by_projection_core(monkeypatch):
    marker = object()

    def observed_coverage(*args, **kwargs):
        del args, kwargs
        return marker

    monkeypatch.setattr(projection, "component_coverage_decision", observed_coverage)

    assert projection._core.component_coverage_decision((), (), ()) is marker


@pytest.mark.parametrize("name", [
    "_expand_selected_snippets", "_facet_aware_candidates", "_focused_line_range",
    "_focused_snippet", "_qualified_fragments", "_requalify_visible_source",
])
def test_public_projection_helpers_are_resolved_at_call_time(monkeypatch, name):
    marker = object()
    seen = []
    def observed(*args, **kwargs):
        seen.append((args, kwargs))
        return marker
    monkeypatch.setattr(projection, name, observed)
    assert getattr(projection._core, name)("sentinel", limit=7) is marker
    assert seen == [(("sentinel",), {"limit": 7})]
