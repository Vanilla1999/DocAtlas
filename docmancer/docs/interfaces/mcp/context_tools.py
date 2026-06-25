from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from docmancer.docs.service import LibraryDocsService


CONTEXT_TOOL_NAMES = {"get_docs_context"}


def context_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in CONTEXT_TOOL_NAMES]


def handle_context_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name != "get_docs_context":
        return None
    result = service.get_docs_context(
        args["question"],
        project_path=args.get("project_path"),
        library=args.get("library"),
        libraries=args.get("libraries"),
        ecosystem=args.get("ecosystem"),
        version=args.get("version"),
        source_type=args.get("source_type"),
        docs_url=args.get("docs_url"),
        module=args.get("module"),
        module_path=args.get("module_path"),
        scope=args.get("scope"),
        mode=args.get("mode"),
        tokens=args.get("tokens"),
        limit=args.get("limit"),
        expand=args.get("expand"),
        prepare_project_docs=args.get("prepare_project_docs"),
        allow_network=args.get("allow_network"),
        allow_latest_fallback=args.get("allow_latest_fallback"),
        force_refresh=args.get("force_refresh"),
        details=args.get("details"),
    )
    if is_dataclass(result):
        return asdict(result)
    if isinstance(result, dict):
        return result
    payload = dict(getattr(result, "__dict__", {}))
    for key in ("tool", "status", "reason_code", "message"):
        if hasattr(result, key):
            payload[key] = getattr(result, key)
    return payload
