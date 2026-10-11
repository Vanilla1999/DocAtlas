"""Generic ranking, canonical range, policy and resource-budget controls."""
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path

import pytest
from docmancer.docs.application.query_block_context import ranked_blocks, select_query_block_context
from docmancer.docs.application.joint_context_candidates import _verified_document
from eval.evidence_quality_v2.run import load_protocol, documents_for
from tests.docs._current_source_guard_fixtures import (
    capture_source_case, source_binding, canonical_range, assert_visible_fact,
)

QUESTION = "Из каких компонентов состоит origin в CORS?"
SOURCE_PATH = "docs/en/docs/tutorial/cors.md"
ORIGIN_FACT = ("An origin is the combination of protocol (`http`, `https`), domain "
               "(`myapp.com`, `localhost`, `localhost.tiangolo.com`), and port (`80`, `443`, `8080`).")




@pytest.fixture
def seed(tmp_path):
    _, _, manifest = load_protocol()
    documents = documents_for("fastapi", manifest)
    cap = capture_source_case(tmp_path, documents, QUESTION, lookups=(ORIGIN_FACT,), scope="all")
    public, source, attempt = source_binding(cap, SOURCE_PATH, ORIGIN_FACT)
    raw = documents[SOURCE_PATH]
    start = raw.index(ORIGIN_FACT)
    result = {"capture": cap, "public": public, "source": source, "attempt": attempt,
              "raw": raw, "start": start, "end": start + len(ORIGIN_FACT)}
    assert canonical_range(public, source, result["start"], result["end"]) is not None
    return result


def test_supplement_never_invents_coverage_or_mutates_input(seed):
    before = deepcopy(seed)
    row, source = canonical_range(seed["public"], seed["source"], seed["start"], seed["end"])
    assert seed == before
    assert row["snippet"] == ORIGIN_FACT
    assert source["retrieval_query_ids"] == []
    assert source["retrieval_query_matches"] == {}
    assert source["_assigned_requirement_ids"] == []
    assert row["project_identity"] == seed["public"]["project_identity"]




@pytest.mark.parametrize("field,value", [
    ("project_identity", "other"), ("generation_id", "old"), ("resolved_version", "wrong"),
    ("_source_snapshot_sha256", "sha256:" + "0" * 64), ("path", "other.md"),
    ("stale", True), ("lifecycle_status", "deprecated"),
])
def test_bad_source_cannot_supply_a_supplement(seed, field, value):
    changed = deepcopy(seed["source"])
    changed[field] = value
    assert canonical_range(seed["public"], changed, seed["start"], seed["end"]) is None


@pytest.mark.parametrize("damage", ["raw", "digest", "missing", "scope", "oversize"])
def test_invalid_reference_cannot_supply_a_supplement(seed, damage):
    original = deepcopy(seed["source"])
    ref = original["_reference_evidence"]
    if damage == "raw": ref["raw_document"] += " changed"
    elif damage == "digest": ref["source"]["content_sha256"] = "0" * 64
    elif damage == "scope": ref["source"]["scope"]["snapshot_id"] = "other"
    elif damage == "oversize": ref["raw_document"] = "x" * 262145
    else: original.pop("_reference_evidence")
    assert _verified_document(original, seed["public"]) is None


def test_new_text_rechecks_inherited_forbidden_terms(seed):
    changed = deepcopy(seed["source"])
    assert changed["retrieval_query_matches"]
    for match in changed["retrieval_query_matches"].values():
        match["forbidden_evidence_terms"] = ["localhost.tiangolo.com"]
    assert canonical_range(seed["public"], changed, seed["start"], seed["end"]) is None


def test_evaluating_candidates_reads_no_files_or_registers_no_resources(seed, monkeypatch):
    from docmancer.docs.application.source_continuation import SourceContinuationReader
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate-time I/O or resource registration")
    monkeypatch.setattr(SourceContinuationReader, "issue", forbidden)
    monkeypatch.setattr(SourceContinuationReader, "issue_range", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert canonical_range(seed["public"], seed["source"], seed["start"], seed["end"]) is not None


def test_explicit_host_lookup_is_not_silently_reinterpreted_for_supplements(seed):
    attempt = deepcopy(seed["attempt"])
    payload, snapshot, retrieval = attempt["projected_payload"], attempt["snapshot"], attempt["before_projection"]
    assert any(q["origin"] == "host_lookup" for q in retrieval["documentation_query_plan"]["queries"])
    before = deepcopy((payload, snapshot))
    assert select_query_block_context(payload, snapshot, retrieval, max_tokens=None) == before




def test_adjacent_bridge_rebinds_without_a_fabricated_local_owner(seed):
    from docmancer.docs.application.query_block_bridge import bridge_options
    from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
    raw = seed["raw"]
    first, original = canonical_range(seed["public"], seed["source"], 0, raw.index("\n\n## Origin"))
    result = bridge_options(first, original, raw, seed["start"], seed["end"], seed["attempt"]["before_projection"])
    assert result is not None
    row, source = result
    assert first["snippet"] in row["snippet"]
    assert source["_reference_evidence"]["owner"] is None
    assert prepare_reference_probe({}, candidate=source, evidence_text=row["snippet"])[1] is None
    assert row["line_start"] == 1 and row["line_end"] == 7


def test_bridge_refuses_to_skip_intervening_prose(seed):
    from docmancer.docs.application.query_block_bridge import bridge_options
    raw = seed["raw"]
    first, original = canonical_range(seed["public"], seed["source"], 0, raw.index("\n\n## Origin"))
    start = raw.index("Any request with")
    end = raw.index("\n\n", start)
    from docmancer.docs.application import query_block_bridge
    with patch.object(query_block_bridge, "_context_row", wraps=query_block_bridge._context_row) as build:
        assert bridge_options(first, original, raw, start, end, seed["attempt"]["before_projection"]) is None
    # No cross-prose candidate is even constructed; a later qualification
    # failure must not be what makes this boundary test pass.
    build.assert_not_called()




@pytest.mark.parametrize("subject", ["QueueTasks", "BatchJobs"])
def test_own_subject_warning_remains_usable(tmp_path, subject):
    from tests.docs._global_evidence_fixtures import capture_fixture, visible
    raw = (f"# {subject}\n\n{subject} groups task functions.\n\n"
           "Tasks execute in order. If one raises an exception, later tasks stop.\n")
    cap = capture_fixture(tmp_path, {"tasks.md": raw},
        f"If one {subject} function raises an exception, what happens to later tasks and their ordering?")
    assert "later tasks stop" in visible(cap)
