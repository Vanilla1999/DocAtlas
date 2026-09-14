"""Keep public projection observation hooks effective across the facade/core split."""
from __future__ import annotations

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
