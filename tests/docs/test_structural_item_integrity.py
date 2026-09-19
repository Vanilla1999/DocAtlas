import pytest

from docmancer.docs.domain.context_windows import _is_complete_source_span


@pytest.mark.parametrize("tail", [
    " Default duration: `73`.",
    " This mode must not be used with shared credentials.",
    " Requires the caller to keep the resource open.",
])
def test_sentence_end_inside_list_item_is_not_item_end(tail):
    prefix = "* `hold_window`: Caches responses."
    raw = prefix + tail + "\n"
    assert not _is_complete_source_span(raw, prefix)


@pytest.mark.parametrize("raw", [
    "* `hold_window`: Caches responses. Default duration: `73`.\n",
    "A complete paragraph.\n",
])
def test_complete_source_still_has_complete_boundary(raw):
    assert _is_complete_source_span(raw, raw)
