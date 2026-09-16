from __future__ import annotations

import pytest

from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


def _continuation_source(**candidate_overrides):
    candidate = {
        "project_identity": "project:test",
        "source_class": "project_doc",
        "freshness": "current",
        "index_freshness": "synchronized",
        "risk_flags": [],
        "lifecycle_status": "active",
    }
    candidate.update(candidate_overrides)
    return {
        "path_or_url": "docs/workflow.md",
        "section": "Workflow",
        "snippet": "continue locally while keeping the documentary claim unproved.",
        "catalog_role": "runbook",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True,
            "relation": "host_lookup",
            "qualification_route": "same_atom_continuation",
            "coverage_kind": "derived",
            "coverage_kinds": ["derived"],
            "query_text": "insufficient evidence documentation workflow",
        }},
        "retrieval_query_ids": ["query-intent-1"],
        "_independent_query_plan": {"queries": [{
            "query_id": "query-intent-1",
            "text": "insufficient evidence documentation workflow",
            "origin": "canonical_intent",
        }]},
        "_qualification_candidate": candidate,
        "_expected_project_identity": "project:test",
        "_lifecycle_intent": "current",
    }


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"project_identity": "project:other"}, "wrong_project_identity"),
    ({"stale": True}, "stale_evidence"),
    ({"index_freshness": "stale"}, "unsynchronized_index"),
    ({"risk_flags": ["untrusted"]}, "unsafe_evidence"),
    ({"lifecycle_status": "superseded"}, "lifecycle_not_allowed"),
])
def test_same_atom_continuation_rechecks_source_eligibility(overrides, reason):
    visible = _requalify_visible_source(
        _continuation_source(**overrides),
        query_text={
            "query-original": "What should the agent do if evidence is insufficient?",
            "query-intent-1": "insufficient evidence documentation workflow",
        },
    )
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert trace["qualification_reason"] == reason
    assert "query-intent-1" not in visible["retrieval_query_ids"]


def test_safe_same_atom_continuation_still_survives_without_lexical_rematch():
    visible = _requalify_visible_source(
        _continuation_source(),
        query_text={
            "query-original": "What should the agent do if evidence is insufficient?",
            "query-intent-1": "insufficient evidence documentation workflow",
        },
    )
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "same_atom_continuation"
    assert trace["coverage_kind"] == "derived"
    assert "query-original" not in visible["retrieval_query_ids"]


@pytest.mark.parametrize("condition", [
    "and the disk is full",
    "and the worktree is dirty",
    "and credentials are missing",
    "and a second repository has stale documentation",
])
def test_conditional_host_lookup_cannot_drop_an_additional_condition(condition):
    question = f"What should I do if project documentation is stale {condition}?"
    plan = build_documentation_query_plan(
        question,
        lookup_queries=("How do I diagnose stale documentation?",),
    )
    host = next(row for row in plan.queries if row.query_id == "query-lookup-1")
    assert host.relation == "host_lookup"
    assert host.public_parent_query_id is None


def test_reviewed_nonconditional_host_rewrite_still_derives_original_lineage():
    plan = build_documentation_query_plan(
        "Где хранится индекс и как он изолирован для каждого проекта?",
        lookup_queries=("project documentation storage index isolation",),
    )
    host = next(row for row in plan.queries if row.query_id == "query-lookup-1")
    assert host.relation == "audited_rewrite"
    assert host.public_parent_query_id == "query-original"
