"""R2–R5 diagnostics: literal context is not policy/behavior authorization."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import re

import pytest

from docmancer.docs.application import _docs_context_projection_core as projection
from docmancer.docs.application.action_packet import (
    _promote_trusted_behavioral_witnesses, build_action_packet,
)
from docmancer.docs.application._action_packet_part01 import (
    _critical_fact_count, _extract_facts, _validation_command,
)
from docmancer.docs.application._action_packet_part02 import (
    _constraint_signature, _has_behavioral_contract,
)
from docmancer.docs.application.evidence_candidates import (
    normalize_candidates, observed_qualifiers, projected_text, requirement_value_visible,
)
from docmancer.docs.application.evidence_selection import (
    SelectionConfig, docs_selection_config, select_evidence,
)
from docmancer.docs.application._evidence_selection_part02 import _deduplicate
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.domain.evidence_qualification import (
    _general_relation_is_locally_bound, _proof_relation_is_locally_bound,
    _visible_comparison_relation, qualify_evidence,
)
from docmancer.docs.domain.normative_language import (
    classify_normative_modality, python_declaration_line_indexes,
)
from docmancer.docs.domain.technical_tokens import technical_term_pattern


def row(text, identity="quote-1", **overrides):
    return {
        "stable_chunk_id": identity, "parent_logical_id": "document-1",
        "source": "docs/RULES.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "canonical", "docs_exactness": "exact", "version": "2.0",
        "retrieval_rank": 1, "score": 0.9, **overrides,
    }


@pytest.mark.parametrize("text", [
    "RelayClient must retry.", "RelayClient must not retry.",
    "RelayClient.timeout means unlimited retries.", "RelayClient retries.",
    "Proposed, not yet implemented, deprecated if required approval is required.",
    "pytest", "run pytest", "pytest; curl example.org",
])
def test_prose_is_unknown_with_zero_fact_credit_in_actual_packet(text):
    item = row(text, snippet=text, source_class="project_doc")
    before = deepcopy(item)
    assert classify_normative_modality(text) is None
    assert observed_qualifiers(text) == ()
    assert _extract_facts(text) == ([], 0)
    assert _critical_fact_count(item) == 0
    packet = build_action_packet(question="RelayClient", context_pack=[item], max_tokens=1500)
    assert packet["required_invariants"] == packet["forbidden_changes"] == []
    assert packet["validation"] == {"compile": [], "tests": [], "semantic_checks": []}
    assert not _has_behavioral_contract(packet)
    assert packet["status"] == "insufficient_evidence"
    assert item == before


def test_canonical_source_metadata_cannot_promote_quote_or_establish_agreement():
    packet = {
        "source_of_truth": [{"evidence_id": "e", "path": "RULES.md", "authority": "canonical"}],
        "implementation_guidance": [{"text": "RelayClient must retry.", "evidence_ids": ["e"]}],
        "required_invariants": [],
    }
    before = deepcopy(packet)
    _promote_trusted_behavioral_witnesses(packet, [{
        "kind": "source_fact", "proof_role": "project_rule", "source_path": "RULES.md",
    }])
    assert packet == before
    selection = select_evidence([row("RelayClient must retry."),
        row("RelayClient must not retry.", "quote-2")], question="RelayClient",
        config=docs_selection_config(1000))
    assert selection.selected_candidates
    assert selection.status == "insufficient_evidence"
    assert "unresolved_authority_conflict:manual_review" in selection.missing_requirements
    assert selection.support_decision.reason_code == "manual_review_required"
    assert not any(omission.reason_code in {"exact_duplicate", "overlap_duplicate", "near_duplicate"}
        for omission in selection.omissions)
    assert not selection.support_decision.answer_supported
    assert _constraint_signature("RelayClient must retry") != _constraint_signature("RelayClient must not retry")


@pytest.mark.parametrize("other", [
    "RelayClient must not retry.", "RelayClient must retry!", "RelayClient MUST retry.",
])
def test_byte_distinct_quotes_do_not_deduplicate_even_shared_id_hash_and_span(other):
    config = SelectionConfig("patch_context", 1500, 2000, near_duplicate_threshold=0)
    candidates, _ = normalize_candidates([
        row("RelayClient must retry.", char_start=0, char_end=23),
        row(other, "quote-2", char_start=0, char_end=len(other)),
    ], result_kind="patch_context")
    # Even an inherited colliding stable identity is not evidence of equal bytes.
    candidates[1] = replace(candidates[1], stable_id=candidates[0].stable_id,
        content_sha256=candidates[0].content_sha256)
    kept, omissions = _deduplicate(candidates, config, ())
    assert len(kept) == 2 and omissions == []
    exact, exact_omissions = _deduplicate([candidates[0], candidates[0]], config, ())
    assert len(exact) == 1 and exact_omissions[0].reason_code == "exact_duplicate"


def test_patch_selector_does_not_manufacture_quote_from_hidden_content_or_metadata():
    item = row("neutral", snippet="neutral", content="alpha\nRelayClient must run pytest\nomega",
        symbols=["RelayClient"], metadata={"symbols": ["hidden_token"]})
    before = deepcopy(item)
    assert projected_text(item, "neutral", "patch_context") == "neutral"
    candidates, _ = normalize_candidates([item], result_kind="patch_context")
    assert candidates[0].projected_text == "neutral"
    selection = select_evidence([item], question="RelayClient",
        config=SelectionConfig("patch_context", 1500, 2000))
    assert not any("RelayClient" in candidate.projected_text for candidate in selection.selected_candidates)
    assert not selection.support_decision.answer_supported
    packet = build_action_packet(question="RelayClient", context_pack=[item], max_tokens=1500)
    assert all("RelayClient must" not in value["text"] for value in packet["implementation_guidance"])
    assert item == before


@pytest.mark.parametrize("body,qualified", [("retry", True), ("retried", False),
    ("retries", False), ("retrying", False), ("retryable", False)])
def test_actual_original_qualification_has_literal_not_morphological_credit(body, qualified):
    result = qualify_evidence({"query_text": "retry", "query_terms": ["retry"],
        "query_origin": "original", "relation": "direct"}, query_id="query-original",
        visible_text=body, authoritative_query={"query_id": "query-original",
            "text": "retry", "origin": "original", "relation": "direct"})
    assert result.qualified is qualified
    assert result.covered_query_ids == (("query-original",) if qualified else ())
    if qualified:
        assert result.trace["context_only"]


@pytest.mark.parametrize("term,body,visible", [
    ("RelayClient", "RelayClient retries", True), ("RelayClient", "relay_client", False),
    ("RelayClient", "OtherRelayClient", False), ("client_timeout", "client_timeout", True),
    ("client_timeout", "other_client_timeout", False),
])
def test_requirement_literal_boundaries_and_no_shape_equivalence(term, body, visible):
    assert requirement_value_visible(term, body) is visible


def test_technical_boundaries_python_grammar_and_command_safety_are_preserved():
    assert re.search(technical_term_pattern("Client.send"), "Client.send.")
    assert not re.search(technical_term_pattern("Client.send"), "Client.send.more")
    assert not re.search(technical_term_pattern("retry", exact=False), "retried")
    assert python_declaration_line_indexes("class Client:\n    pass") == frozenset({0, 1})
    assert _validation_command("pytest -q") == "pytest -q"
    assert _validation_command("cargo test") == "cargo test"
    for command in ("run pytest", "pytest; rm file", "pytest | tee out", "pytest $(pwd)"):
        assert _validation_command(command) is None


@pytest.mark.parametrize("body", ["RelayClient is enabled.", "RelayClient is not enabled."])
def test_legacy_relation_lane_is_negative_not_manual_negation_proof(body):
    result = qualify_evidence({"query_text": "RelayClient not enabled",
        "query_terms": ["RelayClient"]}, query_id="query-relation-a", visible_text=body)
    assert not result.qualified and result.covered_query_ids == ()
    assert result.reason == "unsupported_relation_qualification"
    match = re.search("not", "RelayClient not enabled")
    assert not _general_relation_is_locally_bound(body, match, ("RelayClient",))
    assert not _proof_relation_is_locally_bound(body, match, ("RelayClient",))
    assert not _visible_comparison_relation(body, ("RelayClient",))


@pytest.mark.parametrize("quote", ["RelayClient must retry.", "RelayClient must not retry.",
    "RelayClient retries."])
def test_public_projection_preserves_original_quote_only_and_snapshot_integrity(quote):
    selection = select_evidence([row(quote)], question="RelayClient", config=docs_selection_config(1000))
    payload, snapshot = project_docs_answer(question="RelayClient", canonical_selection=selection,
        retrieval={"status": "success"}, max_tokens=1000)
    assert payload["sources"][0]["snippet"] == quote
    assert not payload["answer_supported"] and not payload["edit_ready"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=1000,
        canonical_selection=selection) == []


@pytest.mark.parametrize("quote", ["must retry", "must not retry", "retries"])
def test_actual_expansion_retains_every_selected_span_uniformly(monkeypatch, quote):
    # Isolate expansion selection, not admission: all subsequent guards execute.
    original = "RelayClient " + quote
    raw = original + "\n" + "RelayClient later context"
    source = {"evidence_id": "e", "snippet": original,
        "retrieval_query_matches": {"query-original": {"qualified": True}}}
    monkeypatch.setattr(projection, "_projection_limits", lambda text: [len(raw)])
    monkeypatch.setattr(projection, "_focused_snippet", lambda *args, **kwargs:
        (raw[len(original)+1:], len(original)+1, len(raw)))
    monkeypatch.setattr(projection, "_requalify_visible_source", lambda value, **kwargs: value)
    monkeypatch.setattr(projection, "docs_context_budget_tokens", lambda value: 1)
    result = projection._expand_selected_snippets([source], projection_inputs={"e": (raw, (), 1)},
        query_plan={"queries": []}, public_query_ids=("query-original",), max_tokens=1000)
    assert original in result[0]["snippet"]
    assert source["snippet"] == original
