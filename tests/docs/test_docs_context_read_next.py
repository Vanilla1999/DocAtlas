"""Production-path regressions for source-bound docs-context recovery targets."""
from __future__ import annotations

from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json

import pytest

from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.interfaces.host_context import SourceReadController
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource


def _real_service(tmp_path, request, *, content=None):
    from eval.evidence_quality_v2 import runtime

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="recovery-smoke"\nversion="0.1"\n')
    path = tmp_path / "docs/polling.md"
    if content is None:
        body = ["# Polling", "", "Retry only after a terminal status is observed.", ""]
        body.extend(f"Polling context line {index}." for index in range(1, 18))
        body.append("Job polling uses docs_status to inspect progress until terminal status.")
        body.extend(f"Additional polling context {index}." for index in range(18, 36))
        content = "\n".join(body) + "\n"
    path.write_text(content)
    (tmp_path / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n  - path: docs/polling.md\n    role: runbook\n"
        "    scope: project\n    authority: source_of_truth\n    status: active\n"
        "    description: Polling lifecycle\n"
    )
    state = (tmp_path / "state").resolve()
    lifecycle = ExitStack()
    request.addfinalizer(lifecycle.close)

    def cleanup_home():
        home = runtime._FIXTURE_HOMES.pop(state, None)
        if home is not None:
            home.cleanup()

    # LIFO: restore the fixture environment before removing its private store.
    lifecycle.callback(cleanup_home)
    service, config = lifecycle.enter_context(runtime.isolated_service(state))
    runtime.index_project(service, config, tmp_path)
    return service


def test_final_public_handler_complete_window_preserves_quality_and_quote(tmp_path, request, record_property):
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    from eval.project_context_quality.capture_public_context import capture_public_call

    service = _real_service(tmp_path, request)
    args = {
        "question": "How does docs_status polling progress work?",
        "lookup_queries": ["docs_status polling progress"],
        "project_path": str(tmp_path),
        "scope": "all",
    }
    # The observer forwards the real projector unchanged and records its bindings.
    record = capture_public_call(service, args)
    payload = record["public_payload"]
    assert payload["kind"] == "docs_context"
    assert payload["context_quality"]["status"] in {"unverified", "partial"}
    assert payload["read_next"] == []
    record_property("public_output_tokens", docs_context_budget_tokens(payload))
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["path_or_url"] == "docs/polling.md"
    assert (source["line_start"], source["line_end"]) == (5, 40)
    raw = (tmp_path / source["path_or_url"]).read_bytes()
    quote = b"\n".join(raw.splitlines()[4:40])
    assert source["snippet"].encode() == quote
    snapshot = record["projection_attempts"][0]["snapshot"]
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert source["content_sha256"] == snapshot[source["evidence_id"]]["content_sha256"]
    bound = snapshot[source["evidence_id"]]["source"]
    assert bound["content"].rstrip("\n").encode() == quote
    assert (bound["line_start"], bound["line_end"]) == (5, 40)
    assert bound["project_identity"] == source["project_identity"]
    assert bound["_source_snapshot_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert bound["_reference_evidence"]["raw_document"].encode() == raw
    reference = bound["_reference_evidence"]["source"]
    assert reference["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert reference["scope"]["snapshot_id"] == bound["generation_id"]
    assert reference["scope"]["project_id"] == source["project_identity"]
    assert source["source_uri"].startswith("docatlas://source/")


def _continuation_document():
    # Distinct lifecycle instructions, not repeated padding or oracle requirements.
    return "# Polling\n\n" + "\n\n".join([
        "Job polling uses docs_status to inspect progress until a terminal status is observed. "
        "Start by recording the job identifier returned by preparation. Keep the identifier "
        "with the project path so that subsequent status requests address the same job.",
        "For a queued job, wait for the worker to accept the request. Queue position is an "
        "observation rather than a completion promise. Do not start another preparation "
        "request while the original job is still queued; overlapping requests make diagnosis harder.",
        "For a running job, compare the current progress with the previous observation and "
        "retain any reported error details. A progress counter can remain unchanged while the "
        "worker processes one document. Lack of a counter change alone does not establish that the job has failed.",
        "The polling loop stops when the status becomes succeeded, failed, or cancelled. "
        "A succeeded job can be inspected through the indexed documentation. A failed job "
        "requires diagnosis before retrying. A cancelled job must not be treated as successfully prepared.",
        "When docs_status polling reports progress, record the observation time alongside "
        "the completed and pending counts. These counts describe that job only. Comparing "
        "counts from different job identifiers does not measure progress of the original preparation request.",
        "If a status request fails, retain the last successful observation without treating "
        "it as the current state. Retry the status request for the same job identifier. "
        "A transport error is not a terminal job state and does not authorize a second preparation request.",
        "Before retrying a failed preparation job, inspect the reported error and check "
        "whether its cause has been addressed. Record the new job identifier separately. "
        "Preserve the failed job observation so that the retry can be distinguished from the original attempt.",
        "Cancellation requests and cancellation completion are separate events. Continue "
        "polling the existing job after requesting cancellation until docs_status reports "
        "a terminal status. A cancellation request may race with successful completion, so retain the observed result.",
        "After a successful preparation job, inspect the prepared documentation using the "
        "same project path. If the expected source is absent, investigate that source rather "
        "than assuming the polling loop verified document coverage. Job completion is not an answer-quality guarantee.",
        "For polling diagnostics, report the job identifier, observation times, status "
        "transitions, and the last error message. Do not replace the actual sequence with "
        "an inferred transition. A queued observation followed by success does not prove that a running observation was received.",
        "For polling shutdown, stop issuing requests only after preserving the final "
        "observation or recording that the host stopped waiting. If the host exits before "
        "a terminal result, mark the investigation as incomplete. Do not label that interrupted observation sequence as success.",
        "Keep polling records separate from credentials and configuration secrets. Store "
        "only the status fields needed to identify the job and explain its progress. When "
        "sharing the diagnostic record, include the source project identity and omit unrelated local environment details.",
    ]) + "\n"


@pytest.mark.parametrize("revoked", [False, True], ids=["authorized", "revoked"])
@pytest.mark.parametrize("legacy_scope", ["control", "absent", True, False])
def test_final_public_handler_continuation_preserves_quality_and_usable_reference(
    tmp_path, request, monkeypatch, revoked, legacy_scope, record_property,
):
    from docmancer.docs.application import joint_seed_envelopes
    from docmancer.docs.application.joint_context_lineage import retained_seed_mapping
    from docmancer.docs.application.model_visible_projection import (
        _snapshot_entry, validate_model_visible_projection,
    )
    from docmancer.docs.interfaces.mcp import context_tools

    service = _real_service(tmp_path, request, content=_continuation_document())
    real_project = context_tools.project_docs_context
    real_envelopes = joint_seed_envelopes.seed_envelopes
    attempts, envelope_attempts = [], []
    witness = "Job polling uses docs_status to inspect progress until a terminal status is observed."

    def observe_envelopes(seed_payload, seed_snapshot):
        result = real_envelopes(seed_payload, seed_snapshot)
        envelope_attempts.append(deepcopy((seed_payload, seed_snapshot, result)))
        return result

    def negative_probe(*args, **kwargs):
        # Inject legacy metadata at a unit boundary, not into acquisition or a
        # fabricated successful payload. Normal producers do not emit this proof.
        retrieval = kwargs["retrieval"]
        if legacy_scope != "control":
            original = next(row for row in retrieval["context_pack"] if witness in row["content"])
            start = original["content"].index(witness)
            plan = retrieval["documentation_query_plan"]
            plan["_component_contract"] = [{"component_id": "opaque:negative-probe"}]
            if legacy_scope == "absent":
                plan.pop("component_scope_complete", None)
            else:
                plan["component_scope_complete"] = legacy_scope
            retrieval["selection_decision"] = {"assignments": [{
                "requirement_id": "opaque:negative-probe",
                "evidence_id": original.get("stable_id") or original["stable_chunk_id"],
                "projected_content_hash": hashlib.sha256(witness.encode()).hexdigest(),
                "unit_char_start": start, "unit_char_end": start + len(witness),
            }]}
        result = real_project(*args, **kwargs)
        attempts.append(deepcopy((retrieval, result[1])))
        return result

    monkeypatch.setattr(context_tools, "project_docs_context", negative_probe)
    monkeypatch.setattr(joint_seed_envelopes, "seed_envelopes", observe_envelopes)
    payload = call_docs_tool_payload("get_docs_context", {
        "question": "How does docs_status polling progress work?",
        "project_path": str(tmp_path),
        "scope": "all",
    }, service)
    assert payload.get("kind") == "docs_context", payload
    assert payload["context_quality"] == {
        "status": "unverified", "reasons": ["coverage_unverified"],
    }, payload["read_next"]
    assert len(payload["read_next"]) == 1, {
        "source_count": len(payload.get("sources") or ()),
        "sources": [{
            **{key: row.get(key) for key in ("evidence_id", "path_or_url", "line_start", "line_end")},
            "snippet_sha256": hashlib.sha256(row["snippet"].encode()).hexdigest(),
        } for row in (payload.get("sources") or ())[:4]],
        "envelope_attempt_count": len(envelope_attempts),
        "envelope_option_counts": [len(options) for _, _, options in envelope_attempts[:4]],
    }
    target = payload["read_next"][0]
    assert target["reason"] in {"inspect_source_context", "requested_part_missing"}
    record_property("public_output_tokens", docs_context_budget_tokens(payload))
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert payload["support_status"] == "retrieval_only"
    assert payload["answer_policy"] == "cite_only"
    assert len(attempts) == 1
    retrieval, snapshot = attempts[0]
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    raw = (tmp_path / "docs/polling.md").read_bytes()
    raw_text = raw.decode("utf-8")
    assert envelope_attempts
    for seed_payload, seed_snapshot, options in envelope_attempts:
        assert len(seed_payload["sources"]) >= 2 and options
        for _, (row, original, kind) in options:
            reference = original["_reference_evidence"]
            start, end = reference["char_start"], reference["char_end"]
            assert kind == "seed_envelope"
            assert 0 <= start < end < len(raw_text), "read_next_compact_envelope_range"
            assert row["snippet"] == original["content"] == raw_text[start:end]
            assert original["byte_start"] == len(raw_text[:start].encode("utf-8"))
            assert original["byte_end"] == len(raw_text[:end].encode("utf-8"))
            assert raw[original["byte_start"]:original["byte_end"]] == row["snippet"].encode("utf-8")
            assert row["line_start"] == raw_text.count("\n", 0, start) + 1
            assert row["line_end"] == raw_text.count("\n", 0, end - 1) + 1
            assert all(old["snippet"] in row["snippet"] for old in seed_payload["sources"]), (
                "read_next_compact_envelope_keeps_raw_seeds"
            )
            mapping = retained_seed_mapping(seed_payload, seed_snapshot, {"sources": [row]}, {
                row["evidence_id"]: _snapshot_entry(original, row),
            })
            assert mapping == {old["evidence_id"]: row["evidence_id"] for old in seed_payload["sources"]}
    assert target["path"] == "docs/polling.md"
    assert target["snapshot_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["path_or_url"] == target["path"]
    assert source["project_identity"] == target["project_identity"]
    raw_lines = raw.splitlines()
    # Keep every previously required line when the quote grows. Selection may
    # retain additional source facts after the output ceiling was removed.
    assert source["line_start"] == 1
    assert 11 <= source["line_end"] < len(raw_lines)
    assert source["snippet"].encode() == b"".join(raw.splitlines(keepends=True)[:source["line_end"]])
    # Recovery must cover the whole unseen suffix; only blank separator lines
    # may be skipped between the visible prefix and its continuation.
    assert source["line_end"] < target["line_start"] <= target["line_end"]
    assert target["line_end"] == len(raw_lines)
    assert not any(line.strip() for line in raw_lines[
        source["line_end"]:target["line_start"] - 1
    ])
    assert source["content_sha256"] == snapshot[source["evidence_id"]]["content_sha256"]
    bound = snapshot[source["evidence_id"]]["source"]
    assert bound["_source_snapshot_sha256"] == target["snapshot_sha256"]
    assert bound["_reference_evidence"]["raw_document"].encode() == raw
    if legacy_scope != "control":
        assignment = retrieval["selection_decision"]["assignments"][0]
        assert witness in source["snippet"]
        assert hashlib.sha256(witness.encode()).hexdigest() == assignment["projected_content_hash"]
    plan = retrieval["documentation_query_plan"]
    assert plan["_component_contract"] == []
    assert plan["component_scope_complete"] is False
    assert plan["_component_coverage"]["mandatory_component_ids"] == []
    assert plan["_component_coverage"]["covered_component_ids"] == []
    assert plan["_component_coverage"]["unresolved_residue"] == ["unverified_original_component_scope"]
    reads = []

    def read_resource(uri):
        result = json.loads(read_docs_resource(uri, service)["text"])
        reads.append(result)
        return result

    controller = SourceReadController(
        payload,
        requested_facts={"rule": "What rule appears around the polling evidence?"},
        read_resource=read_resource,
    )
    if revoked:
        from docmancer.docs.project_docs_catalog import read_project_docs_catalog

        catalog = tmp_path / "docatlas.project-docs.yaml"
        catalog.write_text(catalog.read_text().replace(
            "authority: source_of_truth", "authority: historical\n    impact: search_only",
        ))
        current_catalog = read_project_docs_catalog(tmp_path)
        assert current_catalog.present and current_catalog.valid
        assert len(current_catalog.entries) == 1
        entry = current_catalog.entries[0]
        assert entry.path == target["path"]
        assert entry.scope == "project"
        assert entry.status == "active"
        assert entry.authority == "historical"
        assert entry.impact == "search_only"
    accepted = controller.read(target["source_uri"], missing_fact_id="rule")
    assert len(reads) == 1
    if revoked:
        assert reads[0] == {"status": "source_unavailable", "reason_code": "source_policy_or_snapshot_changed"}
        assert accepted == {"status": "stopped", "reason_code": "source_policy_or_snapshot_changed"}
        assert controller.results == []
    else:
        assert accepted == reads[0]
        assert accepted["status"] == "complete"
        assert accepted["line_start"] == target["line_start"]
        assert accepted["line_end"] == target["line_end"]
        assert accepted["path"] == target["path"]
        assert accepted["project_identity"] == target["project_identity"]
        assert accepted["content_sha256"] == target["snapshot_sha256"]
        assert accepted["snippet"].encode() == b"\n".join(raw_lines[
            target["line_start"] - 1:target["line_end"]
        ])
        assert docs_context_budget_tokens(accepted) <= 600
        assert controller.results == [accepted]


class _Reader:
    def __init__(self, *, fail_range: bool = False):
        self.fail_range = fail_range
        self.ranges = []

    def issue(self, reference, *, uri=None):
        return uri

    def issue_range(self, reference, *, line_start, line_end, uri=None):
        self.ranges.append((reference.path, line_start, line_end, uri))
        return None if self.fail_range else uri


class _ContextApp:
    def __init__(self, raw, reader):
        self.raw = raw
        self.source_reader = reader
        self.unified_context = self

    def get_docs_context(self, *args, **kwargs):
        return deepcopy(self.raw)


def _candidate(path: str, content: str, *, query_id: str, line_start: int, stable_id: str):
    digest = "sha256:" + hashlib.sha256((path + content).encode()).hexdigest()
    catalog = "sha256:" + hashlib.sha256(("catalog:" + path).encode()).hexdigest()
    return {
        "stable_id": stable_id,
        "source_class": "project_doc",
        "path": path,
        "heading_path": "Recovery",
        "content": content,
        "project_identity": "project:recovery",
        "line_start": line_start,
        "line_end": line_start + content.count("\n"),
        "authority": "source_of_truth",
        "doc_scope": "project",
        "lifecycle_status": "active",
        "freshness": "current",
        "index_freshness": "synchronized",
        "risk_flags": [],
        "_source_snapshot_sha256": digest,
        "_source_catalog_hash": catalog,
        "retrieval_query_ids": [query_id],
        "retrieval_query_matches": {
            query_id: {
                "qualified": True,
                "mode": "and",
                "query_text": "export identifiers" if query_id == "query-original" else "complete runnable example",
            }
        },
    }


def _raw_recovery_fixture():
    direct = (
        "Background context before the direct explanation.\n\n"
        "The export operation preserves original identifiers.\n\n"
        "Background context after the direct explanation."
    )
    example = "```python\n" + "# complete runnable example for export identifiers\n" * 180 + "export_identifiers()\n```"
    return {
        "status": "success",
        "mode_selected": "project",
        "project_identity": "project:recovery",
        "context_pack": [
            _candidate("docs/direct.md", direct, query_id="query-original", line_start=20, stable_id="direct"),
            _candidate("docs/example.md", example, query_id="query-example", line_start=100, stable_id="example"),
        ],
        "documentation_query_plan": {
            "original_question": "How does the export operation preserve original identifiers?",
            "query_ids": ["query-original", "query-example"],
            "required_query_ids": ["query-original", "query-example"],
            "public_query_ids": ["query-original", "query-example"],
            "queries": [
                {"query_id": "query-original", "text": "export identifiers", "origin": "original"},
                {"query_id": "query-example", "text": "complete runnable example", "origin": "host_lookup"},
            ],
        },
        "retrieval_diagnostics": {},
    }

