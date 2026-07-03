from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


@dataclass
class Result:
    status: str = "success"
    tool: str = "test"
    answer_available: bool = True
    results: list[dict[str, Any]] = field(default_factory=list)


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def resolve_library(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("resolve_library", args, kwargs))
        return Result(tool="resolve_library_id")

    def get_project_context(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("get_project_context", args, kwargs))
        return Result(tool="get_project_context")

    def get_project_docs(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("get_project_docs", args, kwargs))
        return Result(tool="get_project_docs")

    def get_patch_constraints(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("get_patch_constraints", args, kwargs))
        return Result(tool="get_patch_constraints")

    def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("validate_patch_against_constraints", args, kwargs))
        return Result(tool="validate_patch_against_constraints")

    def get_docs_context(self, *args: Any, **kwargs: Any) -> Result:
        self.calls.append(("get_docs_context", args, kwargs))
        return Result(tool="get_docs_context")


def test_resolve_library_id_accepts_library_name_alias() -> None:
    service = FakeService()

    result = handle_library_tool("resolve_library_id", {"libraryName": "flutter"}, cast(LibraryDocsService, service))

    assert result is not None
    assert result["status"] == "success"
    assert service.calls == [("resolve_library", ("flutter", None, None, None, None, None), {})]


def test_project_context_rejects_whitespace_question_before_service_call() -> None:
    service = FakeService()

    result = handle_project_tool(
        "get_project_context",
        {"project_path": "/repo", "question": "   ", "tokens": 9_999_999, "limit": 100_000},
        cast(LibraryDocsService, service),
    )

    assert result == {"status": "failed", "reason_code": "empty_question", "message": "question must not be empty"}
    assert service.calls == []


def test_project_context_clamps_tokens_and_limit_at_mcp_boundary() -> None:
    service = FakeService()

    result = handle_project_tool(
        "get_project_context",
        {"project_path": "/repo", "question": "architecture", "tokens": 9_999_999, "limit": 100_000},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "success"
    name, args, kwargs = service.calls[0]
    assert name == "get_project_context"
    assert args[:2] == ("/repo", "architecture")
    assert kwargs["tokens"] == 20_000
    assert kwargs["limit"] == 20


def test_get_docs_context_clamps_tokens_and_limit_at_mcp_boundary() -> None:
    service = FakeService()

    result = handle_context_tool(
        "get_docs_context",
        {"question": "riverpod widgets", "tokens": 9_999_999, "limit": 100_000},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "success"
    name, args, kwargs = service.calls[0]
    assert name == "get_docs_context"
    assert args == ("riverpod widgets",)
    assert kwargs["tokens"] == 20_000
    assert kwargs["limit"] == 20


def test_mcp_schemas_expose_hard_bounds_and_library_name_alias() -> None:
    tools = {tool["name"]: tool["inputSchema"] for tool in TOOLS}

    resolve_schema = tools["resolve_library_id"]
    assert "libraryName" in resolve_schema["properties"]
    assert {tuple(item["required"]) for item in resolve_schema["anyOf"]} == {("library",), ("libraryName",)}

    assert tools["get_project_context"]["properties"]["tokens"]["maximum"] == 20_000
    assert tools["get_project_context"]["properties"]["limit"]["maximum"] == 20
    assert tools["get_patch_constraints"]["properties"]["max_constraints"]["maximum"] == 40
    assert tools["get_patch_constraints"]["properties"]["max_tokens"]["maximum"] == 8_000

    target_schema = tools["prefetch_docs_targets"]["properties"]["targets"]["items"]["properties"]
    assert target_schema["max_pages"]["maximum"] == 500
