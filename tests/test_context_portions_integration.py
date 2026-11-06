"""Continuation contracts through real preparation, retrieval and public MCP dispatch."""
from __future__ import annotations

import pytest

from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from docmancer.mcp.docs_server import call_docs_tool_payload, current_docs_surface


@pytest.fixture
def prepared_project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    text = ("# Archive policy\n\nArchive records preserve their original timestamp.\n"
            "Archive records are stored in the west region.\n")
    write_project(project, {"docs/archive.md": text})
    with isolated_service(tmp_path / "state") as (service, config):
        monkeypatch.setenv("DOCATLAS_MCP_TEXT_FALLBACK", "1")
        monkeypatch.setenv("DOCATLAS_MCP_COMPACT_TEXT", "1")
        inventory = index_project(service, config, project)
        assert not inventory["excluded_or_failed_paths"]
        yield service, config, project, text


def test_context_portions_bind_snapshot_and_stop_after_exhaustion(prepared_project, monkeypatch):
    service, config, project, text = prepared_project
    args = {"project_path": str(project), "question": "What is the archive records policy?"}
    first = call_docs_tool_payload("get_docs_context", args, service)
    assert first.get("sources"), first
    assert any("original timestamp" in row["snippet"] for row in first["sources"])
    assert all(row["snippet"] in text for row in first["sources"])
    assert first == call_docs_tool_payload("get_docs_context", {**args, "portion": 1}, service)
    more = first["more_context"]
    assert more["next_portion"] is None and more["remaining_rows"] == 0
    token = more["continuation_token"]
    assert len(token) == 64
    exhausted = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2**31, "continuation_token": token}, service)
    assert not exhausted.get("error"), exhausted
    assert not exhausted.get("sources")
    assert exhausted["more_context"]["next_portion"] is None
    changed_query = call_docs_tool_payload("get_docs_context", {
        **args, "question": "Where are archive records stored?", "portion": 2,
        "continuation_token": token}, service)
    assert changed_query["error"]["reason_code"] == "stale_context_continuation"
    changed_scope = call_docs_tool_payload("get_docs_context", {
        **args, "scope": "all", "portion": 2, "continuation_token": token}, service)
    assert changed_scope["error"]["reason_code"] == "stale_context_continuation"
    monkeypatch.setenv("DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS", "18000")
    changed_budget = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert changed_budget["error"]["reason_code"] == "stale_context_continuation"
    monkeypatch.delenv("DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS")
    (project / "docs/archive.md").write_text(text + "Archive records also retain a checksum.\n")
    index_project(service, config, project)
    changed_source = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert changed_source["error"]["reason_code"] == "stale_context_continuation"


def test_context_portions_reject_invalid_and_unsupported_requests(prepared_project, monkeypatch):
    service, _config, project, _text = prepared_project
    args = {"project_path": str(project), "question": "What is the archive records policy?"}
    first = call_docs_tool_payload("get_docs_context", args, service)
    token = first["more_context"]["continuation_token"]
    for invalid in (0, True, "2"):
        result = call_docs_tool_payload("get_docs_context", {**args, "portion": invalid}, service)
        assert result.get("error") and not result.get("sources"), result
    missing_token = call_docs_tool_payload("get_docs_context", {**args, "portion": 2}, service)
    assert missing_token.get("error") and not missing_token.get("sources"), missing_token
    advanced = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})
    patch = call_docs_tool_payload("get_docs_context", {
        **args, "context_format": "patch_context", "portion": 2, "continuation_token": token},
        service, surface=advanced)
    assert patch["error"]["reason_code"] == "portion_docs_only"
    monkeypatch.setenv("DOCATLAS_CONTEXT_COMPRESSION", "minilm-sections-v1")
    compressed = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert compressed["error"]["reason_code"] == "portion_unavailable"
    monkeypatch.delenv("DOCATLAS_CONTEXT_COMPRESSION")
    library = call_docs_tool_payload("get_docs_context", {
        "library": "unprepared-library", "question": args["question"], "portion": 2,
        "continuation_token": token}, service)
    assert library["error"]["reason_code"] == "portion_unavailable"
