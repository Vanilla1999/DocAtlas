"""Public projection controls for literal-query, context-only documentation."""
from dataclasses import asdict, replace
import hashlib

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_context_projection import project_docs_context, _requalify_visible_source
from docmancer.docs.application.evidence_selection import (
    build_requirements, docs_selection_config, library_docs_selection_config,
    project_docs_selection_config, select_evidence,
)
from docmancer.docs.application.model_visible_projection import project_docs_answer, validate_model_visible_projection
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def candidate(text="Storage persists records safely.", **overrides):
    return {
        "stable_chunk_id": "quote-1", "parent_logical_id": "document-1",
        "source": "docs/storage.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "official", "docs_exactness": "exact", "version": "2.0",
        "retrieval_rank": 1, "score": 0.9, **overrides,
    }


@pytest.mark.parametrize("config", [docs_selection_config, library_docs_selection_config, project_docs_selection_config])
def test_selected_partial_quotes_survive_public_projection_without_proof(config):
    selection = select_evidence([candidate()], question="storage records", config=config(800),
        public_requirements=["unavailable explicit fact"])
    assert selection.selected_candidates and not selection.support_decision.answer_supported
    payload, snapshot = project_docs_answer(question="storage records", retrieval={
        "status": "success", "answer_available": False,
        "selection_profile": config(800).profile, "selection_decision": selection,
    })
    assert payload["sources"][0]["snippet"] == "Storage persists records safely."
    assert snapshot[payload["sources"][0]["evidence_id"]]["projected_source"] == payload["sources"][0]
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert payload["satisfied_requirement_ids"] == payload["selected_evidence_ids"] == []
    assert payload["mandatory_coverage"] == payload["evidence_coverage"] == 0
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800, canonical_selection=selection) == []


def test_old_supported_canonical_decision_cannot_bypass_projection_policy():
    selection = select_evidence([candidate()], question="storage records", config=docs_selection_config(800))
    old = replace(selection, status="ok", support_decision=replace(selection.support_decision,
        answer_supported=True, support_status="supported"))
    payload, snapshot = project_docs_answer(question="storage records", retrieval={"status": "success"}, canonical_selection=old)
    assert payload["sources"] and snapshot
    assert payload["retrieval_only"] is True and payload["answer_supported"] is False
    assert "answer" not in payload and "answer_evidence_ids" not in payload
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800, canonical_selection=old) == []
    forged = {**payload, "answer_supported": True}
    assert validate_model_visible_projection(forged, snapshot=snapshot, max_tokens=800)


@pytest.mark.parametrize("change", [
    {"freshness": "stale"}, {"index_freshness": "stale"}, {"risk_flags": ["unsafe"]},
    {"project_identity": "foreign"}, {"version": "3.0"},
    {"module_id": "foreign"}, {"source": "docs/foreign.md"},
    {"display_content_hash": "0" * 64},
])
def test_old_selected_quotes_are_rechecked_for_current_technical_guards(change):
    selection = select_evidence([candidate(project_identity="repo", module_id="module-1")], question="storage records", config=docs_selection_config(800))
    selected = selection.selected_candidates[0]
    retrieval = {
        "status": "success", "project_identity": "repo", "requested_version": "2.0", "docs_exactness": "exact",
        "module_id": "module-1", "required_evidence_paths": ["docs/storage.md"],
    }
    positive, positive_snapshot = project_docs_answer(
        question="storage records", retrieval=retrieval, canonical_selection=selection,
    )
    assert positive["sources"][0]["snippet"] == selected.display_text
    assert positive_snapshot
    assert validate_model_visible_projection(positive, snapshot=positive_snapshot, max_tokens=800) == []
    old = replace(selection, selected_candidates=(replace(selected, original={**selected.original, **change}),))
    payload, snapshot = project_docs_answer(question="storage records", retrieval=retrieval, canonical_selection=old)
    if "risk_flags" not in change:
        assert not payload.get("sources") and not snapshot
        return
    # Cached descriptive flags cannot create an authoritative veto or edit/proof
    # authority. Current operational policy, not document metadata, owns delivery.
    assert payload == positive and set(snapshot) == set(positive_snapshot)
    assert snapshot[selected.stable_id]["projected_source"] == positive_snapshot[selected.stable_id]["projected_source"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    for metadata in (
        {"risk_flags": []},
        {"metadata": {"risk_flags": ["unsafe"]}},
        {"delivery_decision": {"deliverable": False}, "requires_confirmation": True},
    ):
        cached = replace(selection, selected_candidates=(replace(selected, original={**selected.original, **metadata}),))
        visible, bound = project_docs_answer(question="storage records", retrieval=retrieval, canonical_selection=cached)
        assert visible == positive and set(bound) == set(positive_snapshot)
        assert bound[selected.stable_id]["projected_source"] == positive_snapshot[selected.stable_id]["projected_source"]
        assert validate_model_visible_projection(visible, snapshot=bound, max_tokens=800) == []
    for policy in (
        {"delivery_decision": {"deliverable": False, "reason_code": "source_access_revoked"}},
        {"requires_confirmation": True},
        {"status": "confirmation_required"},
    ):
        blocked, bound = project_docs_answer(
            question="storage records", retrieval={**retrieval, **policy}, canonical_selection=old,
        )
        assert not blocked.get("sources") and not bound
        assert blocked["delivery_decision"]["deliverable"] is False
        assert blocked["answer_supported"] is blocked["answer_available"] is blocked["edit_ready"] is False


def test_quote_budget_and_visible_snapshot_binding_remain_enforced():
    payload, snapshot = project_docs_answer(question="storage records", retrieval={"context_pack": [candidate()]}, max_tokens=800)
    assert payload["sources"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    changed = {**payload, "sources": [{**payload["sources"][0], "snippet": "Different source bytes."}]}
    assert validate_model_visible_projection(changed, snapshot=snapshot, max_tokens=800)
    text = "\n".join(f"Storage records field_{index} must equal value-{index}." for index in range(100))
    large = candidate(text)
    bounded, bound_snapshot = project_docs_answer(question="storage records", retrieval={"context_pack": [large]}, max_tokens=256)
    assert bounded["sources"][0]["snippet"] == text
    assert set(bound_snapshot) == {row["evidence_id"] for row in bounded["sources"]}
    assert validate_model_visible_projection(bounded, snapshot=bound_snapshot, max_tokens=256) == []
    facts = [f"Storage {name} records persist." for name in ("alpha", "bravo", "charlie", "delta")]
    selection = select_evidence([candidate(text, stable_chunk_id=f"quote-{index}", parent_logical_id=f"document-{index}",
                                          source=f"docs/storage-{index}.md") for index, text in enumerate(facts)],
        question="storage records", config=docs_selection_config(800), public_requirements=facts)
    capped, capped_snapshot = project_docs_answer(question="storage records", retrieval={"status": "success"}, canonical_selection=selection)
    assert len(capped["sources"]) == 4
    assert {row["path_or_url"] for row in capped["sources"]} == {f"docs/storage-{index}.md" for index in range(4)}
    assert {row["snippet"] for row in capped["sources"]} == set(facts)
    assert set(capped_snapshot) == {row["evidence_id"] for row in capped["sources"]}
    assert validate_model_visible_projection(capped, snapshot=capped_snapshot, max_tokens=800) == []


@pytest.mark.parametrize("query_id, origin, relation", [
    ("query-need-1", None, None), ("query-original", "host_lookup", "host_lookup"),
    ("query-need-1", "original", "direct"), ("query-lookup-1", "original", "direct"),
])
def test_qualifier_rejects_id_origin_relation_impostors(query_id, origin, relation):
    result = qualify_evidence({"query_text": "storage records", "query_terms": ["storage", "records"],
        "query_origin": origin, "relation": relation}, query_id=query_id,
        visible_text="Storage persists records safely.")
    assert not result.qualified and not result.covered_query_ids


def test_anonymous_helper_is_diagnostic_no_credit_and_public_text_is_exact():
    result = qualify_evidence({"query_text": "storage records", "query_terms": ["storage", "records"]},
        query_id="helper", visible_text="Storage persists records safely.")
    assert result.qualified and not result.covered_query_ids and result.trace["admission_only"]
    assert result.coverage_kind is None
    lookup = asdict(build_documentation_query_plan("storage records").queries[0])
    result = qualify_evidence({"query_text": "billing issues", "query_terms": ["billing", "issues"],
        "query_origin": "original", "relation": "direct"}, query_id="query-original",
        visible_text="Billing issues are documented.", authoritative_query=lookup)
    assert not result.qualified and not result.covered_query_ids


def test_tagging_uses_execution_lookup_not_incoming_lexical_text():
    lookup = build_documentation_query_plan("storage records", lookup_queries=("billing issues",)).queries[1]
    chunk = RetrievedChunk(source="docs/billing.md", chunk_index=0, text="Billing issues are documented.", score=1,
        metadata={"lexical_match": {"query_text": "storage records", "query_origin": "original", "qualified": True}})
    tagged = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup=lookup)
    trace = tagged[0].metadata["retrieval_query_matches"][lookup.query_id]
    assert trace["query_text"] == lookup.text and trace["query_origin"] == "host_lookup"
    assert "query-original" not in tagged[0].metadata["retrieval_query_ids"]


def test_crop_requalification_rebuilds_actual_plan_text_and_drops_generated_needs():
    plan = build_documentation_query_plan("storage records", lookup_queries=("billing issues",)).as_payload()
    source = _requalify_visible_source({
        "path_or_url": "docs/billing.md", "snippet": "Billing issues are documented.",
        "_independent_query_plan": plan,
        "retrieval_query_matches": {
            "query-original": {"query_origin": "original", "relation": "direct", "query_text": "billing issues", "qualified": True},
            "query-need-1": {"query_origin": "original", "relation": "direct", "query_text": "billing issues", "qualified": True},
        },
    }, query_text={q["query_id"]: q["text"] for q in plan["queries"]})
    assert not source["retrieval_query_matches"]["query-original"]["qualified"]
    assert "query-need-1" not in source["retrieval_query_matches"]
    assert source["retrieval_query_matches"]["query-lookup-1"]["qualified"]


def test_context_facade_keeps_explicit_lookup_quote_with_only_its_own_coverage():
    plan = build_documentation_query_plan("storage records", lookup_queries=("billing issues",)).as_payload()
    payload, snapshot = project_docs_context(retrieval={
        "project_identity": "repo", "documentation_query_plan": plan,
        "context_pack": [{"source_class": "project_doc", "path": "docs/billing.md",
            "content": "Billing issues are documented.", "project_identity": "repo", "lifecycle_status": "current",
            "retrieval_query_matches": {"query-original": {"qualified": True, "query_text": "billing issues", "query_origin": "original", "relation": "direct"}}}],
    })
    assert payload["sources"] and snapshot
    assert "query-original" not in payload.get("covered_query_ids", [])
    assert payload.get("covered_query_ids") == ["query-lookup-1"]
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


def test_generated_need_fallback_does_not_deliver_or_credit_unrelated_context():
    plan = build_documentation_query_plan("storage records").as_payload()
    payload, snapshot = project_docs_context(retrieval={
        "project_identity": "repo", "documentation_query_plan": plan,
        "context_pack": [{"source_class": "project_doc", "path": "docs/billing.md",
            "content": "Billing issues are documented.", "project_identity": "repo",
            "retrieval_query_matches": {"query-need-1": {"qualified": True, "query_text": "billing issues", "query_origin": "retrieval_need"}}}],
    })
    assert not payload.get("sources") and not snapshot and not payload.get("covered_query_ids")


def test_original_literal_context_without_discovery_trace_is_delivered_no_credit():
    plan = build_documentation_query_plan("storage records").as_payload()
    payload, snapshot = project_docs_context(retrieval={
        "project_identity": "repo", "documentation_query_plan": plan,
        "context_pack": [{"source_class": "project_doc", "path": "docs/storage.md",
            "content": "Storage persists records safely.", "project_identity": "repo"}],
    })
    assert payload["sources"] and snapshot and not payload.get("covered_query_ids")
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("supplied", [False, True])
@pytest.mark.parametrize("snapshot_exact", [None, False, True])
def test_context_only_projection_preserves_mandatory_exact_snapshot(supplied, snapshot_exact):
    question = "storage records"
    requirements = build_requirements(question, exact_snapshot_required=True)
    selection = select_evidence([candidate(docs_snapshot_exact=snapshot_exact)],
        question=question, config=docs_selection_config(800), requirements=requirements)
    retrieval = {"status": "success", "requirements": requirements,
                 "context_pack": [candidate(docs_snapshot_exact=snapshot_exact)]}
    payload, snapshot = project_docs_answer(question=question, retrieval=retrieval,
        canonical_selection=selection if supplied else None)
    assert bool(payload.get("sources")) is (snapshot_exact is True)
    assert bool(snapshot) is (snapshot_exact is True)
    assert payload["answer_supported"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("supplied", [False, True])
@pytest.mark.parametrize("profile", ["generic", "project_docs_answer", "library_docs_answer"])
def test_context_only_projection_preserves_question_input_limit(supplied, profile):
    question = "storage " + "x" * 4_000
    config = {"generic": docs_selection_config, "project_docs_answer": project_docs_selection_config,
              "library_docs_answer": library_docs_selection_config}[profile](800)
    selection = select_evidence([candidate()], question=question, config=config)
    retrieval = {"status": "success", "selection_profile": profile, "context_pack": [candidate()]}
    if profile == "library_docs_answer":
        retrieval["selection_decision"] = selection
    payload, snapshot = project_docs_answer(question=question, retrieval=retrieval,
        canonical_selection=selection if supplied else None)
    assert payload["status"] == "insufficient_evidence"
    assert not payload.get("sources") and not snapshot
    assert "input_limit:question" in payload["missing"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("supplied", [False, True])
def test_current_public_requirement_overflow_cannot_hide_behind_old_selection(supplied):
    selection = select_evidence([candidate()], question="storage records", config=docs_selection_config(800))
    payload, snapshot = project_docs_answer(question="storage records", retrieval={
        "context_pack": [candidate()], "public_requirements": [f"value-{i}" for i in range(13)],
    }, canonical_selection=selection if supplied else None)
    assert payload["status"] == "insufficient_evidence"
    assert not payload.get("sources") and not snapshot
    assert "input_limit:public_requirements" in payload["missing"]


@pytest.mark.parametrize("failure", ["question", "identifiers", "public_requirements"])
def test_context_projection_rejects_current_and_supplied_input_limits(failure):
    question = "storage records" if failure != "question" else "storage " + "x" * 4_000
    plan = build_documentation_query_plan(question, lookup_queries=("storage records",)).as_payload()
    payload, snapshot = project_docs_context(retrieval={
        "question": question, "documentation_query_plan": plan,
        "missing_requirement_ids": [f"input_limit:{failure}"],
        "context_pack": [{"source_class": "project_doc", "path": "docs/storage.md",
            "content": "Storage persists records safely.", "project_identity": "repo"}],
    })
    assert payload["status"] == "insufficient_evidence"
    assert not payload.get("sources") and not snapshot
    assert f"input_limit:{failure}" in payload["missing"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("contract_origin", ["requirements", "selection_decision"])
@pytest.mark.parametrize("snapshot_exact", [None, False, True])
def test_context_route_preserves_mandatory_snapshot_eligibility(contract_origin, snapshot_exact):
    plan = build_documentation_query_plan("storage records").as_payload()
    requirement = {"requirement_id": "exact_snapshot:true", "kind": "exact_snapshot", "value": "true", "mandatory": True}
    contract = {"requirements": [requirement]}
    retrieval = {
        "documentation_query_plan": plan, "project_identity": "repo",
        "context_pack": [{"source_class": "project_doc", "path": "docs/storage.md",
            "content": "Storage persists records safely.", "project_identity": "repo",
            "docs_snapshot_exact": snapshot_exact}],
        contract_origin: contract if contract_origin == "requirements" else {"requirements": contract},
    }
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert bool(payload.get("sources")) is (snapshot_exact is True)
    assert bool(snapshot) is (snapshot_exact is True)
    assert payload["answer_supported"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
