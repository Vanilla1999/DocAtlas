from __future__ import annotations

from docmancer.docs.interfaces.mcp.context_tools import context_tools, handle_context_tool
from docmancer.mcp.docs_server import TOOLS


def test_get_docs_context_registered_in_mcp_tool_list():
    names = [tool["name"] for tool in TOOLS]
    assert "get_docs_context" in names


def test_get_docs_context_schema():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_docs_context")
    schema = tool["inputSchema"]
    assert schema["required"] == ["question"]
    assert "allow_network" in schema["properties"]
    assert schema["properties"]["mode"]["enum"] == ["auto", "project", "library", "dependency", "mixed", None]


def test_get_docs_context_handler_calls_facade():
    class Facade:
        def __init__(self):
            self.called = False

        def get_docs_context(self, question, **kwargs):
            self.called = True
            assert question == "How?"
            assert kwargs["library"] == "fastapi"
            return type("Result", (), {"tool": "get_docs_context", "status": "success"})()

    facade = Facade()
    result = handle_context_tool("get_docs_context", {"question": "How?", "library": "fastapi"}, facade)
    assert facade.called is True
    assert result["tool"] == "get_docs_context"


def test_existing_mcp_tools_unchanged():
    names = {tool["name"] for tool in TOOLS}
    assert {"get_project_context", "get_project_docs", "get_library_docs", "inspect_project_docs", "inspect_library_docs", "refresh_library_docs", "prefetch_project_dependency_docs"}.issubset(names)


def test_context_tools_filter_only_unified_tool():
    assert [tool["name"] for tool in context_tools(TOOLS)] == ["get_docs_context"]
