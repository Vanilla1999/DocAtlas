"""Source-local witnesses and query lineage must survive projection, not guessing."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from docmancer.docs.application.context_selection import qualified_query_ids, visible_assignment_hashes
from docmancer.docs.application.docs_context_projection import _requalify_visible_source, project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def _boundary_source(reverse: bool, direct: bool = False):
    plan = build_documentation_query_plan(
        "Explain get_docs_context request flow.",
        lookup_queries=("What does the documentation request boundary accept?",),
    )
    parent = next(query for query in plan.queries if query.origin == "host_lookup")
    child = next(query for query in plan.queries if query.relation == "audited_rewrite"
                 and query.public_parent_query_id == parent.query_id)
    pairs = (child, parent) if reverse else (parent, child)
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(
        path="docs/api.md", heading_path="Boundary",
        content="get_docs_context(question, project_path, lookup_queries, module_path, scope) accepts scoped queries.",
        retrieval_query_matches={query.query_id: {
            "query_text": query.text, "relation": query.relation,
            "public_parent_query_id": query.public_parent_query_id,
            "parent_exact_terms": query.parent_exact_terms,
        } for query in pairs},
    )
    if direct:
        source["content"] += " The documentation request boundary accepts scoped input."
    return plan, parent.query_id, child.query_id, source


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("direct", [False, True])
def test_visible_requalification_merges_direct_and_derived_independent_of_order(reverse, direct):
    plan, parent, child, source = _boundary_source(reverse, direct)
    source.update(path_or_url=source["path"], snippet=source["content"])
    before = deepcopy(source)
    result = _requalify_visible_source(source, query_text={q.query_id: q.text for q in plan.queries})
    assert {parent, child} <= qualified_query_ids((result,))
    trace = result["retrieval_query_matches"][parent]
    assert set(trace["coverage_kinds"]) == ({"direct", "derived"} if direct else {"derived"})
    assert trace.get("coverage_kind", "direct") == ("direct" if direct else "derived")
    assert trace["derived_from_query_ids"] == [child]
    assert source == before


@pytest.mark.parametrize("reverse", [False, True])
def test_public_context_keeps_audited_host_coverage_after_trace_permutation(reverse):
    plan, parent, child, source = _boundary_source(reverse)
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": [source], "documentation_query_plan": plan.as_payload(),
    })
    assert parent in payload["covered_query_ids"]
    assert child not in payload["covered_query_ids"]
    assert "query-original" not in payload["covered_query_ids"]
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("reverse", [False, True])
def test_clipping_recomputes_lineage_instead_of_preserving_stale_derived_claims(reverse):
    parent, child = "query-lookup-1", "query-host-rewrite-1"
    pairs = [(parent, {"query_text": "amber", "relation": "host_lookup"}),
             (child, {"query_text": "violet", "relation": "audited_rewrite",
                      "public_parent_query_id": parent})]
    source = {"snippet": "Amber violet.", "path_or_url": "docs/colors.md",
              "retrieval_query_matches": dict(reversed(pairs) if reverse else pairs)}
    texts = {parent: "amber", child: "violet"}
    full = _requalify_visible_source(source, query_text=texts)
    clipped = _requalify_visible_source({**full, "snippet": "Amber."}, query_text=texts)
    trace = clipped["retrieval_query_matches"][parent]
    assert trace["qualified"] is True
    assert trace.get("coverage_kind", "direct") == "direct"
    assert trace.get("coverage_kinds", ["direct"]) == ["direct"]
    assert not trace.get("derived_from_query_ids") and not trace.get("derived_from_query_id")
    assert child not in qualified_query_ids((clipped,))


def _repeated_witness(absolute: bool, unicode: bool):
    witness = "КЛЮЧ сохраняет копии." if unicode else "ALPHA_KEY retains backups."
    raw = f"Before migration: {witness}\nAfter migration: {witness}"
    source = {"stable_id": "chunk-1", "content": raw, "char_start": 100, "line_start": 20}
    def assignment(occurrence: int):
        start = raw.index(witness) if occurrence == 0 else raw.rindex(witness)
        offset = source["char_start"] if absolute else 0
        prefix = "" if absolute else "unit_"
        return {"evidence_id": "chunk-1", "requirement_id": "backup-policy",
                f"{prefix}char_start": offset + start,
                f"{prefix}char_end": offset + start + len(witness),
                "projected_content_hash": sha256(witness.encode()).hexdigest()}
    return source, witness, assignment


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("unicode", [False, True])
def test_equal_text_at_another_offset_cannot_satisfy_the_selected_assignment(absolute, unicode):
    source, witness, assignment = _repeated_witness(absolute, unicode)
    projected = {"snippet": f"After migration: {witness}", "line_start": 21, "line_end": 21}
    assert visible_assignment_hashes(source, projected, (assignment(0),)) == ()
    assert visible_assignment_hashes(source, projected, (assignment(1),)) == (assignment(1)["projected_content_hash"],)


@pytest.mark.parametrize("line", [20, 21])
@pytest.mark.parametrize("occurrence", [0, 1])
def test_repeated_snippet_uses_source_lines_to_bind_one_actual_occurrence(line, occurrence):
    source, witness, assignment = _repeated_witness(False, False)
    projected = {"snippet": witness, "line_start": line, "line_end": line}
    expected = (assignment(occurrence)["projected_content_hash"],) if line == 20 + occurrence else ()
    assert visible_assignment_hashes(source, projected, (assignment(occurrence),)) == expected


@pytest.mark.parametrize("lines", [{}, {"line_start": 999, "line_end": 999},
                                    {"line_start": 20, "line_end": 21}])
def test_ambiguous_or_inconsistent_visible_span_cannot_claim_an_assignment(lines):
    source, witness, assignment = _repeated_witness(False, False)
    assert visible_assignment_hashes(source, {"snippet": witness, **lines}, (assignment(0),)) == ()


def test_unique_visible_span_can_bind_without_optional_line_metadata():
    source, witness, assignment = _repeated_witness(False, False)
    projected = {"snippet": f"After migration: {witness}"}
    assert visible_assignment_hashes(source, projected, (assignment(0),)) == ()
    assert visible_assignment_hashes(source, projected, (assignment(1),)) == (assignment(1)["projected_content_hash"],)


@pytest.mark.parametrize("change", [{"evidence_id": "foreign"}, {"projected_content_hash": "0" * 64},
                                     {"unit_char_start": -1}, {"unit_char_end": 9999}])
def test_invalid_assignment_identity_hash_or_offsets_still_fail_closed(change):
    source, witness, assignment = _repeated_witness(False, False)
    projected = {"snippet": source["content"], "line_start": 20, "line_end": 21}
    assert visible_assignment_hashes(source, projected, ({**assignment(0), **change},)) == ()
