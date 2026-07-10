"""`doc-atlas mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping, cast

from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload, debug_errors_enabled
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.context_tools import context_tools, handle_context_tool
from docmancer.docs.interfaces.mcp.docs_tools import handle_library_tool, library_tools
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool, prefetch_tools
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools

ToolHandler = Callable[[str, dict[str, Any], LibraryDocsService], dict[str, Any] | None]


@dataclass(frozen=True)
class DocsServerConfig:
    expose_legacy: bool = False
    expose_admin: bool = False
    expose_advanced: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "DocsServerConfig":
        return cls(
            expose_legacy=env.get("DOCMANCER_MCP_LEGACY_TOOLS") == "1",
            expose_admin=env.get("DOCMANCER_MCP_ADMIN_TOOLS") == "1",
            expose_advanced=env.get("DOCMANCER_MCP_ADVANCED_TOOLS") == "1",
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def to_tool_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "inputSchema": copy.deepcopy(self.input_schema)}


@dataclass(frozen=True)
class DocsMcpSurface:
    tools: tuple[ToolSpec, ...]
    handlers: Mapping[str, ToolHandler]


RAW_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_docs_context",
        "description": """Default first tool for every documentation, repository, dependency, API, architecture, convention, and source-grounding question.

Agent workflow:
- Call get_docs_context first. It performs safe project preflight internally.
- For coding/API questions, set response_style=\"snippet-first\".
- Call prepare_docs only when this response explicitly returns it as next_action.
- Use docs_status only for explicit health, freshness, source-state, or job-status requests.
- If answer_type is navigation_only or partial_navigational, do not answer yet; read/search the suggested files first.
- This tool provides source-grounded context, not a full code audit or test substitute.
""",
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
                "prepare_project_docs": {"type": ["boolean", "null"], "default": False, "description": "Compatibility opt-in for automatic local bootstrap. The public default is read-only preflight; follow a returned prepare_docs action instead."},
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
        "name": "prepare_docs",
        "description": """Unified confirmation-first lifecycle/admin tool for docs preparation: sync project docs, prefetch dependency/library/manifest/target docs, refresh, prune, or remove registered docs sources.

Agent workflow:
- Use prepare_docs only after get_docs_context returns prepare_docs as next_action, or when the user explicitly asks to sync, refresh, prefetch, prune, or remove docs.
- Use prepare_docs(action=\"prefetch_library_docs\") for public/dependency docs only after network access is approved.
- Prefer this over separate ingest/sync/prefetch/refresh/prune/remove tools.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["sync_project_docs", "prefetch_project_dependency_docs", "prefetch_library_docs", "prefetch_docs_targets", "validate_docs_manifest", "prefetch_docs_manifest", "refresh_library_docs", "prune_library_docs", "remove_library_docs", "cancel_docs_job"]},
                "project_path": {"type": ["string", "null"]},
                "library": {"type": ["string", "null"]},
                "canonical_id": {"type": ["string", "null"]},
                "manifest_path": {"type": ["string", "null"]},
                "job_id": {"type": ["string", "null"]},
                "targets": {"type": ["array", "null"]},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "include_flutter": {"type": ["boolean", "null"]},
                "include_dart": {"type": ["boolean", "null"]},
                "include_rust": {"type": ["boolean", "null"]},
                "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
                "with_vectors": {"type": ["boolean", "null"]},
                "force_refresh": {"type": ["boolean", "null"]},
                "force": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
                "keep_versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "older_than_days": {"type": ["integer", "null"]},
                "dry_run": {"type": ["boolean", "null"], "default": True},
            },
            "required": ["action"],
        },
    },
    {
        "name": "docs_status",
        "description": """Read-only diagnostics for project documentation freshness and asynchronous documentation jobs.

Use this only when the user explicitly asks whether docs are indexed/stale/healthy, wants job progress, or needs diagnostics. For documentation content or coding questions, use get_docs_context instead.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["project", "jobs", "job"]},
                "project_path": {"type": ["string", "null"]},
                "job_id": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
                "details": {"type": ["boolean", "null"]},
            },
            "required": ["action"],
        },
    },
    {
        "name": "docs_job",
        "description": "Unified async docs job manager. Use action='list', 'status', or 'cancel' for jobs started by prepare_docs(..., async=true).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "status", "cancel"]},
                "job_id": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
            },
            "required": ["action"],
        },
    },
    {
        "name": "list_docs_sources",
        "description": "Admin/debug source-health view for locally registered docs sources. Normal answer flows should use get_docs_context; use this for failed/stale library-doc diagnostics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": ["string", "null"], "enum": ["library", "all", None], "default": "library"},
                "canonical_id": {"type": ["string", "null"]},
                "stale_only": {"type": ["boolean", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
            },
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
        "description": """Call this first inside a repository when the user asks about project architecture, repo conventions, implementation workflow, dependency docs, or Context7-like help.

This is read-only. It discovers local docs and exact dependency metadata, then returns reason_code, next_action, arguments_patch, and confirmation requirements.

Agents must follow next_action before generic code search, public docs, or WebFetch.
""",
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
        "name": "get_code_context",
        "description": """Find relevant local source files, extract real code snippets, follow name-based references for a few hops, and return an answer-ready source context pack.

Agent workflow: call inspect_project_docs(project_path) first for repo/documentation state; then use get_code_context for implementation/source-navigation questions. If safe_to_answer=true, answer only from returned snippets and cite file paths and line ranges. If answer_type=navigation_only, read/search files_to_read and search_queries before answering.

This is language-agnostic heuristic retrieval over local source. It is not an LSP, AST-perfect analyzer, call graph, patch validator, or test substitute.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project_path": {"type": "string"},
                "changed_files": {"type": ["array", "null"], "items": {"type": "string"}},
                "entry_symbols": {"type": ["array", "null"], "items": {"type": "string"}},
                "max_hops": {"type": ["integer", "null"], "minimum": 0, "maximum": 4, "default": 2},
                "max_files": {"type": ["integer", "null"], "minimum": 1, "maximum": 50, "default": 12},
                "max_snippets": {"type": ["integer", "null"], "minimum": 1, "maximum": 40, "default": 20},
                "max_lines_per_snippet": {"type": ["integer", "null"], "minimum": 10, "maximum": 200, "default": 80},
                "output_mode": {"type": ["string", "null"], "enum": ["answer", "compact", "debug", "full", None], "default": "answer"},
            },
            "required": ["question", "project_path"],
        },
    },
    {
        "name": "get_patch_plan_context",
        "description": """Use for coding changes after docs lookup: return a Patch Planning Context implementation map from concrete intent to exact source/dependency evidence, changed_files, missing symbols, minimal patch path, risks, and verification.

Agent workflow: inspect_project_docs -> prepare_docs(sync_project_docs if requested) -> get_docs_context for docs -> get_patch_plan_context for source/API map -> get_patch_constraints before editing -> validate_patch_against_constraints after editing -> run tests.

This tool does not generate code, validate patches, run tests, or perform a full audit.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "changed_files": {"type": ["array", "null"], "items": {"type": "string"}},
                "symbol_queries": {"type": ["array", "null"], "items": {"type": "string"}},
                "design_context": {"type": ["object", "null"]},
                "include_dependency_source": {"type": ["boolean", "null"], "default": True},
                "max_files": {"type": ["integer", "null"], "minimum": 1, "maximum": 50, "default": 12},
                "max_snippets": {"type": ["integer", "null"], "minimum": 1, "maximum": 40, "default": 16},
                "max_tokens": {"type": ["integer", "null"], "minimum": 200, "maximum": 12000, "default": 2400},
                "output_mode": {"type": ["string", "null"], "enum": ["compact", "debug", "full", None], "default": "compact"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_patch_constraints",
        "description": """Use immediately before editing code to get source-attributed constraints for a patch.

This is not a code auditor, patch planner, patch validator, static analyzer, or test substitute.
For audits, use Docmancer for context, then run/read/search/analyze code separately.
""",
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
        "description": """Use after editing code: check changed_files or patch_diff against constraints returned by get_patch_constraints.

Treat unknown/manual_review as requiring human/code review. This deterministic best-effort check is not a code auditor, static analyzer, proof of correctness, or test substitute.
Run the relevant tests/linters after this tool.
""",
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

LEGACY_TOOL_NAMES = {
    "resolve_library_id",
    "get_library_docs",
    "refresh_library_docs",
    "prefetch_library_docs",
    "validate_docs_manifest",
    "prefetch_docs_manifest",
    "prefetch_docs_targets",
    "ingest_project_docs",
    "sync_project_docs",
    "bootstrap_project_docs",
    "get_project_docs",
    "get_project_context",
    "get_docs_job_status",
    "list_docs_jobs",
    "cancel_docs_job",
    "prefetch_project_docs",
    "prefetch_project_dependency_docs",
}
ADMIN_TOOL_NAMES = {
    "inspect_library_docs",
    "remove_library_docs",
    "prune_library_docs",
    "list_library_docs",
    "list_docs_sources",
}
ADVANCED_TOOL_NAMES = {
    "inspect_project_docs",
    "docs_job",
    "get_code_context",
    "get_patch_plan_context",
    "get_patch_constraints",
    "validate_patch_against_constraints",
}
PUBLIC_TOOL_NAMES = {"get_docs_context", "prepare_docs", "docs_status"}
CLASSIFIED_TOOL_NAMES = PUBLIC_TOOL_NAMES | ADVANCED_TOOL_NAMES | ADMIN_TOOL_NAMES | LEGACY_TOOL_NAMES


def _handler_for_tool(name: str) -> ToolHandler:
    if name in {tool["name"] for tool in context_tools(RAW_TOOLS)}:
        return handle_context_tool
    if name in {tool["name"] for tool in library_tools(RAW_TOOLS)}:
        return handle_library_tool
    if name in {tool["name"] for tool in prefetch_tools(RAW_TOOLS)}:
        return handle_prefetch_tool
    if name in {tool["name"] for tool in project_tools(RAW_TOOLS)}:
        return handle_project_tool
    raise ValueError(f"No MCP docs handler registered for tool: {name}")


def _strip_null_enum_values(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {key: _strip_null_enum_values(child) for key, child in value.items()}
        if "enum" in cleaned and isinstance(cleaned["enum"], list):
            cleaned["enum"] = [item for item in cleaned["enum"] if item is not None]
        return cleaned
    if isinstance(value, list):
        return [_strip_null_enum_values(item) for item in value]
    return value


def _tool_spec(raw: dict[str, Any]) -> ToolSpec:
    name = str(raw["name"])
    return ToolSpec(
        name=name,
        description=str(raw["description"]),
        input_schema=_strip_null_enum_values(copy.deepcopy(raw["inputSchema"])),
        handler=_handler_for_tool(name),
    )


def build_docs_surface(config: DocsServerConfig) -> DocsMcpSurface:
    specs: list[ToolSpec] = []
    for raw in RAW_TOOLS:
        name = str(raw.get("name") or "")
        if name not in CLASSIFIED_TOOL_NAMES:
            raise ValueError(f"Unclassified MCP docs tool: {name}")
        if name in LEGACY_TOOL_NAMES and not config.expose_legacy:
            continue
        if name in ADMIN_TOOL_NAMES and not config.expose_admin:
            continue
        if name in ADVANCED_TOOL_NAMES and not config.expose_advanced:
            continue
        specs.append(_tool_spec(raw))
    return DocsMcpSurface(
        tools=tuple(specs),
        handlers={spec.name: spec.handler for spec in specs},
    )


ALL_SURFACE = build_docs_surface(DocsServerConfig(expose_legacy=True, expose_admin=True, expose_advanced=True))
DOCS_SURFACE = build_docs_surface(DocsServerConfig.from_env(os.environ))

ALL_TOOLS = [spec.to_tool_dict() for spec in ALL_SURFACE.tools]
TOOLS = [spec.to_tool_dict() for spec in DOCS_SURFACE.tools]

CONTEXT_TOOLS = context_tools(TOOLS)
LIBRARY_TOOLS = library_tools(TOOLS)
PROJECT_TOOLS = project_tools(TOOLS)
PREFETCH_TOOLS = prefetch_tools(TOOLS)


def current_docs_surface(env: Mapping[str, str] | None = None) -> DocsMcpSurface:
    """Build the docs MCP surface from the current environment.

    `TOOLS` remains as an import-time compatibility snapshot for tests and
    older integrations, but the live server calls this so env flag changes are
    not frozen by module import order.
    """
    return build_docs_surface(DocsServerConfig.from_env(os.environ if env is None else env))


def current_tools(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    return [spec.to_tool_dict() for spec in current_docs_surface(env).tools]


def _exception_reason_code(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "bad_request"
    if isinstance(exc, TimeoutError):
        return "network_required"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    return "handler_exception"


def call_docs_tool_payload(
    name: str,
    arguments: dict[str, Any] | None,
    service: LibraryDocsService,
    *,
    surface: DocsMcpSurface | None = None,
) -> dict[str, Any]:
    args = arguments or {}
    active_surface = surface or current_docs_surface()
    handler = active_surface.handlers.get(name)
    if handler is None:
        return build_mcp_error_payload(
            reason_code="unknown_tool",
            message=f"unknown tool: {name}",
            tool=name,
            phase="validation",
        )
    try:
        payload = handler(name, args, service)
    except Exception as exc:
        reason_code = _exception_reason_code(exc)
        return build_mcp_error_payload(
            reason_code=reason_code,
            message=str(exc),
            exception=exc,
            tool=name,
            phase="execution",
            debug=debug_errors_enabled(args),
        )
    if payload is None:
        return build_mcp_error_payload(
            reason_code="unknown_tool",
            message=f"unknown tool: {name}",
            tool=name,
            phase="validation",
        )
    return payload


MCP_RESOURCES: list[dict[str, str]] = [
    {
        "uri": "docmancer://agent/quickstart",
        "name": "Docmancer agent quickstart",
        "description": "How agents should use Docmancer MCP without confusing it with a code auditor or raw Context7 clone.",
        "mimeType": "text/markdown",
        "text": """# Docmancer agent quickstart

Docmancer is a local documentation/context router and project cartographer.

Docmancer is not a code auditor.

It is not:
- a code auditor;
- a static analyzer;
- a test runner;
- a code generator;
- an AST-perfect/LSP code intelligence engine.

Use Docmancer before generic code search when the user asks about:
- project architecture;
- repo conventions;
- dependency/library documentation;
- Context7-like docs help;
- source-grounded repository context.

The default public surface has exactly three tools:
- `get_docs_context`: first tool for content and coding questions;
- `prepare_docs`: lifecycle work only after a returned next_action or explicit user request;
- `docs_status`: explicit freshness, health, source-state, or job-progress checks.

## Default project workflow

1. Call:
   `get_docs_context(project_path=..., question=..., mode="auto", response_style="snippet-first", output_mode="answer")`

2. If and only if the response returns `prepare_docs` as its next action, follow it. For example:
   `prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)`

3. Retry `get_docs_context` after successful preparation.

4. Interpret the result:
   - `answer_type="direct"`: you may answer from the returned snippets/sources.
   - `answer_type="navigation_only"`: do not answer yet. Read/search the suggested files first, then answer.
   - `partial_navigational`: treat it as source-search guidance, not a complete answer.
   - `requires_confirmation=true`: ask the user before network/dependency fetches.

Use `docs_status(action="project", project_path=...)` only when the user asks
whether documentation is indexed, stale, or healthy. Use `action="jobs"` or
`action="job"` only for asynchronous job progress.

## Context7-like library workflow

For public/dependency docs, use the canonical public tool:

`get_docs_context(question=..., library=..., ecosystem=..., version=..., mode="library" | "mixed", response_style="snippet-first")`

If docs are missing/stale and the user approves network access, use:

`prepare_docs(action="prefetch_library_docs", library=..., ecosystem=..., version=...)`

Do not use WebFetch as a substitute for registered Docmancer docs until Docmancer has returned no trusted route.

## Patch workflow

Before editing code, call `get_docs_context(...)`, then use normal source
read/search tools and run tests/linters. Optional code/plan/constraint tools are
available only when the advanced surface is explicitly enabled with
`DOCMANCER_MCP_ADVANCED_TOOLS=1`.

## Audit workflow

For audits, Docmancer only supplies documentation/context. It does not find all bugs.

Use Docmancer for architecture/docs context, then use normal code tools:
- read/search/grep;
- analyzer/linter;
- tests;
- dependency inspection;
- duplicate/large-file checks.

Always separate:
- facts from Docmancer docs;
- facts from source code;
- your own analysis.
""",
    },
    {
        "uri": "docmancer://workflow/project-docs",
        "name": "Project docs workflow",
        "description": "Single-entry workflow for project-owned docs.",
        "mimeType": "text/markdown",
        "text": """# Project docs workflow

1. Call `get_docs_context(project_path=..., question=..., mode="auto", output_mode="compact")`.
2. If the response explicitly returns `prepare_docs` as next_action, follow it and retry `get_docs_context`.
3. Inspect `answer_available`, `answer_type`, `answer_completeness`, and `trust_contract.sources`.
4. Treat `partial_navigational` as navigation/source-search guidance, not a complete answer.
5. Use dependency/public network fetches only with explicit approval (`allow_network=true`).
""",
    },
    {
        "uri": "docmancer://agent/tool-selection",
        "name": "Docmancer public tool selection",
        "description": "Mutually exclusive first-call policy for the three public Docs MCP tools.",
        "mimeType": "text/markdown",
        "text": """# Public tool selection

1. Natural documentation, API, dependency, architecture, convention, and coding questions → `get_docs_context`.
2. Explicit sync/refresh/prefetch/prune/remove request, or a returned next_action → `prepare_docs`.
3. Explicit index freshness, health, source-state, or async job-progress request → `docs_status`.

Never call an advanced or legacy tool unless the corresponding environment flag exposes it.
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
        "description": "Canonical public workflow for exact library/dependency docs.",
        "mimeType": "text/markdown",
        "text": """# Library docs workflow

Use the public unified tool first:

1. Call:
   `get_docs_context(question=..., library=..., ecosystem=..., version=..., mode="library", response_style="snippet-first")`

2. If the response returns `requires_confirmation=true`, `reason_code=network_required`, or missing/stale docs, ask the user before network access.

3. If approved, call:
   `prepare_docs(action="prefetch_library_docs", library=..., ecosystem=..., version=..., force_refresh=false)`

4. Retry:
   `get_docs_context(question=..., library=..., ecosystem=..., version=..., mode="library", response_style="snippet-first")`

5. If working inside a repository, call:
   `get_docs_context(project_path=..., question=..., mode="mixed", response_style="snippet-first")`

Do not use WebFetch as a substitute for registered docs before Docmancer has returned no trusted route.

Legacy tools such as `resolve_library_id` and `get_library_docs` may exist only when legacy surface is explicitly enabled. Do not assume they are available.
""",
    },
]

MCP_RESOURCE_TEMPLATES: list[dict[str, str]] = [
    {
        "uriTemplate": "docmancer://workflow/project-docs/{project_path}",
        "name": "Project-specific docs workflow",
        "description": "Use with a local project_path to guide get_docs_context and returned prepare_docs actions.",
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

1. `get_docs_context(project_path=\"{project_path}\", question=..., mode=\"auto\", output_mode=\"compact\")`
2. If the response returns `prepare_docs` as next_action, follow it and retry `get_docs_context`.
3. Inspect `trust_contract.sources.selected`, `trust_contract.sources.rejected`, and `trust_contract.sources.risky` before using the answer.
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

1. `get_docs_context(
       question=...,
       library=\"{library}\",
       ecosystem=\"{ecosystem}\",
       version=\"{version}\",
       mode=\"library\",
       response_style=\"snippet-first\"
   )`

2. If docs are missing/stale and network is approved:
   `prepare_docs(
       action=\"prefetch_library_docs\",
       library=\"{library}\",
       ecosystem=\"{ecosystem}\",
       version=\"{version}\"
   )`

3. Retry `get_docs_context(...)`.

Do not assume legacy `resolve_library_id` / `get_library_docs` tools are available on the public surface.
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
            for tool in current_tools()
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
        return _json_text(mcp_types, call_docs_tool_payload(name, arguments, service))

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve() -> None:
    asyncio.run(_run_async(LibraryDocsService()))
