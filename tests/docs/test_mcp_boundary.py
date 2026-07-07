from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, cast

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.models import LibraryInfo
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


@dataclass
class SubService:
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    def record(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> Any:
        self.calls.append((method, args, kwargs))
        return result

    def resolve_library(self, *args: Any, **kwargs: Any) -> Any:
        info = LibraryInfo(library_id="flutter/stable", library="flutter", ecosystem="dart", version="stable", status="success", source_id="test-flutter")
        return self.record("resolve_library", args, kwargs, info)

    def get_project_context(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("get_project_context", args, kwargs, _make_dataclass_result("get_project_context"))

    def get_docs_context(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("get_docs_context", args, kwargs, _make_result("get_docs_context"))

    def inspect_project_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("inspect_project_docs", args, kwargs, _make_result("inspect_project_docs"))

    def sync_project_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("sync_project_docs", args, kwargs, _make_result("sync_project_docs"))

    def get_project_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("get_project_docs", args, kwargs, _make_result("get_project_docs"))

    def get_patch_constraints(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("get_patch_constraints", args, kwargs, _make_dataclass_result("get_patch_constraints"))

    def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("validate_patch_against_constraints", args, kwargs, _make_dataclass_result("validate_patch_against_constraints"))

    def prefetch_project_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("prefetch_project_docs", args, kwargs, _make_dataclass_result("prefetch_project_docs"))

    def prefetch_project_dependency_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("prefetch_project_dependency_docs", args, kwargs, _make_dataclass_result("prefetch_project_dependency_docs"))

    def get_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("get_docs", args, kwargs, _make_result("get_library_docs"))

    def inspect_library_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("inspect_library_docs", args, kwargs, _make_result("inspect_library_docs"))

    def remove_library_docs(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("remove_library_docs", args, kwargs, _make_result("remove_library_docs"))

    def list_libraries(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("list_libraries", args, kwargs, _make_result("list_library_docs"))

    def prefetch_docs_targets(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("prefetch_docs_targets", args, kwargs, _make_result("prefetch_docs_targets"))

    def validate_docs_manifest(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("validate_docs_manifest", args, kwargs, _make_result("validate_docs_manifest"))

    def prefetch_docs_manifest(self, *args: Any, **kwargs: Any) -> Any:
        return self.record("prefetch_docs_manifest", args, kwargs, _make_result("prefetch_docs_manifest"))


def _make_result(tool: str) -> dict[str, Any]:
    return {
        "status": "success",
        "tool": tool,
        "answer_available": True,
        "results": [],
        "context_pack": [],
        "trust_contract": {"sources": {"selected": []}},
    }


def _make_dataclass_result(tool: str) -> Any:
    return _MockDataclass(tool=tool, status="success", answer_available=True, results=[], context_pack=[], trust_contract={"sources": {"selected": []}})


@dataclass
class _MockDataclass:
    tool: str
    status: str
    answer_available: bool
    results: list
    context_pack: list
    trust_contract: dict


class FakeService:
    def __init__(self) -> None:
        self.library_docs = SubService()
        self.project_docs = SubService()
        self.project_context = SubService()
        self.patch_constraints = SubService()
        self.patch_constraint_validation = SubService()
        self.dependency_docs = SubService()
        self.unified_context = SubService()
        self.docs_targets = SubService()
        self.docs_prefetch = SubService()
        self.docs_manifest = SubService()


def test_resolve_library_id_accepts_library_name_alias() -> None:
    service = FakeService()

    result = handle_library_tool("resolve_library_id", {"libraryName": "flutter"}, cast(LibraryDocsService, service))

    assert result is not None
    assert result["status"] == "success"
    assert service.library_docs.calls == [
        ("resolve_library", ("flutter", None, None, None, None, None), {})
    ]


def test_project_context_rejects_whitespace_question_before_service_call() -> None:
    service = FakeService()

    result = handle_project_tool(
        "get_project_context",
        {"project_path": "/repo", "question": "   ", "tokens": 9_999_999, "limit": 100_000},
        cast(LibraryDocsService, service),
    )

    assert result["status"] == "failed"
    assert result["reason_code"] == "empty_question"
    assert service.project_context.calls == []


def test_project_context_clamps_tokens_and_limit_at_mcp_boundary() -> None:
    service = FakeService()

    result = handle_project_tool(
        "get_project_context",
        {"project_path": "/repo", "question": "architecture", "tokens": 9_999_999, "limit": 100_000},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "success"
    name, args, kwargs = service.project_context.calls[0]
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
    name, args, kwargs = service.unified_context.calls[0]
    assert name == "get_docs_context"
    assert args == ("riverpod widgets",)
    assert kwargs["tokens"] == 20_000
    assert kwargs["limit"] == 20


def test_get_docs_context_rejects_whitespace_question_with_hint() -> None:
    service = FakeService()

    result = handle_context_tool(
        "get_docs_context",
        {"question": "   ", "library": "riverpod"},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "failed"
    assert result["reason_code"] == "empty_question"
    assert result["error"]["hints"] == [
        "Provide a non-empty question, for example: 'Flutter Riverpod providers' or 'FastAPI dependency injection'."
    ]
    assert service.unified_context.calls == []


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


def test_prefetch_project_docs_deprecated_alias_returns_warning() -> None:
    service = FakeService()

    result = handle_project_tool(
        "prefetch_project_docs",
        {"project_path": "/tmp/test"},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "success"
    warnings = result.get("warnings") or []
    assert any(w.get("code") == "deprecated_tool_alias" for w in warnings)


def test_prefetch_project_dependency_docs_canonical_no_warning() -> None:
    service = FakeService()

    result = handle_project_tool(
        "prefetch_project_dependency_docs",
        {"project_path": "/tmp/test"},
        cast(LibraryDocsService, service),
    )

    assert result is not None
    assert result["status"] == "success"
    warnings = result.get("warnings") or []
    assert not any(w.get("code") == "deprecated_tool_alias" for w in warnings)
