"""Assignment visibility is source/offset-bound, not a text-hash equivalence class."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from docmancer.docs.application.context_selection import (
    component_coverage_decision, visible_assignment_hashes,
)
from docmancer.docs.application.docs_context_projection import (
    _expand_selected_snippets, _qualified_fragments, project_docs_context,
)
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection


WITNESS = "ALPHA_KEY retains backups."


def _source(content, identity="chunk-1"):
    return {
        "stable_id": identity, "source_class": "project_doc", "content": content,
        "path": "docs/backup.md", "project_identity": "git:example/project",
        "lifecycle_status": "active", "freshness": "current",
        "index_freshness": "synchronized", "risk_flags": [],
        "line_start": 1, "char_start": 100,
    }


def _assignment(requirement, source, start, *, absolute=False):
    offset, prefix = (source["char_start"], "") if absolute else (0, "unit_")
    return {
        "requirement_id": requirement, "evidence_id": source["stable_id"],
        "projected_content_hash": sha256(WITNESS.encode()).hexdigest(),
        f"{prefix}char_start": offset + start,
        f"{prefix}char_end": offset + start + len(WITNESS),
    }


def _case(*, foreign=False, absolute=False):
    raw = "Earlier: " + WITNESS + "\n\n" + "Unrelated padding. " * 80 + "\n\nCurrent: " + WITNESS
    source = _source(raw)
    earlier = _source(raw, "chunk-other") if foreign else source
    assignments = (
        _assignment("earlier", earlier, 9, absolute=absolute),
        _assignment("current", source, raw.rindex(WITNESS), absolute=absolute),
    )
    query = "Current ALPHA_KEY"
    source["retrieval_query_matches"] = {
        "query-original": {"query_text": query},
        "query-lookup-1": {"query_text": query},
    }
    plan = {
        "original_question": query,
        "query_ids": ["query-original", "query-lookup-1"],
        "public_query_ids": ["query-original", "query-lookup-1"],
        "queries": [
            {"query_id": "query-original", "text": query, "origin": "original",
             "requirement_id": "current", "facet_id": "current-facet"},
            {"query_id": "query-lookup-1", "text": query, "origin": "host_lookup",
             "requirement_id": "earlier", "facet_id": "earlier-facet"},
        ],
        "_component_contract": [{"component_id": "earlier"}, {"component_id": "current"}],
    }
    return source, assignments, plan


@pytest.mark.parametrize("foreign", [False, True])
@pytest.mark.parametrize("absolute", [False, True])
def test_equal_hash_cannot_cover_an_invisible_assignment_in_component_accounting(foreign, absolute):
    source, assignments, plan = _case(foreign=foreign, absolute=absolute)
    projected = {
        "evidence_id": "ev-visible", "snippet": "Current: " + WITNESS,
        "line_start": 5, "line_end": 5, "_qualification_candidate": source,
        "_visible_assignment_hashes": [assignments[1]["projected_content_hash"]],
    }
    before = deepcopy((source, assignments, projected))
    decision = component_coverage_decision(plan["_component_contract"], assignments, (projected,))
    assert decision.covered_component_ids == ("current",)
    assert decision.missing_component_ids == ("earlier",)
    assert decision.status == "partial"
    assert (source, assignments, projected) == before


@pytest.mark.parametrize("foreign", [False, True])
@pytest.mark.parametrize("absolute", [False, True])
def test_public_projection_does_not_recover_missing_requirements_by_equal_text(foreign, absolute):
    source, assignments, plan = _case(foreign=foreign, absolute=absolute)
    diagnostics = {}
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": [source], "documentation_query_plan": plan,
        "selection_decision": {"assignments": assignments},
    }, selection_diagnostics=diagnostics)
    assert any("Current:" in item["snippet"] for item in payload["sources"])
    assert all("Earlier:" not in item["snippet"] for item in payload["sources"])
    assert diagnostics["component_coverage"]["covered_component_ids"] == ["current"]
    assert diagnostics["component_coverage"]["status"] == "partial"
    facets = {item["id"]: item for item in payload["facets"]}
    assert facets["current-facet"]["status"] == "covered"
    assert facets["earlier-facet"]["status"] == "retrieval_only"
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("absolute", [False, True])
def test_fragment_requirements_keep_the_selected_occurrence_identity(absolute):
    source, assignments, plan = _case(absolute=absolute)
    normalized = {
        **source, "path_or_url": source["path"], "evidence_id": "ev-visible",
        "_qualification_candidate": source, "_assigned_requirement_ids": ["earlier", "current"],
    }
    variants = _qualified_fragments(
        normalized, raw_snippet=source["content"], query_ids={"query-original"},
        query_text={"query-original": plan["original_question"]},
        source_line_start=1, assignments=assignments,
    )
    current = [item for item in variants if "Current:" in item["snippet"]]
    assert current
    assert all(item["_assigned_requirement_ids"] == ["current"] for item in current)


def test_same_occurrence_may_support_two_independently_assigned_requirements():
    source = _source(WITNESS)
    assignments = tuple(_assignment(name, source, 0) for name in ("backup", "retention"))
    projected = {"evidence_id": "ev-visible", "snippet": WITNESS,
                 "_qualification_candidate": source,
                 "_visible_assignment_hashes": [assignments[0]["projected_content_hash"]]}
    decision = component_coverage_decision(
        tuple({"component_id": name} for name in ("backup", "retention")),
        assignments, (projected,),
    )
    assert decision.covered_component_ids == ("backup", "retention")
    assert decision.status == "full"


@pytest.mark.parametrize("offsets", [{"unit_char_start": False, "unit_char_end": True},
                                    {"char_start": False, "char_end": True}])
def test_boolean_offsets_are_not_character_coordinates(offsets):
    source = {"stable_id": "chunk-1", "content": "x", "char_start": 0}
    assignment = {"requirement_id": "x", "evidence_id": "chunk-1",
                  "projected_content_hash": sha256(b"x").hexdigest(), **offsets}
    assert visible_assignment_hashes(source, {"snippet": "x"}, (assignment,)) == ()


def test_expansion_cannot_swap_assignments_that_have_the_same_text_hash():
    source, assignments, _ = _case()
    visible = {
        **source, "evidence_id": "ev-visible", "path_or_url": source["path"],
        "snippet": "Earlier: " + WITNESS, "line_start": 1, "line_end": 1,
        "retrieval_query_matches": {"query-original": {
            "query_text": "ALPHA_KEY retains", "qualified": True}},
        "_qualification_candidate": source, "_assigned_requirement_ids": ["earlier"],
        "_visible_assignment_hashes": [assignments[0]["projected_content_hash"]],
    }
    expanded = _expand_selected_snippets(
        [visible], projection_inputs={"ev-visible": (source["content"], ("Current ALPHA_KEY",), 1)},
        query_plan={"queries": [{"query_id": "query-original", "text": "ALPHA_KEY retains"}]},
        public_query_ids=("query-original",), max_tokens=800, assignments=assignments,
    )
    assert expanded[0]["snippet"] == visible["snippet"]
    assert visible_assignment_hashes(source, expanded[0], (assignments[0],))


@pytest.mark.parametrize("forged", [[], ["stale"], [sha256(WITNESS.encode()).hexdigest()]])
def test_cached_hashes_alone_are_never_assignment_provenance(forged):
    source = _source(WITNESS)
    assignment = _assignment("backup", source, 0)
    decision = component_coverage_decision(
        ({"component_id": "backup"},), (assignment,),
        ({"evidence_id": "ev-public", "_visible_assignment_hashes": forged},),
    )
    assert decision.status == "unavailable"
