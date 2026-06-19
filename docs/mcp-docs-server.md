# Docmancer MCP docs server

Docmancer exposes its documentation runtime through a Context7-style MCP server:

```bash
docmancer mcp docs-serve
```

Use this server when a coding agent needs local, source-grounded documentation context instead of relying on model memory, latest-only hosted docs, or repeated `WebFetch` calls.

## What the MCP server covers

Docmancer's MCP docs server has three main lanes:

1. **Library docs** — resolve, fetch, refresh, prefetch, inspect, and query public or registered documentation sources.
2. **Project-owned docs** — discover, reconcile, index, and query reviewable repository docs such as `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, roadmap files, and module/package docs in monorepos.
3. **Dependency docs from project metadata** — read supported manifests/lockfiles and prefetch exact dependency documentation for the versions the project actually uses.

Project-owned docs and dependency docs are intentionally separate. `sync_project_docs` / `ingest_project_docs` index files that already live in the repository. `prefetch_project_docs` / `prefetch_project_dependency_docs` fetch dependency documentation from the network based on manifests or lockfiles.

Implementation note for maintainers: the public MCP tool names and schemas remain centralized in `docmancer/mcp/docs_server.py`, while tool handling is split by lane under `docmancer/docs/interfaces/mcp/`:

- `docs_tools.py` handles library-docs tools;
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

```json
{
  "mcpServers": {
    "docmancer-docs": {
      "command": "docmancer",
      "args": ["mcp", "docs-serve"]
    }
  }
}
```

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

## Project-owned docs tools

| Tool | Purpose |
|---|---|
| `sync_project_docs` | **Canonical lifecycle action.** Discovers, reconciles, prunes orphaned/stale indexed sources, and indexes new/changed project docs in one call. Returns `current_count`, `new_count`, `changed_count`, `orphaned_removed`, `indexed_sources`. Prefer over `ingest_project_docs`. |
| `inspect_project_docs` | Read-only discovery of local project docs and exact dependency metadata. Call this first for a no-side-effects view. |
| `ingest_project_docs` | Legacy low-level index operation. Does not reconcile or prune — use `sync_project_docs`. |
| `bootstrap_project_docs` | Safe high-level onboarding: inspect, sync if needed, inspect again. Stops before repo writes or dependency-docs network fetches. |
| `get_project_docs` | Query indexed project docs for repo-specific architecture, conventions, runbooks, ADRs, README, roadmap, wiki, or module/package questions. Supports optional `module`, `module_path`, and `scope`; missing, stale, not-indexed, unmatched, or ambiguous docs return structured next actions. |
| `get_project_context` | Return a compact repo-grounded context pack after sync. Combines project docs with one exact dependency-doc source when requested/detectable; includes a Trust Contract plus `next_actions`. Supports `mode`: `auto`, `project-only`, `deps-only`, or `public-docs`; also supports optional `module`, `module_path`, and `scope` for module-scoped context. |

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
sync_project_docs(project_path, with_vectors=true)
-> get_project_context(project_path, question)
```

The higher-level bootstrap alternative:

```text
bootstrap_project_docs(project_path, question?)
-> get_project_context(project_path, question)
```

The old explicit flow (still available but deprecated):

```text
inspect_project_docs(project_path)
-> if reason_code is project_docs_found_not_indexed: sync_project_docs(project_path)
-> if reason_code is project_docs_stale: sync_project_docs(project_path)
-> if reason_code is project_docs_ready: get_project_context(project_path, question)
```

For module-specific questions in monorepos, inspect first so the agent can see discovered modules, then query with an exact `module_path` when possible:

```text
inspect_project_docs(project_path)
-> project_docs.modules / project_docs.indexed_modules
-> get_project_context(project_path, question, module_path="services/auth", scope="module")
```

`get_project_docs` and `get_project_context` accept:

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

Compact `sync_project_docs` response:

```json
{
  "tool": "sync_project_docs",
  "status": "success",
  "current_count": 3,
  "new_count": 1,
  "changed_count": 0,
  "orphaned_removed": 1
}
```

Compact `inspect_project_docs` response:

```json
{
  "tool": "inspect_project_docs",
  "reason_code": "project_docs_ready",
  "next_action": {
    "type": "sync_project_docs",
    "tool": "sync_project_docs"
  },
  "candidate_count": 4,
  "indexed_count": 4,
  "stale_count": 0,
  "ignored_count": 0,
  "requires_confirmation": false
}
```

Compact `ingest_project_docs` response:

```json
{
  "tool": "ingest_project_docs",
  "status": "success",
  "candidate_count": 4,
  "sections_indexed": 24
}
```

Compact `bootstrap_project_docs` response:

```json
{
  "tool": "bootstrap_project_docs",
  "status": "ready",
  "reason_code": "project_docs_ready",
  "next_action": {
    "type": "get_project_context",
    "tool": "get_project_context"
  },
  "requires_confirmation": false
}
```

Compact `get_project_docs` response:

```json
{
  "tool": "get_project_docs",
  "status": "success",
  "answer_available": true,
  "source_summary": {
    "candidates": 4,
    "indexed": 4,
    "stale": 0,
    "ignored": 0
  },
  "results": [ ... ]
}
```

Compact `get_project_context` response:

```json
{
  "tool": "get_project_context",
  "status": "success",
  "answer_available": true,
  "source_summary": {
    "candidates": 4,
    "indexed": 4,
    "stale": 0,
    "ignored": 0
  },
  "selected_sources": [ ... ],
  "results": [ ... ]
}
```

## Maintained docs index and verification

For multi-doc repositories, recommend a maintained `docs/INDEX.md` as the canonical map of official project-owned docs. It should link root docs, architecture docs, ADRs, module/package docs, runbooks, investigation notes, and explicitly list generated/tooling docs that should be ignored. Agents should treat that index as evidence of which nested docs are intentional and maintained.

After docs are added, moved, refreshed, or reorganized, use this smoke-test loop before relying on answers:

```text
sync_project_docs(project_path, with_vectors=true)
-> inspect_project_docs(project_path) to confirm
-> get_project_context/get_project_docs with 2-3 project-specific questions
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
| `project_docs_found_not_indexed` | Docs candidates exist but are not indexed yet. | Call `sync_project_docs`. |
| `project_docs_stale` | Indexed project docs changed on disk or are orphaned/ignored. | Call `sync_project_docs` to reconcile. |
| `project_docs_ready` | Project docs are discovered and current. | Call `get_project_context` or `get_project_docs`. |
| `architecture_doc_creation_recommended` | Docs exist but no high-level overview/architecture doc was discovered. | Ask before creating `ARCHITECTURE.md`; then sync and inspect. |
| `no_project_docs_results` | Project docs are indexed but the query returned no matching sections. | Inspect project docs and refine/remediate before guessing. |
| `module_not_found` | A requested `module` or `module_path` was not found among discovered module docs. | Inspect available modules and retry with an exact `module_path`, or ask the user whether to search all project docs. |
| `module_ambiguous` | A requested module name matches more than one module path. | Ask the user to choose a module path; do not choose silently. |
| `no_module_docs` | The module target exists in the module-resolution flow, but no maintained docs were available for the requested module scope. | Do not invent architecture; optionally fall back to project-level docs or ask before creating module README/ARCHITECTURE docs. |

## Safety rules for agents

- Call `inspect_project_docs` first for repo-specific questions (read-only), unless using `bootstrap_project_docs` or going straight to `sync_project_docs`.
- `sync_project_docs` is the recommended lifecycle action; it reconciles and prunes in one call.
- Do not WebFetch project architecture/conventions before trying project-owned docs.
- Do not treat `prefetch_project_docs` as project-owned docs ingest; it is dependency-docs prefetch.
- Do not create or edit `ARCHITECTURE.md` without user confirmation.
- Do not create or edit module README/ARCHITECTURE docs without user confirmation.
- Do not silently choose between ambiguous modules; retry with exact `module_path` after user clarification.
- Do not run dependency-docs prefetch without user confirmation when it may fetch from the network.
- Keep official project knowledge as reviewable files in the repository, not hidden agent memory.
- Treat maintained `docs/INDEX.md` as the canonical map of project-owned docs when present.
- After docs are added, moved, or refreshed, recommend the post-ingestion verification loop and confirm expected files are cited.
