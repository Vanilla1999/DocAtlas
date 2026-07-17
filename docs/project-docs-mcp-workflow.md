# Project docs MCP workflow

Project docs are the reviewable documentation files that belong to a repository: `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, roadmap files, module/package docs, and similar files. DocAtlas can discover, index, reconcile, and query those files through MCP so coding agents answer from the repo's own docs before falling back to generic public documentation.

## Use this workflow when

Use project-docs MCP tools when the user asks about:

- how this repository works;
- architecture, conventions, runbooks, ADRs, or roadmap;
- repo-specific implementation guidance;
- package, app, service, crate, library, or feature-area docs inside a monorepo;
- deploy/runbook or conventions for a specific module;
- project-owned docs as context for a code change;
- a Context7-like docs workflow but grounded in the local repository.

## Canonical lifecycle: sync

`sync_project_docs` is the recommended lifecycle action. It replaces the old two-step `inspect → ingest` loop:

1. **discovers** current candidates from the filesystem;
2. **prunes** orphaned indexed sources (files that no longer exist);
3. **deduplicates** duplicate indexed sources by path, keeping the most recently ingested row;
4. **removes** stale indexed sections (files that changed on disk);
5. **indexes** new and changed candidates;
6. **reports** current_count, new_count, changed_count, orphaned_removed, dedup_removed, stale_removed, indexed_sources.

No need to call `inspect` first: sync does a full reconcile. Call `inspect` only when you need read-only discovery without side effects.

## Preferred happy path

For public MCP clients, start with context and follow its decision:

```text
get_docs_context(project_path=..., question=..., mode="project")
-> returned prepare_docs action when required
-> retry get_docs_context
```

The default surface has exactly three tools: `get_docs_context`, `prepare_docs`, and `docs_status`. `prepare_docs(action="sync_project_docs")` reconciles the local project-docs index with the current filesystem discovery snapshot when context returns it or the user explicitly requests synchronization:

- discovers current reviewable project-doc candidates;
- removes orphaned indexed docs whose files were deleted or are no longer discovered;
- removes stale indexed sections for changed files;
- indexes new and changed reviewable docs;
- verifies the final indexed state before reporting results.

`ingest_project_docs` and direct `sync_project_docs` are legacy/compatibility-surface operations. New agent instructions should prefer `prepare_docs(action="sync_project_docs")` because project docs are owned by the repository filesystem, and the index is only a cache of that current state.

## Advanced low-level flow

Agents that enable `DOCMANCER_MCP_ADVANCED_TOOLS=1` can use lower-level inspection tools:

```text
inspect_project_docs(project_path)
```

Then follow the returned `reason_code`:

| `reason_code` | What it means | Agent action |
|---|---|---|
| `project_docs_ready` | Project docs are discovered and current. | Call `get_docs_context(mode="project")`. |
| `project_docs_found_not_indexed` | Reviewable docs exist but are not indexed. | Call `prepare_docs(action="sync_project_docs")`. |
| `project_docs_stale` | Indexed docs changed on disk, were deleted, or are no longer part of current discovery. | Call `prepare_docs(action="sync_project_docs")`. |
| `no_project_docs` | No reviewable docs were discovered. | Ask before creating a reviewable `ARCHITECTURE.md`. |
| `architecture_doc_creation_recommended` | Some docs exist, but no high-level overview/architecture doc was found. | Ask before creating `ARCHITECTURE.md`. |
| `no_project_docs_results` | Indexed docs did not answer the query. | Inspect docs and reconcile with `prepare_docs(action="sync_project_docs")` before guessing. |

After sync, proceed to:

```text
get_docs_context(project_path=..., question=..., mode="project")
```

`get_docs_context(mode="project")` returns a compact Trust Contract with selected, rejected, and risky sources, plus `next_actions` for missing, stale, non-exact, or unmatched docs.

For module-specific queries, use exact module filters:

```text
get_docs_context(
  project_path=...,
  question=...,
  mode="project",
  module_path="packages/backend",
  scope="module"
)
```

`inspect_project_docs` exposes `project_docs.modules` for discovered module docs and `project_docs.indexed_modules` for indexed module docs. Each module summary includes `module_id`, `module_name`, `module_path`, `module_type`, `doc_count`, and `docs`.

## Module docs workflow

Use module docs when the user asks about a specific package, app, service, crate, library, module, feature-area, deploy/runbook, or module-specific convention.

Common discovered module roots include:

```text
packages/*
apps/*
services/*
modules/*
libs/*
crates/*
plugins/*
components/*
```

Within each module root, DocAtlas looks for maintained docs such as `README*`, `ARCHITECTURE*`, `CHANGELOG*`, `CONTRIBUTING*`, `docs/`, `doc/`, ADR folders, and runbook folders. It does not index source code as module docs.

Prefer `module_path` over `module` when known:

| Argument | Use |
|---|---|
| `module_path="services/auth"` | Exact and unambiguous. Preferred for agent retries. |
| `module="auth"` | Exact module id/name lookup. May return `module_ambiguous`. |
| `scope="module"` | Restrict retrieval to module docs. A resolved module path also implies module scope. |
| `scope="project"` | Restrict retrieval to repo-level docs. |
| `scope="all"` | Search both repo-level and module docs. |

If the request is vague and multiple modules could match, the agent must ask the user instead of choosing silently.

If the requested module has no maintained docs, do not invent architecture. The agent may search project-level docs if appropriate, or ask before creating reviewable module documentation such as `services/auth/README.md` or `services/auth/ARCHITECTURE.md`.

## Confirmation gates

Project-docs onboarding has explicit safety gates.

| Gate | `confirmation_reason` | Why it exists |
|---|---|---|
| Repository write | `repo_write` | Creating or editing `ARCHITECTURE.md` changes official project docs and must be reviewable by the user. |
| Module docs write | `repo_write` | Creating or editing module README/ARCHITECTURE docs changes official module knowledge and must be reviewable by the user. |
| Dependency-docs network fetch | `network_fetch` | Prefetching dependency docs may download external documentation and should not happen silently. |

When `requires_confirmation` is `true`, the agent should explain the proposed action and ask the user before continuing.

## Creating `ARCHITECTURE.md`

DocAtlas does not create architecture docs itself. If `inspect_project_docs` or `bootstrap_project_docs` returns `no_project_docs` or `architecture_doc_creation_recommended`, the coding agent should ask:

```text
I could inspect the repository and create ARCHITECTURE.md as a reviewable project doc. Should I do that?
```

If approved, the coding agent should:

1. inspect the codebase;
2. write `ARCHITECTURE.md` as a normal repository file;
3. call `inspect_project_docs`;
4. call `prepare_docs(action="sync_project_docs")`;
5. answer future repo-specific questions from `get_docs_context(mode="project")`.

Do not store generated architecture only in hidden memory. Official project knowledge should remain a file humans can review and edit.

## Dependency docs are separate

Advanced inspection reports dependency metadata from supported manifests and lockfiles. This includes direct npm dependencies from `package.json` resolved through the authoritative `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`. That metadata is useful for exact-version docs, but it is not the same as project-owned docs.

Use:

```text
prepare_docs(action="sync_project_docs", project_path=...)
```

for repository files such as README/docs/wiki/ADR (discovers, reconciles, and indexes).

Use:

```text
prefetch_project_dependency_docs(project_path)
```

or the existing compatible tool name:

```text
prefetch_project_docs(project_path)
```

for exact dependency documentation from manifests/lockfiles.

Prefer `prefetch_project_dependency_docs` in new instructions because it makes the behavior explicit.

## Maintained project-doc catalog

For repositories with nonstandard documentation names or more than a few files, keep a reviewable `docatlas.project-docs.yaml` catalog. When it exists, DocAtlas indexes only validated catalog entries: exact documents and configured roots. Without it, common README/docs/module locations remain a cold-start fallback.

```yaml
schema_version: 1
documents:
  - path: ARCHITECTURE.md
    role: project_architecture
    scope: project
    description: Whole-project architecture and component boundaries.
    authority: source_of_truth
    status: active
    impact: track

  - path: packages/auth/design.md
    role: module_architecture
    scope: module
    module_path: packages/auth
    description: Authentication module architecture and token lifecycle.
    authority: source_of_truth
    status: active
    impact: track

roots:
  - path: backend/docs
    scope: module
    module_path: backend
    authority: source_of_truth

  - path: frontend/guides
    scope: module
    module_path: frontend
    authority: supporting
    index: INDEX.md
```

An entry under `roots` enables bounded recursive discovery below that exact repository directory. When `index` is present, discovery is narrower: DocAtlas includes the index and follows only local documentation links that stay inside the configured root. External links, traversal, symlink targets, missing targets, and index loops cannot expand the project-doc boundary and are reported as warnings.

The host coding model may edit this normal Git file after inspecting the repository. DocAtlas only validates and consumes it. Invalid paths, root traversal, symlinked roots, duplicates, missing files, and unsupported formats fail closed with warnings. An invalid explicit catalog blocks retrieval, ingestion, and synchronization without pruning the existing index; fix the catalog and inspect again. Catalog paths and descriptions are untrusted routing metadata, not agent instructions. Use `status: completed` or `superseded` and `impact: search_only` for exact historical documents. Completed and superseded sources are excluded from ordinary retrieval and remain searchable only for explicit history or completed-roadmap questions.

When project documentation is missing, the returned authoring handoff reports `complete`, `partial`, or `missing` per required section, including named evidence paths/facts and bounded missing-evidence requests. The complete serialized handoff is capped at 12 KiB. If evidence must be omitted, missing categories and the existing sync/retry actions remain present and `documentation_gap.bounds.omitted_counts` records the truncation.

## Verification loop

After adding, moving, deleting, refreshing, or reorganizing project docs, verify that discovery, indexing, and retrieval agree before relying on answers.

Checklist:

1. Run `inspect_project_docs(project_path)`.
   - Confirm the expected files appear in `project_docs.found`.
   - Check `project_docs.ignored`, `project_docs.stale`, and `source_state_guidance`.

2. If docs are new, changed, stale, orphaned, or missing from the index, run:

   ```text
   prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)
   ```

3. Run `inspect_project_docs(project_path)` again.
   - Confirm `reason_code` is `project_docs_ready` or follow the returned `next_action`.

4. Ask two or three project-specific smoke-test questions with `get_docs_context(mode="project")`.
   - Use terms that should only appear in the expected docs.
   - Confirm the expected files are cited in `selected_sources`, `indexed_sources`, or result chunks.
5. If expected files are not cited, fix the source map instead of guessing:
   - add or correct entries in `docatlas.project-docs.yaml`;
   - move maintained docs under `docs/`, `wiki/`, ADR, roadmap, or runbook-style locations;
   - update discovery configuration or `docmancer.docs.yaml` manifest entries if the docs are external dependency/public docs;
   - re-run sync and repeat the smoke test.

Suggested smoke-test questions:

```text
get_docs_context(project_path=..., question="What is the architecture decision for <unique ADR term>?", mode="project")
get_docs_context(project_path=..., question="How do we deploy <unique service/module name>?", mode="project")
get_docs_context(project_path=..., question="<description or unique phrase from a cataloged document>", mode="project")
get_docs_context(project_path=..., question="<unique module phrase>", mode="project", module_path="<module>", scope="module")
get_docs_context(project_path=..., question="<module-specific question>", mode="project", module_path="<module>", scope="module")
```

Agents should recommend this verification loop whenever docs were just added, refreshed, reorganized, or when a user expected a source that was not cited.

## Example response handling

Example: docs exist but are not indexed.

```json
{
  "reason_code": "project_docs_found_not_indexed",
  "requires_confirmation": false,
  "next_action": {
    "type": "prepare_docs",
    "tool": "prepare_docs"
  },
  "arguments_patch": {
    "action": "sync_project_docs",
    "project_path": "/path/to/repo",
    "with_vectors": true
  }
}
```

The agent should call `prepare_docs` with the provided arguments.

Example: stale or orphaned docs.

```json
{
  "reason_code": "project_docs_stale",
  "requires_confirmation": false,
  "next_action": {
    "type": "sync_project_docs",
    "tool": "sync_project_docs"
  },
  "arguments_patch": {
    "project_path": "/path/to/repo",
    "with_vectors": true
  }
}
```

The agent should call `sync_project_docs` to reconcile.

Example: module name is ambiguous.

```json
{
  "status": "module_ambiguous",
  "reason_code": "module_ambiguous",
  "answer_available": false,
  "next_action": {
    "type": "inspect_project_docs",
    "tool": "inspect_project_docs"
  },
  "message": "Module name 'auth' matches multiple module paths. Retry with module_path."
}
```

The agent should show the candidate module paths from `inspect_project_docs` and ask which one to use.

Example: no high-level architecture doc.

```json
{
  "reason_code": "architecture_doc_creation_recommended",
  "requires_confirmation": true,
  "confirmation_reason": "repo_write",
  "next_action": {
    "type": "ask_user_to_create_project_doc",
    "suggested_file": "ARCHITECTURE.md",
    "handled_by": "coding_agent"
  }
}
```

The agent should ask before creating the file.

Example: dependency docs available but missing locally.

```json
{
  "dependency_sources": {
    "dependency_next_action": {
      "type": "ask_user_to_prefetch_dependency_docs",
      "tool_after_confirmation": "prefetch_project_docs",
      "alias_tool_after_confirmation": "prefetch_project_dependency_docs",
      "requires_confirmation": true,
      "confirmation_reason": "network_fetch"
    }
  }
}
```

The agent should ask before prefetching dependency docs.
