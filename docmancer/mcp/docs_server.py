"""`doc-atlas mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload, debug_errors_enabled
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.context_tools import context_tools, handle_context_tool
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool, library_tools
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, prefetch_tools
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_docs_context",
        "description": "Return one source-grounded documentation context pack by routing the question to project-owned docs, public library docs, exact dependency docs, or a mixed project-plus-library flow.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "response_style": {"type": ["string", "null"], "enum": ["auto", "snippet-first", "evidence-first", None], "default": "auto", "description": "Choose snippet-first presentation for coding tasks or preserve evidence-first context."},
                "library": {"type": ["string", "null"]},
                "libraries": {"type": ["array", "null"], "items": {"type": "string"}},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "module": {"type": ["string", "null"]},
                "module_path": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None]},
                "mode": {"type": ["string", "null"], "enum": ["auto", "project", "library", "dependency", "mixed", None]},
                "tokens": {"type": ["integer", "null"], "minimum": 1, "maximum": 20000},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "expand": {"type": ["string", "null"]},
                "prepare_project_docs": {"type": ["boolean", "null"]},
                "allow_network": {"type": ["boolean", "null"]},
                "allow_latest_fallback": {"type": ["boolean", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "prefetch_auto": {"type": ["boolean", "null"], "description": "When true, automatically prefetch dependency/library docs from the network without requiring user confirmation."},
                "page": {"type": ["integer", "null"], "minimum": 1, "default": 1},
                "page_size": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "include_sections": {"type": ["array", "null"], "items": {"type": "string", "enum": ["context_pack", "supporting_snippets", "trust_contract", "diagnostics", "metrics"]}},
                "output_mode": {"type": ["string", "null"], "enum": ["answer", "compact", "debug", "full", None], "default": "answer", "description": "answer is the default minimal agent-friendly response; compact includes structured context; debug includes diagnostics; full returns raw output."},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["question"],
        },
    },
    {
        "name": "resolve_library_id",
        "description": "Resolve a documentation library from the local registry or explicit docs_url. Registered sources should be retried through Docmancer with returned candidates/arguments_patch; never WebFetch registered docs before that retry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": ["string", "null"]},
                "libraryName": {"type": ["string", "null"], "description": "Deprecated alias for library; accepted for older MCP clients."},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
            },
            "anyOf": [{"required": ["library"]}, {"required": ["libraryName"]}],
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
                "tokens": {"type": ["integer", "null"], "minimum": 1, "maximum": 20000},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "project_path": {"type": ["string", "null"]},
                "response_style": {"type": ["string", "null"], "enum": ["auto", "snippet-first", "evidence-first", None], "default": "auto", "description": "Choose snippet-first presentation for coding tasks or preserve evidence-first context."},
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
                            "max_pages": {"type": ["integer", "null"], "minimum": 1, "maximum": 500},
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
        "description": """Legacy low-level index operation for discovered project-owned docs files. Prefer sync_project_docs for normal reconcile flows.
This only ingests reviewable local docs candidates such as README, docs/, wiki/, ARCHITECTURE, ADR, and roadmap.
It does not prune orphaned entries and does not ingest source code, dependency directories, build outputs, or dependency docs.
Call inspect_project_docs first only when using this legacy tool intentionally.""",
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
        "description": """Canonical lifecycle action for project-owned docs.
Reconcile the project-docs index with the current repository discovery snapshot: remove orphaned/stale indexed docs, index new or changed reviewable docs, and verify the final index state before reporting counts.""",
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
        "description": """Safely prepare project-owned docs for a repository question.
This tool may inspect project docs, run sync_project_docs to reconcile the project-docs index with current reviewable README/docs/wiki/ARCHITECTURE/ADR files, and inspect again.
It never writes repository files and never fetches dependency docs from the network.
If repo writes or dependency-doc network fetches are needed, it stops with confirmation_required, next_action, and arguments_patch.""",
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
                "tokens": {"type": ["integer", "null"], "minimum": 1, "maximum": 20000},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
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
        "description": """Return one repo-grounded context pack for a coding question after inspect_project_docs, bootstrap_project_docs, or any required sync_project_docs step.
Combines indexed project-owned docs with exact dependency-doc evidence when requested or detectable, and always returns a compact Trust Contract with selected, rejected, and risky sources plus next_actions.
For story-specific implementation questions, inspect answer_type and answer_completeness: partial_navigational means the docs are useful for architecture/source navigation but exact requested terms are missing, so follow recommended_next_actions/code_search before treating the context as a complete answer.
Does not use deleted, orphaned, or stale project-doc content by default.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "question": {"type": "string"},
                "tokens": {"type": ["integer", "null"], "minimum": 1, "maximum": 20000},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "expand": {"type": ["string", "null"]},
                "library": {"type": ["string", "null"]},
                "libraries": {"type": ["array", "null"], "items": {"type": "string"}},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "module": {"type": ["string", "null"]},
                "module_path": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None]},
                "mode": {"type": ["string", "null"], "enum": ["auto", "project-only", "deps-only", "public-docs", None]},
                "response_style": {"type": ["string", "null"], "enum": ["auto", "snippet-first", "evidence-first", None], "default": "auto", "description": "Choose snippet-first presentation for coding tasks or preserve evidence-first context."},
                "allow_network": {"type": ["boolean", "null"], "default": False, "description": "Permit dependency/public docs network fetches. Defaults to false and returns confirmation instead."},
                "page": {"type": ["integer", "null"], "minimum": 1, "default": 1},
                "page_size": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "include_sections": {"type": ["array", "null"], "items": {"type": "string", "enum": ["context_pack", "supporting_snippets", "trust_contract", "diagnostics", "metrics"]}},
                "output_mode": {"type": ["string", "null"], "enum": ["answer", "compact", "debug", "full", None], "default": "answer", "description": "answer is the default minimal agent-friendly response; compact includes structured context; debug includes diagnostics; full returns raw output."},
                "details": {"type": ["boolean", "null"], "description": "Compatibility flag; for get_project_context it does not request full output unless output_mode='full'."},
            },
            "required": ["project_path", "question"],
        },
    },
    {
        "name": "get_patch_constraints",
        "description": "Return compact, source-attributed project constraints for a coding patch. Designed to provide actionable project constraints for coding agents; this does not validate patches or change get_docs_context behavior.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "changed_files": {"type": ["array", "null"], "items": {"type": "string"}},
                "max_constraints": {"type": "integer", "default": 12, "minimum": 1, "maximum": 40},
                "max_tokens": {"type": "integer", "default": 1200, "minimum": 100, "maximum": 8000},
                "include_sources": {"type": "boolean", "default": True},
                "output_mode": {"type": ["string", "null"], "enum": ["compact", "debug", "full", None], "default": "compact"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "validate_patch_against_constraints",
        "description": "Use after editing code to check changed files or a patch diff against constraints returned by get_patch_constraints. This is a deterministic best-effort validator; it does not prove correctness and does not replace tests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "constraints": {"type": ["object", "array"]},
                "project_path": {"type": ["string", "null"]},
                "changed_files": {"type": ["array", "null"], "items": {"type": "string"}},
                "patch_diff": {"type": ["string", "null"]},
                "strict": {"type": "boolean", "default": False},
            },
            "required": ["constraints"],
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
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
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
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
            },
        },
    },
    {
        "name": "prefetch_project_docs",
        "description": "[DEPRECATED] Use prefetch_project_dependency_docs instead. Read a Flutter/Dart/Rust project and prefetch exact dependency documentation from project manifests/lockfiles. May fetch from the network, so ask for confirmation before running.",
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

CONTEXT_TOOLS = context_tools(TOOLS)
LIBRARY_TOOLS = library_tools(TOOLS)
PROJECT_TOOLS = project_tools(TOOLS)
PREFETCH_TOOLS = prefetch_tools(TOOLS)

MCP_RESOURCES: list[dict[str, str]] = [
    {
        "uri": "docmancer://workflow/project-docs",
        "name": "Project docs workflow",
        "description": "Discovery-first workflow for project-owned docs.",
        "mimeType": "text/markdown",
        "text": """# Project docs workflow

1. Call `inspect_project_docs(project_path)` before repo-specific architecture, conventions, runbook, or Context7-like questions.
2. If the response asks for reconciliation, call `sync_project_docs(project_path, with_vectors=true)` before `get_project_context`.
3. Call `get_project_context(project_path, question, output_mode=\"compact\")` and inspect `answer_available`, `answer_type`, `answer_completeness`, and `trust_contract.sources`.
4. Treat `partial_navigational` as navigation/source-search guidance, not a complete answer.
5. Use dependency/public network fetches only with explicit approval (`allow_network=true`).
""",
    },
    {
        "uri": "docmancer://schema/trust-contract",
        "name": "Trust Contract schema",
        "description": "Canonical Trust Contract fields returned by project context tools.",
        "mimeType": "application/json",
        "text": json.dumps({
            "schema_version": "trust-contract-1.1",
            "sources": {"selected": [], "rejected": [], "risky": []},
            "context_sources": {"source_evidence": [], "repo_map": []},
            "warnings": [],
            "next_actions": [],
            "policy": {"direct_webfetch": "forbidden|discovery_only", "reason_code": "trusted_context_available|no_trusted_context"},
        }, ensure_ascii=False, indent=2),
    },
    {
        "uri": "docmancer://workflow/library-docs",
        "name": "Library docs workflow",
        "description": "Registry-first workflow for exact library/dependency docs.",
        "mimeType": "text/markdown",
        "text": """# Library docs workflow

1. Call `resolve_library_id(library, ecosystem, version, source_type)` before using external docs.
2. If the response returns `candidates`, retry through Docmancer with the candidate `arguments_patch` or explicit `docs_url`.
3. Call `get_library_docs(...)` after registration/resolution.
4. If `reason_code=needs_docs_url`, do not WebFetch as a substitute; pass `docs_url` or prefetch/register an explicit docs target.
5. Network ingestion is explicit: use `prefetch_library_docs`, `prefetch_docs_targets`, or a tool response with `allow_network=true` where supported.
""",
    },
]

MCP_RESOURCE_TEMPLATES: list[dict[str, str]] = [
    {
        "uriTemplate": "docmancer://workflow/project-docs/{project_path}",
        "name": "Project-specific docs workflow",
        "description": "Use with a local project_path to guide inspect/sync/get_project_context calls.",
        "mimeType": "text/markdown",
    },
    {
        "uriTemplate": "docmancer://library/{ecosystem}/{library}/{version}",
        "name": "Registered library docs lookup",
        "description": "Guide for resolving and querying exact dependency documentation through Docmancer.",
        "mimeType": "text/markdown",
    },
]


def read_docs_resource(uri: str) -> dict[str, str] | None:
    for resource in MCP_RESOURCES:
        if resource["uri"] == uri:
            return resource
    if uri.startswith("docmancer://workflow/project-docs/"):
        project_path = uri.removeprefix("docmancer://workflow/project-docs/")
        return {
            "uri": uri,
            "name": "Project-specific docs workflow",
            "mimeType": "text/markdown",
            "text": f"""# Project docs workflow for `{project_path}`

1. `inspect_project_docs(project_path=\"{project_path}\")`
2. If required, `sync_project_docs(project_path=\"{project_path}\", with_vectors=true)`
3. `get_project_context(project_path=\"{project_path}\", question=..., output_mode=\"compact\")`
4. Inspect `trust_contract.sources.selected`, `trust_contract.sources.rejected`, and `trust_contract.sources.risky` before using the answer.
""",
        }
    if uri.startswith("docmancer://library/"):
        parts = uri.removeprefix("docmancer://library/").split("/", 2)
        if len(parts) == 3:
            ecosystem, library, version = parts
            return {
                "uri": uri,
                "name": "Registered library docs lookup",
                "mimeType": "text/markdown",
                "text": f"""# Library docs workflow for `{ecosystem}:{library}@{version}`

1. `resolve_library_id(library=\"{library}\", ecosystem=\"{ecosystem}\", version=\"{version}\")`
2. If `status=needs_docs_url`, retry through Docmancer with an explicit `docs_url` or prefetch/register a docs target.
3. `get_library_docs(library=\"{library}\", ecosystem=\"{ecosystem}\", version=\"{version}\", topic=...)`
4. Do not WebFetch registered docs before retrying with returned `candidates` or `arguments_patch`.
""",
            }
    return None


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

    @server.list_resources()
    async def _list_resources() -> list[mcp_types.Resource]:
        return [
            mcp_types.Resource(
                uri=cast(Any, resource["uri"]),
                name=resource["name"],
                description=resource["description"],
                mimeType=resource["mimeType"],
            )
            for resource in MCP_RESOURCES
        ]

    @server.list_resource_templates()
    async def _list_resource_templates() -> list[mcp_types.ResourceTemplate]:
        return [
            mcp_types.ResourceTemplate(
                uriTemplate=template["uriTemplate"],
                name=template["name"],
                description=template["description"],
                mimeType=template["mimeType"],
            )
            for template in MCP_RESOURCE_TEMPLATES
        ]

    @server.read_resource()
    async def _read_resource(uri: Any) -> str:
        resource = read_docs_resource(str(uri))
        if resource is None:
            raise ValueError(f"unknown resource: {uri}")
        return resource["text"]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.TextContent]:
        try:
            args = arguments or {}
            for handler in (handle_context_tool, handle_library_tool, handle_prefetch_tool, handle_project_tool):
                payload = handler(name, args, service)
                if payload is not None:
                    return _json_text(mcp_types, payload)
        except Exception as exc:
            return _json_text(
                mcp_types,
                build_mcp_error_payload(
                    reason_code="unhandled_exception",
                    message=str(exc),
                    exception=exc,
                    tool=name,
                    phase="execution",
                    debug=debug_errors_enabled(arguments or {}),
                ),
            )
        return _json_text(
            mcp_types,
            build_mcp_error_payload(
                reason_code="unknown_tool",
                message=f"unknown tool: {name}",
                tool=name,
                phase="validation",
            ),
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve() -> None:
    asyncio.run(_run_async(LibraryDocsService()))
