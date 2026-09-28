"""Generic ranking, canonical range, policy and resource-budget controls."""
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path

import pytest
from docmancer.docs.application.query_block_context import ranked_blocks, select_query_block_context
from docmancer.docs.application.joint_context_lineage import retained_seed_mapping
from eval.evidence_quality_v2.run import load_protocol, documents_for, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call


def test_document_body_terms_are_not_truncated_to_query_term_limit():
    raw = "# Guide\n\n## Details\n\n" + " ".join(f"marker{x}" for x in range(50)) + " alpha_symbol persists.\n"
    result = ranked_blocks(raw, "document", "What is alpha_symbol?")
    assert result and "alpha_symbol" in raw[result[0][1]:result[0][2]]


@pytest.mark.parametrize("subject", ["Coordinate", "Envelope", "DispatchMode"])
def test_explicit_subject_heading_selects_its_own_first_prose(subject):
    raw = (f"# Widget Reference\n\n## Diagnostics\n\nWidget {subject} diagnostics are diagnostic.\n\n"
           f"## {subject}\n\nA {subject} contains an axis, a unit, and a frame.\n\n"
           f"## Examples\n\nA {subject} example is shown below.\n")
    result = ranked_blocks(raw, "document", f"What does a {subject} contain in Widget?")
    assert "an axis, a unit, and a frame" in raw[result[0][1]:result[0][2]]


def test_metadata_only_match_is_not_a_candidate():
    assert ranked_blocks("# Manual\n\n## alpha_symbol\n\nCompletely unrelated material.\n", "document", "alpha_symbol") == []


def test_heading_inside_code_is_not_a_subject_lead():
    rows = ranked_blocks("# Manual\n\n```text\n## alpha_symbol\nalpha_symbol text\n```\n", "document", "alpha_symbol")
    assert not any(rank[0] for rank, *_ in rows)


def test_oversized_block_inventory_abstains_instead_of_silently_truncating():
    raw = "# Manual\n\n" + "\n\n".join("alpha_symbol content." for _ in range(257))
    assert ranked_blocks(raw, "document", "alpha_symbol") == []


@pytest.fixture
def seed(tmp_path):
    _, _, manifest = load_protocol()
    project = tmp_path / "project"
    write_project(project, documents_for("fastapi", manifest))
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, project)
        with patch("docmancer.docs.application.query_block_context.select_query_block_context",
                   side_effect=lambda p, s, r, **kw: (p, s)):
            payload, trace = observe_call(service, {
                "question": "Из каких компонентов состоит origin в CORS?",
                "project_path": str(project), "scope": "all",
            })
    return payload, trace["snapshot"], trace["stages"]["projector_inputs"][0], project


def test_supplement_never_invents_coverage_or_mutates_input(seed):
    payload, snapshot, retrieval, project = seed
    before = deepcopy((payload, snapshot))
    out, bound = select_query_block_context(payload, snapshot, deepcopy(retrieval), max_tokens=800)
    assert (payload, snapshot) == before
    assert retained_seed_mapping(payload, snapshot, out, bound)
    for field in ("covered_query_ids", "missing_query_ids", "answer_supported", "edit_ready"):
        assert out[field] == payload[field]
    assert audit_payload(out, bound, project) == []


@pytest.mark.parametrize("field,value", [
    ("project_identity", "other"), ("generation_id", "old"), ("resolved_version", "wrong"),
    ("_source_snapshot_sha256", "sha256:" + "0" * 64), ("path", "other.md"),
    ("stale", True), ("risk_flags", ["untrusted_instruction"]), ("lifecycle_status", "deprecated"),
])
def test_bad_source_cannot_supply_a_supplement(seed, field, value):
    payload, snapshot, retrieval, _ = seed
    changed = deepcopy(snapshot)
    for row in payload["sources"]:
        changed[row["evidence_id"]]["source"][field] = value
    assert select_query_block_context(payload, changed, deepcopy(retrieval), max_tokens=800)[0] == payload


@pytest.mark.parametrize("damage", ["raw", "digest", "missing", "scope", "oversize"])
def test_invalid_reference_cannot_supply_a_supplement(seed, damage):
    payload, snapshot, retrieval, _ = seed
    changed = deepcopy(snapshot)
    for row in payload["sources"]:
        original = changed[row["evidence_id"]]["source"]
        ref = original["_reference_evidence"]
        if damage == "raw": ref["raw_document"] += " changed"
        elif damage == "digest": ref["source"]["content_sha256"] = "0" * 64
        elif damage == "scope": ref["source"]["scope"]["snapshot_id"] = "other"
        elif damage == "oversize": ref["raw_document"] = "x" * 262145
        else: original.pop("_reference_evidence")
    assert select_query_block_context(payload, changed, deepcopy(retrieval), max_tokens=800)[0] == payload


def test_new_text_rechecks_inherited_forbidden_terms(seed):
    payload, snapshot, retrieval, _ = seed
    changed = deepcopy(snapshot)
    for row in payload["sources"]:
        for match in changed[row["evidence_id"]]["source"]["retrieval_query_matches"].values():
            match["forbidden_evidence_terms"] = ["localhost.tiangolo.com"]
    out, _ = select_query_block_context(payload, changed, deepcopy(retrieval), max_tokens=800)
    assert all("localhost.tiangolo.com" not in s["snippet"] for s in out["sources"])


def test_evaluating_candidates_reads_no_files_or_registers_no_resources(seed, monkeypatch):
    from docmancer.docs.application.source_continuation import SourceContinuationReader
    payload, snapshot, retrieval, _ = seed
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate-time I/O or resource registration")
    monkeypatch.setattr(SourceContinuationReader, "issue", forbidden)
    monkeypatch.setattr(SourceContinuationReader, "issue_range", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    select_query_block_context(payload, snapshot, deepcopy(retrieval), max_tokens=800)


@pytest.mark.parametrize("mode", ["host", "checked", "empty", "answer"])
def test_other_contracts_are_unchanged(seed, mode):
    payload, snapshot, retrieval, _ = deepcopy(seed)
    if mode == "host": retrieval["documentation_query_plan"]["queries"].append({"origin": "host_lookup"})
    elif mode == "checked": payload["context_quality"] = {"status": "checked"}
    elif mode == "empty": payload["sources"] = []
    else: payload["answer_supported"] = True
    before = deepcopy((payload, snapshot))
    assert select_query_block_context(payload, snapshot, retrieval, max_tokens=800) == before


def test_adjacent_bridge_rebinds_without_a_fabricated_local_owner(seed):
    from docmancer.docs.application.query_block_bridge import bridge_options
    from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
    payload, snapshot, retrieval, _ = seed
    first = next(row for row in payload["sources"] if row["line_start"] == 1)
    original = snapshot[first["evidence_id"]]["source"]
    raw = original["_reference_evidence"]["raw_document"]
    rank, start, end, _ = ranked_blocks(raw, "document", retrieval["question"])[0]
    row, source = bridge_options(first, original, raw, start, end, retrieval)
    assert first["snippet"] in row["snippet"]
    assert source["_reference_evidence"]["owner"] is None
    assert prepare_reference_probe({}, candidate=source, evidence_text=row["snippet"])[1] is None
    assert row["line_start"] == 1 and row["line_end"] == 7


def test_bridge_refuses_to_skip_intervening_prose(seed):
    from docmancer.docs.application.query_block_bridge import bridge_options
    payload, snapshot, retrieval, _ = seed
    first = next(row for row in payload["sources"] if row["line_start"] == 1)
    original = snapshot[first["evidence_id"]]["source"]
    raw = original["_reference_evidence"]["raw_document"]
    start = raw.index("Any request with")
    end = raw.index("\n\n", start)
    from docmancer.docs.application import query_block_bridge
    with patch.object(query_block_bridge, "_context_row", wraps=query_block_bridge._context_row) as build:
        assert bridge_options(first, original, raw, start, end, retrieval) is None
    # No cross-prose candidate is even constructed; a later qualification
    # failure must not be what makes this boundary test pass.
    build.assert_not_called()


def test_literal_zero_budget_never_changes_the_packet(seed):
    payload, snapshot, retrieval, _ = seed
    assert select_query_block_context(payload, snapshot, retrieval, max_tokens=0) == (payload, snapshot)


def test_ranking_is_repeatable_with_different_document_identifiers():
    raw = "# Widget\n\n## Details\n\nWidget supports durable storage.\n\n## Storage\n\nStorage preserves pages.\n"
    a = ranked_blocks(raw, "first-id", "Widget storage")
    b = ranked_blocks(raw, "second-id", "Widget storage")
    assert [(score, start, end) for score, start, end, _ in a] == [(score, start, end) for score, start, end, _ in b]


@pytest.mark.parametrize("subject,other", [("QueueTasks", "OtherTasks"), ("BatchJobs", "SideJobs")])
def test_supplement_cannot_borrow_a_subject_from_a_sibling_section(tmp_path, subject, other):
    from tests.docs._global_evidence_fixtures import capture_fixture, visible
    raw = (f"# {subject}\n\n{subject} groups task functions.\n\n"
           f"## {other}\n\nTasks execute in order. If one raises an exception, later tasks stop.\n")
    cap = capture_fixture(tmp_path, {"tasks.md": raw},
        f"If one {subject} function raises an exception, what happens to later tasks?")
    assert "later tasks stop" not in visible(cap)


@pytest.mark.parametrize("subject", ["QueueTasks", "BatchJobs"])
def test_own_subject_warning_remains_usable(tmp_path, subject):
    from tests.docs._global_evidence_fixtures import capture_fixture, visible
    raw = (f"# {subject}\n\n{subject} groups task functions.\n\n"
           "Tasks execute in order. If one raises an exception, later tasks stop.\n")
    cap = capture_fixture(tmp_path, {"tasks.md": raw},
        f"If one {subject} function raises an exception, what happens to later tasks and their ordering?")
    assert "later tasks stop" in visible(cap)
