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
        "description": "Call this first when working inside a repository and the user asks to use Docmancer, asks about project architecture, asks how this repo works, or expects Context7-like docs help. This read-only tool discovers local project docs and exact dependency metadata, then returns recommended next actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "ingest_project_docs",
        "description": "Index discovered project-owned docs files for a repository. This only ingests reviewable local docs candidates such as README, docs/, wiki/, ARCHITECTURE, ADR, and roadmap; it does not ingest source code, dependency directories, or build outputs. Call inspect_project_docs first to show candidates and get user confirmation if required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "skip_known": {"type": ["boolean", "null"]},
                "with_vectors": {"type": ["boolean", "null"]},
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "get_project_docs",
        "description": "Query indexed project-owned docs for one repository using project-scoped filters. Use this before WebFetch or generic library docs for repo-specific architecture, conventions, runbooks, ADRs, README, roadmap, or wiki questions. If docs are missing or not indexed, this returns structured next_actions instead of a generic failure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "query": {"type": "string"},
                "tokens": {"type": ["integer", "null"]},
                "limit": {"type": ["integer", "null"]},
                "expand": {"type": ["string", "null"]},
            },
            "required": ["project_path", "query"],
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
                            args.get("source_type"),
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
                            source_type=args.get("source_type"),
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
                            source_type=args.get("source_type"),
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
                            source_type=args.get("source_type"),
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                            async_=bool(args.get("async") or False),
                        )
                    ),
                )
            if name == "validate_docs_manifest":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.validate_docs_manifest(
                            args["manifest_path"],
                            project_path=args.get("project_path"),
                            targets=args.get("targets"),
                        )
                    ),
                )
            if name == "prefetch_docs_manifest":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.prefetch_docs_manifest(
                            args["manifest_path"],
                            project_path=args.get("project_path"),
                            targets=args.get("targets"),
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                            async_=bool(args.get("async") or False),
                        )
                    ),
                )
            if name == "prefetch_docs_targets":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.prefetch_docs_targets(
                            args.get("targets") or [],
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                            async_=bool(args.get("async") or False),
                        )
                    ),
                )
            if name == "inspect_project_docs":
                return _json_text(mcp_types, asdict(service.inspect_project_docs(args["project_path"])))
            if name == "ingest_project_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.ingest_project_docs(
                            args["project_path"],
                            skip_known=bool(args.get("skip_known") if args.get("skip_known") is not None else True),
                            with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True),
                        )
                    ),
                )
            if name == "get_project_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.get_project_docs(
                            args["project_path"],
                            args["query"],
                            tokens=args.get("tokens"),
                            limit=args.get("limit"),
                            expand=args.get("expand"),
                        )
                    ),
                )
            if name == "get_docs_job_status":
                job = service.get_docs_job_status(args["job_id"])
                if job is None:
                    return _json_text(mcp_types, {"job_id": args["job_id"], "status": "not_found"})
                return _json_text(mcp_types, asdict(job))
            if name == "list_docs_jobs":
                jobs = service.list_docs_jobs(status=args.get("status"), limit=args.get("limit"))
                return _json_text(
                    mcp_types,
                    {
                        "jobs": [
                            {
                                "job_id": job.job_id,
                                "kind": job.kind,
                                "status": job.status,
                                "phase": job.phase,
                                "message": job.message,
                                "started_at": job.started_at,
                                "updated_at": job.updated_at,
                            }
                            for job in jobs
                        ]
                    },
                )
            if name == "cancel_docs_job":
                return _json_text(mcp_types, asdict(service.cancel_docs_job(args["job_id"])))
            if name == "inspect_library_docs":
                return _json_text(mcp_types, asdict(service.inspect_library_docs(args["canonical_id"])))
            if name == "remove_library_docs":
                return _json_text(mcp_types, asdict(service.remove_library_docs(args["canonical_id"])))
            if name == "prune_library_docs":
                return _json_text(
                    mcp_types,
                    asdict(
                        service.prune_library_docs(
                            library=args.get("library"),
                            keep_versions=args.get("keep_versions") or [],
                            older_than_days=int(args.get("older_than_days") or 90),
                            dry_run=bool(args.get("dry_run") if args.get("dry_run") is not None else True),
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
                            include_rust=bool(
                                args.get("include_rust")
                                if args.get("include_rust") is not None
                                else True
                            ),
                            include_packages=args.get("include_packages") or [],
                            force_refresh=bool(args.get("force_refresh") or False),
                            continue_on_error=bool(
                                args.get("continue_on_error")
                                if args.get("continue_on_error") is not None
                                else True
                            ),
                            async_=bool(args.get("async") or False),
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
