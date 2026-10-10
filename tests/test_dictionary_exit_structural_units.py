from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from docmancer.docs.domain import answer_units as api
from docmancer.docs.domain import _answer_units_part02 as proofs
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation,
    obligations_can_authorize_docs_answer,
)


def _obligation(kind="exact_fact", **kwargs):
    return ProofObligation("explicit", kind, "Widget", **kwargs)


def test_structural_units_preserve_source_hash_spans_and_order():
    text = (
        "# Context\nUnrecognized relation flurbs Widget.\n\n"
        "- alpha\n- beta\n\n| name | value |\n| --- | --- |\n| odd | quux |\n"
        'Widget.status = "quux"\n```python\ndef widget():\n    pass\n```\n'
    )
    units = api.extract_answer_units(text)
    assert units == api.extract_answer_units(text)
    assert {unit.kind for unit in units} >= {
        "heading_context", "bullet", "table_row", "key_value", "code_declaration", "unit_group",
    }
    assert all(not unit.proposition for unit in units)
    assert [(u.char_start, u.char_end, u.kind, u.unit_id) for u in units] == sorted(
        (u.char_start, u.char_end, u.kind, u.unit_id) for u in units
    )
    for unit in units:
        assert text[unit.char_start:unit.char_end] == unit.text
        assert unit.content_sha256 == hashlib.sha256(unit.text.encode()).hexdigest()
        identity = hashlib.sha256(
            f"{unit.kind}\0{unit.char_start}\0{unit.char_end}\0{unit.text}".encode()
        ).hexdigest()
        assert unit.unit_id == "unit-" + identity[:20]


@pytest.mark.parametrize("text", [
    "Widget is a useful object. Widget returns values.",
    "First Widget reads input. Then Widget writes output.",
    "Widget завершен. Затем Widget читает данные.",
    "Widget flurbs arbitrary objects. Widget frobs other objects.",
])
@pytest.mark.parametrize("softwrap", [False, True])
def test_prose_vocabulary_does_not_certify_or_group(text, softwrap):
    units = api.extract_answer_units(text, include_soft_wrapped_prose=softwrap)
    assert units
    assert all(not unit.proposition for unit in units)
    assert not any(unit.kind == "unit_group" for unit in units)


@pytest.mark.parametrize("kind", [
    "definition", "behavior", "status", "workflow", "purpose", "effect",
    "attribute", "inventory", "command", "location", "comparison", "usage", "relation", "exact_fact",
])
def test_structural_context_is_not_semantic_support(kind):
    text = (
        "# Widget\nWidget is active and returns 42.\n"
        "Widget status: completed\n- First Widget reads input\n- Then Widget writes output\n"
    )
    units = api.extract_answer_units(text, source_fields={"path": "docs/Widget.md"})
    source = {"path": "docs/Widget.md", "authority": "source_of_truth"}
    obligation = _obligation(kind)
    assert units
    assert api.best_local_proof(obligation, units, source=source) is None
    assert all(
        api.local_proof_for_obligation(obligation, unit, source=source).reason
        == "structural_context_not_proposition" for unit in units
    )


@pytest.mark.parametrize("kind", ["definition", "behavior", "status", "workflow"])
def test_removed_detectors_fail_closed_even_with_supplied_proposition_flag(kind):
    unit = replace(api.extract_answer_units("Widget is active and returns values.")[0], proposition=True)
    proof = api.local_proof_for_obligation(_obligation(kind), unit)
    assert not proof.valid
    assert proof.reason == "semantic_detector_removed"
    assert proofs._definition_clause(_obligation("definition"), unit.text) is None
    assert proofs._behavior_clause(_obligation("behavior"), unit.text) is None
    assert proofs._source_document_behavior_clause(_obligation("behavior"), unit.text, "README") is None
    assert proofs._value_score("status", "active completed quux") == 0


@pytest.mark.parametrize("relation", [None, "relation", "flurbs"])
def test_unknown_relation_does_not_gain_support_from_literal_occurrence(relation):
    unit = replace(api.extract_answer_units("Widget flurbs target and returns values.")[0], proposition=True)
    assert not api.local_proof_for_obligation(
        _obligation("relation", relation=relation, target="target"), unit,
    ).valid


@pytest.mark.parametrize("value_kind,value", [
    ("status", "quux"), ("version_range", "^3.11"), ("duration", "17 ms"),
    ("number", "42"), ("boolean", "false"), ("path", "/tmp/opencode/Widget"),
])
def test_explicit_typed_literal_equality_is_not_answer_authority(value_kind, value):
    obligation = _obligation(
        subject_kind="config_key", attribute="value", value_kind=value_kind, expected_value=value,
    )
    units = api.extract_answer_units(f'Widget.value = "{value}"')
    match = api.best_local_proof(obligation, units)
    assert match is not None
    unit, proof = match
    assert not unit.proposition
    assert proof.valid and proof.reason == "explicit_literal_value_only"
    assert not obligations_can_authorize_docs_answer((obligation,))


@pytest.mark.parametrize("text", [
    'Other.value = "quux"', 'Widget.other = "quux"', 'Widget.value = "quux-extra"',
    'Widget.value = "QUUX"', "Widget has value quux.",
    '# Widget\nvalue: quux', 'Widget.value = "quux"\nOther.value = "oops"',
])
def test_literal_contract_does_not_infer_relation_or_substring_value(text):
    obligation = _obligation(
        subject_kind="config_key", attribute="value", value_kind="status", expected_value="quux",
    )
    units = api.extract_answer_units(text)
    if "Other.value" in text and text.startswith("Widget.value"):
        # Only the single exact declaration can witness equality, not its group.
        assert all(
            not api.local_proof_for_obligation(obligation, u).valid
            for u in units if "\n" in u.text
        )
    else:
        assert api.best_local_proof(obligation, units) is None


@pytest.mark.parametrize("change", [
    {"relation": "contract_fact"}, {"target": "Other"}, {"context": "current release"},
    {"subject_kind": None}, {"expected_value": None}, {"value_kind": "identifier_list"},
])
def test_literal_contract_requires_explicit_narrow_type(change):
    obligation = _obligation(subject_kind="config_key", expected_value="quux", value_kind="status")
    assert api.best_local_proof(replace(obligation, **change), api.extract_answer_units("Widget: quux")) is None


def test_literal_contract_obeys_lifecycle_and_source_field_boundaries():
    obligation = _obligation(subject_kind="config_key", expected_value="quux", value_kind="status")
    units = api.extract_answer_units("Widget: quux")
    assert api.best_local_proof(obligation, units, source={"lifecycle_status": "superseded"}) is None
    assert api.best_local_proof(replace(obligation, lifecycle_intent="historical"), units) is None
    source_unit = api._make_source_field_unit("status", "Widget: quux")
    assert source_unit is not None and not source_unit.proposition
    assert not api.local_proof_for_obligation(obligation, source_unit).valid


def test_softwrap_and_bullet_groups_are_exact_bounded_context():
    text = "Widget flurbs\nunknown values.\n\n- alpha\n  continued\n- beta\n"
    units = api.extract_answer_units(text, include_soft_wrapped_prose=True)
    paragraph = next(u for u in units if u.kind == "paragraph_sentence")
    group = next(u for u in units if u.kind == "unit_group")
    assert paragraph.text == "Widget flurbs\nunknown values."
    assert group.text == "- alpha\n  continued\n- beta"
    assert api.materialize_answer_units(text, (paragraph,)) == paragraph.text
    assert api.materialize_answer_units(text, (group,)) == group.text


def test_punctuation_boundaries_keep_identifiers_versions_and_clause_offsets():
    text = "mcp.server uses 3.11. Other flurbs values; Next frobs input."
    units = api.extract_answer_units(text)
    assert [u.text for u in units] == ["mcp.server uses 3.11.", "Other flurbs values; Next frobs input."]
    clauses = api._bounded_clauses(text)
    assert len(clauses) == 3
    assert all(text[start:end] == clause for start, end, clause in clauses)
    assert api._word_distance((0, 10), (16, 20), text) == 1


def test_unit_validation_trimming_truncation_and_cap_are_preserved():
    text = "  " + "x" * 2000 + "  "
    unit = api.extract_answer_units(text)[0]
    assert len(unit.text) == api.MAX_ANSWER_UNIT_CHARS
    assert text[unit.char_start:unit.char_end] == unit.text
    assert len(api.extract_answer_units("\n".join(f"line {i}" for i in range(100)))) == api.MAX_ANSWER_UNITS
    with pytest.raises(ValueError, match="hash mismatch"):
        replace(unit, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="offsets"):
        replace(unit, char_start=-1)
    field = api._make_source_field_unit("path", "docs/Widget.md")
    with pytest.raises(ValueError, match="content offsets"):
        replace(field, char_start=0, char_end=1)


def test_materialization_order_dedupe_gap_and_source_fields_are_preserved():
    source = "Alpha flurbs values. Middle frobs values. Omega blips values."
    units = api.extract_answer_units(source)
    field = api._make_source_field_unit("path", "docs/Widget.md")
    assert api.materialize_answer_units(source, (units[-1], units[0], units[0], field)) == source + "\n\ndocs/Widget.md"
    assert api.materialize_answer_units(source, (units[0], units[-1]), max_gap_chars=0) == units[0].text + "\n\n" + units[-1].text


def test_truncated_literal_declaration_cannot_certify_a_prefix():
    text = "Widget: " + "x" * 2000
    unit = api.extract_answer_units(text)[0]
    obligation = _obligation(subject_kind="config_key", expected_value="x")
    assert not api.local_proof_for_obligation(obligation, unit).valid
