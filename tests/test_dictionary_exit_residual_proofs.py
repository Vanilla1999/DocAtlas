from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import re

import pytest

from docmancer.docs.domain import answer_units as api
from docmancer.docs.domain import _answer_units_part02 as residual
from docmancer.docs.domain import governance_value_proof as governance
from docmancer.docs.domain.question_premise_proof import premise_relation_proof
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation, obligations_can_authorize_docs_answer,
)


def obligation(kind="exact_fact", **kwargs):
    return ProofObligation("explicit-residual", kind, "Widget", **kwargs)


def supplied(text):
    return replace(api.extract_answer_units(text)[0], proposition=True)


@pytest.mark.parametrize("kind", [
    "purpose", "effect", "attribute", "inventory", "command", "location",
    "comparison", "usage", "relation", "definition", "behavior", "status", "workflow",
])
@pytest.mark.parametrize("subject", ["Widget", "Forged", "Docs MCP"])
def test_supplied_proposition_and_canonical_metadata_cannot_certify(kind, subject):
    unit = supplied("Widget returns true because it is used for retrieval, while Other blocks output.")
    query = replace(obligation(kind), subject=subject)
    source = {"title": subject, "path": f"docs/{subject}.md", "authority": "canonical"}
    proof = api.local_proof_for_obligation(query, unit, source=source)
    assert not proof.valid
    assert proof.reason == "semantic_detector_removed"
    assert (proof.subject_score, proof.relation_score, proof.value_score, proof.completeness_score) == (0, 0, 0, 0)
    with pytest.raises(FrozenInstanceError):
        proof.valid = True


@pytest.mark.parametrize("relation,text", [
    ("governed_scope", "Widget and Other share the same policy."),
    ("governance_ownership", "Platform team owns Widget."),
    ("governance_version", "Widget is pinned to 3.11.0."),
    ("governance_state", "Widget remains deferred."),
    ("governance_requirement", "Android 13 requires Widget."),
    ("governance_facet", "Widget controls the policy."),
    ("unknown_relation", "Widget unknown_relation Other."),
    (None, "Widget is valid."),
])
@pytest.mark.parametrize("authority", ["canonical", "supporting", "source_of_truth"])
def test_governance_and_unknown_relations_return_immutable_negative(relation, text, authority):
    proof = governance.relation_proof(obligation("relation", relation=relation), text, source={"authority": authority})
    assert proof is not None and not proof.valid
    assert proof.reason in {"governance_authority_missing", "semantic_proof_unavailable"}
    assert proof.subject_score == proof.value_score == proof.relation_score == 0
    with pytest.raises(FrozenInstanceError):
        proof.reason = "approved"


@pytest.mark.parametrize("relation", ["premise_check", "premise_cardinality", "unknown", None])
@pytest.mark.parametrize("text", [
    "Widget always removes project docs because it is required.",
    "Widget never deletes project docs because it preserves files.",
    "There are exactly three public Docs MCP tools because of design.",
    "Widget иногда сохраняет файлы, потому что это необходимо.",
    "",
])
def test_premise_no_synonyms_cardinality_or_metadata_subject_fallback(relation, text):
    query = obligation("relation", relation=relation, expected_value="always", target="delete project docs")
    proof = premise_relation_proof(query, text, source={"title": "Docs MCP Widget", "authority": "canonical"})
    assert isinstance(proof, tuple) and proof[0] is False
    assert proof[1:3] == (0, 0) and proof[4] == 0
    assert proof[3] in {"premise_truth_unresolved", "premise_cardinality_unresolved", "semantic_proof_unavailable"}


@pytest.mark.parametrize("value_kind,value", [
    ("text", "literal"), ("status", "deferred"), ("number", "3"),
    ("boolean", "false"), ("version_range", "^3.11"), ("duration", "17 ms"),
    ("path", "/tmp/opencode/Widget"),
])
@pytest.mark.parametrize("proposition", [False, True])
def test_narrow_literal_equality_survives_without_answer_authority(value_kind, value, proposition):
    text = f'Widget.value = "{value}"'
    unit = replace(api.extract_answer_units(text)[0], proposition=proposition)
    query = obligation(subject_kind="config_key", attribute="value", value_kind=value_kind, expected_value=value)
    proof = api.local_proof_for_obligation(query, unit, source={"content": text})
    assert proof.valid and proof.reason == "explicit_literal_value_only"
    assert not obligations_can_authorize_docs_answer((query,))


@pytest.mark.parametrize("change", [
    {"unit_id": "unit-forged"}, {"char_end": 200}, {"char_start": 1, "char_end": 23},
])
def test_literal_forged_identity_and_offsets_do_not_certify(change):
    unit = replace(supplied('Widget.value = "false"'), **change)
    query = obligation(subject_kind="config_key", attribute="value", value_kind="boolean", expected_value="false")
    assert not api.local_proof_for_obligation(query, unit).valid


@pytest.mark.parametrize("source", [
    {"content": 'Other.value = "false"'},
    {"text": 'Other.value = "false"'},
    {"content": None},
    {"content": 'Widget.value = "false"', "text": 'Other.value = "false"'},
    {"content": 'Widget.value = "false"; Other.value = "true"'},
])
def test_wrong_supplied_source_cannot_certify_literal(source):
    query = obligation(subject_kind="config_key", attribute="value", value_kind="boolean", expected_value="false")
    proof = api.local_proof_for_obligation(query, supplied('Widget.value = "false"'), source=source)
    assert not proof.valid and proof.reason == "literal_source_span_mismatch"


@pytest.mark.parametrize("text", [
    '# Widget\nOther.value = "false"',
    'Widget.value = "false"\nOther.value = "true"',
    'Widget.value = "false"\rOther.value = "true"',
    'Widget.value = "FALSE"',
    'Widget.value = "false-extra"',
    'Widget does not have value false.',
])
def test_multiline_neighboring_declaration_and_negated_prose_not_certified(text):
    query = obligation(subject_kind="config_key", attribute="value", value_kind="boolean", expected_value="false")
    for unit in api.extract_answer_units(text):
        if unit.text == 'Widget.value = "false"':
            continue  # Only this exact single declaration is a local equality witness.
        assert not api.local_proof_for_obligation(query, replace(unit, proposition=True), source={"title": "Widget"}).valid


@pytest.mark.parametrize("change", [
    {"subject": "Unknown"}, {"relation": "unknown"}, {"context": "Android 13"},
    {"target": "Other"}, {"subject_kind": None}, {"expected_value": "true"},
])
def test_literal_subject_scope_and_contract_cannot_be_inferred(change):
    query = obligation(subject_kind="config_key", attribute="value", value_kind="boolean", expected_value="false")
    assert not api.local_proof_for_obligation(replace(query, **change), supplied('Widget.value = "false"'), source={"title": "Widget"}).valid


def test_context_retained_empty_and_overflow_packets_not_approved():
    text = "Widget controls policy. Widget uses values."
    units = api.extract_answer_units(text)
    assert api.materialize_answer_units(text, units) == text
    assert all(not u.proposition for u in units)
    query = obligation(subject_kind="config_key", expected_value="false", value_kind="boolean")
    unit = supplied("Widget: false")
    assert api.best_local_proof(query, ()) is None
    assert api.best_local_proof(query, [unit] * api.MAX_ANSWER_UNITS) is not None
    assert api.best_local_proof(query, [unit] * (api.MAX_ANSWER_UNITS + 1)) is None
    assert not api.local_proof_for_obligation(query, unit, source={"lifecycle_status": "superseded"}).valid
    assert not api.local_proof_for_obligation(replace(query, lifecycle_intent="historical"), unit).valid


def test_compatibility_helpers_negative_and_negation_guard_retained():
    query = obligation("comparison", target="Other")
    assert residual._inventory_facts("three public tools: `a`, `b`, `c`", item_kind="public_tool") == (None, (), False)
    assert residual._comparison_predicates(query, "Widget returns values while Other blocks output") == (set(), set())
    assert not residual._explicit_comparison_is_local(query, "Widget unlike Other")
    assert not residual._special_relation_valid("request_handling", "server handles request")
    assert not residual._contract_fact_relation_valid("Widget returns docs_context")
    assert residual._value_score("boolean", "yes true enabled false") == 0
    text = "Widget does not return values"
    assert residual._predicate_is_negated(re.search("return", text), text)
