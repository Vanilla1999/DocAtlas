from __future__ import annotations

from dataclasses import asdict

from docmancer.docs.interfaces.mcp.project_tools import _compact_project_context
from docmancer.docs.application.project_context_service import ProjectContextService
from tests.docs.test_project_context_service import FakeProjectContextFacade


def test_compact_output_omits_raw_project_docs_results():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))

    compact = _compact_project_context(result)

    assert compact["project_docs"]["omitted"] is True
    assert compact["project_docs"]["results"] == []
    assert compact["project_docs"]["see"] == "context_pack"


def test_full_output_preserves_raw_project_docs_results():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))

    assert result["project_docs"]["results"]


def test_compact_output_keeps_context_pack_trust_contract_and_outline():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))
    compact = _compact_project_context(result)

    assert compact["context_pack"]
    assert compact["trust_contract"]
    assert compact["answer_outline"]
