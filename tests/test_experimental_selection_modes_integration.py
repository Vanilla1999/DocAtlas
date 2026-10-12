"""Public budget-mode execution and observational isolation without a model.

One real prepare, three public context calls, zero model/source-read calls.
Reuses an existing source/question oracle. No retrieval, selection, authority,
storage or finalization is replaced. Run separately from the frozen V40 quality
measurement; the checks do not tune its model or candidate policy.
"""
from __future__ import annotations

import json
import sys

from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer
from docmancer.docs.application.query_trace import query_trace
from eval.evidence_quality_v2 import runtime
from tests.test_prepared_retrieval_integration import (
    ADMISSION_ENV, CAP_ENV, PARENTS_ENV, WIDE_CAP,
    SCOPE_DOCUMENTS, SHUTTER_QUESTION,
    _assert_facts, _assert_packet_sources, _committed_documents, _context,
    _database_state, _file_state, _packet_proxy, _semantic_packet, state_root,
)


def test_budget_mode_and_observer_leave_public_evidence_unchanged(
    tmp_path, monkeypatch, state_root, record_property,
):
    project = tmp_path / "project"
    documents = {"docs/camera.md": SCOPE_DOCUMENTS["docs/camera.md"]}
    required = {"docs/camera.md": (
        "`SHUTTER_DELAY` sets shutter delay to 230 milliseconds.",
        "Changing `SHUTTER_DELAY` requires restarting the camera controller.",
    )}
    imported_before = {name: name in sys.modules for name in ("torch", "transformers", "safetensors")}
    runtime.write_project(project, documents)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.setenv(PARENTS_ENV, "1")
        inventory = runtime.index_project(service, config, project)
        _committed_documents(inventory, project, documents)
        original_db, original_files = _database_state(inventory), _file_state(project)
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        env.setenv("DOCATLAS_EXPERIMENT_SELECTOR", "budget")
        env.setenv("DOCATLAS_EXPERIMENT_SELECTOR_TOP_K", "2")
        # A model path is irrelevant to budget mode, even when no such files exist.
        env.setenv("DOCATLAS_EXPERIMENT_MINI_PATH", str(tmp_path / "absent-model"))
        with query_trace(False):
            plain = _context(service, project, SHUTTER_QUESTION)
        assert _database_state(inventory) == original_db
        assert _file_state(project) == original_files

        observed = []
        def mutate_copy(receipt):
            observed.append(receipt["selection"].copy())
            for candidate in receipt["pool"]:
                candidate["text"] = "Observer must never become source evidence."
                candidate["metadata"]["authority"] = "denied"
                candidate["binding"]["canonical_path"] = "/outside/project.md"
            receipt["selection"]["selected_indices"] = []
            return []

        with experimental_selection_observer(mutate_copy) as observation, query_trace(True):
            copied = _context(service, project, SHUTTER_QUESTION)
        assert observation.calls == 1 and not observation.errors
        assert len(observed) == 1 and observed[0]["mode"] == "budget"
        assert observed[0]["model_forwards"] == 0
        assert _database_state(inventory) == original_db
        assert _file_state(project) == original_files

        def broken_observer(receipt):
            raise RuntimeError("diagnostic sink unavailable")

        with experimental_selection_observer(broken_observer) as failed, query_trace(False):
            recovered = _context(service, project, SHUTTER_QUESTION)
        assert failed.calls == 1 and failed.errors == ["RuntimeError: diagnostic sink unavailable"]
        assert _database_state(inventory) == original_db
        assert _file_state(project) == original_files
        for payload in (plain, copied, recovered):
            _assert_packet_sources(payload, project, documents)
            _assert_facts(payload, project, required)
            assert _packet_proxy(payload) <= WIDE_CAP
            assert _semantic_packet(payload) == _semantic_packet(plain)
        imported_after = {name: name in sys.modules for name in imported_before}
        assert imported_after == imported_before
        record_property("optional_model_modules_before_after", json.dumps({"before": imported_before, "after": imported_after}))
        record_property("public_prepare_calls", 1)
        record_property("public_context_calls", 3)
        record_property("model_forwards", 0)
        record_property("source_continuation_calls", 0)
