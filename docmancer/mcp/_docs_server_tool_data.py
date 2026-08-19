"""Static MCP tool schemas and classifications."""
from __future__ import annotations
from ._docs_server_schema import *  # noqa: F401,F403

RAW_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_docs_context",
        "description": """Default first tool for every documentation, repository, dependency, API, architecture, convention, and source-grounding question.

Agent workflow:
- Call get_docs_context first. It performs safe project preflight internally.
- For coding/API questions, set response_style=\"snippet-first\".
- For coding and patch tasks, use delivery_strategy=\"bounded_direct\" as the default pre-edit handoff; raw retrieval stays hidden and only a validated ActionPacket plus bounded recovery metadata enters model context.
- In bounded delivery call prepare_docs only from recommended_next_action; unbounded compatibility output may use next_action.
- Use docs_status only for explicit health, freshness, source-state, or job-status requests, or when get_docs_context returns it as recommended_next_action.
- Scope planning: for one known module use scope="module" plus exact module_path; module_path always implies module scope. For project-wide policy use scope="project" and omit module/module_path. If a task needs both module-local and project-wide evidence, make two bounded calls (module then project) rather than widening one module call. For cross-module questions use scope="all" without module filters, or separate exact module calls. On module_ambiguous, follow docs_status and retry with an exact returned module_path.
- In bounded delivery, stop before editing when action_packet.status is insufficient_evidence. In unbounded exploration, navigation_only or partial_navigational requires source search before answering.
- This tool provides source-grounded context, not a full code audit or test substitute.
- For change-aware documentation maintenance, pass maintenance with either base/head or explicit changed_paths; obey its fail-closed authoring brief.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project_path": {"type": ["string", "null"]},
                "response_style": {"type": ["string", "null"], "enum": ["auto", "snippet-first", "evidence-first", None], "default": "auto", "description": "Choose snippet-first presentation for coding tasks or preserve evidence-first context."},
                "delivery_strategy": {"type": ["string", "null"], "enum": ["bounded_direct", None], "description": "Return one deterministic, source-attributed ActionPacket without exposing raw retrieval content."},
                "packet_tokens": {"type": ["integer", "null"], "minimum": 256, "maximum": 2000, "default": 1500, "description": "Bounded structured response budget; ActionPacket wrapper and recovery metadata are included in the 2000-token hard ceiling."},
                "library": {"type": ["string", "null"]},
                "libraries": {"type": ["array", "null"], "items": {"type": "string"}},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "module": {"type": ["string", "null"], "description": "Module id/name lookup for module-scoped project docs. Prefer exact module_path when known; an ambiguous name fails closed instead of being guessed."},
                "module_path": {"type": ["string", "null"], "description": "Exact discovered module path such as packages/orders. Supplying module_path always implies module scope and never widens into project or sibling modules."},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None], "description": "Project-doc scope: project = repo-level docs only; module = one module (use exact module_path); all = repo-level plus modules only when no module filter is supplied. For module + project obligations prefer two bounded calls."},
                "mode": {"type": ["string", "null"], "enum": ["auto", "project", "library", "dependency", "mixed", None], "description": "Evidence lane selection: project for repository/module documentation, dependency for project-pinned dependency docs, library for an explicit external library, mixed only when both project and library evidence are intentionally required."},
                "tokens": {"type": ["integer", "null"], "minimum": 1, "maximum": 20000},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "expand": {"type": ["string", "null"]},
                "allow_latest_fallback": {"type": ["boolean", "null"]},
                "page": {"type": ["integer", "null"], "minimum": 1, "default": 1},
                "page_size": {"type": ["integer", "null"], "minimum": 1, "maximum": 20},
                "include_sections": {"type": ["array", "null"], "items": {"type": "string", "enum": ["context_pack", "supporting_snippets", "trust_contract", "diagnostics", "metrics"]}},
                "output_mode": {"type": ["string", "null"], "enum": ["answer", "compact", "debug", "full", None], "default": "answer", "description": "answer is the default minimal agent-friendly response; compact includes structured context; debug includes diagnostics; full returns raw output."},
                "details": {"type": ["boolean", "null"]},
                "maintenance": {
                    "type": ["object", "null"],
                    "properties": {
                        "base": {"type": ["string", "null"]},
                        "head": {"type": ["string", "null"], "default": "HEAD"},
                        "changed_paths": {"type": ["array", "null"], "maxItems": 200, "items": {"type": "string"}},
                        "changed_symbols": {"type": ["array", "null"], "maxItems": 200, "items": {"type": "string"}},
                        "candidate_offset": {"type": ["integer", "null"], "minimum": 0},
                        "candidate_limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["question"],
            "allOf": [{
                "if": {
                    "required": ["packet_tokens"],
                    "properties": {"packet_tokens": {"type": "integer"}},
                },
                "then": {
                    "required": ["delivery_strategy"],
                    "properties": {"delivery_strategy": {"const": "bounded_direct"}},
                },
            }],
        },
        "outputSchema": GET_DOCS_CONTEXT_OUTPUT_SCHEMA,
    },
    {
        "name": "prepare_docs",
        "description": """Unified confirmation-first lifecycle/admin tool for docs preparation: sync project docs, prefetch dependency/library/manifest/target docs, refresh, prune, or remove registered docs sources.

Agent workflow:
- Use prepare_docs only after get_docs_context returns bounded recommended_next_action or unbounded next_action, or when the user explicitly asks to sync, refresh, prefetch, prune, or remove docs.
- Use prepare_docs(action=\"prefetch_library_docs\") for public/dependency docs only after network access is approved.
- Prefer this over separate ingest/sync/prefetch/refresh/prune/remove tools.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["sync_project_docs", "prefetch_project_dependency_docs", "prefetch_library_docs", "discover_library_docs", "prefetch_docs_targets", "inspect_docs_target", "validate_docs_manifest", "prefetch_docs_manifest", "refresh_library_docs", "prune_library_docs", "remove_library_docs", "clear_index", "cancel_docs_job"]},
                "project_path": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"], "enum": ["project-local", None]},
                "confirm": {
                    "type": ["boolean", "null"],
                    "description": "Second-call apply flag for action='clear_index' only; omit for every other action.",
                },
                "plan_digest": {
                    "type": ["string", "null"],
                    "pattern": "^[0-9a-f]{64}$",
                    "description": "Optional digest from the preview response; binds confirmation to that exact cleanup plan.",
                },
                "allow_incomplete": {
                    "type": ["boolean", "null"],
                    "description": "Acknowledge that reported remote or unowned vector state will remain.",
                },
                "library": {"type": ["string", "null"]},
                "canonical_id": {"type": ["string", "null"]},
                "manifest_path": {"type": ["string", "null"]},
                "job_id": {"type": ["string", "null"]},
                "targets": {"type": ["array", "null"], "items": DOCS_TARGET_INPUT_SCHEMA},
                "target": {**DOCS_TARGET_INPUT_SCHEMA, "type": ["object", "null"]},
                "max_pages": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
                "ecosystem": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "source_type": {"type": ["string", "null"]},
                "docs_url": {"type": ["string", "null"]},
                "docs_url_template": {"type": ["string", "null"]},
                "question": {"type": ["string", "null"], "description": "Optional retrieval question used to prioritize bounded documentation ingestion."},
                "include_flutter": {"type": ["boolean", "null"]},
                "include_dart": {"type": ["boolean", "null"]},
                "include_rust": {"type": ["boolean", "null"]},
                "include_go": {"type": ["boolean", "null"]},
                "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
                "with_vectors": {"type": ["boolean", "null"]},
                "changed_paths": {"type": ["array", "null"], "maxItems": 500, "items": {"type": "string"}},
                "deleted_paths": {"type": ["array", "null"], "maxItems": 500, "items": {"type": "string"}},
                "renamed_paths": {
                    "type": ["array", "null"],
                    "maxItems": 500,
                    "items": {
                        "type": "object",
                        "properties": {"old_path": {"type": "string"}, "new_path": {"type": "string"}},
                        "required": ["old_path", "new_path"],
                        "additionalProperties": False,
                    },
                },
                "force_refresh": {"type": ["boolean", "null"]},
                "force": {"type": ["boolean", "null"]},
                "continue_on_error": {"type": ["boolean", "null"]},
                "async": {"type": ["boolean", "null"]},
                "keep_versions": {"type": ["array", "null"], "items": {"type": "string"}},
                "older_than_days": {"type": ["integer", "null"], "minimum": 0},
                "dry_run": {"type": ["boolean", "null"], "default": True},
            },
            "required": ["action"],
            "allOf": [{
                "if": {"properties": {"action": {"const": "inspect_docs_target"}}},
                "then": {
                    "required": ["target"],
                    "properties": {"target": {**DOCS_TARGET_INPUT_SCHEMA, "type": "object"}},
                },
            }, {
                "if": {"properties": {"action": {"const": "clear_index"}}},
                "else": {"not": {"required": ["confirm"]}},
            }],
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
                "action": {"type": "string", "enum": ["project", "library", "jobs", "job"]},
                "project_path": {"type": ["string", "null"]},
                "canonical_id": {"type": ["string", "null"]},
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
                "project_path": {"type": ["string", "null"]},
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
                    "items": DOCS_TARGET_INPUT_SCHEMA,
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
            "properties": {"job_id": {"type": "string"}, "project_path": {"type": ["string", "null"]}},
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
                "project_path": {"type": ["string", "null"]},
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
        "description": "Remove one exact documentation target from project-owned storage by canonical id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "canonical_id": {"type": "string"},
                "project_path": {"type": "string"},
            },
            "required": ["canonical_id", "project_path"],
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
                "include_go": {"type": ["boolean", "null"]},
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
                "include_go": {"type": ["boolean", "null"]},
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

PUBLIC_ADVERTISED_DESCRIPTIONS: dict[str, str] = {
    "get_docs_context": (
        "Default source-grounded documentation tool. Call before a coding edit or for a documentation/API question. "
        "For one known module use scope=module with exact module_path; module_path always implies module scope. "
        "For project-wide policy use scope=project without module filters. If a task needs both module-local and "
        "project-wide evidence, make two bounded calls (module then project). For cross-module questions use "
        "scope=all without module filters. On module ambiguity follow the returned docs_status recovery and retry "
        "with an exact module_path. Stop before editing on insufficient_evidence."
    ),
    "prepare_docs": (
        "Confirmation-first documentation preparation. Call only from get_docs_context "
        "recommended_next_action or an explicit user sync, refresh, index, or prefetch request."
    ),
    "docs_status": (
        "Read-only project documentation or background-job status. Use when the user explicitly asks about "
        "health, freshness, indexing, or job progress, or when get_docs_context returns docs_status as its "
        "recommended_next_action."
    ),
}

PUBLIC_ADVERTISED_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "minLength": 1},
            "project_path": {"type": ["string", "null"]},
            "library": {"type": ["string", "null"]},
            "libraries": {"type": ["array", "null"], "items": {"type": "string"}},
            "ecosystem": {"type": ["string", "null"]},
            "version": {"type": ["string", "null"]},
            "source_type": {"type": ["string", "null"]},
            "docs_url": {"type": ["string", "null"]},
            "module": {
                "type": ["string", "null"],
                "description": "Module id/name lookup. Prefer exact module_path; ambiguous names fail closed.",
            },
            "module_path": {
                "type": ["string", "null"],
                "description": "Exact discovered module path. Supplying it always implies module scope.",
            },
            "scope": {
                "type": ["string", "null"],
                "enum": ["project", "module", "all", None],
                "description": "project = repo-level docs only; module = one module; all = repo-level plus modules only without a module filter. Use two calls for module + project obligations.",
            },
            "mode": {
                "type": ["string", "null"],
                "enum": ["auto", "project", "library", "dependency", "mixed", None],
                "description": "Select project/module docs, explicit library docs, project-pinned dependency docs, or intentional mixed evidence.",
            },
        },
        "required": ["question"],
    },
    "prepare_docs": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "sync_project_docs", "prefetch_project_dependency_docs",
                    "prefetch_library_docs", "discover_library_docs",
                    "inspect_docs_target",
                    "validate_docs_manifest", "prefetch_docs_manifest",
                    "refresh_library_docs", "prune_library_docs",
                    "remove_library_docs", "clear_index", "cancel_docs_job",
                ],
            },
            "project_path": {"type": ["string", "null"]},
            "scope": {"type": ["string", "null"], "enum": ["project-local", None]},
            "confirm": {
                "type": ["boolean", "null"],
                "description": "Second-call apply flag for action='clear_index' only; omit for every other action.",
            },
            "plan_digest": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
            "allow_incomplete": {"type": ["boolean", "null"]},
            "library": {"type": ["string", "null"]},
            "ecosystem": {"type": ["string", "null"]},
            "version": {"type": ["string", "null"]},
            "canonical_id": {"type": ["string", "null"]},
            "job_id": {"type": ["string", "null"]},
            "manifest_path": {"type": ["string", "null"]},
            "source_type": {"type": ["string", "null"]},
            "docs_url": {"type": ["string", "null"]},
            "question": {"type": ["string", "null"]},
            "include_flutter": {"type": ["boolean", "null"]},
            "include_dart": {"type": ["boolean", "null"]},
            "include_rust": {"type": ["boolean", "null"]},
            "include_go": {"type": ["boolean", "null"]},
            "include_packages": {"type": ["array", "null"], "items": {"type": "string"}},
            "with_vectors": {"type": ["boolean", "null"], "default": False},
            "force": {"type": ["boolean", "null"]},
            "force_refresh": {"type": ["boolean", "null"]},
            "continue_on_error": {"type": ["boolean", "null"]},
            "dry_run": {"type": ["boolean", "null"], "default": True},
            "target": {"type": ["object", "null"]},
            "max_pages": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
        },
        "required": ["action"],
        "allOf": [{
            "if": {"properties": {"action": {"const": "clear_index"}}},
            "then": {
                "required": ["scope", "project_path"],
                "properties": {
                    "scope": {"const": "project-local"},
                    "project_path": {"type": "string", "minLength": 1},
                },
            },
        }, {
            "if": {"properties": {"action": {"const": "clear_index"}}},
            "else": {"not": {"required": ["confirm"]}},
        }, {
            "if": {"properties": {"action": {"const": "remove_library_docs"}}},
            "then": {
                "required": ["canonical_id", "project_path"],
                "properties": {
                    "canonical_id": {"type": "string", "minLength": 1},
                    "project_path": {"type": "string", "minLength": 1},
                },
            },
        }],
    },
    "docs_status": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["project", "library", "jobs", "job"]},
            "project_path": {"type": ["string", "null"]},
            "canonical_id": {"type": ["string", "null"]},
            "job_id": {"type": ["string", "null"]},
        },
        "required": ["action"],
    },
}

PUBLIC_ADVERTISED_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA,
}

__all__=[n for n in globals() if not n.startswith('__')]
