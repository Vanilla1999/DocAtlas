from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docmancer.docs.interfaces.mcp.project_tools import _compact_project_context, handle_project_tool
from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult
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


def test_mcp_project_context_details_stays_compact_without_full_output_opt_in():
    service: Any = type(
        "FakeService",
        (),
        {"get_project_context": lambda self, *args, **kwargs: ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router")},
    )()

    payload = handle_project_tool("get_project_context", {"project_path": "/repo", "question": "use go_router", "details": True}, service)

    assert payload is not None
    assert payload["output_mode"] == "compact"
    assert payload["project_docs"]["results"] == []
    assert payload["warnings"][-1]["code"] == "project_context_full_output_requires_output_mode_full"


def test_mcp_project_context_full_output_requires_explicit_output_mode():
    service: Any = type(
        "FakeService",
        (),
        {"get_project_context": lambda self, *args, **kwargs: ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router")},
    )()

    payload = handle_project_tool("get_project_context", {"project_path": "/repo", "question": "use go_router", "details": True, "output_mode": "full"}, service)

    assert payload is not None
    assert payload["output_mode"] == "full"
    assert payload["project_docs"]["results"]


def test_compact_output_keeps_context_pack_trust_contract_and_outline():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))
    compact = _compact_project_context(result)

    assert compact["context_pack"]
    assert compact["trust_contract"]
    assert compact["answer_outline"]


def test_compact_output_preserves_trust_contract_context_sources(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
class HelpRequestDetailsScreen {
  final label = 'Вернуть в работу';
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API with enough context for stable project-doc selection.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
            )
        ],
        indexed_sources=[{"path": "ARCHITECTURE.md", "source": str(tmp_path / "ARCHITECTURE.md")}],
    )

    result = asdict(ProjectContextService(facade).get_project_context(str(tmp_path), 'Как реализовать кнопку "Вернуть в работу"?', mode="project-only"))
    compact = _compact_project_context(result)

    source_evidence = compact["trust_contract"]["context_sources"]["source_evidence"]
    assert source_evidence[0]["path"] == "lib/help_request_details_screen.dart"
    assert source_evidence[0]["line_start"] == 2
    assert source_evidence[0]["matched_terms"] == ["Вернуть в работу"]


def test_compact_output_exposes_answer_completeness_contract():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API via help_request_details_screen.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            )
        ],
    )
    result = asdict(ProjectContextService(facade).get_project_context("/repo", 'Как реализовать кнопку "Вернуть в работу"?', mode="project-only"))

    compact = _compact_project_context(result)

    assert compact["answer_type"] == "partial_navigational"
    assert compact["answer_completeness"]["status"] == "partial"
    assert compact["answer_completeness"]["missing_terms"] == ["Вернуть в работу"]
    assert compact["recommended_next_actions"][-1]["action"] == "search_project_sources"
