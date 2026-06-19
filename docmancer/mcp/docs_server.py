"""`docmancer mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool, library_tools
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, prefetch_tools
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools


TOOLS: list[dict[str, Any]] = [
    {
        "name": "resolve_library_id",
        "description": "Resolve a documentation library from the local registry or explicit docs_url. Registered sources should be retried through Docmancer with returned candidates/arguments_patch; never WebFetch registered docs before that retry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
            },
            "required": ["library"],
        },
    },
    {
        "name": "get_library_docs",
        "description": "Resolve from the local registry, ingest or refresh if needed, then query local documentation. Registered sources do not require docs_url on later calls. If working inside a repository or answering repo-specific architecture/implementation questions, call inspect_project_docs first so Docmancer can discover local project docs and exact dependency metadata. If candidates or next_actions are returned, retry through Docmancer with the supplied arguments_patch; never WebFetch registered docs before that retry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string"},
                "topic": {"type": ["string", "null"]},
                "tokens": {"type": ["integer", "null"]},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
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
                "source_type": {"type": ["string", "null"]},
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
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
            },
            "required": ["library"],
        },
    },


    {
        "name": "validate_docs_manifest",
        "description": "Validate a docmancer.docs.yaml manifest without fetching documentation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest_path": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "targets": {"type": ["array", "null"], "items": {"type": "string"}},
            },
            "required": ["manifest_path"],
        },
    },
    {
        "name": "prefetch_docs_manifest",
        "description": "Validate and prefetch documentation targets declared in docmancer.docs.yaml.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest_path": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "targets": {"type": ["array", "null"], "items": {"type": "string"}},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
            },
            "required": ["manifest_path"],
        },
    },
    {
        "name": "prefetch_docs_targets",
        "description": "Download and index one or more explicit documentation targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "library": {"type": "string"},
                            "ecosystem": {"type": ["string", "null"]},
                            "version": {"type": ["string", "null"]},
                            "source_type": {"type": ["string", "null"]},
                            "docs_url": {"type": ["string", "null"]},
                            "docs_url_template": {"type": ["string", "null"]},
                            "seed_urls": {"type": ["array", "null"], "items": {"type": "string"}},
                            "allowed_domains": {"type": ["array", "null"], "items": {"type": "string"}},
                            "path_prefixes": {"type": ["array", "null"], "items": {"type": "string"}},
                            "max_pages": {"type": ["integer", "null"]},
                            "browser": {"type": ["boolean", "null"]},
                            "doc_format": {"type": ["string", "null"]},
                            "warnings": {"type": ["array", "null"], "items": {"type": "string"}},
                        },
                        "required": ["library"],
                    },
                },
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
            },
            "required": ["targets"],
        },
    },

    {
        "name": "inspect_project_docs",
        "description": "Call this first when working inside a repository and the user asks to use Docmancer, asks about project architecture, asks how this repo works, or expects Context7-like docs help. This read-only tool discovers local project docs and exact dependency metadata, then returns reason_code, next_action, arguments_patch, and any required user confirmation. Follow next_action before generic code search, public docs, or WebFetch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "ingest_project_docs",
        "description": "Legacy low-level index operation for discovered project-owned docs files. Prefer sync_project_docs for normal reconcile flows. This only ingests reviewable local docs candidates such as README, docs/, wiki/, ARCHITECTURE, ADR, and roadmap; it does not prune orphaned entries and does not ingest source code, dependency directories, build outputs, or dependency docs. Call inspect_project_docs first to show candidates and get user confirmation if required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "skip_known": {"type": ["boolean", "null"]},
                "with_vectors": {"type": ["boolean", "null"]},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "sync_project_docs",
        "description": "Reconcile project-owned docs index with the current repository discovery snapshot. Removes stale and orphaned indexed project-doc sources, indexes new or changed reviewable docs, and verifies the final index state before reporting counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "with_vectors": {"type": ["boolean", "null"]},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "bootstrap_project_docs",
        "description": "Safely prepare project-owned docs for a repository question. This tool may inspect project docs and ingest/refresh existing reviewable README/docs/wiki/ARCHITECTURE/ADR files, but it never writes repository files and never fetches dependency docs from the network. If repo writes or dependency-doc network fetches are needed, it stops with confirmation_required, next_action, and arguments_patch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "question": {"type": ["string", "null"]},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "get_project_docs",
        "description": "Query indexed project-owned docs for one repository using project-scoped filters. Use this before WebFetch or generic library docs for repo-specific architecture, conventions, runbooks, ADRs, README, roadmap, or wiki questions. If docs are missing, stale, not indexed, or do not match, this returns structured reason_code, next_action, next_actions, and arguments_patch instead of a generic failure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "query": {"type": "string"},
                "tokens": {"type": ["integer", "null"]},
                "limit": {"type": ["integer", "null"]},
                "expand": {"type": ["string", "null"]},
                "module": {"type": ["string", "null"]},
                "module_path": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None]},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "get_project_context",
        "description": "Return one repo-grounded context pack for a coding question after inspect_project_docs and any required sync_project_docs step. Combines indexed project-owned docs with one exact dependency docs source when requested/detectable, and always returns a compact Trust Contract with selected, rejected, and risky sources plus next_actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "question": {"type": "string"},
                "tokens": {"type": ["integer", "null"]},
                "limit": {"type": ["integer", "null"]},
                "expand": {"type": ["string", "null"]},
                "library": {"type": ["string", "null"]},
                "libraries": {"type": ["array", "null"], "items": {"type": "string"}},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "module": {"type": ["string", "null"]},
                "module_path": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None]},
                "mode": {"type": ["string", "null"], "enum": ["auto", "project-only", "deps-only", "public-docs", None]},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["project_path", "question"],
        },
    },
    {
        "name": "get_docs_job_status",
        "description": "Return persistent progress for one docs indexing/prefetch job.",
        "inputSchema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "list_docs_jobs",
        "description": "List docs indexing/prefetch jobs, optionally filtered by status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"]},
            },
        },
    },
    {
        "name": "cancel_docs_job",
        "description": "Request cancellation for a docs indexing/prefetch job.",
        "inputSchema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        },
    },

    {
        "name": "inspect_library_docs",
        "description": "Inspect one exact documentation target by canonical id.",
        "inputSchema": {
            "type": "object",
            "properties": {"canonical_id": {"type": "string"}},
            "required": ["canonical_id"],
        },
    },
    {
        "name": "remove_library_docs",
        "description": "Remove one exact documentation target by canonical id.",
        "inputSchema": {
            "type": "object",
            "properties": {"canonical_id": {"type": "string"}},
            "required": ["canonical_id"],
        },
    },
    {
        "name": "prune_library_docs",
        "description": "Prune old documentation targets with dry-run support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": ["string", "null"]},
                "keep_versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "older_than_days": {"type": ["integer", "null"]},
                "dry_run": {"type": ["boolean", "null"]},
            },
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
        "description": "Read a Flutter/Dart/Rust project and prefetch exact dependency documentation from project manifests/lockfiles. This is for dependency docs, not project-owned README/docs/wiki files; call inspect_project_docs first to discover local project docs. May fetch from the network, so ask for confirmation before running unless the user already approved dependency docs prefetch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "include_flutter": {"type": ["boolean", "null"]},
                "include_dart": {"type": ["boolean", "null"]},
                "include_rust": {"type": ["boolean", "null"]},
                "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "prefetch_project_dependency_docs",
        "description": "Alias for prefetch_project_docs with clearer naming. Read a Flutter/Dart/Rust project and prefetch exact dependency documentation from project manifests/lockfiles. This is for dependency docs, not project-owned README/docs/wiki files. May fetch from the network, so ask for confirmation before running unless the user already approved dependency docs prefetch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "include_flutter": {"type": ["boolean", "null"]},
                "include_dart": {"type": ["boolean", "null"]},
                "include_rust": {"type": ["boolean", "null"]},
                "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
                "force_refresh": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
]

LIBRARY_TOOLS = library_tools(TOOLS)
PROJECT_TOOLS = project_tools(TOOLS)
PREFETCH_TOOLS = prefetch_tools(TOOLS)


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
            for handler in (handle_library_tool, handle_prefetch_tool, handle_project_tool):
                payload = handler(name, args, service)
                if payload is not None:
                    return _json_text(mcp_types, payload)
        except Exception as exc:
            return _json_text(mcp_types, {"status": "failed", "message": str(exc)})
        return _json_text(mcp_types, {"status": "failed", "message": f"unknown tool: {name}"})

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve() -> None:
    asyncio.run(_run_async(LibraryDocsService()))
