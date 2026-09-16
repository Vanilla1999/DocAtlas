from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
from docmancer.docs.application._project_docs_service_part03 import (
    _merge_same_atom_continuations,
    _qualify_same_atom_continuations,
)


def _cross_atom_list_chunks(next_text="documentary claim unproved. Stop before an edit when hard_stop=true.\n6. Next independent rule."):
    common = {
        "parent_logical_id": "parent-1",
        "project_identity": "project:test",
        "source_class": "project_file",
        "atom_type": "list",
    }
    return [
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=4,
            text="5. If evidence is insufficient, continue locally with source/tests while keeping the ",
            score=2,
            metadata={
                **common, "atom_id": "atom-left", "stable_chunk_id": "child-left",
                "char_span": [100, 181],
                "retrieval_query_matches": {"query-intent-1": {
                    "qualified": True, "relation": "host_lookup",
                }},
                "retrieval_query_ids": ("query-intent-1",),
            },
        ),
        RetrievedChunk(
            source="docs/workflow.md", chunk_index=5, text=next_text, score=1,
            metadata={
                **common, "atom_id": "atom-right", "stable_chunk_id": "child-right",
                "char_span": [181, 181 + len(next_text)],
                "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                "retrieval_query_ids": (),
            },
        ),
    ]


def test_cross_atom_list_fragment_continues_current_item_when_next_chunk_has_no_marker():
    rows = _qualify_same_atom_continuations(_cross_atom_list_chunks(), "query-intent-1")
    trace = rows[1].metadata["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "same_list_item_continuation"
    assert trace["coverage_kind"] == "derived"


def test_cross_atom_list_fragment_reassembles_for_projection_without_changing_cap():
    qualified = _qualify_same_atom_continuations(_cross_atom_list_chunks(), "query-intent-1")
    rows = _merge_same_atom_continuations(qualified, "query-intent-1")
    assert len(rows) == 1
    assert "documentary claim unproved" in rows[0].text
    assert "hard_stop=true" in rows[0].text
    assert "6. Next independent rule." in rows[0].text
    assert rows[0].metadata["reassembled_from_stable_chunk_ids"] == ["child-left", "child-right"]


def test_cross_atom_list_bridge_never_starts_at_a_new_list_marker():
    rows = _qualify_same_atom_continuations(
        _cross_atom_list_chunks("6. Next independent rule."), "query-intent-1"
    )
    trace = rows[1].metadata["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert len(_merge_same_atom_continuations(rows, "query-intent-1")) == 2


def test_cross_atom_list_continuation_still_rechecks_source_policy():
    source = {
        "path_or_url": "docs/workflow.md", "section": "Workflow",
        "snippet": "documentary claim unproved. Stop before unsafe edits.",
        "catalog_role": "runbook",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "relation": "host_lookup",
            "qualification_route": "same_list_item_continuation",
            "coverage_kind": "derived", "coverage_kinds": ["derived"],
            "query_text": "insufficient evidence documentation workflow",
        }},
        "retrieval_query_ids": ["query-intent-1"],
        "_independent_query_plan": {"queries": [{
            "query_id": "query-intent-1", "text": "insufficient evidence documentation workflow",
            "origin": "canonical_intent",
        }]},
        "_qualification_candidate": {
            "project_identity": "project:other", "source_class": "project_doc",
            "freshness": "current", "index_freshness": "synchronized",
            "risk_flags": [], "lifecycle_status": "active",
        },
        "_expected_project_identity": "project:test",
        "_lifecycle_intent": "current",
    }
    visible = _requalify_visible_source(source, query_text={
        "query-original": "What should the agent do if evidence is insufficient?",
        "query-intent-1": "insufficient evidence documentation workflow",
    })
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert trace["qualification_reason"] == "wrong_project_identity"
