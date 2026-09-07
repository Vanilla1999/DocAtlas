"""Exact indexed sections retain real lookup attribution without answer proof."""
from __future__ import annotations

import pytest

from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests.test_named_document_context_integration import _named_document_service


@pytest.mark.parametrize("term", ["meet_type", "retry_count", "RequestHandler", "CACHE_MODE"])
def test_index_fallback_qualifies_existing_exact_anchor(tmp_path, monkeypatch, term):
    path = "docs/REFERENCE.md"
    service, project = _named_document_service(tmp_path, monkeypatch, [path], {
        path: f"# Reference\n\n## Counter\n{term} records completed progress.\n"
        "\n## Other\nOtherSetting controls something unrelated.\n",
    })
    # Force the documented source-local fallback, not a global index scan.
    monkeypatch.setattr(service.project_docs, "query_project_docs", lambda *a, **kw: [])
    store = service.project_docs._agent_instance().store
    def no_full_scan(*a, **kw):
        pytest.fail("exact document fallback enumerated the whole generation")
    monkeypatch.setattr(store, "list_sections_for_embedding", no_full_scan)
    question = f"In {path}, summarize {term}."
    result = call_docs_tool_payload("get_docs_context", {
        "question": question, "project_path": project, "scope": "project",
    }, service)
    assert result["status"] == "ok", result
    assert result["kind"] == "docs_context"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["edit_ready"] is False
    assert {s["path_or_url"] for s in result["sources"]} == {path}
    visible = "\n".join(s["snippet"] for s in result["sources"])
    assert f"{term} records completed progress." in visible
    assert "OtherSetting" not in visible
    plan = build_documentation_query_plan(question, explicit_path=path)
    term_ids = {q.query_id for q in plan.queries if q.origin == "exact_anchor" and q.text == term}
    assert term_ids
    assert term_ids <= set(result["covered_query_ids"])
    assert "query-original" not in result["covered_query_ids"]
    assert len(result["sources"]) <= 3
    assert estimate_projection_tokens(result) <= 800


@pytest.mark.parametrize("content", [
    "# Reference\n\nOtherSetting records completed progress.\n",
    "# meet_type\n\nOtherSetting records completed progress.\n",
    "# Reference\n\nmeet_type_extra records completed progress.\n",
    "# Reference\n\n[meet_type](other.md)\n",
])
def test_exact_path_is_not_topic_evidence(tmp_path, monkeypatch, content):
    path = "docs/REFERENCE.md"
    service, project = _named_document_service(tmp_path, monkeypatch, [path], {path: content})
    monkeypatch.setattr(service.project_docs, "query_project_docs", lambda *a, **kw: [])
    result = call_docs_tool_payload("get_docs_context", {
        "question": f"In {path}, summarize meet_type.", "project_path": project,
    }, service)
    assert result["context_available"] is False, result
    assert not result.get("sources")
    assert result["answer_supported"] is False
