"""Dormant adapter direct-call closure, not a default pipeline bypass claim."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import MappingProxyType

import pytest

from docmancer.docs.application import retrieval_need_support as adapter
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, select_evidence, validate_evidence_sufficiency,
)
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.evidence_qualification import derived_parent_trace
from docmancer.docs.domain.project_answer_contract import ProofObligation


CREDIT = {
    "need_local_witness": True, "admission_route": "typed_local",
    "matched_need_ids": ["query-need-1"], "need_witness_spans": [[0, 20]],
    "need_witness_source_key": "old-body", "_admission_demands": ["forged"],
    "context_eligible": True, "context_need_ids": ["query-need-1"],
    "_need_context": {"supported": True},
}
QUERY = {"query_origin": "retrieval_need", "need_relation": "default"}


def test_reviewers_original_unknown_default_repro_is_closed_without_mutating_trace():
    trace = {"qualified": True, "need_local_witness": True}
    before = deepcopy(trace)
    result = adapter.apply_retrieval_need_witness(QUERY, trace, "Unrelated quux is 9000.")
    assert result["qualified"] is False
    assert result["qualification_reason"] == "missing_need_local_witness"
    assert "need_local_witness" not in result
    assert trace == before and result is not trace


@pytest.mark.parametrize("relation", ["default", "unknown", "unresolved", "", None,
    "callable_form", "mapping", "literal_value"])
def test_unknown_need_cannot_retain_any_inherited_witness_credit(relation):
    trace = {"qualified": True, **deepcopy(CREDIT), "source": "docs/Ω.md",
        "visible_text": "Original Ω\u0301\tquote 🤖"}
    before = deepcopy(trace)
    result = adapter.apply_retrieval_need_witness(
        {**QUERY, "need_relation": relation}, MappingProxyType(trace), "Unrelated quux is 9000.")
    assert result["qualified"] is False and not set(CREDIT).intersection(result)
    assert result["visible_text"].encode() == trace["visible_text"].encode()
    assert result["source"] == trace["source"] and trace == before
    assert derived_parent_trace(result, source_query_id="query-need-1", parent_query_id="query-original") is None


@pytest.mark.parametrize("qualified", [False, None, 1, 0, "true", "False", [], {}])
def test_unqualified_or_invalid_prequalification_is_not_promoted(monkeypatch, qualified):
    def forbidden(*args, **kwargs):
        pytest.fail("unqualified trace must not request promotion")
    monkeypatch.setattr(adapter, "retrieval_need_local_witness", forbidden)
    trace = {"qualified": qualified, **deepcopy(CREDIT)}
    before = deepcopy(trace)
    result = adapter.apply_retrieval_need_witness(QUERY, trace, "literal context")
    assert result["qualified"] is False and not set(CREDIT).intersection(result)
    assert trace == before


def test_existing_rejection_reason_and_absent_qualification_are_preserved_safely():
    result = adapter.apply_retrieval_need_witness(QUERY,
        {"qualified": False, "qualification_reason": "stale_evidence", **CREDIT}, "quote")
    assert result["qualification_reason"] == "stale_evidence"
    result = adapter.apply_retrieval_need_witness(QUERY, CREDIT, "quote")
    assert result["qualified"] is False and not set(CREDIT).intersection(result)


@pytest.mark.parametrize("proof", [None, False, 1, 0, "true", "matched", (), (True, ()), {}, []])
def test_unknown_absent_and_invalid_primitive_results_fail_closed(monkeypatch, proof):
    calls = []
    def primitive(query, text, *, source=None):
        calls.append((query, text, source))
        return proof
    monkeypatch.setattr(adapter, "retrieval_need_local_witness", primitive)
    result = adapter.apply_retrieval_need_witness(QUERY, {"qualified": True, **CREDIT}, "quote")
    assert len(calls) == 1
    assert result["qualified"] is False and not set(CREDIT).intersection(result)


@pytest.mark.parametrize("text,source", [("", None), (" \t\n", None), (None, None),
    (123, None), ([], None), ("quote", True), ("quote", "verified-owner"), ("quote", [])])
def test_invalid_body_or_source_input_cannot_retain_prequalified_credit(monkeypatch, text, source):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid inputs must fail before primitive evaluation")
    monkeypatch.setattr(adapter, "retrieval_need_local_witness", forbidden)
    result = adapter.apply_retrieval_need_witness(QUERY, {"qualified": True, **CREDIT}, text, source=source)
    assert result["qualified"] is False
    assert result["qualification_reason"] == "invalid_need_witness_input"
    assert not set(CREDIT).intersection(result)


def test_fresh_true_primitive_only_preserves_prequalification_not_old_provenance(monkeypatch):
    # Adapter ABI control only: a stub is not real source or NL proof evidence.
    calls = []
    def primitive(query, text, *, source=None):
        calls.append((query, text, source))
        return True
    monkeypatch.setattr(adapter, "retrieval_need_local_witness", primitive)
    trace = {"qualified": True, **deepcopy(CREDIT)}
    before = deepcopy(trace)
    source = MappingProxyType({"version": "2.0", "snapshot": "current"})
    result = adapter.apply_retrieval_need_witness(QUERY, trace, "actual current body", source=source)
    assert calls == [(QUERY, "actual current body", source)]
    assert result["qualified"] is True and result["need_local_witness"] is True
    assert set(CREDIT).intersection(result) == {"need_local_witness"}
    assert trace == before


@pytest.mark.parametrize("origin", [None, "", "original", "host_lookup", "technical"])
def test_non_need_technical_lane_is_unchanged_and_does_not_call_primitive(monkeypatch, origin):
    def forbidden(*args, **kwargs):
        pytest.fail("non-need technical lane must remain untouched")
    monkeypatch.setattr(adapter, "retrieval_need_local_witness", forbidden)
    trace = {"qualified": True, "qualification_reason": "visible_exact_path", **deepcopy(CREDIT)}
    before = deepcopy(trace)
    result = adapter.apply_retrieval_need_witness({"query_origin": origin}, trace, "docs/Ω.md")
    assert result == trace == before and result is not trace


@pytest.mark.parametrize("value", ["false", "17 ms", "^3.11", "Ω\u0301"])
def test_existing_literal_proof_is_preserved_but_is_not_an_adapter_relation_contract(value):
    text = f'Widget.value = "{value}"'
    unit = extract_answer_units(text)[0]
    obligation = ProofObligation("literal", "exact_fact", "Widget", attribute="value",
        subject_kind="config_key", expected_value=value)
    proof = local_proof_for_obligation(obligation, unit)
    assert proof.valid and proof.reason == "explicit_literal_value_only"
    assert not local_proof_for_obligation(replace(obligation, expected_value=value + "!"), unit).valid
    assert not unit.proposition
    result = adapter.apply_retrieval_need_witness(
        {**QUERY, "need_subject": "Widget", "text": "Widget.value"},
        {"qualified": True, **CREDIT}, text)
    assert not result["qualified"] and "need_local_witness" not in result


def test_downstream_selection_retains_quote_as_context_without_need_or_answer_credit():
    text = "Unrelated quux is 9000. Original Ω\u0301 quote."
    trace = adapter.apply_retrieval_need_witness(QUERY, {"qualified": True, **CREDIT}, text)
    candidate = {"stable_chunk_id": "context-1", "parent_logical_id": "doc-1",
        "source": "docs/reference.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "official", "docs_exactness": "exact", "retrieval_rank": 1,
        "score": 0.9, "retrieval_query_matches": {"query-need-1": trace}}
    decision = select_evidence([candidate], question="What is quux default timeout?",
        config=docs_selection_config(800))
    assert decision.selected_candidates
    assert decision.selected_candidates[0].display_text.encode() == text.encode()
    assert not decision.support_decision.answer_supported
    assert "unsupported_answer_authorization:context_only" in decision.missing_requirements
    assert validate_evidence_sufficiency(decision, result_kind="docs_answer") == []
    assert not trace["qualified"] and not set(CREDIT).intersection(trace)
