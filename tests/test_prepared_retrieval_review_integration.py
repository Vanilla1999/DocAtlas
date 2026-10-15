"""Public prepared-reader reuse and fallback, reusing the frozen optics oracle.

One real member preparation and four in-process MCP context calls; no model or
source-continuation call. The query, documents, facts and cap are unchanged from
the original integration fixture. Diagnostics explain which reader ran; final
facts, raw spans, the complete stable DTO and read-only state remain the oracle.
The only arranged corruption changes the optional derived parser revision in
the isolated SQLite manifest, never raw source bytes, source permissions or the
production parser. No retrieval, selection, storage or validation is mocked.
"""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

from docmancer.docs.application.query_trace import query_trace
from eval.evidence_quality_v2 import runtime
from tests.test_prepared_retrieval_integration import (
    ADMISSION_ENV, CAP_ENV, PARENTS_ENV, WIDE_CAP,
    OPTICS_DOCUMENTS, OPTICS_FACTS, OPTICS_QUESTION,
    _assert_facts, _assert_packet_sources, _committed_documents, _context,
    _database_state, _file_state, _packet_proxy, _prepared_manifest,
    _semantic_packet, state_root,
)


def _capture_trace(captured, *, phase, project, service):
    """Retain emitted bytes after the call; never observe or rerun producers."""
    destination = os.environ.get("PYTEST_DOCATLAS_ARTIFACT_DIR")
    if destination:
        output = Path(destination).expanduser().resolve()
        storage = Path(service.config.index.db_path).resolve().parent
        if output.is_relative_to(project.resolve()) or output.is_relative_to(storage):
            raise ValueError("trace audit directory must be outside fixture project and storage")
        output.mkdir(parents=True, exist_ok=True)
        (output / f"prepared-trace-{phase}.log").write_text(captured.err, encoding="utf-8")
    events = []
    for line in captured.err.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "docatlas_query_trace":
            events.append(event)
    assert '"event": "docatlas_query_trace"' not in captured.out
    return events


def test_prepared_reader_reuses_rows_and_revision_falls_back_without_public_change(
    tmp_path, monkeypatch, state_root, capsys, record_property,
):
    """1 prepare, 4 contexts, 0 source reads, 0 model calls; fixed sequence."""
    project = tmp_path / "project"
    runtime.write_project(project, OPTICS_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.setenv(PARENTS_ENV, "1")
        inventory = runtime.index_project(service, config, project)
        _committed_documents(inventory, project, OPTICS_DOCUMENTS)
        manifest = _prepared_manifest(inventory)
        assert manifest and manifest["generation_id"] == inventory["generation_id"]
        original_state, files_before = _database_state(inventory), _file_state(project)
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        capsys.readouterr()

        env.delenv(PARENTS_ENV)
        with query_trace(False):
            on_demand = _context(service, project, OPTICS_QUESTION)
        assert not _capture_trace(capsys.readouterr(), phase="parser-off",
                                  project=project, service=service)
        assert _database_state(inventory) == original_state
        assert _file_state(project) == files_before

        env.setenv(PARENTS_ENV, "1")
        with query_trace(False):
            prepared_silent = _context(service, project, OPTICS_QUESTION)
        assert not _capture_trace(capsys.readouterr(), phase="prepared-off",
                                  project=project, service=service)
        assert _database_state(inventory) == original_state
        assert _file_state(project) == files_before

        with query_trace(True):
            prepared_traced = _context(service, project, OPTICS_QUESTION)
        valid_events = _capture_trace(capsys.readouterr(), phase="prepared-on",
                                      project=project, service=service)
        assert len(valid_events) == 1, valid_events
        valid_observation = valid_events[0]["projection_observation"]
        valid = valid_observation["upstream_received"]["prepared_parents"]
        # These counters concern SourceReferenceContext only. Other consumers
        # still parse structure; this is not a zero-parsing or latency claim.
        assert valid["prepared_enabled"] is True
        assert valid["prepared_hits"] > 0
        assert valid["documents"] == valid["prepared_hits"]
        assert valid["parser_calls"] == 0
        assert _database_state(inventory) == original_state
        assert _file_state(project) == files_before
        record_property("valid_prepared_reader_metrics", json.dumps(valid, sort_keys=True))

        # Arrange incompatible derived data. Keep generation identity, raw
        # snapshots, parent rows and all permission/catalog data unchanged.
        with closing(sqlite3.connect(inventory["storage_path"])) as connection:
            validation_json = connection.execute(
                "SELECT validation_json FROM index_generations WHERE generation_id=?",
                (inventory["generation_id"],),
            ).fetchone()[0]
            validation = json.loads(validation_json)
            validation["prepared_parents"]["parent_parser_revision"] = "incompatible-review-revision"
            connection.execute(
                "UPDATE index_generations SET validation_json=? WHERE generation_id=?",
                (json.dumps(validation, sort_keys=True), inventory["generation_id"]),
            )
            connection.commit()
        arranged_state = _database_state(inventory)
        with query_trace(True):
            fallback = _context(service, project, OPTICS_QUESTION)
        fallback_events = _capture_trace(capsys.readouterr(), phase="revision-fallback",
                                         project=project, service=service)
        assert len(fallback_events) == 1, fallback_events
        missed = fallback_events[0]["projection_observation"]["upstream_received"]["prepared_parents"]
        assert missed["prepared_enabled"] is True
        assert missed["prepared_hits"] == 0
        assert missed["parser_calls"] > 0
        assert missed["documents"] == missed["parser_calls"]
        miss_counts = {row["reason"]: row["count"] for row in missed["miss_reasons"]["items"]}
        assert miss_counts.get("incompatible_parent_revision", 0) == missed["documents"]
        record_property("revision_fallback_reader_metrics", json.dumps(missed, sort_keys=True))
        assert _database_state(inventory) == arranged_state
        assert _file_state(project) == files_before

        for payload in (on_demand, prepared_silent, prepared_traced, fallback):
            _assert_packet_sources(payload, project, OPTICS_DOCUMENTS)
            _assert_facts(payload, project, OPTICS_FACTS)
            assert _packet_proxy(payload) <= WIDE_CAP
            assert _semantic_packet(payload) == _semantic_packet(on_demand)
        record_property("public_context_calls", 4)
        record_property("public_prepare_calls", 1)
        record_property("model_calls", 0)
