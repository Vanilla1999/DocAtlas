"""Exact indexed sections retain real lookup attribution without answer proof."""
from __future__ import annotations

import pytest

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests.test_named_document_context_integration import _named_document_service


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
