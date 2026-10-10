"""Bounds, inspection trust and preservation controls for the follow-up repair."""
from copy import deepcopy
from pathlib import Path

import pytest

from docmancer.docs.domain.query_script_runs import mixed_script_phrases
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.query_block_recovery import select_query_block_recovery
from docmancer.docs.application.inspection_recovery_seeds import inspection_recovery_seeds
from docmancer.docs.application.source_continuation import SourceContinuationReader, _read_next_row
from eval.evidence_quality_v2.run import load_protocol, documents_for
from tests.docs._current_source_guard_fixtures import (
    capture_source_case, source_binding, canonical_range, assert_visible_fact,
)

SOURCE_PATH = "docs/tutorial/parameter-types/bool.md"
FACTS = ("Have in mind that it's a string with a preceding space and then a `/`.",
         'So, it\'s `" /-S"` not `"/-S"`.')


@pytest.mark.parametrize("question,expected", [
    ("Как работает resource cache?", ("resource cache",)),
    ("Как устроен resource\tcache?", ("resource\tcache",)),
    ("缓存 resource cache 如何工作？", ("resource cache",)),
    ("Wie arbeitet der resource cache?", ()),
    ("Как устроен cache?", ()),
    ("Только русские слова.", ()),
    ("Как resource и cache связаны?", ()),
    ("Как cаche field работает?", ()),  # Cyrillic a inside an identifier
    ("Как resource cache / resource cache?", ("resource cache",)),
    ("Как resource cache, event stream, result store?", ("resource cache", "event stream")),
    ("Как " + "a" * 180 + " cache?", ()),
    ("Как resource cache?" + "x" * 5000, ()),
])
def test_script_runs_are_verbatim_bounded_not_translations(question, expected):
    assert mixed_script_phrases(question) == expected
    assert all(text in question for text in expected)


def test_literal_script_runs_do_not_become_implicit_queries_or_permissions():
    question = "Как resource cache не удаляет `CACHE_DIR`, если event stream остановлен?"
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].text == question
    assert [(q.query_id, q.origin, q.text, q.public_parent_query_id) for q in plan.queries] == [
        ("query-original", "original", question, None)]
    assert not plan.component_contract and plan.component_scope_complete is False


@pytest.fixture
def source_seed(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c["id"] == "typer-05")
    documents = documents_for("typer", manifest)
    cap = capture_source_case(tmp_path, documents, case["question"], lookups=("preceding space",), scope="all")
    for fact in FACTS:
        assert_visible_fact(cap, SOURCE_PATH, fact)
    public, source, attempt = source_binding(cap, SOURCE_PATH, FACTS[0])
    raw = documents[SOURCE_PATH]
    start, end = raw.index(FACTS[0]), raw.index(FACTS[-1]) + len(FACTS[-1])
    assert canonical_range(public, source, start, end) is not None
    return {"capture": cap, "public": public, "source": source, "attempt": attempt,
            "question": case["question"], "start": start, "end": end}


def original_empty_request(seed):
    # An explicit unit input, not a claimed public delivery or synthesized hint.
    payload = {"kind": "docs_context", "status": "insufficient_evidence", "sources": [],
               "support_status": "insufficient_evidence", "answer_supported": False,
               "answer_available": False, "edit_ready": False, "read_next": []}
    retrieval = {"question": seed["question"], "project_identity": seed["public"]["project_identity"],
                 "_source_continuation_project_root": str(seed["capture"]["fixture_project"]),
                 "documentation_query_plan": build_documentation_query_plan(seed["question"]).as_payload(),
                 "context_pack": [deepcopy(seed["source"])]}
    return payload, {}, retrieval


def test_original_prose_cannot_mint_inspection_or_answer_permission(source_seed):
    p, s, r = original_empty_request(source_seed)
    before = deepcopy((p, s))
    assert inspection_recovery_seeds(r) == []
    assert select_query_block_recovery(p, s, r, max_tokens=None) == before


@pytest.mark.parametrize("damage", ["false_qualified", "parent", "not_verbatim", "hard_stop"])
def test_injected_legacy_hint_has_no_current_query_authority(source_seed, damage):
    p, s, r = original_empty_request(source_seed)
    hint = {"query_id": "query-hint-1", "origin": "retrieval_hint", "text": "boolean option",
            "coverage_required": False, "public_parent_query_id": None}
    if damage == "parent": hint["public_parent_query_id"] = "query-original"
    if damage == "not_verbatim": hint["text"] = "nonexistent zebrawidget"
    r["documentation_query_plan"]["queries"].append(hint)
    r["context_pack"][0]["retrieval_query_matches"][hint["query_id"]] = {
        "qualified": True, "query_text": hint["text"], "query_origin": "retrieval_hint"}
    if damage == "hard_stop": r["hard_stop"] = True
    assert inspection_recovery_seeds(r) == []
    assert select_query_block_recovery(p, s, r, max_tokens=None) == (p, s)


def test_exact_inspection_range_keeps_both_facts_and_rechecks_policy(source_seed):
    row, source = canonical_range(source_seed["public"], source_seed["source"],
                                  source_seed["start"], source_seed["end"])
    assert all(fact in row["snippet"] for fact in FACTS)
    assert row["line_end"] - row["line_start"] + 1 <= SourceContinuationReader.max_lines
    target = _read_next_row(str(source_seed["capture"]["fixture_project"]), source,
                           line_start=row["line_start"], line_end=row["line_end"], reason="inspect_source_context")
    assert target is not None
    assert (target["line_start"], target["line_end"]) == (row["line_start"], row["line_end"])
    assert target["path"] == SOURCE_PATH
    assert source["retrieval_query_matches"] == {} and source["_assigned_requirement_ids"] == []
    changed = deepcopy(source_seed["source"])
    assert changed["retrieval_query_matches"]
    for match in changed["retrieval_query_matches"].values():
        match["forbidden_evidence_terms"] = ["To do that", "preceding space", "separated by"]
    assert canonical_range(source_seed["public"], changed, source_seed["start"], source_seed["end"]) is None


def test_existing_requested_part_target_is_not_replaced(source_seed):
    p, s, r = original_empty_request(source_seed)
    p["read_next"] = [{"reason": "requested_part_missing", "source_uri": "docatlas://source/committed"}]
    assert select_query_block_recovery(p, s, r, max_tokens=None) == (p, s)


def test_explicit_lookup_is_not_removed_to_enable_implicit_inspection(source_seed):
    attempt = deepcopy(source_seed["attempt"])
    p, s, r = attempt["projected_payload"], attempt["snapshot"], attempt["before_projection"]
    assert any(q["origin"] == "host_lookup" for q in r["documentation_query_plan"]["queries"])
    assert select_query_block_recovery(p, s, r, max_tokens=None) == (p, s)


def test_trial_reads_no_files_and_registers_no_resources(source_seed, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("trial performed I/O or registered resources")
    for method in ("issue", "issue_range"):
        monkeypatch.setattr(SourceContinuationReader, method, forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    row, source = canonical_range(source_seed["public"], source_seed["source"],
                                  source_seed["start"], source_seed["end"])
    assert _read_next_row(str(source_seed["capture"]["fixture_project"]), source,
                          line_start=row["line_start"], line_end=row["line_end"], reason="inspect_source_context")


def test_original_question_keeps_the_exact_negative_option_spelling(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c["id"] == "typer-05")
    cap = capture_source_case(tmp_path, documents_for("typer", manifest), case["question"], scope="all")
    for fact in FACTS:
        assert_visible_fact(cap, SOURCE_PATH, fact)
