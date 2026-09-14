"""Final-surviving-evidence quality-state regressions."""
from __future__ import annotations

from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.context_selection import ContextSelectionDecision
from docmancer.docs.application.model_visible_projection import project_insufficient


def _source() -> dict:
    return {
        "evidence_id": "ev-1", "path_or_url": "docs/topic.md", "section": "Topic",
        "snippet": "Visible source-backed context.", "version_binding": "v1",
        "content_sha256": "a" * 64, "project_identity": "project:test",
        "line_start": 1, "line_end": 1, "authority": "source_of_truth", "scope": "project",
        "retrieval_query_matches": {"query-original": {"qualified": True}},
    }


def _decision(full: bool = True) -> ContextSelectionDecision:
    return ContextSelectionDecision(("ev-1",), ("query-original",) if full else (), () if full else ("query-original",))


def _plan(*, coverage=None, omissions=()):
    value = {
        "queries": [{"query_id": "query-original", "text": "Why does it work?", "origin": "original"}],
        "public_query_ids": ["query-original"],
        "_projection_omissions": list(omissions),
    }
    if coverage is not None:
        value["_component_coverage"] = coverage
    return value


def test_free_form_full_retrieval_stays_unverified():
    payload = _payload([_source()], decision=_decision(True), query_plan=_plan())
    assert payload["query_coverage"] == "full"
    assert payload["context_quality"] == {"status": "unverified", "reasons": ["coverage_unverified"]}
    assert payload["read_next"] == []


def test_known_missing_component_is_partial_and_budget_reason_is_scoped():
    coverage = {
        "mandatory_component_ids": ["a", "b"], "covered_component_ids": ["a"],
        "missing_component_ids": ["b"], "unresolved_residue": [], "status": "partial",
    }
    payload = _payload([_source()], decision=_decision(), query_plan=_plan(
        coverage=coverage,
        omissions=[{"reason": "token_budget", "component_ids": ["b"]}],
    ))
    assert payload["context_quality"] == {
        "status": "partial", "reasons": ["requested_part_missing", "budget_limited"]
    }


def test_unrelated_budget_rejection_does_not_degrade_checked_contract():
    coverage = {
        "mandatory_component_ids": ["a"], "covered_component_ids": ["a"],
        "missing_component_ids": [], "unresolved_residue": [], "status": "full",
    }
    payload = _payload([_source()], decision=_decision(), query_plan=_plan(
        coverage=coverage,
        omissions=[{"reason": "token_budget", "component_ids": ["unrelated"]}],
    ))
    assert payload["context_quality"] == {"status": "checked", "reasons": []}


def test_unresolved_residue_prevents_checked_even_with_full_component_contract():
    coverage = {
        "mandatory_component_ids": ["a"], "covered_component_ids": ["a"],
        "missing_component_ids": [], "unresolved_residue": ["why"], "status": "partial",
    }
    payload = _payload([_source()], decision=_decision(), query_plan=_plan(coverage=coverage))
    assert payload["context_quality"]["status"] == "unverified"
    assert "coverage_unverified" in payload["context_quality"]["reasons"]


def test_docs_context_insufficient_is_unavailable_not_checked():
    payload = project_insufficient(
        kind="docs_context", missing=["No safe source."], recommended_next_action=None,
    )
    assert payload["context_quality"]["status"] == "unavailable"
    assert payload["read_next"] == []
