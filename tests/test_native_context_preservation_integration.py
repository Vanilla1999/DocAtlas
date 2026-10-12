"""Known V40-V04 failure, through public MCP and real prepared SQLite storage.

One prepare, two context calls (trace off/on), no models or source continuations.
Both complete outputs are saved before the unchanged full-source witness is
asserted. A diagnostic-only baseline must remain a genuine task FAIL, not xfail.
"""
from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

import tiktoken

from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer
from docmancer.docs.application.query_trace import query_trace
from docmancer.mcp.docs_server import call_docs_tool_payload
from eval.evidence_quality_v2 import runtime
from tests.test_prepared_retrieval_integration import (
    _assert_packet_sources, _committed_documents, _database_state, _file_state,
    _relative_source, _semantic_packet, state_root,
)


REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / "reports/admission-experiments/prepared-retrieval/late-context-diagnostics-20261012/FROZEN_INPUTS.json"


def _save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _witness_coverage(payload, project, documents, witness):
    """Independent raw interval coverage; ambiguous matches receive intersection credit."""
    raw = documents[witness["path"]]
    lines = raw.splitlines(keepends=True)
    begin = sum(map(len, lines[:witness["line_start"] - 1]))
    end = sum(map(len, lines[:witness["line_end"]]))
    assert raw[begin:end] == witness["raw_text"]
    begin += len(witness["raw_text"]) - len(witness["raw_text"].lstrip())
    end -= len(witness["raw_text"]) - len(witness["raw_text"].rstrip())
    covered = set()
    contributing = []
    for row in payload.get("sources") or ():
        if _relative_source(row, project) != witness["path"]:
            continue
        snippet = row["snippet"]
        low = sum(map(len, lines[:row["line_start"] - 1]))
        high = sum(map(len, lines[:row["line_end"]]))
        positions = []
        offset = raw.find(snippet, low, high)
        while snippet and offset >= 0:
            positions.append(offset)
            offset = raw.find(snippet, offset + 1, high)
        if positions:
            left, right = max(positions), min(positions) + len(snippet)
            contribution = set(range(max(left, begin), min(right, end)))
            covered.update(contribution)
            if contribution:
                contributing.append(row["evidence_id"])
    missing = sorted(set(range(begin, end)) - covered)
    return {"complete": not missing, "required_char_start": begin, "required_char_end": end,
            "missing_character_count": len(missing), "first_missing_character": missing[0] if missing else None,
            "contributing_evidence_ids": contributing}


def _assert_trace_contract(records):
    events = {}
    for mode, record in records.items():
        events[mode] = []
        for line in record["trace"].splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue  # Any unrelated stderr remains in the saved file.
            if isinstance(event, dict) and str(event.get("event", "")).startswith("docatlas_"):
                events[mode].append(event)
    assert events["trace-off"] == []
    on = events["trace-on"]
    assert [event["event"] for event in on] == [
        "docatlas_request_start", "docatlas_query_trace", "docatlas_request_end",
    ]
    assert len({event["request_id"] for event in on}) == 1
    assert on[0]["request_id"] and on[-1].get("trace_incomplete") is False
    flow = on[1]["projection_observation"]["returned_core_diagnostics"]["context_flow"]
    assert flow["schema_version"] == 1
    assert flow["event_limit"] == 256 and flow["source_limit"] == 64
    assert flow["event_count"] == flow["recorded_events"] == len(flow["events"]) <= 256
    assert flow["omitted_events"] == flow["serialization_omitted_events"] == flow["diagnostic_error_count"] == 0
    assert [event["sequence"] for event in flow["events"]] == list(range(1, flow["event_count"] + 1))
    boundaries = [event for event in flow["events"] if event["event"] == "boundary"]
    assert {"recheck.input", "recheck.output", "budget.input", "budget.output"} <= {
        event["stage"] for event in boundaries
    }
    for event in boundaries:
        assert event.get("observation") != "diagnostic_error", event
        assert event["source_rows_omitted"] == event["serialization_omitted_source_rows"] == 0
        assert event["source_count"] == len(event["rows"]) <= 64
    # The log explains boundaries; it never supplies the task's expected fact.


def test_selected_native_context_survives_public_delivery_with_trace_parity(
    tmp_path, monkeypatch, state_root, record_property,
):
    frozen = json.loads(INPUTS.read_text(encoding="utf-8"))
    for item in frozen["frozen_corpus_inputs"] + frozen["sources"]:
        data = (REPO / item.get("repo_path", item["path"])).read_bytes()
        assert len(data) == item["bytes"] and _sha(data) == item["sha256"], item
    witness = frozen["expected_final"]["gold_witness"]
    assert _sha(witness["raw_text"].encode("utf-8")) == witness["raw_sha256"]
    assert _sha(witness["raw_text"].strip().encode("utf-8")) == witness["outer_trimmed_sha256"]
    documents = {item["path"]: (REPO / item["repo_path"]).read_text(encoding="utf-8")
                 for item in frozen["sources"]}
    raw_lines = documents[witness["path"]].splitlines(keepends=True)
    assert "".join(raw_lines[witness["line_start"] - 1:witness["line_end"]]) == witness["raw_text"]
    project = tmp_path / "projects" / frozen["project_group"]
    output = Path(os.environ.get("PYTEST_DOCATLAS_ARTIFACT_DIR", str(tmp_path / "artifacts"))).resolve()
    output = output / "V40-V04-budget"
    assert not output.is_relative_to(project.resolve()) and not output.is_relative_to(state_root.resolve())
    output.mkdir(parents=True, exist_ok=False)
    _save(output / "inputs.json", {"frozen_inputs_sha256": _sha(INPUTS.read_bytes()), "inputs": frozen})
    encoding = tiktoken.get_encoding("o200k_base")
    imported_before = {name: name in sys.modules for name in ("torch", "transformers", "safetensors")}
    runtime.write_project(project, documents)
    operations = {"scenarios": 1, "prepare_calls_attempted": 0, "context_calls_attempted": 0,
                  "context_calls_returned": 0, "source_continuation_calls": 0, "answer_generator_calls": 0}
    records = {}
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        assert not output.is_relative_to(Path(config.index.db_path).resolve().parent)
        for name, value in frozen["configuration"].items():
            env.setenv(name, value)
        operations["prepare_calls_attempted"] += 1
        _save(output / "operations.json", operations)
        inventory = runtime.index_project(service, config, project)
        _save(output / "preparation.json", inventory)
        _committed_documents(inventory, project, documents)
        original_db, original_files = _database_state(inventory), _file_state(project)
        arguments = {"question": frozen["question"], "project_path": str(project), "scope": "project"}
        for enabled in (False, True):
            mode = "trace-on" if enabled else "trace-off"
            destination = output / mode
            destination.mkdir()
            before_db, before_files = _database_state(inventory), _file_state(project)
            assert before_db == original_db and before_files == original_files
            metadata = {"case_id": frozen["case_id"], "mode": "budget", "trace_enabled": enabled,
                        "arguments": arguments, "status": "started", "same_initial_state": True,
                        "database_sha256_before": _sha(repr(before_db).encode()),
                        "files_sha256_before": _sha(repr(before_files).encode())}
            _save(destination / "metadata.json", metadata)
            operations["context_calls_attempted"] += 1
            _save(output / "operations.json", operations)
            receipts, stderr, payload = [], io.StringIO(), None
            start, cpu = time.perf_counter(), time.process_time()
            with experimental_selection_observer(receipts.append) as observation:
                try:
                    with redirect_stderr(stderr), query_trace(enabled):
                        payload = call_docs_tool_payload("get_docs_context", dict(arguments), service)
                    metadata["status"] = "returned"
                    operations["context_calls_returned"] += 1
                except Exception as exc:
                    metadata.update(status="error", error_type=type(exc).__name__, error=str(exc))
                finally:
                    metadata.update(elapsed_seconds=time.perf_counter() - start,
                                    process_cpu_seconds=time.process_time() - cpu)
            after_db, after_files = _database_state(inventory), _file_state(project)
            metadata.update(observation_calls=observation.calls, observation_errors=observation.errors,
                            database_unchanged=after_db == original_db, files_unchanged=after_files == original_files,
                            database_sha256_after=_sha(repr(after_db).encode()),
                            files_sha256_after=_sha(repr(after_files).encode()))
            if payload is not None:
                wire = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
                (destination / "public-payload.json").write_bytes(wire)
                metadata.update(wire_sha256=_sha(wire), wire_utf8_bytes=len(wire),
                                utf8_quarter_proxy=(len(wire) + 3) // 4,
                                codec_o200k_base=len(encoding.encode(wire.decode("utf-8"), disallowed_special=())))
            (destination / "trace.jsonl").write_text(stderr.getvalue(), encoding="utf-8")
            _save(destination / "selection.json", receipts)
            _save(destination / "metadata.json", metadata)
            _save(output / "operations.json", operations)
            records[mode] = {"payload": payload, "metadata": metadata, "receipts": receipts, "trace": stderr.getvalue()}
            # A real state mutation stops before another call, never just a missing fact.
            assert metadata["database_unchanged"] and metadata["files_unchanged"], metadata

        imported_after = {name: name in sys.modules for name in imported_before}
        model_forwards = sum(receipt["selection"]["model_forwards"]
                             for record in records.values() for receipt in record["receipts"])
        operations.update(model_forwards=model_forwards, optional_model_modules_before=imported_before,
                          optional_model_modules_after=imported_after)
        _save(output / "operations.json", operations)
        for name, value in operations.items():
            record_property(name, json.dumps(value) if isinstance(value, dict) else value)

        # Both outputs and their receipts exist before any completeness decision.
        coverage = {}
        for mode, record in records.items():
            payload, metadata = record["payload"], record["metadata"]
            assert metadata["status"] == "returned", metadata
            _assert_packet_sources(payload, project, documents)
            assert payload["context_available"] is True
            for flag in ("answer_supported", "answer_available", "edit_ready"):
                assert payload[flag] is False
            for row in payload["sources"]:
                assert row["version_binding"] == "unversioned"
                assert row["project_identity"] == "local:" + _sha(str(project.resolve()).encode())
            assert max(metadata["utf8_quarter_proxy"], metadata["codec_o200k_base"]) <= 12000
            assert metadata["observation_calls"] == len(record["receipts"]) == 1
            assert metadata["observation_errors"] == []
            selection = record["receipts"][0]["selection"]
            assert selection["mode"] == "budget" and selection["model_forwards"] == 0
            coverage[mode] = _witness_coverage(payload, project, documents, witness)
        _save(output / "witness-coverage.json", coverage)
        assert imported_before == imported_after and model_forwards == 0
        off, on = records["trace-off"], records["trace-on"]
        assert _semantic_packet(off["payload"]) == _semantic_packet(on["payload"])
        for field in ("pool", "complete_candidates", "excluded"):
            assert off["receipts"][0][field] == on["receipts"][0][field], field
        assert off["receipts"][0]["selection"]["selected_indices"] == on["receipts"][0]["selection"]["selected_indices"]
        _assert_trace_contract(records)
        assert all(result["complete"] for result in coverage.values()), coverage
