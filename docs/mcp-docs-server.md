# DocAtlas MCP docs server

DocAtlas exposes its documentation runtime through a Context7-style MCP server:

```bash
doc-atlas mcp docs-serve
```

Use this server when a coding agent needs local, source-grounded documentation context instead of relying on model memory, latest-only hosted docs, or repeated `WebFetch` calls.

## What the MCP server covers

DocAtlas's MCP docs server has one high-level router plus three main lanes:

```text
get_docs_context(question, project_path?, library?, mode="auto")
```

`get_docs_context` returns one source-grounded context pack by routing deterministically to project-owned docs, public library docs, exact dependency docs, or a mixed project-plus-library flow. It is additive: advanced users and existing agents can still call the lane-specific tools directly.

`get_docs_context`, `get_library_docs`, and `get_project_context` also accept `response_style`: `auto`, `snippet-first`, or `evidence-first`. `auto` switches to snippet-first for coding/API/command/config questions when a usable snippet exists in the already selected trusted sources. `snippet-first` never removes `context_pack` or the Trust Contract, and it never creates fake code when no snippet exists.

```json
{
  "question": "How do I use FastAPI Depends?",
  "library": "fastapi",
  "response_style": "snippet-first"
}
```

1. **Library docs** — resolve, fetch, refresh, prefetch, inspect, and query public or registered documentation sources.
2. **Project-owned docs** — discover, reconcile, stale-check, prune orphaned indexed entries, and query reviewable repository docs such as `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, roadmap files, and module/package docs in monorepos.
3. **Dependency docs from project metadata** — read supported manifests/lockfiles and prefetch exact dependency documentation for the versions the project actually uses.

Project-owned docs and dependency docs are intentionally separate. `prepare_docs(action="sync_project_docs")` is the public lifecycle action for files that already live in the repository. Legacy direct verbs such as `sync_project_docs`, `ingest_project_docs`, `bootstrap_project_docs`, `get_project_docs`, and `get_project_context` remain compatibility/admin concepts, but new agent instructions should use the public `inspect_project_docs -> prepare_docs(action="sync_project_docs") -> get_docs_context(mode="project")` path. Dependency prefetch actions fetch documentation from the network based on manifests or lockfiles and require explicit approval.

Implementation note for maintainers: the public MCP tool names and schemas remain centralized in `docmancer/mcp/docs_server.py`, while tool handling is split by lane under `docmancer/docs/interfaces/mcp/`:

- `docs_tools.py` handles library-docs tools;
- `context_tools.py` handles the unified context router;
- `project_tools.py` handles project-owned docs and project dependency-docs tools;
- `prefetch_tools.py` handles manifest, target prefetch, and job tools.

This split is internal only; MCP clients should see the same tool names and response shapes.

Internal application-service wiring is also intentionally split behind the compatibility facade in
`docmancer/docs/service.py`. Public MCP tools call stable facade methods, while focused helpers under
`docmancer/docs/application/` own smaller concerns such as target resolution, manifest validation,
prefetch execution, registry operations, and project dependency-version resolution. Maintainers should
prefer adding new behavior to the focused helper for that concern and keep the facade as wiring plus
backwards compatibility.

## MCP client configuration

The fastest path is the one-line installer, which registers this docs server into Claude Code, OpenCode, and/or Codex for you:

```bash
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh
```

See [`scripts/install.sh`](../scripts/install.sh). To configure a client manually, add:

```json
{
  "mcpServers": {
    "docmancer-docs": {
      "command": "doc-atlas",
      "args": ["mcp", "docs-serve"]
    }
  }
}
```

## Library docs tools

## Unified context tool

| Tool | Purpose |
|---|---|
| `get_docs_context` | Return one source-grounded documentation context pack by routing the question to project-owned docs, public library docs, exact dependency docs, or mixed project-plus-library context. |

Default behavior:

| Input | Mode selected |
|---|---|
| `project_path` only | `project` |
| `library` or `libraries` only | `library` |
| `project_path` plus `library`/`libraries` | `mixed` |
| `mode="dependency"` | `dependency` |
| no `project_path`, `library`, or `libraries` | `invalid_request` |

Safety defaults:

| Option | Default | Meaning |
|---|---:|---|
| `prepare_project_docs` | `true` | Run safe local project bootstrap before project/mixed/dependency context. |
| `allow_network` | `false` | Missing/stale library or dependency docs return `confirmation_required` instead of fetching. |
| `allow_latest_fallback` | `false` | Exact-version requests never silently use latest docs. |
| `force_refresh` | `false` | Existing indexed docs are queried when usable. |
| `details` | `false` | Compact lane summaries by default; `true` includes normalized lane details. |

The unified tool delegates to existing facade methods such as `bootstrap_project_docs`, `get_project_context`, `get_library_docs`, and dependency prefetch/context services. It does not implement a second retrieval engine.

## Library docs tools

| Tool | Purpose |
|---|---|
| `resolve_library_id` | Resolve a documentation library from the local registry or an explicit `docs_url`; registered sources should be retried through Docmancer with returned candidates or `arguments_patch`. |
| `get_library_docs` | Resolve from the local registry, ingest or refresh if needed, then query local documentation. Registered sources do not require `docs_url` on later calls. |
| `refresh_library_docs` | Refresh one documentation library/version. Prefer `prefetch_library_docs` for ahead-of-time multi-version indexing. |
| `prefetch_library_docs` | Download and index one or more library versions ahead of time. |
| `inspect_library_docs` | Inspect one exact documentation target by canonical id. |
| `remove_library_docs` | Remove one exact documentation target by canonical id. |
| `prune_library_docs` | Prune old documentation targets with dry-run support. |
| `list_library_docs` | List locally registered documentation libraries. |

## Project-owned docs public surface

| Tool | Purpose |
|---|---|
| `inspect_project_docs` | Read-only discovery of local project docs and exact dependency metadata. Reports reason_code, next_action, stale/ignored/orphaned sources, and compact state. |
| `prepare_docs(action="sync_project_docs")` | Public lifecycle action. Reconciles the project-docs index with the current repository discovery snapshot: prunes orphaned/stale indexed docs, indexes new or changed reviewable docs, and verifies final state. |
| `get_docs_context(mode="project")` | Query indexed current project-owned docs for repo-specific architecture, conventions, runbooks, ADRs, README, roadmap, wiki, or module/package questions. Includes a Trust Contract and structured next_actions. |
| `get_patch_plan_context` | Build a compact implementation map from source/dependency/design evidence: current behavior, relevant files, existing APIs, missing symbols, minimal patch path, risks, verification, warnings, and next actions. It is not a replacement for `get_docs_context` or `get_patch_constraints`. |
| `get_patch_constraints` | Return compact, source-attributed constraints before patching. Designed to provide actionable project constraints for coding agents; it does not validate patches or change `get_docs_context` behavior. |
| `validate_patch_against_constraints` | Deterministically check changed files or a patch diff against a caller-supplied constraint packet after editing. Best-effort advisory guardrail only; it does not prove correctness or replace tests. |

Legacy/admin direct verbs (`sync_project_docs`, `ingest_project_docs`, `bootstrap_project_docs`, `get_project_docs`, `get_project_context`, direct prefetch/refresh/remove/list tools) are hidden from the default Docs MCP surface unless explicitly enabled for compatibility or diagnostics.

Recommended agent workflow:

```text
Question about this repo?       inspect_project_docs -> prepare_docs(action="sync_project_docs") only if inspect says stale/not indexed -> get_docs_context(mode="project")
Coding change / bug fix?        get_docs_context -> get_patch_plan_context -> get_patch_constraints -> edit -> validate_patch_against_constraints -> tests
Dependency/API question?        inspect_project_docs -> get_docs_context(mode="dependency"|"mixed", allow_network=false first) -> prepare_docs(prefetch_*) only after approval
After a patch is written?       validate_patch_against_constraints plus real project tests; unknown/manual_review is not a pass
Debugging Docmancer itself?     use output_mode="debug" or "full"; normal coding agents should use "answer"/"compact"
```

Tool roles, in one line each:

- `inspect_project_docs`: read-only preflight; tells whether local project docs are indexed/stale and what action to take next.
- `prepare_docs(action="sync_project_docs")`: mutate/sync the local project-doc index only when inspect recommends it or the user approved it.
- `get_docs_context`: answer from project/dependency/library docs; use this before guessing architecture or APIs.
- `get_patch_plan_context`: source/API implementation map for coding; pass `changed_files` and `symbol_queries` when known.
- `get_patch_constraints`: pre-edit guardrails; pass `changed_files`; not a planner and not a validator.
- `validate_patch_against_constraints`: post-edit deterministic check; advisory only, then run real tests.

Recommended patch workflow:

```text
get_docs_context
→ get_patch_plan_context
→ get_patch_constraints
→ edit
→ validate_patch_against_constraints
```

Tool roles:

- `get_docs_context`: retrieve project/library docs and broad context.
- `get_patch_plan_context`: build an implementation map from source, dependency, and design evidence.
- `get_patch_constraints`: return source-attributed constraints before patching.
- `validate_patch_against_constraints`: advisory validation after patching.

`get_patch_plan_context` fills the gap between broad docs context and pre-edit constraints. It helps an agent identify exact files, existing APIs, missing symbols, and a minimal implementation path, but it does not generate code and does not validate a patch.

Example `get_patch_plan_context` arguments:

```json
{
  "question": "Plan changing Flutter menu_line from inline menu to bottom sheet using menu.pen design and pole_base_kit APIs. Preserve screenshot/camera/tabs/ScanDoc/rating/info/logout/admin, remove legacy BT QR buttons, preserve needFlashLight/needBT/isEmulator semantics.",
  "project_path": "/path/to/project",
  "symbol_queries": [
    "menu_line",
    "menu_icon",
    "system_line",
    "menu_notifier",
    "tab_icon",
    "showBottomDialog",
    "PBBottomSheet",
    "PBButton",
    "PBIcon",
    "PBIcons"
  ],
  "design_context": {
    "artifact": "menu.pen",
    "summary": "Caller-normalized design summary for the bottom-sheet menu"
  },
  "include_dependency_source": true,
  "max_files": 12,
  "max_snippets": 16,
  "max_tokens": 2400,
  "output_mode": "compact"
}
```

Expected result summary:

- top-level contract includes `reason_code`, `token_estimate`, and `output_mode`;
- `current_behavior` entries include `behavior`, `file`, `start_line`, `end_line`, `symbol`, `evidence`, and `confidence`;
- `risks_and_constraints` entries include `risk`, `severity`, `source`, and `mitigation`;
- caller-provided `design_context` is passed through into the plan context;
- exact relevant files for `menu_line`, `menu_icon`, `system_line`, `menu_notifier`, and tabs behavior when requested;
- `showBottomDialog: not_found` in `missing_symbols` when the project does not define it;
- `PBBottomSheet.open` found in resolved dependency source when available through `.dart_tool/package_config.json`;
- unrelated broad docs can appear in `rejected_sources` when they match generic words but not exact patch terms;
- `minimal_patch_path` describing replacement of the inline menu with a bottom sheet without generating a patch;
- `verification` includes `flutter analyze` for Flutter/UI-like tasks.

Non-goals:

- does not generate a patch;
- does not guarantee safe merge;
- does not index the whole `.pub-cache`;
- does not replace code reading by the agent;
- does not replace constraints validation.

`get_patch_constraints` arguments:

```json
{
  "question": "Update permission preflight behavior",
  "project_path": "/path/to/repo",
  "changed_files": ["lib/modules/permission/domain/services/permission_service.dart"],
  "max_constraints": 12,
  "max_tokens": 1200,
  "include_sources": true
}
```

The tool uses deterministic local heuristics over visible project docs and dependency metadata. It can surface generated-file rules, source-of-truth rules, provider/delegation conventions, pinned dependency/version contracts, lockfile guardrails, and suggested checks. Every constraint includes source attribution, confidence, and short evidence. If the packet exceeds the budget, must/high-confidence constraints are kept first and a warning is returned.


### validate_patch_against_constraints — deterministic post-edit guardrail

Use after editing code:

1. Call `get_patch_constraints` before editing.
2. Edit code.
3. Call `validate_patch_against_constraints` with the returned constraints plus `changed_files` or `patch_diff`.
4. Fix deterministic violations.
5. Run the project tests.

Arguments:

```json
{
  "constraints": "object|array",
  "project_path": "string|null",
  "changed_files": "array[string]|null",
  "patch_diff": "string|null",
  "strict": "boolean"
}
```

Return shape:

```json
{
  "total_constraints": 0,
  "satisfied": 0,
  "violated": 0,
  "unknown": 0,
  "results": [],
  "warnings": [],
  "confidence": "high|medium|low"
}
```

The validator is deterministic best-effort. It detects clear generated-file edits, lockfile edits, provider/UI policy edits, and source-of-truth layer matches. `unknown` means manual review is required. It does not call an LLM, does not fetch docs, does not prove correctness, and does not replace tests.

### get_patch_constraints — expanded deterministic heuristics

Supported visible-source patterns include architecture docs (`ARCHITECTURE.md`, `docs/architecture.md`), ADRs, `CONTRIBUTING.md`, root/module READMEs, and maintained `docs/` files. The compiler looks for cautious deterministic phrases such as `must`, `must not`, `should`, `belongs to`, `owned by`, `source of truth`, `canonical`, `single source`, `do not duplicate`, `do not bypass`, `do not hardcode`, and documented layer ownership/delegation language.

Owner extraction covers forms such as `PermissionService owns permission policy`, `policy belongs in PermissionService`, `PermissionService is source of truth for policy`, `Do not implement policy in providers; delegate to PermissionService`, and `Provider delegates to PermissionService`. Generated-artifact rules cover docs mentioning generated files, regeneration, source models, `build_runner`, `*.g.dart`, `*.freezed.dart`, protobuf outputs, `*.generated.*`, `generated/`, and `dist/`.

Dependency/version constraints are compiled from visible supported manifests and lockfiles including `pubspec.yaml`/`pubspec.lock`, `pyproject.toml`, `requirements.txt`, `poetry.lock`, `uv.lock`, `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Cargo.toml`/`Cargo.lock`, and `go.mod`/`go.sum` where deterministic versions are available. `changed_files` and task keywords only rank constraints and checks; they do not create high-confidence invented owners or versions without visible source evidence.

Response shape:

```json
{
  "task": "Update permission preflight behavior",
  "constraints": [],
  "forbidden_edits": [],
  "dependency_contracts": [],
  "source_of_truth_rules": [],
  "suggested_checks": [],
  "warnings": [],
  "sources": [],
  "token_estimate": 0,
  "confidence": "high"
}
```

Do not treat this as proof that DocAtlas improves coding-agent success. It is a compact constraint compiler surface for agent prompts, not a production patch validator.

## Dependency-docs project tools

| Tool | Purpose |
|---|---|
| `prefetch_project_docs` | Existing tool name for prefetching exact dependency docs from supported manifests/lockfiles. This is not project-owned docs ingest. |
| `prefetch_project_dependency_docs` | Non-breaking alias for `prefetch_project_docs` with clearer naming. Prefer this name in new docs and agent instructions. |

These tools may fetch documentation from the network. Ask for user confirmation before running unless the user has already approved dependency-docs prefetch.

## Manifest, target, and job tools

| Tool | Purpose |
|---|---|
| `validate_docs_manifest` | Validate a `docmancer.docs.yaml` manifest without fetching documentation. |
| `prefetch_docs_manifest` | Validate and prefetch documentation targets declared in a manifest. |
| `prefetch_docs_targets` | Download and index one or more explicit documentation targets. |
| `get_docs_job_status` | Return persistent progress for a docs indexing or prefetch job. |
| `list_docs_jobs` | List docs jobs, optionally filtered by status. |
| `cancel_docs_job` | Request cancellation for a docs indexing or prefetch job. |

## Recommended project-docs happy path

For repo-specific questions, agents should prefer this flow:

```text
inspect_project_docs(project_path)
-> prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true) if needed
-> get_docs_context(project_path=..., question=..., mode="project")
```

Legacy compatibility surfaces may still expose direct project-doc tools. Public MCP clients should prefer the unified flow above.

The explicit decision flow is:

```text
inspect_project_docs(project_path)
-> if reason_code is project_docs_found_not_indexed: prepare_docs(action="sync_project_docs", project_path=...)
-> if reason_code is project_docs_stale: prepare_docs(action="sync_project_docs", project_path=...)
-> if reason_code is project_docs_ready: get_docs_context(project_path=..., question=..., mode="project")
```

For module-specific questions in monorepos, inspect first so the agent can see discovered modules, then query with an exact `module_path` when possible:

```text
inspect_project_docs(project_path)
-> project_docs.modules / project_docs.indexed_modules
-> get_docs_context(project_path=..., question=..., mode="project", module_path="services/auth", scope="module")
```

`get_docs_context(mode="project")` accepts:

| Argument | Meaning |
|---|---|
| `module_path` | Exact module path such as `packages/backend`, `apps/web`, or `services/auth`. Prefer this when known. |
| `module` | Exact module id or module name. If the same name appears under multiple parents, Docmancer returns `module_ambiguous`; agents must ask the user instead of choosing silently. |
| `scope` | `project`, `module`, or `all`. A resolved module automatically scopes retrieval to module docs. |

If a user asks a vague module question such as "How does auth work?" and multiple modules could match, agents should ask which module to use or whether to search across all project docs. They should not infer the target from code paths or model memory.

If no project docs exist, or if the repo has docs but no high-level overview/architecture doc, Docmancer should not silently write repository files. It returns a confirmation-required remediation path so the coding agent can ask the user before creating a reviewable `ARCHITECTURE.md`.

If dependency docs are available from manifests/lockfiles but missing locally, Docmancer should not silently fetch from the network. It returns a confirmation-required dependency-docs prefetch action.

## Compact MCP responses

All project-docs lifecycle tools return compact responses by default. Pass `details: true` for the full structured response.

Compact `prepare_docs(action="sync_project_docs")` response:

```json
{
  "status": "success",
  "project_path": "/path/to/repo",
  "candidate_count": 4,
  "summary": {
    "current": 3,
    "new": 1,
    "changed": 0,
    "orphaned": 0,
    "orphaned_removed": 1,
    "dedup_removed": 0,
    "stale_removed": 0,
    "missing": 0,
    "sections_indexed": 24
  }
}
```

Compact `inspect_project_docs` response:

```json
{
  "project_path": "/path/to/repo",
  "project_detected": true,
  "reason_code": "project_docs_ready",
  "next_action": {
    "type": "get_project_context",
    "tool": "get_project_context"
  },
  "source_summary": {
    "candidates": 4,
    "indexed": 4,
    "stale": 0,
    "ignored": 0
  },
  "recommended_next_actions": []
}
```

Compact `ingest_project_docs` response:

```json
{
  "status": "success",
  "project_path": "/path/to/repo",
  "candidate_count": 4,
  "sections_indexed": 24,
  "source_summary": {
    "indexed": 4,
    "missing": 0,
    "skipped": 0
  }
}
```

Compact `bootstrap_project_docs` response:

```json
{
  "project_path": "/path/to/repo",
  "status": "ready",
  "reason_code": "project_docs_ready",
  "actions_taken": ["inspect", "sync"],
  "next_action": {
    "type": "get_project_context",
    "tool": "get_project_context"
  }
}
```

Compact `get_project_docs` response:

```json
{
  "project_path": "/path/to/repo",
  "query": "architecture",
  "status": "success",
  "answer_available": true,
  "source_summary": {
    "candidates": 4,
    "indexed": 4,
    "stale": 0,
    "ignored": 0
  },
  "results": [ ... ],
  "next_action": {},
  "next_actions": []
}
```

Compact `get_project_context` response:

```json
{
  "project_path": "/path/to/repo",
  "question": "how does auth work",
  "status": "success",
  "answer_available": true,
  "mode": "auto",
  "context_pack": [ ... ],
  "answer_outline": {
    "query_intent": "architecture",
    "recommended_reading_order": [ ... ],
    "coverage": { ... },
    "warnings": []
  },
  "trust_contract": {
    "selected_sources": [ ... ],
    "selected": [ ... ],
    "rejected": [ ... ],
    "risky": [ ... ]
  },
  "next_actions": [],
  "metrics": { ... },
  "warnings": []
}
```

## Maintained docs index and verification

For multi-doc repositories, recommend a maintained `docs/INDEX.md` as the canonical map of official project-owned docs. It should link root docs, architecture docs, ADRs, module/package docs, runbooks, investigation notes, and explicitly list generated/tooling docs that should be ignored. Agents should treat that index as evidence of which nested docs are intentional and maintained.

After docs are added, moved, refreshed, or reorganized, use this smoke-test loop before relying on answers:

```text
prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)
-> inspect_project_docs(project_path) to confirm
-> get_docs_context(mode="project") with 2-3 project-specific questions
-> confirm expected files appear in selected_sources, indexed_sources, or result chunks
```

If expected files are missing, fix links in `docs/INDEX.md` or root docs, move maintained docs into discovered docs locations, update discovery/manifest entries, then re-sync and repeat the smoke test. If a response reports `indexed_source_not_discovered`, it means the indexed file was not selected by the current discovery pass; it is not automatically deleted, invalid, or irrelevant.

## Structured project-docs contract

Project-docs MCP responses use a stable structured contract so agents can follow the next step without guessing:

| Field | Meaning |
|---|---|
| `reason_code` | Primary machine-readable state for project docs readiness. |
| `next_action` | One recommended next step with the tool/action type and relevant arguments. |
| `next_actions` / `recommended_next_actions` | Additional recommended follow-up actions when a response can surface more than one remediation path. |
| `requires_confirmation` | Whether the agent must ask the user before continuing. |
| `confirmation_reason` | Why confirmation is needed, for example `repo_write` or `network_fetch`. |
| `arguments_patch` | Exact arguments the agent can apply to the next tool call after approval or after following the flow. |
| `agent_message` | Short instruction for coding agents. |
| `user_message` | User-facing explanation suitable for chat. |

Current project-docs `reason_code` values:

| `reason_code` | Meaning | Expected next step |
|---|---|---|
| `no_project_docs` | No reviewable project-owned docs were discovered. | Ask before creating `ARCHITECTURE.md`; then sync and inspect. |
| `project_docs_found_not_indexed` | Docs candidates exist but are not indexed yet. | Call `prepare_docs(action="sync_project_docs")`. |
| `project_docs_stale` | Indexed project docs changed on disk or are orphaned/ignored. | Call `prepare_docs(action="sync_project_docs")` to reconcile. |
| `project_docs_ready` | Project docs are discovered and current. | Call `get_docs_context(mode="project")`. |
| `architecture_doc_creation_recommended` | Docs exist but no high-level overview/architecture doc was discovered. | Ask before creating `ARCHITECTURE.md`; then sync and inspect. |
| `no_project_docs_results` | Project docs are indexed but the query returned no matching sections. | Inspect project docs and refine/remediate before guessing. |
| `module_not_found` | A requested `module` or `module_path` was not found among discovered module docs. | Inspect available modules and retry with an exact `module_path`, or ask the user whether to search all project docs. |
| `module_ambiguous` | A requested module name matches more than one module path. | Ask the user to choose a module path; do not choose silently. |
| `no_module_docs` | The module target exists in the module-resolution flow, but no maintained docs were available for the requested module scope. | Do not invent architecture; optionally fall back to project-level docs or ask before creating module README/ARCHITECTURE docs. |

## Safety rules for agents

- Read `answer_outline.recommended_reading_order` when present; it is non-LLM guidance derived from selected sources.
- Read `trust_contract.selected_sources` or the compatibility alias `trust_contract.selected` before citing sources.
- For each context item, use either flat fields (`path`, `title`, `heading_path`, `freshness`) or nested fields (`source.path`, `source.title`, `section.heading_path`).
- Treat `CHANGELOG.md` as release-history evidence unless the user asks about changes, releases, migrations, or version history.
- Distinguish the Docs MCP server (`doc-atlas mcp docs-serve`) from the Packs MCP runtime (`doc-atlas mcp packs-serve`; `serve` is a compatibility alias).
- Call `inspect_project_docs` first for repo-specific questions (read-only).
- `prepare_docs(action="sync_project_docs")` is the recommended public lifecycle action; it reconciles and prunes in one call.
- Do not WebFetch project architecture/conventions before trying project-owned docs.
- Do not treat `prefetch_project_docs` as project-owned docs ingest; it is dependency-docs prefetch.
- Do not create or edit `ARCHITECTURE.md` without user confirmation.
- Do not create or edit module README/ARCHITECTURE docs without user confirmation.
- Do not silently choose between ambiguous modules; retry with exact `module_path` after user clarification.
- Do not run dependency-docs prefetch without user confirmation when it may fetch from the network.
- Keep official project knowledge as reviewable files in the repository, not hidden agent memory.
- Treat maintained `docs/INDEX.md` as the canonical map of project-owned docs when present.
- After docs are added, moved, or refreshed, recommend the post-ingestion verification loop and confirm expected files are cited.
