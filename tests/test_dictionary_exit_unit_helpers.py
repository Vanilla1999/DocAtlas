from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import re

import pytest

from docmancer.docs.domain import answer_units as api
from docmancer.docs.domain import _answer_units_part01 as helpers
from docmancer.docs.domain import _answer_units_shared as shared
from docmancer.docs.domain.project_answer_contract import ProofObligation


@pytest.mark.parametrize("text", [
    "Widget is used for retrieval. Other returns values.",
    "Widget flurbs arbitrary objects. Other frobs other objects.",
    "Widget используется для поиска. Другой возвращает данные.",
    "Widget awaits mcp.server version 3.11. Next preserves input.",
])
@pytest.mark.parametrize("softwrap", [False, True])
def test_useful_prose_keeps_exact_units_without_semantic_credit(text, softwrap):
    units = api.extract_answer_units(text, include_soft_wrapped_prose=softwrap)
    assert units == api.extract_answer_units(text, include_soft_wrapped_prose=softwrap)
    assert units and all(not unit.proposition for unit in units)
    assert api.materialize_answer_units(text, units) == text
    assert not any(unit.kind == "unit_group" for unit in units)
    for unit in units:
        assert unit.text == text[unit.char_start:unit.char_end]
        assert unit.text.encode() == text[unit.char_start:unit.char_end].encode()
        assert unit.content_sha256 == hashlib.sha256(unit.text.encode()).hexdigest()
        identity = hashlib.sha256(f"{unit.kind}\0{unit.char_start}\0{unit.char_end}\0{unit.text}".encode()).hexdigest()
        assert unit.unit_id == "unit-" + identity[:20]


@pytest.mark.parametrize("subject", ["Widget", "Unknown", "DOCATLAS_HOME"])
@pytest.mark.parametrize("text", [
    "Widget is used for retrieval.",
    "Widget deletes cache without deleting project sources.",
    "Widget preserves configuration.",
    "Widget overrides the storage root and defaults to /tmp/opencode.",
    "Widget используется для поиска и сохраняет файлы.",
    "",
])
def test_direct_purpose_effect_helpers_are_negative(subject, text):
    query = ProofObligation("helper", "purpose", subject)
    assert helpers._purpose_clause(query, text) is None
    for relation in ("delete", "preserve", "unknown", None):
        assert helpers._effect_relation_valid(replace(query, kind="effect", relation=relation), text) is False
    assert helpers._context_score(subject, text, f"canonical title {subject}") == 0
    assert helpers._context_score(None, text, "") == 0
    assert helpers._context_score("", text, "") == 0
    match = re.search("Widget|^", text)
    assert helpers._predicate_has_object(match, text) is False
    assert helpers._positive_relation_match(match, text) is False
    assert helpers._positive_relation(re.compile(".*"), text) is False


@pytest.mark.parametrize("name", [
    "_VERSION_VALUE_RE", "_DURATION_RE", "_USAGE_RE", "_CONTRAST_RE",
    "_TOOL_WORD_RE", "_TOOL_INVENTORY_ANCHOR_RE", "_EXPLICIT_COUNT_RE",
    "_PURPOSE_RE", "_PURPOSE_COPULA_RE", "_DELETE_PREDICATE_RE",
    "_PRESERVE_PREDICATE_RE", "_NEGATED_DELETE_RE", "_ARCH_COMPONENT_RE", "_ARCH_RELATION_RE",
])
def test_compatibility_pattern_symbols_have_no_semantic_matches(name):
    pattern = getattr(shared, name)
    assert getattr(api, name) is pattern
    for text in ("", "3.11 17 ms three tools use Widget whereas Other", "Widget deletes and preserves cache", "server routes through registry", "три инструмента используются для поиска"):
        assert pattern.search(text) is None
        assert pattern.match(text) is None
        assert pattern.fullmatch(text) is None
        assert tuple(pattern.finditer(text)) == ()
    assert shared._NUMBER_WORD_VALUES == {}


@pytest.mark.parametrize("subject,attribute,value", [
    ("Widget", "value", "false"), ("DOCATLAS_HOME", None, "/tmp/opencode"),
    ("widget", "version", "^3.11"), ("Widget", "duration", "17 ms"),
])
def test_typed_literal_parser_and_case_sensitive_exception_remain(subject, attribute, value):
    key = subject + ("." + attribute if attribute else "")
    text = f'{key} = "{value}"'
    query = ProofObligation("literal", "exact_fact", subject, attribute=attribute, subject_kind="config_key", expected_value=value)
    unit = api.extract_answer_units(text)[0]
    assert unit.kind == "key_value" and not unit.proposition
    assert shared._KEY_VALUE_RE.fullmatch(text)
    assert api.local_proof_for_obligation(query, unit).reason == "explicit_literal_value_only"
    assert api.local_proof_for_obligation(query, unit).valid
    assert not api.local_proof_for_obligation(replace(query, subject=subject.swapcase()), unit).valid
    assert not api.local_proof_for_obligation(replace(query, expected_value=value + "-extra"), unit).valid


def test_structural_grammar_softwrap_grouping_source_fields_order_and_dedupe():
    text = (
        "# Context\nWidget flurbs\nunknown values.\n\n"
        "- alpha\n  continued\n- beta\n\n"
        "| key | value |\n| --- | --- |\n| odd | quux |\n"
        "```python\ndef widget():\n    pass\n```\n"
    )
    units = api.extract_answer_units(text, include_soft_wrapped_prose=True, source_fields={"title": "Context", "path": "docs/Widget.md"})
    assert {u.kind for u in units} >= {"heading_context", "paragraph_sentence", "bullet", "unit_group", "table_row", "code_declaration", "source_field"}
    assert next(u for u in units if u.kind == "paragraph_sentence").text == "Widget flurbs\nunknown values."
    group = next(u for u in units if u.kind == "unit_group")
    assert group.text == "- alpha\n  continued\n- beta"
    assert api.materialize_answer_units(text, (group, group)) == group.text
    assert all(not u.proposition for u in units)
    content = [u for u in units if u.source_field is None]
    assert [(u.char_start, u.char_end, u.kind, u.unit_id) for u in content] == sorted((u.char_start, u.char_end, u.kind, u.unit_id) for u in content)
    for unit in content:
        assert text[unit.char_start:unit.char_end] == unit.text
    fields = [u for u in units if u.source_field is not None]
    assert [u.source_field for u in fields] == ["path", "title"]
    assert all(u.char_start is None and u.char_end is None for u in fields)


def test_segmentation_helpers_trim_bounds_and_immutable_validation_unchanged():
    assert helpers._bounded_text("  quoted  ") == "quoted"
    assert helpers._bounded_text("x" * 2000) == "x" * api.MAX_ANSWER_UNIT_CHARS
    assert helpers._make_unit("sentence", "   ", 0, 3, proposition=False) is None
    unit = helpers._make_unit("sentence", "  Ω quote  ", 0, 11, proposition=False)
    assert (unit.text, unit.char_start, unit.char_end) == ("Ω quote", 2, 9)
    with pytest.raises(FrozenInstanceError):
        unit.text = "modified"
    with pytest.raises(ValueError, match="hash mismatch"):
        replace(unit, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="offsets"):
        replace(unit, char_start=-1)
    with pytest.raises(ValueError, match="exceeds bound"):
        replace(unit, text="x" * (api.MAX_ANSWER_UNIT_CHARS + 1))
    assert len(api.extract_answer_units("\n".join(f"line {i}" for i in range(100)))) == api.MAX_ANSWER_UNITS
    assert api.extract_answer_units("") == ()
    assert helpers._make_source_field_unit("path", "") is None


def test_clause_offsets_punctuation_versions_and_word_distance_unchanged():
    text = " mcp.server flurbs 3.11. Other frobs values;\nNext reads Ω. "
    clauses = helpers._bounded_clauses(text)
    assert [c for _, _, c in clauses] == ["mcp.server flurbs 3.11.", "Other frobs values;", "Next reads Ω."]
    assert all(text[start:end] == clause for start, end, clause in clauses)
    assert helpers._bounded_clauses("") == ()
    assert helpers._word_distance((0, 2), (7, 9), "aa two bb xx") == 1
    assert helpers._word_distance((7, 9), (0, 2), "aa two bb xx") == 1
    assert helpers._word_distance((0, 4), (2, 5), "overlap") == 0


def test_negation_guard_not_inverted_to_positive_proof():
    assert shared._NEGATION_RE.search("Widget does not return values")
    assert shared._NEGATION_RE.search("Widget нельзя использовать")
    query = ProofObligation("negative", "effect", "Widget", relation="preserve")
    assert not helpers._effect_relation_valid(query, "Widget does not delete sources")
