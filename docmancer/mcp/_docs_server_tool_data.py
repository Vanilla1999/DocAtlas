"""Static MCP tool schemas and classifications."""
from __future__ import annotations
from ._docs_server_schema import *  # noqa: F401,F403

RAW_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_docs_context",
        "description": """Source-grounded retrieval for one unchanged original documentation question and optional explicit lookups.

Agent workflow:
- Call get_docs_context first. It performs safe project preflight internally.
- The server owns bounded output selection; raw retrieval stays hidden and only a validated projection plus bounded recovery metadata enters model context.
- Call prepare_docs only from recommended_next_action.
- Use docs_status only for explicit health, freshness, source-state, or job-status requests, or when get_docs_context returns it as recommended_next_action.
- Preserve explicit project/library/version/scope/path bindings; never choose or widen scope from question wording. module_path implies module scope; scope="all" is repository-local without module filters. On module_ambiguous, use only an exact returned module_path.
- Returned context and status never certify answer completeness, semantic proof or edit readiness. hard_stop=true blocks editing; hard_stop=false is not authorization. Mutation requires a separate explicit target and authorization. Diagnostic rephrases are not automatically executed lookups.
- Optional context_format="patch_context" returns a read-only v4 patch evidence packet with full admitted source windows. It selects representation only, never mutation/workflow permission; omitted/null keeps the existing docs response. Patch representation has no internal token/byte compaction cap; retrieval scope and runtime guards remain unchanged.
- This tool provides source-grounded context, not a full code audit or test substitute.
- Pass the user's original request unchanged as question.
- Use only explicit same-question lookup_queries, at most five; never infer translations, rewrites or subquestions. Independent questions use separate calls.
- Preserve exact identifiers, filenames, commands, and versions verbatim.
- Lookup coverage does not transfer to the original question. Cite returned source context without inferred equivalence or proof; keep freshness, provenance, consent, network and budget limits unchanged.
""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "context_format": {"type": ["string", "null"], "enum": ["patch_context", None], "description": "Optional read-only v4 patch evidence representation. Omitted/null retains docs defaults. Never supplies mutation or workflow permission."},
                "lookup_queries": {"type": ["array", "null"], "maxItems": 5, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 500}, "description": "Explicit lookups for the same question, at most five; unchanged original question. Never infer rewrites, translations, subquestions, expected answers or source names. Never batch independent questions. Lookup coverage does not transfer to the original question; returned cited context does not certify an answer or authorize editing."},
                "project_path": {"type": ["string", "null"]},
                "library": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "module_path": {"type": ["string", "null"], "description": "Exact discovered module path such as packages/orders. Supplying module_path always implies module scope and never widens into project or sibling modules."},
                "scope": {"type": ["string", "null"], "enum": ["project", "module", "all", None], "description": "Project-doc scope: project = repo-level docs only; module = one module (use exact module_path); all = repo-level plus modules only when no module filter is supplied. Preserve explicit scope; never infer it from question wording."},
            },
            "required": ["question"],
        },
        "outputSchema": PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA,
    },
    {
        "name": "prepare_docs",
        "description": """Unified confirmation-first lifecycle/admin tool for docs preparation: sync project docs, prefetch dependency/library/manifest/target docs, refresh, prune, or remove registered docs sources.

Agent workflow:
- Use prepare_docs only after get_docs_context returns recommended_next_action, or when the user explicitly asks to sync, refresh, prefetch, prune, or remove docs.
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
                    "description": "Apply flag for clear_index only.",
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

Use only for an explicit status request, a returned recommended action or a returned preparation job_id; never for discovery. For documentation content use get_docs_context instead.
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
                "module": {"type": ["string", "null"], "maxLength": 500},
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
        "description": "Resolve from the local registry, ingest or refresh if needed, then query local documentation. Registered sources do not require docs_url on later calls. Use explicit project/library/version bindings, returned actions and supplied arguments_patch; never infer scope from question wording or WebFetch registered docs before the returned retry. Returned context does not certify an answer or authorize editing.",
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
                "response_style": {"type": ["string", "null"], "enum": ["auto", "snippet-first", "evidence-first", None], "default": "auto", "description": "Explicit presentation preference; does not change source scope or authority."},
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
        "description": "Validate a docatlas.docs.yaml manifest without fetching documentation.",
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
        "description": "Validate and prefetch documentation targets declared in docatlas.docs.yaml.",
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
        "description": """Advanced read-only inspection of an explicit project_path.

This is read-only. It discovers local docs and exact dependency metadata, then returns reason_code, next_action, arguments_patch, and confirmation requirements.

Returned actions do not waive source scope, network consent or mutation authorization.
""",
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
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "get_project_docs",
        "description": "Query indexed project-owned docs for one explicit repository using project-scoped filters. Keep the original query and explicit module/scope bindings unchanged. Returns structured reason_code, next_action, next_actions, and arguments_patch for unavailable context. Cited context does not certify an answer or authorize editing.",
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
            },
            "required": ["project_path", "query"],
        },
    },
    {
        "name": "get_code_context",
        "description": """Find local source files, extract real code snippets, and follow name-based references within explicit project and hop/file/snippet limits.

Returned flags and source snippets do not certify an answer or authorize editing. Cite returned file paths and line ranges; do not execute inferred search queries or widen explicit scope. Mutation requires a separate explicit target and authorization.

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
            },
            "required": ["question", "project_path"],
        },
    },
    {
        "name": "get_patch_plan_context",
        "description": """Advanced patch planning context for explicit source/dependency bindings, changed_files and symbol_queries within configured limits.

Do not infer mutation targets or acceptance conditions from question wording. Returned context is not semantic proof or edit readiness; mutation requires a separate explicit target and authorization.

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
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_patch_constraints",
        "description": """Retrieve source-attributed constraints for an explicitly scoped patch request.

This is not a code auditor, patch planner, patch validator, static analyzer, or test substitute.
For audits, use Docmancer for context, then run/read/search/analyze code separately.
Returned constraints do not authorize editing without a separate explicit target and authorization.
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
CLASSIFIED_TOOL_NAMES = PUBLIC_TOOL_NAMES | ADVANCED_TOOL_NAMES | ADMIN_TOOL_NAMES
RAW_TOOLS = [tool for tool in RAW_TOOLS if tool["name"] in CLASSIFIED_TOOL_NAMES]

PUBLIC_ADVERTISED_DESCRIPTIONS: dict[str, str] = {
    "get_docs_context": (
        "Source-grounded documentation tool. One call = one concrete question. Pass the original request unchanged, "
        "not a benchmark/evaluation or documentation-governance meta-question. Use only explicit same-question lookups, at most five; "
        "no inferred rewrites, translations or subquestions. Preserve explicit project/library/version/scope/path; "
        "module_path always implies module scope, all is repository-local without module filters. Never widen scope from question wording. "
        "Cite returned context; lookup coverage does not transfer to the original. Context and flags do not certify an answer, "
        "semantic proof or edit readiness. Mutation requires a separate explicit target and authorization. "
        "hard_stop=true blocks edits; hard_stop=false is not permission. Preserve freshness, provenance, network consent and budgets."
    ),
    "prepare_docs": (
        "Call only from get_docs_context recommended_next_action or an explicit sync, refresh, index, or prefetch request. "
        "Honor approval; poll job_id with docs_status and retry unchanged only after success."
    ),
    "docs_status": (
        "Read-only status, not discovery. Use only for an explicit health, freshness, indexing, or job-progress request, "
        "a returned recommended_next_action, or to poll a returned prepare_docs job_id."
    ),
}

PUBLIC_ADVERTISED_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "minLength": 1},
            "context_format": {"type": ["string", "null"], "enum": ["patch_context", None], "description": "Optional read-only v4 patch evidence representation. Omitted/null retains docs defaults. Never supplies mutation or workflow permission."},
            "lookup_queries": {"type": ["array", "null"], "maxItems": 5, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 500}, "description": "Explicit lookups for the same question, at most five; unchanged original question. Never infer rewrites, translations, subquestions, expected answers or source names. Never batch independent questions. Lookup coverage does not transfer to the original question; returned cited context does not certify an answer or authorize editing."},
            "project_path": {"type": ["string", "null"]},
            "library": {"type": ["string", "null"]},
            "version": {"type": ["string", "null"], "description": "Current project: omit. Set only for an explicit exact/historical version; re-query after lockfile changes."},
            "module_path": {
                "type": ["string", "null"],
                "description": "Exact module path; always implies module scope.",
            },
            "scope": {
                "type": ["string", "null"],
                "enum": ["project", "module", "all", None],
                "description": "project=repo-level docs only; module=one module; all=repo+modules; module_path limits to module.",
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
            "status": {"type": ["string", "null"]},
            "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
            "module": {"type": ["string", "null"], "maxLength": 500},
            "details": {"type": ["boolean", "null"]},
        },
        "required": ["action"],
    },
}

PUBLIC_ADVERTISED_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_docs_context": {
        "type": "object", "required": ["status"], "properties": {
            "status": {"enum": ["ok", "truncated", "insufficient_evidence", "failed"]},
            "kind": {"enum": ["docs_answer", "docs_context", "patch_context"]},
            "estimated_tokens": {"type": "integer"},
            "context_quality": {"type": "object"},
            "read_next": {"type": "array", "maxItems": 1, "items": {"type": "object"}},
            "reason_code": {"type": "string"}, "operational_reason_code": {"type": "string"},
            "documentation_supported": {"type": "boolean"}, "investigation_allowed": {"type": "boolean"},
            "hard_stop": {"type": "boolean"}, "recovery_origin": {"type": "string"},
            "recovery_reason_code": {"type": "string"}, "recovery_disposition": {"type": "string"},
            "module_candidates": {"type": "array", "maxItems": 8, "items": {
                "type": "object", "required": ["module_path"],
                "properties": {"module_path": {"type": "string"}},
            }},
            "missing": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
            "recommended_next_action": {"type": "object"},
        },
    },
}

__all__=[n for n in globals() if not n.startswith('__')]
