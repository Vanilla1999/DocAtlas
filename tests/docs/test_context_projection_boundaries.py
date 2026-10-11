"""Projection must keep source-local text intact without inventing answer proof."""
from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import (
    _focused_snippet,
    project_docs_context,
)
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def test_path_only_projection_uses_the_current_exact_topic_guard(tmp_path):
    from hashlib import sha256

    from tests.docs._reference_binding_fixtures import capture_reference_case
    from tests.docs._global_evidence_fixtures import capture_fixture

    question = "In docs/settings.md, explain ALPHA_KEY."
    text = "ALPHA_KEY enables durable storage."
    capture = capture_reference_case(tmp_path, {"docs/settings.md": text}, question)
    result = capture["public_payload"]
    snapshot = capture["projection_attempts"][-1]["snapshot"]
    assert result["context_available"] is True
    assert result["sources"][0]["snippet"] == text
    source = result["sources"][0]
    bound = snapshot[source["evidence_id"]]["source"]
    reference = bound["_reference_evidence"]
    assert source["path_or_url"] == reference["source"]["canonical_path"] == "docs/settings.md"
    assert source["project_identity"] == reference["source"]["scope"]["project_id"]
    assert reference["source"]["content_sha256"] == sha256(text.encode("utf-8")).hexdigest()
    assert bound["_reference_root_plan"]["question"] == question
    assert bound["_reference_root_plan"]["catalog_complete"] is True
    assert (source["line_start"], source["line_end"]) == (1, 1)
    # The literal body is useful context; a path does not become a public query.
    assert result["covered_query_ids"] == []
    assert result["missing_query_ids"] == ["query-original"]
    assert result["answer_supported"] is False
    assert result["edit_ready"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []

    for label, path, body in (
        ("filename_only", "docs/settings.md", "A generic setting enables durable storage."),
        ("heading_only", "docs/settings.md", "# ALPHA_KEY\n\nA generic setting enables durable storage."),
        ("identifier_prefix", "docs/settings.md", "ALPHA_KEY_EXTRA enables durable storage."),
        ("wrong_path", "docs/other.md", text),
    ):
        # A correct read veto may happen before the source projector is reached.
        negative = capture_fixture(tmp_path / label, {path: body}, question)["public_payload"]
        assert negative.get("error") is None, negative
        assert negative["kind"] == "docs_context", negative
        assert negative["status"] == "insufficient_evidence", negative
        assert not negative.get("sources"), label
        assert not negative.get("covered_query_ids"), label
        assert negative.get("answer_supported") is not True, label
        assert negative.get("edit_ready") is not True, label



@pytest.fixture
def lexical_gap_project(tmp_path):
    """Cold public member preparation, not a selector or projector substitute."""
    from eval.evidence_quality_v2 import runtime

    project = tmp_path / "project"
    state = tmp_path / "state"
    runtime.write_project(project, {"docs/queue.md": (
        "# Queue buffer configuration\n\n"
        "`QUEUE_BUFFER` configures the queue buffer. The default is 17 records. "
        "Changes require restarting the worker.\n"
    )})
    try:
        with runtime.isolated_service(state) as (service, config):
            assert service._cold._service is None
            assert not service._cold.member_storage_policy.db_path.exists()
            inventory = runtime.index_project(service, config, project)
            assert inventory["indexed_paths"] == ["docs/queue.md"]
            assert inventory["excluded_or_failed_paths"] == []
            yield project, service, inventory
    finally:
        home = runtime._FIXTURE_HOMES.pop(state.resolve(), None)
        if home is not None:
            home.cleanup()


def _gap_read_request(project):
    # No expected answer, lookup schedule, version or proof requirements.
    return {"question": "Explain queue buffer configuration.",
            "project_path": str(project), "scope": "all"}


def test_gap_does_not_override_real_read_preflight_consent(lexical_gap_project):
    from eval.evidence_quality_v2.observer import observe_call

    project, service, _ = lexical_gap_project
    source = project / "docs/queue.md"
    source.write_bytes(source.read_bytes() + b"Changed after the confirmed snapshot.\n")
    payload, trace = observe_call(service, _gap_read_request(project))
    assert payload["requires_confirmation"] is True
    assert payload["confirmation_reason"] == "project_docs_preflight"
    assert payload["context_available"] is False and not payload.get("sources")
    assert payload["edit_ready"] is False
    assert trace["stages"]["projector_inputs"] == []
    assert not (project / "ARCHITECTURE.md").exists()


def test_gap_preserves_network_consent_and_does_not_call_fetch(lexical_gap_project, monkeypatch):
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload

    project, service, _ = lexical_gap_project
    def forbidden(*args, **kwargs):
        pytest.fail("network fetch without a grant")
    monkeypatch.setattr(service.materialize(), "get_docs", forbidden)
    result = service.get_project_context(str(project), _gap_read_request(project)["question"],
        library="unindexed-library", mode="auto", scope="all", allow_network=False)
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "network_fetch"
    assert result.next_action["confirmation_reason"] == "network_fetch"
    assert not result.delivery_decision.deliverable
    assert any(action.get("confirmation_reason") == "repo_write" for action in result.next_actions)
    payload = call_docs_tool_payload("get_docs_context", {
        **_gap_read_request(project), "library": "unindexed-library",
    }, service)
    assert payload["requires_confirmation"] is True
    assert payload["context_available"] is False and not payload.get("sources")
    assert payload["edit_ready"] is False


def test_gap_quote_cannot_bypass_revoked_source_read_grant(lexical_gap_project, monkeypatch):
    import json
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
    from docmancer.mcp.docs_server import read_docs_resource

    project, service, _ = lexical_gap_project
    payload = call_docs_tool_payload("get_docs_context", _gap_read_request(project), service)
    source = payload["sources"][0]
    catalog = project / "docatlas.project-docs.yaml"
    catalog.write_text(catalog.read_text().replace("source_of_truth", "historical"))
    def forbidden(*args, **kwargs):
        pytest.fail("revoked source read reached hydration")
    monkeypatch.setattr(service.source_reader.gateway, "read_snapshot", forbidden)
    read = json.loads(read_docs_resource(source["source_uri"], service)["text"])
    assert read["status"] == "source_unavailable"
    assert "snippet" not in read
    assert not (project / "ARCHITECTURE.md").exists()


def test_gap_quote_is_not_a_mutation_grant(lexical_gap_project, monkeypatch):
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload

    project, service, _ = lexical_gap_project
    payload = call_docs_tool_payload("get_docs_context", _gap_read_request(project), service)
    assert payload["sources"] and payload["edit_ready"] is False
    policy = service._cold.member_storage_policy
    before = policy.db_path.read_bytes()
    generation = policy.generation()
    def forbidden(*args, **kwargs):
        pytest.fail("mutation producer called without a grant")
    monkeypatch.setattr(service._cold.project_docs, "sync_project_docs", forbidden)
    result = call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project),
    }, service._cold)
    assert result["error"]["reason_code"] in {"validation_error", "permission_denied"}
    reader = service.materialize(read_only_startup=True)
    assert reader is service._cold._read_service
    assert service.sync_project_docs.__self__ is reader
    monkeypatch.setattr(reader, "_project_sync_project_docs_impl", forbidden, raising=False)
    with pytest.raises(PermissionError, match="no explicit mutation grant"):
        service.sync_project_docs(str(project))
    assert service._cold._service is None
    assert policy.generation() == generation and policy.db_path.read_bytes() == before
    assert not (project / "ARCHITECTURE.md").exists()


def test_frozen_request_flow_prefers_project_context_module_witnesses():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-natural-request-flow")
    result = run(cases=(LiveCase(
        case_id=case["id"], question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert "docs/modules/project-context-retrieval.md" in {
        source["path_or_url"] for source in payload["sources"]
    }
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
