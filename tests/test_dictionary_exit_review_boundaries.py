"""Reviewer regressions for current scope authority and explicit delivery vetoes."""
from dataclasses import asdict, replace

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.evidence_selection import (
    build_requirements, docs_selection_config, select_evidence,
)
from docmancer.docs.application.model_visible_projection import (
    canonical_projection_bytes, project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.interfaces.mcp import context_tools as ingress
from tests.test_dictionary_exit_projection import candidate
from tests.test_dictionary_exit_public_request import PartialFacade


QUESTION = "storage records"
SCOPES = [
    {"project_identity": "foreign"},
    {"module_id": "module-foreign"},
    {"exact_version": "3.0"},
    {"required_evidence_paths": ["docs/foreign.md"]},
]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("project_identity", ["foreign", "repo"])
def test_serialized_current_project_scope_works_for_fresh_and_cached_selection(cached, project_identity):
    item = candidate(project_identity="repo", module_id="module-1")
    current = build_requirements(QUESTION, project_identity=project_identity)
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    trace = {}
    payload, snapshot = project_docs_answer(question=QUESTION,
        retrieval={"context_pack": [item], "requirements": asdict(current)},
        canonical_selection=old if cached else None, selection_diagnostics=trace)
    expected = project_identity == "repo"
    assert bool(payload.get("sources")) is expected
    assert bool(snapshot) is expected
    assert payload["answer_supported"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert trace["requirements_hash"] == select_evidence([item], question=QUESTION,
        config=docs_selection_config(800), requirements=current).requirements.requirements_hash


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("contract", [
    {}, {"project_identity": "foreign"}, {"requirements": None},
    {"requirements": "foreign"}, {"requirements": {"kind": "project_identity"}},
    {"requirements": ["foreign"]}, {"requirements": [None]},
    {"requirements": [{}]},
    {"requirements": [{"requirement_id": "scope", "kind": "project_identity"}]},
    {"requirements": [{"requirement_id": "scope", "kind": "project_identity", "value": None}]},
    {"requirements": [{"requirement_id": "scope", "kind": "project_identity", "value": ""}]},
    {"requirements": [{"requirement_id": 123, "kind": "project_identity", "value": "foreign"}]},
    {"requirements": [{"requirement_id": "scope", "kind": "project_identity", "value": "foreign", "mandatory": "false"}]},
    {"requirements": [{"requirement_id": "scope", "kind": "project_identity", "value": "foreign", "unknown": True}]},
    {"requirements": [], "unknown": True},
    {"requirements": [
        {"requirement_id": "scope", "kind": "project_identity", "value": "repo"},
        {"requirement_id": "scope", "kind": "project_identity", "value": "foreign"},
    ]},
    {"requirements": [
        {"requirement_id": "version:one", "kind": "exact_version", "value": "2.0"},
        {"requirement_id": "version:two", "kind": "exact_version", "value": "3.0"},
    ]},
    {"requirements": [
        {"requirement_id": "scope", "kind": "project_identity", "value": "foreign"}, None,
    ]},
])
def test_malformed_serialized_contract_never_becomes_an_unscoped_quote(contract, cached):
    item = candidate(project_identity="repo", module_id="module-1")
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    payload, snapshot = project_docs_answer(question=QUESTION,
        retrieval={"context_pack": [item], "requirements": contract},
        canonical_selection=old if cached else None)
    assert payload["status"] == "insufficient_evidence"
    assert not payload.get("sources") and not snapshot
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert payload["missing"] == ["Current context requirements are invalid."]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("serialized", [False, True])
@pytest.mark.parametrize("cached_origin", ["canonical", "retrieval"])
def test_current_requirements_revalidate_cached_scope(scope, serialized, cached_origin):
    item = candidate(project_identity="repo", module_id="module-1")
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    assert len(old.selected_candidates) == 1
    current = build_requirements(QUESTION, **scope)
    fresh = select_evidence([item], question=QUESTION, config=docs_selection_config(800), requirements=current)
    if "required_evidence_paths" not in scope:
        assert not fresh.selected_candidates
    # Evidence paths are checked again at the quote boundary, independently
    # of the selector's partial-context retention policy.
    fresh_payload, fresh_snapshot = project_docs_answer(question=QUESTION,
        retrieval={"requirements": current}, canonical_selection=fresh)
    assert not fresh_payload.get("sources") and not fresh_snapshot
    retrieval = {"status": "success", "context_pack": [item],
                 "requirements": asdict(current) if serialized else current}
    if cached_origin == "retrieval":
        retrieval["selection_decision"] = old
    payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval,
        canonical_selection=old if cached_origin == "canonical" else None)
    assert payload["status"] == "insufficient_evidence"
    assert not payload.get("sources") and not snapshot
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("scope", SCOPES)
def test_current_mandatory_scope_cannot_be_overwritten_by_cached_id(scope):
    item = candidate(project_identity="repo", module_id="module-1")
    current = build_requirements(QUESTION, **scope)
    target = next(row for row in current if row.kind in {
        "project_identity", "module_id", "exact_version", "evidence_path"})
    allowed = {"project_identity": "repo", "module_id": "module-1",
               "exact_version": "2.0", "evidence_path": "docs/storage.md"}[target.kind]
    old_requirements = replace(current, requirements=tuple(
        replace(row, value=allowed) if row.requirement_id == target.requirement_id else row
        for row in current))
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800), requirements=old_requirements)
    assert old.selected_candidates
    payload, snapshot = project_docs_answer(question=QUESTION,
        retrieval={"requirements": current}, canonical_selection=old)
    assert not payload.get("sources") and not snapshot


@pytest.mark.parametrize("scope", SCOPES)
def test_conflicting_current_args_and_requirement_contract_fail_closed(scope):
    item = candidate(project_identity="repo", module_id="module-1")
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    retrieval = {"requirements": build_requirements(QUESTION, **scope),
        "project_identity": "repo", "module_id": "module-1",
        "docs_exactness": "exact", "requested_version": "2.0",
        "required_evidence_paths": ["docs/storage.md"]}
    payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval, canonical_selection=old)
    assert not payload.get("sources") and not snapshot


@pytest.mark.parametrize("serialized", [False, True])
def test_current_nonblocking_contract_keeps_partial_quote(serialized):
    item = candidate(project_identity="repo", module_id="module-1")
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    current = build_requirements(QUESTION, project_identity="repo", module_id="module-1",
        exact_version="2.0", required_evidence_paths=["docs/storage.md"],
        public_requirements=["unavailable explicit fact"])
    trace = {}
    payload, snapshot = project_docs_answer(question=QUESTION,
        retrieval={"requirements": asdict(current) if serialized else current}, canonical_selection=old,
        selection_diagnostics=trace)
    assert payload["sources"] and snapshot
    assert payload["answer_supported"] is False
    public_ids = {row.requirement_id for row in current if row.public_provenance == "public_task_contract"}
    assert public_ids and public_ids <= set(trace["missing_requirements"])
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("kind, allowed, foreign", [
    ("project_identity", "repo", "foreign"),
    ("module_id", "module-1", "module-foreign"),
    ("exact_version", "2.0", "3.0"),
])
def test_conflicting_mandatory_bindings_inside_current_contract_fail_closed(kind, allowed, foreign):
    item = candidate(project_identity="repo", module_id="module-1")
    old = select_evidence([item], question=QUESTION, config=docs_selection_config(800))
    current = build_requirements(QUESTION, **{kind: allowed})
    binding = next(row for row in current if row.kind == kind)
    current = replace(current, requirements=(*current.requirements,
        replace(binding, requirement_id="current:conflicting-binding", value=foreign)))
    payload, snapshot = project_docs_answer(question=QUESTION,
        retrieval={"requirements": current}, canonical_selection=old)
    assert not payload.get("sources") and not snapshot


BLOCKS = [
    {"requires_confirmation": True, "confirmation_reason": "network_access",
     "reason_code": "network_confirmation_required"},
    {"status": "confirmation_required", "confirmation_reason": "network_access",
     "reason_code": "network_confirmation_required"},
    {"delivery_decision": {"deliverable": False, "reason_code": "explicit_delivery_denied"}},
    {"status": "confirmation_required", "requires_confirmation": True,
     "confirmation_reason": "network_access",
     "delivery_decision": {"deliverable": False, "reason_code": "network_confirmation_required"}},
]


class BlockedFacade(PartialFacade):
    def __init__(self, block):
        super().__init__()
        self.block = block

    def get_docs_context(self, question, **kwargs):
        return {**super().get_docs_context(question, **kwargs), **self.block}


def assert_blocked(payload, block):
    reason = (block.get("delivery_decision") or {}).get("reason_code") or block["reason_code"]
    assert payload["status"] == "insufficient_evidence"
    assert payload["reason_code"] == reason
    assert payload["delivery_decision"] == {"deliverable": False, "reason_code": reason}
    assert not payload.get("sources") and not payload.get("context_available")
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    if block.get("requires_confirmation") or block.get("status") == "confirmation_required":
        assert payload["requires_confirmation"] is True
        assert payload["confirmation_reason"] == "network_access"
    assert len(canonical_projection_bytes(payload)) <= 300 * 4
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=800) == []


@pytest.mark.parametrize("block", BLOCKS)
@pytest.mark.parametrize("projector", ["docs_context", "docs_answer"])
def test_direct_projection_obeys_each_explicit_delivery_block(block, projector):
    retrieval = BlockedFacade(block).get_docs_context("MarbleValve")
    if projector == "docs_context":
        payload, snapshot = project_docs_context(retrieval=retrieval)
    else:
        retrieval["context_pack"] = [candidate()]
        payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval)
    assert not snapshot
    assert_blocked(payload, block)


@pytest.mark.parametrize("block", BLOCKS)
def test_actual_public_handler_preserves_explicit_block_without_recovery(monkeypatch, block):
    facade = BlockedFacade(block)

    def forbidden_recovery(*args, **kwargs):
        pytest.fail("explicit nondelivery must not enter partial-read recovery")

    monkeypatch.setattr(ingress, "projection_recovery_action", forbidden_recovery)
    result = ingress.handle_context_tool("get_docs_context", {
        "question": "MarbleValve", "scope": "project", "project_path": "/repo",
        "allow_network": False,
    }, facade)
    assert facade.calls[0][1]["allow_network"] is False
    assert result["kind"] == "docs_context"
    assert_blocked(result, block)


def test_actual_public_partial_quote_survives_without_explicit_block():
    result = ingress.handle_context_tool("get_docs_context", {
        "question": "MarbleValve", "scope": "project", "project_path": "/repo",
        "allow_network": False,
    }, PartialFacade())
    assert result["status"] == "ok" and result["sources"]
    assert result["context_available"] and result["query_coverage"] == "partial"
    assert result["answer_supported"] is result["answer_available"] is result["edit_ready"] is False
