"""Dictionary-exit admission contract; no frozen acceptance corpus is changed."""
from __future__ import annotations

import hashlib
from dataclasses import asdict

import pytest

from docmancer.docs.application.evidence_selection import (
    build_requirements, docs_selection_config, library_docs_selection_config,
    project_docs_selection_config, select_evidence, validate_evidence_sufficiency,
)
from docmancer.docs.application._evidence_selection_part02 import _facet_requirement_matches
from docmancer.docs.application.evidence_semantic_density import source_fact_unit_semantic_score
from docmancer.docs.application.model_visible_projection import project_patch_context
from docmancer.docs.domain.admission_grammar import canonical_phrase, parse_admission_frame
from docmancer.docs.domain.evidence_qualification import derived_parent_trace, qualify_evidence
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation, build_project_answer_contract, can_authorize_docs_answer,
)
from docmancer.docs.domain.question_plan_command_rules import _command_sync, _docs_mcp_server_command
from docmancer.docs.domain.question_plan_proof import _bounded_subject_aliases, _semantic_terms, relation_proof
from docmancer.docs.domain._answer_units_part02 import _attribute_aliases


def _candidate(text: str, **overrides):
    return {
        "stable_chunk_id": "literal-source", "parent_logical_id": "document-1",
        "source": "docs/reference.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "official", "docs_exactness": "exact", "version": "2.0",
        "retrieval_rank": 1, "score": 0.9, **overrides,
    }


@pytest.mark.parametrize("question", [
    "Which command starts the Docs MCP server?",
    "Which command syncs project docs after file changes?",
    "Explain the architecture of the responsive MCP server",
    "Какой таймаут по умолчанию у QueueHub?",
    "What does get_docs_context return?",
])
def test_read_contract_does_not_compile_expected_answers(question):
    contract = build_project_answer_contract(question)
    assert not contract.proof_obligations
    assert not contract.subjects
    assert not contract.retrieval_hints
    assert not contract.concept_queries
    assert not can_authorize_docs_answer(contract)
    for profile in ("project_docs_answer", "library_docs_answer"):
        requirements = build_requirements(question, profile=profile)
        assert not requirements.required_entities
        assert not requirements.required_facets
        assert not requirements.retrieval_hints
        assert not requirements.concept_queries
        assert all(row.kind == "exact_term" for row in requirements)


def test_index_generated_expected_api_contract_is_not_user_authority():
    requirements = build_requirements(
        "Compare alpha with beta and show code", profile="library_docs_answer",
        library_requirement_contract={
            "entities": ["InventedAPI", "ExpectedAPI"],
            "facets": ["comparison", "result_access"],
            "code_groups": [["expected_call()"]],
        },
    )
    assert not requirements.requirements


def test_command_and_semantic_grammar_tables_are_removed():
    assert _command_sync("Which command syncs project docs?") is None
    assert _docs_mcp_server_command("Which command starts the Docs MCP server?") is None
    assert parse_admission_frame("Can a handler be ordinary?") is None
    assert canonical_phrase("таймаут normal") == "таймаут normal"
    assert _bounded_subject_aliases("BrowserPermissionGate") == ()
    assert _semantic_terms("входа permissions") == {"входа", "permissions"}
    assert _attribute_aliases("timeout") == ("timeout",)
    assert source_fact_unit_semantic_score("Only after approval: timeout: 20") == 0


@pytest.mark.parametrize("facet", [
    "architecture", "responsiveness", "comparison:alpha:beta", "result_access:alpha:x",
    "behavior:alpha", "usage:alpha", "workflow:alpha", "request_handling",
    "recall_mechanism", "authority_invariant",
])
def test_lexical_facets_are_not_answer_proof(facet):
    assert not _facet_requirement_matches(
        facet, "alpha returns a result while beta runs async in a worker. "
        "The server routes requests through the handler. Use alpha then run beta. "
        "Exact-term retrieval preserves authority scope unchanged.",
    )
    obligation = ProofObligation("literal", "relation", "alpha", relation=facet)
    assert relation_proof(obligation, "alpha " + facet).valid is False


@pytest.mark.parametrize("config_factory", [
    docs_selection_config, project_docs_selection_config, library_docs_selection_config,
])
def test_quotes_are_context_not_supported_answers(config_factory):
    decision = select_evidence(
        [_candidate("The API returns docs_context and does not authorize edits.")],
        question="What does the API return?", config=config_factory(800),
    )
    assert decision.support_decision.answer_supported is False
    assert "unsupported_answer_authorization:context_only" in decision.missing_requirements
    assert validate_evidence_sufficiency(decision, result_kind="docs_answer") == []


def test_explicit_scope_contract_is_preserved_without_answer_authorization():
    requirements = build_requirements(
        "Read reference", profile="project_docs_answer",
        required_evidence_paths=("docs/reference.md",), exact_version="2.0",
        exact_snapshot_required=True, project_identity="project-1", module_id="module-1",
        public_requirements=({"kind": "required_fact", "value": "explicit literal"},),
    )
    assert {row.kind for row in requirements} == {
        "evidence_path", "exact_version", "exact_snapshot", "project_identity", "module_id", "required_fact",
    }
    with pytest.raises(ValueError, match="provenance"):
        build_requirements("Read", public_requirements=({"value": "x", "public_provenance": "guessed"},))
    overflow = build_project_answer_contract("x" * 4001)
    assert overflow.input_limits == ("question",)
    assert overflow.question_hash != build_project_answer_contract("x" * 4000).question_hash


@pytest.mark.parametrize("overrides, reason", [
    ({"project_identity": "foreign"}, "wrong_project_identity"),
    ({"freshness": "stale"}, "stale_evidence"),
    ({"index_freshness": "dirty"}, "unsynchronized_index"),
    ({"risk_flags": ["unsafe"]}, "unsafe_evidence"),
])
def test_read_attribution_preserves_eligibility_guards(overrides, reason):
    result = qualify_evidence(
        {"query_origin": "host_lookup", "relation": "host_lookup", "query_terms": ["alpha", "beta"]},
        query_id="lookup-1", visible_text="alpha beta are literal context.",
        candidate={"project_identity": "project-1", **overrides},
        expected_project_identity="project-1",
    )
    assert result.qualified is False
    assert result.reason == reason


def test_independent_lookup_attribution_never_derives_original():
    trace = {"qualified": True, "relation": "audited_rewrite"}
    assert derived_parent_trace(trace, source_query_id="lookup-1", parent_query_id="query-original") is None
    lookup = build_documentation_query_plan("unrelated question", lookup_queries=("alpha beta",)).queries[1]
    result = qualify_evidence(
        {"query_origin": lookup.origin, "relation": lookup.relation, "query_text": lookup.text,
         "query_terms": ["alpha", "beta"]},
        query_id=lookup.query_id, visible_text="alpha beta are literal context.",
        authoritative_query=asdict(lookup),
    )
    assert result.covered_query_ids == (lookup.query_id,)
    assert result.trace["context_only"] is True
    rejected = qualify_evidence(
        {"query_origin": "host_lookup", "relation": "audited_rewrite", "public_parent_query_id": "query-original"},
        query_id="lookup-1", visible_text="alpha beta are literal context.",
    )
    assert not rejected.covered_query_ids


@pytest.mark.parametrize("packet", [
    {"status": "ok"},
    {"status": "invalid", "mutation_intent": {"ready": True}},
    {"status": "ok", "mutation_intent": {"ready": True}, "omitted_counts": {"mandatory_requirements": 1}},
])
def test_context_does_not_bypass_mutation_readiness(packet):
    projected, _ = project_patch_context(packet=packet, evidence_items=[])
    assert projected["edit_ready"] is False
