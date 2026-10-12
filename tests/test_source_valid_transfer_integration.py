"""Fixed nonnumeric transfer check at the actual public MCP boundary.

One test makes exactly 2 public preparations and 4 public context calls with
real lexical retrieval and storage. Both control and broad modes use the same
12000-token experiment cap and prepared-parent setting. There are no resource
reads or model calls. The second project renames document paths and reverses
the two clauses of the question; required source facts remain identical.

The fixture was authored during independent review, after reading the initial
implementation but before its own execution. It is a transfer check, not a
blind holdout or a general quality estimate. Control failure or incremental
improvement is NOT required. Preserve failures; do not change inputs for PASS.
"""
from __future__ import annotations

import pytest

from eval.evidence_quality_v2 import runtime
from tests.test_prepared_retrieval_integration import (
    ADMISSION_ENV,
    CAP_ENV,
    PARENTS_ENV,
    _assert_facts,
    _assert_packet_sources,
    _committed_documents,
    _context,
    _database_state,
    _file_state,
    _packet_proxy,
    _relative_source,
)


TRANSFER_CAP = 12000
LABEL_DOCUMENT = (
    "# Sealed parcel labelling\n\n"
    "For a relief shipment, sealed parcels carry a violet custody tag.\n"
    "Write the destination on the tag using water-resistant ink.\n"
)
CUSTODY_DOCUMENT = (
    "# Custody sheet handling\n\n"
    "The depot steward receives the custody sheet for a relief shipment.\n"
    "The depot steward signs the custody sheet after checking the parcel seals.\n"
)
LABEL_FACTS = (
    "For a relief shipment, sealed parcels carry a violet custody tag.",
    "Write the destination on the tag using water-resistant ink.",
)
CUSTODY_FACTS = (
    "The depot steward receives the custody sheet for a relief shipment.",
    "The depot steward signs the custody sheet after checking the parcel seals.",
)
TRANSFER_CASES = (
    {
        "name": "original",
        "label_path": "docs/alpha.md",
        "custody_path": "docs/beta.md",
        "question": (
            "For a relief shipment, how must sealed parcels be labelled "
            "and who receives and signs the custody sheet?"
        ),
    },
    {
        "name": "renamed_reordered",
        "label_path": "docs/omega.md",
        "custody_path": "docs/delta.md",
        "question": (
            "For a relief shipment, who receives and signs the custody sheet "
            "and how must sealed parcels be labelled?"
        ),
    },
)


@pytest.fixture
def transfer_states(tmp_path):
    states = tuple(tmp_path / f"member-state-{case['name']}" for case in TRANSFER_CASES)
    try:
        yield states
    finally:
        for state in states:
            home = runtime._FIXTURE_HOMES.pop(state.resolve(), None)
            if home is not None:
                home.cleanup()


def _delivered_facts(payload, project, facts):
    """Independent authored literal facts, irrespective of evidence-row layout."""
    delivered = set()
    for relative, required in facts.items():
        snippets = [row["snippet"] for row in payload.get("sources") or ()
                    if _relative_source(row, project) == relative]
        for fact in required:
            if any(fact in snippet for snippet in snippets):
                delivered.add(fact)
    return delivered


def test_source_valid_transfer_preserves_facts_after_path_and_clause_reordering(
    tmp_path, monkeypatch, transfer_states, record_property,
):
    """2 preparations, 4 context calls, 0 resource reads, 0 model calls."""
    broad_fact_sets = []
    for case, state in zip(TRANSFER_CASES, transfer_states, strict=True):
        project = tmp_path / f"project-{case['name']}"
        documents = {
            case["label_path"]: LABEL_DOCUMENT,
            case["custody_path"]: CUSTODY_DOCUMENT,
        }
        facts = {
            case["label_path"]: LABEL_FACTS,
            case["custody_path"]: CUSTODY_FACTS,
        }
        runtime.write_project(project, documents)
        with runtime.isolated_service(state) as (service, config), monkeypatch.context() as env:
            env.setenv(PARENTS_ENV, "1")
            env.setenv(CAP_ENV, str(TRANSFER_CAP))
            inventory = runtime.index_project(service, config, project)
            _committed_documents(inventory, project, documents)
            before, files_before = _database_state(inventory), _file_state(project)
            baseline = _context(service, project, case["question"])
            env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
            broad = _context(service, project, case["question"])
            for payload in (baseline, broad):
                _assert_packet_sources(payload, project, documents)
                assert _packet_proxy(payload) <= TRANSFER_CAP
            baseline_facts = _delivered_facts(baseline, project, facts)
            broad_facts = _delivered_facts(broad, project, facts)
            record_property(f"{case['name']}_baseline_facts", len(baseline_facts))
            record_property(f"{case['name']}_broad_facts", len(broad_facts))
            _assert_facts(broad, project, facts)
            assert set(broad.get("covered_query_ids") or ()) <= set(baseline.get("covered_query_ids") or ())
            assert broad.get("support_status") == "retrieval_only"
            assert broad.get("coverage_policy") == "retrieval_attribution_only"
            assert broad.get("answer_supported") is False
            assert broad.get("answer_available") is False
            assert broad.get("edit_ready") is False
            broad_fact_sets.append(broad_facts)
            assert _database_state(inventory) == before
            assert _file_state(project) == files_before
    assert broad_fact_sets[0] == broad_fact_sets[1] == set(LABEL_FACTS + CUSTODY_FACTS)
