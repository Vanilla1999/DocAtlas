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


def test_path_only_projection_uses_the_current_exact_topic_guard():
    retrieval = _host_lookup_context_retrieval()
    question = "In docs/settings.md, explain ALPHA_KEY."
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question=question, explicit_paths=["docs/settings.md"],
                required_query_ids=[], public_query_ids=["query-original", "query-path-1"],
                queries=[
                    {"query_id": "query-original", "text": question, "origin": "original"},
                    {"query_id": "query-path-1", "text": "docs/settings.md", "origin": "exact_path"},
                ])
    source = retrieval["context_pack"][0]
    source.update(path="docs/settings.md", content="ALPHA_KEY enables durable storage.",
                  line_start=11, retrieval_query_matches={}, retrieval_query_ids=[])
    retrieval["context_pack"] = [source]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["context_available"] is True
    assert result["sources"][0]["snippet"] == source["content"]
    assert result["covered_query_ids"] == ["query-path-1"]
    assert result["answer_supported"] is False
    assert result["edit_ready"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_table_windows_never_start_or_end_inside_a_row(limit):
    rows = ["| Stage | Operation |", "| --- | --- |"] + [
        f"| stage-{i} | gateway accepts a bounded request and sends candidates to the next stage; "
        "untrusted input must never authorize edits |" for i in range(14)
    ]
    text = "  \n" + "\n".join(rows) + "\n  "
    snippet, start, end = _focused_snippet(text, ("gateway bounded candidates",), limit=limit)
    assert snippet
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert all(line in rows for line in snippet.splitlines())


def test_oversized_table_row_does_not_drop_its_restriction():
    row = "| gateway | " + "bounded request " * 35 + "; never authorize edits |"
    text = "| Stage | Rule |\n| --- | --- |\n" + row
    snippet, start, end = _focused_snippet(text, ("gateway bounded request",), limit=160)
    assert row in snippet or "gateway" not in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_prose_window_does_not_start_in_the_middle_of_a_word(limit):
    text = "Prefix " * 25 + "ALPHA_KEY " + "configuration " * 70
    snippet, start, end = _focused_snippet(text, ("ALPHA_KEY configuration",), limit=limit)
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert not start or text[start - 1].isspace()
    assert end == len(text) or text[end].isspace()


def test_stronger_explicit_lookup_precedes_generated_alias_bonus():
    retrieval = _host_lookup_context_retrieval()
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question="Explain the processing path.",
                public_query_ids=["query-original", "query-lookup-1"],
                required_query_ids=[], queries=[
                    {"query_id": "query-original", "text": "Explain the processing path.", "origin": "original"},
                    {"query_id": "query-lookup-1", "text": "gateway request candidates selection", "origin": "host_lookup"},
                    {"query_id": "query-intent-1", "text": "internal policy", "origin": "canonical_intent"},
                ])
    strong, weak = retrieval["context_pack"][:2]
    strong.update(path="docs/strong.md", content="The gateway handles request candidates.",
                  retrieval_query_matches={"query-lookup-1": {"query_text": "gateway request candidates selection"}})
    weak.update(path="docs/weak.md", content="Internal policy describes the gateway request.",
                retrieval_query_matches={
                    "query-lookup-1": {"query_text": "gateway request candidates selection"},
                    "query-intent-1": {"query_text": "internal policy"},
                })
    retrieval["context_pack"] = [weak, strong]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["sources"][0]["path_or_url"] == "docs/strong.md"
    assert "query-original" not in result["covered_query_ids"]
    assert "query-intent-1" not in result["covered_query_ids"]
    assert result["answer_supported"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


def test_table_focus_prefers_the_row_matching_the_whole_lookup():
    target = "| wire | documentation transport boundary accepts requests |"
    text = ("| Area | Responsibility |\n| --- | --- |\n"
            "| introduction | documentation overview |\n"
            + "\n".join(f"| area-{i} | unrelated processing step |" for i in range(9))
            + "\n" + target + "\n"
            + "\n".join(f"| appendix-{i} | unrelated appendix |" for i in range(9)))
    snippet, start, end = _focused_snippet(text, ("documentation transport boundary",), limit=160)
    assert target in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


def test_snippet_expansion_cannot_replace_an_already_visible_fact():
    from docmancer.docs.application.docs_context_projection import _expand_selected_snippets

    retained = "ALPHA_KEY requires a disk backup."
    raw = ("ALPHA_KEY uses memory buffers to process incoming requests.\n\n"
           + "Unrelated background explanation. " * 25 + "\n\n" + retained)
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(evidence_id="ev-retained", path_or_url=source["path"], snippet=retained,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"],
                      "exact_terms": ["ALPHA_KEY"], "qualified": True,
                  }})
    expanded = _expand_selected_snippets([source],
        projection_inputs={"ev-retained": (raw, ("ALPHA_KEY",), 1)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800)
    assert retained in expanded[0]["snippet"]
    assert expanded[0]["snippet"] in raw


def test_complete_qualified_variant_precedes_mid_sentence_prefix():
    from docmancer.docs.application.docs_context_projection import _qualified_fragments

    raw = (
        "# Cleanup\n\n"
        "`clear-index` removes derived index state while preserving project\n"
        "sources, configuration, and unrelated files; it never\n"
        "silently widens the cleanup scope. The command is preview-only\n"
        "unless `--apply` is supplied.\n"
    )
    query = "Does clearing derived storage preserve source files and configuration?"
    source = {
        "evidence_id": "ev-cleanup",
        "path_or_url": "docs/cleanup.md",
        "snippet": raw,
        "project_identity": "git:example/project",
        "authority": "source_of_truth",
        "scope": "project",
        "catalog_role": "runbook",
        "retrieval_query_ids": ["query-lookup-2"],
        "retrieval_query_matches": {"query-lookup-2": {
            "query_text": query,
            "query_terms": ["clearing", "derived", "storage", "preserve", "source", "files", "configuration"],
            "qualified": True,
        }},
        "_qualification_candidate": {
            "source_class": "project_doc",
            "project_identity": "git:example/project",
            "freshness": "current",
            "index_freshness": "synchronized",
            "risk_flags": [],
            "lifecycle_status": "active",
        },
        "_expected_project_identity": "git:example/project",
        "_lifecycle_intent": "current",
    }
    variants = _qualified_fragments(
        source,
        raw_snippet=raw,
        query_ids={"query-lookup-2"},
        query_text={"query-lookup-2": query},
        source_line_start=1,
    )
    assert variants
    assert "silently widens the cleanup scope." in variants[0]["snippet"]
    assert variants[0]["snippet"] in raw


def test_frozen_cache_reset_keeps_preview_and_preserve_in_visible_context():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-paraphrase-cache-reset")
    result = run(cases=(LiveCase(
        case_id=case["id"],
        question=case["question"],
        relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]),
        scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False


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


def test_lexical_gap_quotes_do_not_require_proposed_repo_write_consent(lexical_gap_project):
    import hashlib
    from eval.evidence_quality_v2.observer import observe_call

    project, service, inventory = lexical_gap_project
    raw_bytes = (project / "docs/queue.md").read_bytes()
    policy = service._cold.member_storage_policy
    payload, trace = observe_call(service, _gap_read_request(project))
    assert len(trace["stages"]["projector_inputs"]) == 1
    retrieval = trace["stages"]["projector_inputs"][0]
    assert retrieval["requires_confirmation"] is False
    assert retrieval["delivery_decision"]["deliverable"] is True
    gaps = [action for action in retrieval["next_actions"]
            if action.get("action") == "create_reviewable_project_doc"]
    assert gaps and all(action["requires_confirmation"] is True for action in gaps)
    assert all(action["confirmation_reason"] == "repo_write" for action in gaps)
    assert not (project / "ARCHITECTURE.md").exists()
    assert payload["context_available"] is True
    assert payload.get("requires_confirmation", False) is False
    assert payload["answer_supported"] is False and payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert payload["context_quality"]["status"] == "unverified"
    assert "unsupported_answer_authorization:context_only" in retrieval["missing_requirement_ids"]
    assert not retrieval["selection_decision"]["assignments"]
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["path_or_url"] == "docs/queue.md"
    assert source["snippet"].encode() in raw_bytes
    bound = trace["snapshot"][source["evidence_id"]]
    candidate = bound["source"]
    from docmancer.docs.application.model_visible_projection import _source_digest
    # Public docs hashes bind the source envelope, not just snippet bytes.
    assert source["content_sha256"] == _source_digest(candidate)
    assert candidate["content"].encode() == raw_bytes[candidate["char_start"]:candidate["char_end"]]
    assert candidate["display_content_hash"] == hashlib.sha256(raw_bytes).hexdigest()
    assert candidate["generation_id"] == inventory["generation_id"]
    assert candidate["instruction_trust"] == "untrusted_data"
    qualification = bound["qualification"]["retrieval_query_matches"]["query-original"]
    assert qualification["qualified"] is True and qualification["context_only"] is True
    assert qualification["query_text"] == _gap_read_request(project)["question"]
    assert candidate["_assigned_requirement_ids"] == []
    assert source["line_start"] == 1 and source["line_end"] == 3
    assert validate_model_visible_projection(payload, snapshot=trace["snapshot"], max_tokens=800) == []
    assert (project / "docs/queue.md").read_bytes() == raw_bytes
    assert policy.generation() == inventory["generation_id"]
    from contextlib import closing
    with closing(policy.connect()) as db:
        rows = [dict(row) for row in db.execute(
            "SELECT stable_chunk_id, source_path, display_text, line_start, line_end "
            "FROM retrieval_children WHERE generation_id = ?", (inventory["generation_id"],),
        )]
    assert rows == inventory["rows"]


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
    monkeypatch.setattr(service.materialize(), "_project_sync_project_docs_impl", forbidden, raising=False)
    with pytest.raises(PermissionError, match="no explicit mutation grant"):
        service.sync_project_docs(str(project))
    assert policy.generation() == generation and policy.db_path.read_bytes() == before
    assert not (project / "ARCHITECTURE.md").exists()


def test_frozen_architecture_infrastructure_boundary_enters_retrieval_candidates():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-natural-architecture")
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
