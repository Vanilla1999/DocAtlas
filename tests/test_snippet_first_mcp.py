from __future__ import annotations

import pytest

from docmancer.docs.domain.snippets import validate_response_style
from docmancer.docs.models import DocsResult, ProjectContextResult
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.mcp.docs_server import ALL_TOOLS, TOOLS


def tool_schema(name):
    return next(tool for tool in TOOLS if tool["name"] == name)["inputSchema"]


def legacy_tool_schema(name):
    return next(tool for tool in ALL_TOOLS if tool["name"] == name)["inputSchema"]


def test_response_style_is_internal_compatibility_not_public_catalog_cost():
    assert "response_style" not in tool_schema("get_docs_context")["properties"]


def test_response_style_registered_in_get_library_docs_schema():
    assert "response_style" in legacy_tool_schema("get_library_docs")["properties"]


def test_response_style_registered_in_get_project_context_schema():
    assert "response_style" in legacy_tool_schema("get_project_context")["properties"]


def test_invalid_response_style_rejected():
    with pytest.raises(ValueError):
        validate_response_style("snippets")


class FakeService:
    def get_docs_context(self, question, **kwargs):
        return type("Result", (), {"tool": "get_docs_context", "status": "success", "response_style": kwargs.get("response_style")})()

    def get_docs(self, library, **kwargs):
        return DocsResult(
            library_id="python:fastapi@latest:web",
            library=library,
            version="latest",
            topic=kwargs.get("topic"),
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            response_style=kwargs.get("response_style") or "evidence-first",
        )

    def get_project_context(self, project_path, question, **kwargs):
        return ProjectContextResult(project_path=project_path, question=question, response_style=kwargs.get("response_style") or "evidence-first")


def test_existing_calls_without_response_style_remain_valid():
    assert handle_context_tool("get_docs_context", {"question": "How?", "library": "fastapi"}, FakeService())["status"] == "success"


def test_mcp_handlers_pass_response_style():
    assert handle_context_tool("get_docs_context", {"question": "How?", "library": "fastapi", "response_style": "snippet-first"}, FakeService())["response_style"] == "snippet-first"
    assert handle_library_tool("get_library_docs", {"library": "fastapi", "response_style": "snippet-first"}, FakeService())["response_style"] == "snippet-first"
    assert handle_project_tool("get_project_context", {"project_path": "/repo", "question": "How?", "response_style": "snippet-first"}, FakeService())["response_style"] == "snippet-first"
