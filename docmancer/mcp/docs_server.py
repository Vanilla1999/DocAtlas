"""`docmancer mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from docmancer.docs.service import LibraryDocsService


TOOLS: list[dict[str, Any]] = [
    {
        "name": "resolve_library_id",
        "description": "Resolve a documentation library from the local registry or explicit docs_url.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
            },
            "required": ["library"],
        },
    },
    {
        "name": "get_library_docs",
        "description": "Ingest or refresh a library if needed, then query its local documentation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "topic": {"type": ["string", "null"]},
                "tokens": {"type": ["integer", "null"]},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "project_path": {"type": ["string", "null"]},
            },
            "required": ["library"],
        },
    },
    {
        "name": "refresh_library_docs",
        "description": "Refresh one documentation library/version. For ahead-of-time multi-version indexing, prefer prefetch_library_docs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "force": {"type": ["boolean", "null"]},
            },
            "required": ["library"],
        },
    },
    {
        "name": "prefetch_library_docs",
        "description": "Download and index documentation for one or more versions ahead of time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "ecosystem": {"type": ["string", "null"]},
                "versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
            },
            "required": ["library"],
        },
    },
    {
        "name": "list_library_docs",
        "description": "List locally registered documentation libraries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stale_only": {"type": ["boolean", "null"]},
                "limit": {"type": ["integer", "null"]},
            },
        },
    },
    {
        "name": "prefetch_project_docs",
        "description": "Read a Flutter/Dart project and prefetch docs for selected dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "include_flutter": {"type": ["boolean", "null"]},
                "include_dart": {"type": ["boolean", "null"]},
                "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
]


def _json_text(mcp_types: Any, payload: dict[str, Any]) -> list[Any]:
    return [mcp_types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


async def _run_async(service: LibraryDocsService) -> None:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as mcp_types

    server: Server = Server("docmancer-docs")

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(name=tool["name"], description=tool["description"], inputSchema=tool["inputSchema"])
            for tool in TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.TextContent]:
        try:
            args = arguments or {}
            if name == "resolve_library_id":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.resolve_library(
                            args["library"],
                            args.get("ecosystem"),
                            args.get("version"),
                            args.get("docs_url"),
                            args.get("docs_url_template"),
                        )
                    ),
                )
            if name == "get_library_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.get_docs(
                            args["library"],
                            topic=args.get("topic"),
                            tokens=args.get("tokens"),
                            ecosystem=args.get("ecosystem"),
                            version=args.get("version"),
                            docs_url=args.get("docs_url"),
                            docs_url_template=args.get("docs_url_template"),
                            force_refresh=bool(args.get("force_refresh") or False),
                            project_path=args.get("project_path"),
                        )
                    ),
                )
            if name == "refresh_library_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.refresh_docs(
                            args["library"],
                            ecosystem=args.get("ecosystem"),
                            version=args.get("version"),
                            docs_url=args.get("docs_url"),
                            versions=args.get("versions"),
                            docs_url_template=args.get("docs_url_template"),
                            force=bool(args.get("force") if args.get("force") is not None else True),
                        )
                    ),
                )
            if name == "prefetch_library_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.prefetch_docs(
                            args["library"],
                            ecosystem=args.get("ecosystem"),
                            versions=args.get("versions"),
                            docs_url=args.get("docs_url"),
                            docs_url_template=args.get("docs_url_template"),
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                        )
                    ),
                )
            if name == "list_library_docs":
                libraries = service.list_libraries(
                    stale_only=bool(args.get("stale_only") or False),
                    limit=args.get("limit"),
                )
                return _json_text(mcp_types, {"libraries": [asdict(item) for item in libraries]})
            if name == "prefetch_project_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.prefetch_project_docs(
                            args["project_path"],
                            include_flutter=bool(
                                args.get("include_flutter")
                                if args.get("include_flutter") is not None
                                else True
                            ),
                            include_dart=bool(args.get("include_dart") or False),
                            include_packages=args.get("include_packages") or [],
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                        )
                    ),
                )
        except Exception as exc:
            return _json_text(mcp_types, {"status": "failed", "message": str(exc)})
        return _json_text(mcp_types, {"status": "failed", "message": f"unknown tool: {name}"})

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve() -> None:
    asyncio.run(_run_async(LibraryDocsService()))
