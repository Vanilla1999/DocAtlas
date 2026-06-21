from __future__ import annotations

from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult
from tests.docs.test_project_context_service import FakeProjectContextFacade


def test_code_symbol_query_does_not_accept_generic_wiki_only_context():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(project_path="/repo", query="classes", results=[ProjectDocsChunk(title="Architecture", content="This project has a documentation server with several responsibilities and architecture layers.", source="/repo/wiki/Architecture.md", url=None, path="wiki/Architecture.md")])

    result = ProjectContextService(facade).get_project_context("/repo", "What classes and functions implement the MCP server?", mode="project-only")

    assert result.answer_available is False
    assert result.reason == "insufficient_code_symbol_evidence"


def test_code_symbol_query_boosts_docs_with_python_file_references():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(project_path="/repo", query="classes", results=[
        ProjectDocsChunk(title="Wiki", content="Generic architecture overview with responsibilities and components.", source="/repo/wiki/Architecture.md", url=None, path="wiki/Architecture.md"),
        ProjectDocsChunk(title="Server implementation", content="docmancer/mcp/docs_server.py defines class DocsServer and def handle_tool for MCP tools.", source="/repo/docs/server.md", url=None, path="docs/server.md"),
    ])

    result = ProjectContextService(facade).get_project_context("/repo", "What classes and functions implement the MCP server?", mode="project-only")

    assert result.answer_available is True
    assert result.context_pack[0]["title"] == "Server implementation"


def test_code_symbol_query_returns_insufficient_evidence_warning_when_no_symbols_found():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(project_path="/repo", query="classes", results=[ProjectDocsChunk(title="Readme", content="The project provides docs tooling and MCP integration with useful documentation workflows.", source="/repo/README.md", url=None, path="README.md")])

    result = ProjectContextService(facade).get_project_context("/repo", "List key files and functions", mode="project-only")

    assert any(warning["code"] == "insufficient_code_symbol_evidence" for warning in result.answer_outline["warnings"])
