import inspect

import pytest

from docmancer.docs.domain.context_blocks import source_block_alternatives
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


def test_completeness_can_bind_actual_occurrence():
    assert "span_start" in inspect.signature(_is_complete_source_span).parameters
    phrase = "* `limit`: Cached."
    raw = phrase + " Only for local requests.\n\n" + phrase + "\n"
    second = raw.rindex(phrase)
    assert not _is_complete_source_span(raw, phrase, span_start=0)
    assert _is_complete_source_span(raw, phrase, span_start=second)
    assert not _is_complete_source_span(raw, phrase)


@pytest.mark.parametrize("marker", ["-", "+", "*", "1.", "1)"])
def test_list_item_integrity_is_entity_and_value_invariant(marker):
    prefix = f"{marker} `lease_span`: Caches responses."
    raw = prefix + " Default duration: `41`.\n"
    assert not _is_complete_source_span(raw, prefix)
    assert _is_complete_source_span(raw, raw)


def test_indented_and_nested_list_content_stays_with_owning_item():
    prefix = "* `lease_span`: Supports two modes."
    raw = (
        prefix + "\n"
        "  Default duration: `41`.\n"
        "  - `local`\n"
        "  - `shared`\n"
    )
    assert not _is_complete_source_span(raw, prefix)
    assert _is_complete_source_span(raw, raw)


def test_complete_neighboring_list_items_remain_independent():
    first = "- `lease_span`: Cache locally."
    second = "- `retry_span`: Retry once."
    raw = first + "\n" + second + "\n"
    assert _is_complete_source_span(raw, first)
    assert _is_complete_source_span(raw, second, span_start=raw.index(second))
    assert _is_complete_source_span(raw, first + "\n" + second)


@pytest.mark.parametrize("directive", ["??? note", "!!! warning"])
def test_unsupported_markdown_remains_structurally_unverified(directive):
    raw = directive + "\n    Hidden condition.\n"
    alternatives = source_block_alternatives(raw)
    assert "structure_unverified" in alternatives.limitations
    assert alternatives.spans == ()


def test_projection_owner_remains_within_repository_module_budget():
    from pathlib import Path
    from scripts.check_python_module_size import DEFAULT_MAX_LINES, oversized_modules

    root = Path(__file__).resolve().parents[2]
    owner = "docmancer/docs/application/_docs_context_projection_core.py"
    assert owner not in {path for _, path in oversized_modules(root, DEFAULT_MAX_LINES)}
