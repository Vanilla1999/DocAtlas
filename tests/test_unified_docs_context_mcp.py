from __future__ import annotations

import json

from docmancer.docs.interfaces.mcp.context_tools import context_tools, handle_context_tool
from docmancer.docs.interfaces.mcp.project_tools import MCP_COMPACT_OUTPUT_MAX_BYTES
from docmancer.docs.models import UnifiedDocsContextResult
from docmancer.mcp.docs_server import TOOLS


def test_get_docs_context_registered_in_mcp_tool_list():
    names = [tool["name"] for tool in TOOLS]
    assert "get_docs_context" in names


def test_get_docs_context_schema():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_docs_context")
    schema = tool["inputSchema"]
    assert schema["required"] == ["question"]
    assert "allow_network" in schema["properties"]
    assert schema["properties"]["output_mode"]["enum"] == ["answer", "compact", "debug", "full", None]
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


def test_get_docs_context_default_answer_reports_compaction_without_debug_noise():
    large = "x" * 120_000

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return UnifiedDocsContextResult(
                question=question,
                context_pack=[{"doc_scope": "project", "path": "docs/ScanDoc.md", "content": large}],
                trust_contract={"selected": [{"path": "docs/ScanDoc.md", "snippet": large}], "rejected": [], "risky": []},
            )

    result = handle_context_tool("get_docs_context", {"question": "find current web API camera implementation", "project_path": "/repo"}, Facade())

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert result["output_mode"] == "answer"
    assert result["response_truncated"] is True
    assert result["mcp_compaction"]["truncated"] is True
    assert "context_pack" not in result
    assert any(isinstance(warning, dict) and warning.get("code") == "mcp_response_truncated" for warning in result.get("warnings", []))
    assert not any(isinstance(warning, dict) and str(warning.get("code") or "").startswith("mcp_compact_output_") for warning in result.get("warnings", []))


def test_get_docs_context_debug_output_keeps_compaction_diagnostics():
    large = "x" * 120_000

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return UnifiedDocsContextResult(
                question=question,
                context_pack=[{"doc_scope": "project", "path": "docs/ScanDoc.md", "content": large}],
                trust_contract={"selected": [{"path": "docs/ScanDoc.md", "snippet": large}], "rejected": [], "risky": []},
            )

    result = handle_context_tool("get_docs_context", {"question": "find current web API camera implementation", "project_path": "/repo", "output_mode": "debug"}, Facade())

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert result["mcp_compaction"]["truncated"] is True
