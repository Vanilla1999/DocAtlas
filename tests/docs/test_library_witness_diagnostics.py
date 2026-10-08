"""Explain missed indexed literals without granting answers or edit authority.

An automatic diagnostic may find a fact outside primary retrieval. That finding
labels the retrieval miss; it never replaces primary context or proves absence.
All acquisition/storage ports here are finite fixtures, not live index evidence.
"""
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from docmancer.docs.application import evidence_selection as selector
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application._library_docs_service_part03 import _indexed_library_source
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from tests.docs.test_docs_lossless_selection import (
    _LIBRARY_ROOT, _bind_library_fixture_pages, _library_window,
    _public_library_fixture,
)


class _FiniteStore:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def query(self, query, *, limit, budget, filters):
        self.calls.append((query, limit, budget, filters))
        response = self.responses.get(query, [])
        if isinstance(response, Exception):
            raise response
        # Honor the actual store port's requested finite hit bound.
        return deepcopy(response[:limit])


class _FixtureGateway(AgentIndexGateway):
    def agent_instance(self, record=None):
        assert record == self.fixture_record
        return self.fixture_agent


def _gateway(record, store):
    # Only bypass agent/index lifecycle construction. Native probe query
    # construction, limits, filters, dedupe and failure classification run.
    gateway = object.__new__(_FixtureGateway)
    gateway.fixture_record = record
    gateway.fixture_agent = SimpleNamespace(store=store)
    return gateway


def _fixture(tmp_path, *, complete=True, mode="hit", stale_orphan=False):
    primary = _library_window("primary", "Delivery requires consent_token.")
    witness = _library_window("region-witness", "deployment_region = eu_central", source=_LIBRARY_ROOT + "/regions")
    _bind_library_fixture_pages([primary, witness])
    assert _indexed_library_source(witness.source, witness.text, witness.metadata) is not None
    service, trace = _public_library_fixture(tmp_path, [primary], complete)
    record = service.registry.get("fixture-library", source_type="web")
    corpus = [primary, witness]

    def count(requested):
        assert requested == record
        trace["manifest_checks"].append("full_fixture_count")
        return len({row.source for row in corpus}), len(corpus)

    def coverage(requested, pages):
        assert requested == record and pages == 2
        trace["manifest_checks"].append("full_fixture_coverage")
        expected = sorted({row.source for row in corpus})
        return expected, list(expected), [], ["orphan-source"] if stale_orphan else [], "fixture-manifest"

    service.registry_ops.count_index_entries = count
    service.registry_ops.manifest_coverage = coverage
    responses = {"deployment_region": [witness]} if mode == "hit" else {}
    if mode == "error":
        responses = {"deployment_region": RuntimeError("fixture query unavailable")}
    store = _FiniteStore(responses) if mode != "unavailable" else None
    gateway = _gateway(record, store)

    def probe(requested, requirements, *, missing_requirement_ids, filters):
        trace["probe"].append({"missing_ids": list(missing_requirement_ids), "filters": dict(filters), "requirements_hash": requirements.requirements_hash})
        return gateway.probe_library_requirements(requested, requirements, missing_requirement_ids=missing_requirement_ids, filters=filters)

    service.facade.agent_gateway.probe_library_requirements = probe
    return SimpleNamespace(service=service, trace=trace, primary=primary, witness=witness, record=record, store=store, gateway=gateway)


def _get(fixture):
    return fixture.service.get_docs("fixture-library", topic="Delivery contract deployment_region", version="1", ecosystem="fixture", source_type="web")


def _diagnostic(result):
    return result.diagnostics["retrieval"]["index_witness"]


def _helper(fixture, decision):
    info = fixture.service.resolve_library("fixture-library", source_type="web")
    return fixture.service._bounded_library_index_witness(
        record=fixture.record, info=info, requirements=decision.requirements, support_decision=decision.support_decision,
        retrieval_filters={"library_id": fixture.record.library_id}, allowed_ids={fixture.record.library_id},
        expected_roots={_LIBRARY_ROOT}, dispatcher_candidate_ids={row.stable_id for row in decision.selected_candidates},
        resolved_version="1", requested_version="1", docs_exactness="exact", docs_snapshot_exact=True, exact_version_match=True,
    )


def _assert_context_only(result):
    assert result.context_available
    assert not result.answer_supported and not result.answer_available
    assert not result.support_decision.answer_supported
    assert result.decision == "insufficient_evidence"
    assert result.support_decision.missing_requirement_ids
    assert asdict(result).get("edit_ready") is not True
    assert not any(isinstance(action, dict) and action.get("auto_execute") is True for action in result.next_actions)


def test_indexed_omission_labels_retrieval_miss_without_delivering_probe_facts(tmp_path):
    before = _get(_fixture(tmp_path, mode="no-hit"))
    fixture = _fixture(tmp_path)
    result = _get(fixture)
    _assert_context_only(before)
    _assert_context_only(result)
    missing_fact = next(row.requirement_id for row in result.requirements if row.value == "deployment_region")
    diagnostic = _diagnostic(result)
    assert diagnostic["status"] == "witness_found"
    assert diagnostic["witnesses"] == [{"evidence_id": "region-witness", "covered_requirement_ids": [missing_fact]}]
    assert diagnostic["queried_requirement_ids"] == [missing_fact]
    assert diagnostic["candidate_count"] == 1 and diagnostic["failure_count"] == 0
    assert result.reason_code == result.support_decision.reason_code == "retrieval_miss"
    assert result.support_decision.missing_requirement_ids == before.support_decision.missing_requirement_ids
    assert result.support_decision.decision_hash != before.support_decision.decision_hash
    for field in ("requirements_hash", "selector_config_hash", "eligibility_contract_hash", "candidate_trace_hash", "selection_hash", "assignment_hash"):
        assert getattr(result.support_decision, field) == getattr(before.support_decision, field)
    assert result.decision_hash == result.support_decision.decision_hash
    assert [row.metadata["stable_chunk_id"] for row in result.results] == ["primary"]
    assert result.results[0].content == fixture.primary.text
    assert "eu_central" not in json.dumps(result.diagnostics)
    assert "eu_central" not in json.dumps({"results": [asdict(row) for row in result.results], "primary_snippet": result.primary_snippet, "supporting_snippets": result.supporting_snippets, "primary_snippets": result.primary_snippets})
    assert fixture.store.calls == [("deployment_region", 3, 120, {"library_id": "fixture-library", "resolved_version": "1", "exact_snapshot_required": True})]


@pytest.mark.parametrize("mode,expected", [("no-hit", "no_witness"), ("unavailable", "unavailable"), ("error", "unavailable")], ids=["no-hit", "unavailable-store", "query-error"])
def test_diagnostic_failure_or_no_hit_keeps_gaps_and_primary_context(tmp_path, mode, expected):
    fixture = _fixture(tmp_path, mode=mode)
    result = _get(fixture)
    _assert_context_only(result)
    assert _diagnostic(result)["status"] == expected
    assert result.reason_code != "retrieval_miss"
    assert [row.metadata["stable_chunk_id"] for row in result.results] == ["primary"]
    assert any(row.value == "deployment_region" and row.requirement_id in result.support_decision.missing_requirement_ids for row in result.requirements)
    # An empty or failed diagnostic cannot assert that the requested fact is absent.
    assert "absence_proven" not in json.dumps(result.diagnostics)


@pytest.mark.parametrize("complete,stale_orphan", [(False, False), (True, True)], ids=["incomplete-manifest", "stale-orphan"])
def test_unproven_complete_manifest_never_queries_witness_store(tmp_path, complete, stale_orphan):
    fixture = _fixture(tmp_path, complete=complete, stale_orphan=stale_orphan)
    result = _get(fixture)
    _assert_context_only(result)
    assert _diagnostic(result) == {"status": "not_attempted", "reason_code": "corpus_not_proven_complete"}
    assert not fixture.trace["probe"] and not fixture.store.calls


def test_native_sufficient_no_gap_decision_does_not_schedule_diagnosis(tmp_path):
    fixture = _fixture(tmp_path)
    item = {"stable_chunk_id": "primary", "path": fixture.primary.source, "display_text": fixture.primary.text}
    requirements = EvidenceRequirementSet((EvidenceRequirement("present", "required_fact", fixture.primary.text),))
    decision = selector.select_evidence([item], question="", config=selector.patch_selection_config(), requirements=requirements)
    assert decision.support_decision.answer_supported and not decision.support_decision.missing_requirement_ids
    assert decision.assignments and not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")
    result = _helper(fixture, decision)
    assert result == {"status": "not_needed"}
    assert not fixture.trace["probe"] and not fixture.store.calls


def test_incomplete_probe_is_not_an_omission_or_absence_verdict(tmp_path):
    fixture = _fixture(tmp_path, mode="no-hit")
    fixture.store.responses["deployment_region"] = RuntimeError("fixture query unavailable")
    requirements = selector.build_requirements("deployment_region retention_policy", profile="library_docs_answer", exact_version="1")
    item = {"stable_chunk_id": "primary", "source": fixture.primary.source, "content": fixture.primary.text, "resolved_version": "1", "version_binding": "exact"}
    decision = selector.select_evidence([item], question="deployment_region retention_policy", config=selector.library_docs_selection_config(4000), requirements=requirements)
    assert decision.selected_candidates and decision.support_decision.missing_requirement_ids
    assert not decision.support_decision.answer_supported
    before_hash = decision.support_decision.decision_hash
    result = _helper(fixture, decision)
    assert result["status"] == "incomplete" and result["failure_count"] == 1
    assert result["candidate_count"] == 0 and "witnesses" not in result
    assert len(fixture.store.calls) == 2
    assert decision.support_decision.decision_hash == before_hash
    assert not decision.support_decision.answer_supported


@pytest.mark.parametrize("attack", ["library", "root", "version", "digest", "span"], ids=["library", "root", "version", "digest", "span"])
def test_invalid_indexed_witness_cannot_label_source_bound_omission(tmp_path, attack):
    fixture = _fixture(tmp_path)
    positive = _get(fixture)
    assert _diagnostic(positive)["status"] == "witness_found"
    _assert_context_only(positive)
    invalid = deepcopy(fixture.witness)
    if attack == "library":
        invalid.metadata["library_id"] = "other-library"
    elif attack == "root":
        invalid.source = "https://foreign.example/regions"
    elif attack == "version":
        invalid.metadata["version"] = invalid.metadata["resolved_version"] = "2"
    elif attack == "digest":
        invalid.metadata["content_hash"] = "0" * 64
    elif attack == "span":
        invalid.metadata["char_span"][1] -= 1
    fixture.store.responses["deployment_region"] = [invalid]
    denied = _get(fixture)
    _assert_context_only(denied)
    assert _diagnostic(denied)["status"] != "witness_found"
    assert denied.reason_code != "retrieval_miss"
    assert denied.support_decision.missing_requirement_ids == positive.support_decision.missing_requirement_ids
    assert [row.metadata["stable_chunk_id"] for row in denied.results] == ["primary"]


def test_native_gateway_defaults_bound_queries_hits_budget_and_dedupe(tmp_path):
    fixture = _fixture(tmp_path)
    requirements = EvidenceRequirementSet(tuple(EvidenceRequirement(f"q{index}", "exact_term", f"term_{index}") for index in range(6)) + (
        EvidenceRequirement("optional", "exact_term", "optional_term", mandatory=False),
        EvidenceRequirement("scope", "exact_version", "1"),
    ))
    shared = _library_window("shared", "Common indexed fact.")
    responses = {f"term_{index}": [shared, shared, _library_window(f"unique-{index}", f"term_{index} = enabled")] for index in range(6)}
    store = _FiniteStore(responses)
    gateway = _gateway(fixture.record, store)
    filters = {"library_id": fixture.record.library_id, "resolved_version": "1", "exact_snapshot_required": True}
    original_filters = dict(filters)
    probe = gateway.probe_library_requirements(fixture.record, requirements, missing_requirement_ids=[row.requirement_id for row in requirements], filters=filters)
    assert probe.status == "ok" and probe.failure_count == 0
    assert probe.queried_requirement_ids == ("q0", "q1", "q2", "q3")
    assert [row[0] for row in store.calls] == [f"term_{index}" for index in range(4)]
    assert all(row[1:3] == (3, 30) and row[3] is filters for row in store.calls)
    assert filters == original_filters
    assert [row.metadata["stable_chunk_id"] for row in probe.chunks] == ["shared", "unique-0", "unique-1", "unique-2", "unique-3"]


@pytest.mark.parametrize("mode,expected,failures", [("empty", "no_witness", 0), ("all-errors", "unavailable", 2), ("partial-empty", "incomplete", 1), ("partial-hit", "ok", 1)], ids=["empty", "all-errors", "partial-empty", "partial-hit"])
def test_gateway_partial_error_counts_and_raw_hits_remain_honest(tmp_path, mode, expected, failures):
    fixture = _fixture(tmp_path)
    requirements = EvidenceRequirementSet(tuple(EvidenceRequirement(f"q{index}", "exact_term", f"term_{index}") for index in range(2)))
    hit = _library_window("hit", "term_1 = enabled")
    responses = {}
    if mode != "empty":
        responses["term_0"] = RuntimeError("fixture query error")
    if mode == "all-errors":
        responses["term_1"] = RuntimeError("fixture query error")
    elif mode == "partial-hit":
        responses["term_1"] = [hit]
    store = _FiniteStore(responses)
    probe = _gateway(fixture.record, store).probe_library_requirements(fixture.record, requirements, missing_requirement_ids=["q0", "q1"], filters={"library_id": fixture.record.library_id})
    assert probe.status == expected and probe.failure_count == failures
    assert probe.queried_requirement_ids == ("q0", "q1")
    assert len(store.calls) == 2 and all(row[1:3] == (3, 60) for row in store.calls)
    assert len(probe.chunks) == int(mode == "partial-hit")


def test_gateway_nonqueryable_scope_is_not_an_absence_claim(tmp_path):
    fixture = _fixture(tmp_path)
    requirements = EvidenceRequirementSet((EvidenceRequirement("scope", "exact_version", "1"),))
    probe = fixture.gateway.probe_library_requirements(fixture.record, requirements, missing_requirement_ids=["scope"], filters={"library_id": fixture.record.library_id})
    assert probe.status == "not_applicable"
    assert not probe.queried_requirement_ids and not probe.chunks and not fixture.store.calls
