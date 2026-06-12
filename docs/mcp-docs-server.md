# Docmancer MCP docs server

Docmancer exposes its documentation runtime through a Context7-style MCP server:

```bash
docmancer mcp docs-serve
```

Use this server when a coding agent needs local, source-grounded documentation context instead of relying on model memory, latest-only hosted docs, or repeated `WebFetch` calls.

## What the MCP server covers

Docmancer's MCP docs server has three main lanes:

1. **Library docs** — resolve, fetch, refresh, prefetch, inspect, and query public or registered documentation sources.
2. **Project-owned docs** — discover, ingest, stale-check, and query reviewable repository docs such as `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, and roadmap files.
3. **Dependency docs from project metadata** — read supported manifests/lockfiles and prefetch exact dependency documentation for the versions the project actually uses.

Project-owned docs and dependency docs are intentionally separate. `ingest_project_docs` indexes files that already live in the repository. `prefetch_project_docs` / `prefetch_project_dependency_docs` fetch dependency documentation from the network based on manifests or lockfiles.

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

Example client config:

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

For registered sources, agents should retry through Docmancer using returned candidates or `arguments_patch`. They should not use `WebFetch` for a registered source before trying the Docmancer retry path.

## Project-owned docs tools

| Tool | Purpose |
|---|---|
| `inspect_project_docs` | Read-only discovery of local project docs and exact dependency metadata. Call this first inside a repository unless using `bootstrap_project_docs`. |
| `ingest_project_docs` | Index discovered reviewable project-owned docs after `inspect_project_docs` recommends it. Does not ingest source code, dependency directories, build outputs, or dependency docs. |
| `bootstrap_project_docs` | Safe high-level onboarding for a repository question: inspect, ingest or refresh existing reviewable docs, then inspect again. Stops before repo writes or dependency-docs network fetches. |
| `get_project_docs` | Query indexed project-owned docs for repo-specific architecture, conventions, runbooks, ADRs, README, roadmap, or wiki questions. Missing, stale, not-indexed, or unmatched docs return structured next actions. |
| `get_project_context` | Return a compact repo-grounded context pack after inspect/ingest. It combines project docs with one exact dependency-doc source when requested/detectable and includes a Trust Contract plus `next_actions`. Supports `mode`: `auto`, `project-only`, `deps-only`, or `public-docs`. |

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
bootstrap_project_docs(project_path, question?)
-> get_project_context(project_path, question)
```

The lower-level explicit flow is:

```text
inspect_project_docs(project_path)
-> if reason_code is project_docs_found_not_indexed: ingest_project_docs(project_path)
-> if reason_code is project_docs_stale: ingest_project_docs(project_path)
-> if reason_code is project_docs_ready: get_project_context(project_path, question)
```

If no project docs exist, or if the repo has docs but no high-level overview/architecture doc, Docmancer should not silently write repository files. It returns a confirmation-required remediation path so the coding agent can ask the user before creating a reviewable `ARCHITECTURE.md`.

If dependency docs are available from manifests/lockfiles but missing locally, Docmancer should not silently fetch from the network. It returns a confirmation-required dependency-docs prefetch action.

## Maintained docs index and verification

For multi-doc repositories, recommend a maintained `docs/INDEX.md` as the canonical map of official project-owned docs. It should link root docs, architecture docs, ADRs, module/package docs, runbooks, investigation notes, and explicitly list generated/tooling docs that should be ignored. Agents should treat that index as evidence of which nested docs are intentional and maintained.

After docs are added, moved, refreshed, or reorganized, use this smoke-test loop before relying on answers:

```text
inspect_project_docs(project_path)
-> ingest_project_docs(project_path, skip_known=false, with_vectors=true) when docs are new or stale
-> inspect_project_docs(project_path) again
-> get_project_context/get_project_docs with 2-3 project-specific questions
-> confirm expected files appear in selected_sources, indexed_sources, or result chunks
```

If expected files are missing, fix links in `docs/INDEX.md` or root docs, move maintained docs into discovered docs locations, update discovery/manifest entries, then re-ingest and repeat the smoke test. If a response reports `indexed_source_not_discovered`, it means the indexed file was not selected by the current discovery pass; it is not automatically deleted, invalid, or irrelevant.

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
| `no_project_docs` | No reviewable project-owned docs were discovered. | Ask before creating `ARCHITECTURE.md`; then inspect and ingest. |
| `project_docs_found_not_indexed` | Docs candidates exist but are not indexed yet. | Call `ingest_project_docs`. |
| `project_docs_stale` | Indexed project docs changed on disk. | Call `ingest_project_docs` to refresh. |
| `project_docs_ready` | Project docs are discovered and current. | Call `get_project_context` or `get_project_docs`. |
| `architecture_doc_creation_recommended` | Docs exist but no high-level overview/architecture doc was discovered. | Ask before creating `ARCHITECTURE.md`; then inspect and ingest. |
| `no_project_docs_results` | Project docs are indexed but the query returned no matching sections. | Inspect project docs and refine/remediate before guessing. |

## Safety rules for agents

- Call `inspect_project_docs` first for repo-specific questions, unless using `bootstrap_project_docs`.
- Do not WebFetch project architecture/conventions before trying project-owned docs.
- Do not treat `prefetch_project_docs` as project-owned docs ingest; it is dependency-docs prefetch.
- Do not create or edit `ARCHITECTURE.md` without user confirmation.
- Do not run dependency-docs prefetch without user confirmation when it may fetch from the network.
- Keep official project knowledge as reviewable files in the repository, not hidden agent memory.
- Treat maintained `docs/INDEX.md` as the canonical map of project-owned docs when present.
- After docs are added, moved, or refreshed, recommend the post-ingestion verification loop and confirm expected files are cited.
