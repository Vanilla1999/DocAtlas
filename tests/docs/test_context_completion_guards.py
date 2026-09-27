"""Bounds, inspection trust and preservation controls for the follow-up repair."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from docmancer.docs.domain.query_script_runs import mixed_script_phrases
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.query_block_recovery import select_query_block_recovery
from docmancer.docs.application.inspection_recovery_seeds import inspection_recovery_seeds
from docmancer.docs.application.context_packet_labels import compact_section_labels
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from eval.evidence_quality_v2.run import load_protocol, documents_for, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call


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


def test_new_hints_do_not_change_original_constraints_or_optional_cap():
    question = "Как resource cache не удаляет `CACHE_DIR`, если event stream остановлен?"
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].text == question
    hints = [q for q in plan.queries if q.text in mixed_script_phrases(question)]
    assert hints
    assert all(q.coverage_required is False and q.public_parent_query_id is None for q in hints)
    assert sum(q.query_id.startswith(("query-hint-", "query-concept-", "query-relation-", "query-component-"))
               for q in plan.queries) <= 4


@pytest.fixture
def empty_seed(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c["id"] == "typer-05")
    root = tmp_path / "project"
    write_project(root, documents_for("typer", manifest))
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        with patch("docmancer.docs.application.query_block_recovery.select_query_block_recovery",
                   side_effect=lambda p, s, r, **kw: (p, s)):
            _, trace = observe_call(service, {"question": case["question"], "project_path": str(root), "scope": "all"})
    first = trace["stages"]["projector_outputs"][0]["payload"]
    return first, trace["snapshot"], trace["stages"]["projector_inputs"][0], root


def test_empty_packet_only_gains_inspection_not_support_or_source_quotes(empty_seed):
    p, s, r, _ = empty_seed
    before = deepcopy((p, s))
    out, bound = select_query_block_recovery(p, s, deepcopy(r), max_tokens=800)
    assert out["read_next"]
    assert not out.get("sources")
    assert out["status"] == "insufficient_evidence"
    assert out["support_status"] == "insufficient_evidence"
    assert out["answer_supported"] is False and out["edit_ready"] is False
    assert docs_context_budget_tokens(out) <= 300
    assert out["read_next"][0]["line_end"] - out["read_next"][0]["line_start"] < 40
    assert "__read_next__" in bound
    assert (p, s) == before


@pytest.mark.parametrize("field,value", [
    ("project_identity", "foreign"), ("generation_id", "old"),
    ("resolved_version", "wrong"), ("_source_snapshot_sha256", "sha256:" + "0" * 64),
    ("path", "docs/elsewhere.md"), ("stale", True),
    ("risk_flags", ["untrusted_instruction"]), ("lifecycle_status", "deprecated"),
])
def test_invalid_hint_source_never_issues_inspection(empty_seed, field, value):
    p, s, r, _ = deepcopy(empty_seed)
    for source in r["context_pack"]:
        source[field] = value
    out, _ = select_query_block_recovery(p, s, r, max_tokens=800)
    assert out == p


@pytest.mark.parametrize("damage", ["raw", "missing", "scope", "false_qualified", "parent", "not_verbatim", "hard_stop"])
def test_snapshot_and_hint_contracts_fail_closed(empty_seed, damage):
    p, s, r, _ = deepcopy(empty_seed)
    for source in r["context_pack"]:
        if damage == "raw": source["_reference_evidence"]["raw_document"] += "changed"
        elif damage == "missing": source.pop("_reference_evidence", None)
        elif damage == "scope": source["_reference_evidence"]["source"]["scope"]["snapshot_id"] = "elsewhere"
        elif damage == "false_qualified":
            for match in source["retrieval_query_matches"].values():
                match.update(query_text="nonexistent zebrawidget", query_terms=["nonexistent", "zebrawidget"], qualified=True)
    for q in r["documentation_query_plan"]["queries"]:
        if q.get("origin") == "retrieval_hint":
            if damage == "parent": q["public_parent_query_id"] = "query-original"
            elif damage in {"not_verbatim", "false_qualified"}: q["text"] = "nonexistent zebrawidget"
    if damage == "hard_stop": r["hard_stop"] = True
    assert select_query_block_recovery(p, s, r, max_tokens=800)[0] == p


def test_added_range_rechecks_policy_and_is_not_a_whole_document_grant(empty_seed):
    p, s, r, _ = deepcopy(empty_seed)
    for source in r["context_pack"]:
        for match in source["retrieval_query_matches"].values():
            match["forbidden_evidence_terms"] = ["To do that", "preceding space", "separated by"]
    out, bound = select_query_block_recovery(p, s, r, max_tokens=800)
    if out["read_next"]:
        raw = bound["__read_next__"]["source"]["_reference_evidence"]["raw_document"]
        t = out["read_next"][0]
        text = "\n".join(raw.splitlines()[t["line_start"]-1:t["line_end"]])
        assert not any(term.casefold() in text.casefold() for term in ["To do that", "preceding space", "separated by"])


def test_existing_requested_part_target_is_not_replaced(empty_seed):
    p, s, r, _ = deepcopy(empty_seed)
    p["read_next"] = [{"reason": "requested_part_missing", "source_uri": "docatlas://source/committed"}]
    assert select_query_block_recovery(p, s, r, max_tokens=800) == (p, s)


@pytest.mark.parametrize("condition", ["host", "checked", "answer", "too_small", "exact_path"])
def test_noninspection_contracts_unchanged(empty_seed, condition):
    p, s, r, _ = deepcopy(empty_seed)
    budget = 800
    if condition == "host": r["documentation_query_plan"]["queries"].append({"origin": "host_lookup"})
    elif condition == "checked": p["context_quality"] = {"status": "checked"}
    elif condition == "answer": p["answer_supported"] = True
    elif condition == "too_small": budget = 1
    else: r["documentation_query_plan"]["explicit_paths"] = ["docs/another.md"]
    assert select_query_block_recovery(p, s, r, max_tokens=budget) == (p, s)


def test_trial_reads_no_files_and_registers_no_resources(empty_seed, monkeypatch):
    from docmancer.docs.application.source_continuation import SourceContinuationReader
    p, s, r, _ = deepcopy(empty_seed)
    def forbidden(*a, **kw):
        raise AssertionError("trial performed I/O or registered resources")
    for method in ("issue", "issue_range"):
        monkeypatch.setattr(SourceContinuationReader, method, forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    out, _ = select_query_block_recovery(p, s, r, max_tokens=800)
    assert out["read_next"]
