# Project docs MCP workflow

Project docs are the reviewable documentation files that belong to a repository: `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, roadmap files, module/package docs, and similar files. Docmancer can discover, index, reconcile, and query those files through MCP so coding agents answer from the repo's own docs before falling back to generic public documentation.

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
3. **removes** stale indexed sections (files that changed on disk);
4. **indexes** new and changed candidates;
5. **reports** current_count, new_count, changed_count, orphaned_removed, indexed_sources.

No need to call `inspect` first: sync does a full reconcile. Call `inspect` only when you need read-only discovery without side effects.

## Preferred happy path

For most agents, the simplest safe flow is:

```text
bootstrap_project_docs(project_path, question?)
get_project_context(project_path, question)
```

For explicit lifecycle control, use:

```text
inspect_project_docs(project_path)
sync_project_docs(project_path, with_vectors=true)
get_project_context(project_path, question)
```

`sync_project_docs` is the canonical project-docs lifecycle action. It reconciles the local project-docs index with the current filesystem discovery snapshot:

- discovers current reviewable project-doc candidates;
- removes orphaned indexed docs whose files were deleted or are no longer discovered;
- removes stale indexed sections for changed files;
- indexes new and changed reviewable docs;
- verifies the final indexed state before reporting results.

`ingest_project_docs` is a legacy low-level operation. New agent instructions should prefer `sync_project_docs` because project docs are owned by the repository filesystem, and the index is only a cache of that current state.

## Explicit low-level flow

Agents that need precise control can use the lower-level tools:

```text
inspect_project_docs(project_path)
```

Then follow the returned `reason_code`:

| `reason_code` | What it means | Agent action |
|---|---|---|
| `project_docs_ready` | Project docs are discovered and current. | Call `get_project_context` or `get_project_docs`. |
| `project_docs_found_not_indexed` | Reviewable docs exist but are not indexed. | Call `sync_project_docs`. |
| `project_docs_stale` | Indexed docs changed on disk, were deleted, or are no longer part of current discovery. | Call `sync_project_docs`. |
| `no_project_docs` | No reviewable docs were discovered. | Ask before creating a reviewable `ARCHITECTURE.md`. |
| `architecture_doc_creation_recommended` | Some docs exist, but no high-level overview/architecture doc was found. | Ask before creating `ARCHITECTURE.md`. |
| `no_project_docs_results` | Indexed docs did not answer the query. | Inspect docs and reconcile with `sync_project_docs` before guessing. |

After `sync_project_docs`, proceed to:

```text
get_project_context(project_path, question)
```

`get_project_context` returns a compact Trust Contract with selected, rejected, and risky sources, plus `next_actions` for missing, stale, non-exact, or unmatched docs. Use `mode` when the agent should constrain sources explicitly: `auto`, `project-only`, `deps-only`, or `public-docs`.

Or, for project docs only:

```text
get_project_docs(project_path, query)
```

For module-specific queries, use exact module filters:

```text
get_project_docs(
  project_path,
  query,
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

Within each module root, Docmancer looks for maintained docs such as `README*`, `ARCHITECTURE*`, `CHANGELOG*`, `CONTRIBUTING*`, `docs/`, `doc/`, ADR folders, and runbook folders. It does not index source code as module docs.

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

Docmancer does not create architecture docs itself. If `inspect_project_docs` or `bootstrap_project_docs` returns `no_project_docs` or `architecture_doc_creation_recommended`, the coding agent should ask:

```text
I could inspect the repository and create ARCHITECTURE.md as a reviewable project doc. Should I do that?
```

If approved, the coding agent should:

1. inspect the codebase;
2. write `ARCHITECTURE.md` as a normal repository file;
3. call `inspect_project_docs`;
4. call `sync_project_docs`;
5. answer future repo-specific questions from `get_project_context` or `get_project_docs`.

Do not store generated architecture only in hidden memory. Official project knowledge should remain a file humans can review and edit.

## Dependency docs are separate

`inspect_project_docs` also reports dependency metadata from supported manifests and lockfiles. That metadata is useful for exact-version docs, but it is not the same as project-owned docs.

Use:

```text
sync_project_docs(project_path)
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

## Maintained docs index

For repositories with more than a few documentation files, keep a reviewable documentation map at:

```text
docs/INDEX.md
```

Docmancer can discover common root docs and documentation directories without this file, but a maintained index makes intent explicit for both humans and agents. Treat `docs/INDEX.md` as the canonical map of project-owned docs: it should link the files that are official, maintained, and safe to use as project evidence.

Copy-paste template:

```markdown
# Documentation Index

This file is the canonical map of maintained project-owned documentation.

## Start here

- [README](../README.md) — product/project overview and setup.
- [Architecture](../ARCHITECTURE.md) — high-level architecture and major decisions.

## Architecture and decisions

- [Architecture overview](architecture.md) — current system shape and boundaries.
- [ADR index](adr/README.md) — accepted architecture decision records.

## Modules and packages

- [Backend module](../packages/backend/README.md) — backend-specific conventions.
- [Frontend module](../packages/frontend/README.md) — frontend-specific conventions.
- [Auth service](../services/auth/README.md) — authentication service architecture and runbook.

## Runbooks

- [Deploy runbook](runbooks/deploy.md) — release and rollback steps.
- [Incident runbook](runbooks/incidents.md) — operational response steps.

## Investigation notes

- [Investigations](investigations/README.md) — time-bound research notes. Mark each note with owner/date/status.

## Generated or tooling docs to ignore

- `build/`, `dist/`, `coverage/`, `.dart_tool/`, `node_modules/`, `.venv/` — generated, dependency, or tooling output.
- Link a generated file here only if humans intentionally maintain it as project documentation.

## Maintenance rules

- Add new official docs here when they are created or moved.
- Remove or mark stale docs when decisions change.
- After reorganizing docs, run the Docmancer verification loop: sync, then inspect, then ask smoke-test questions and confirm expected files are cited.
```

When an expected nested document is missing from results, first check whether it is linked from root docs or `docs/INDEX.md`, lives under a discovered docs location, or needs a discovery/manifest update. If `inspect_project_docs` reports `indexed_source_not_discovered`, do not assume the indexed file is deleted or invalid: it means the current discovery pass did not select it as a project-doc candidate. Link it from `docs/INDEX.md` or root docs, move it under a discovered docs location, adjust discovery, or run `sync_project_docs` to remove obsolete index entries.

## Verification loop

After adding, moving, deleting, refreshing, or reorganizing project docs, verify that discovery, indexing, and retrieval agree before relying on answers.

Checklist:

1. Run `inspect_project_docs(project_path)`.
   - Confirm the expected files appear in `project_docs.found`.
   - Check `project_docs.ignored`, `project_docs.stale`, and `source_state_guidance`.

2. If docs are new, changed, stale, orphaned, or missing from the index, run:

   ```text
   sync_project_docs(project_path, with_vectors=true)
   ```

3. Run `inspect_project_docs(project_path)` again.
   - Confirm `reason_code` is `project_docs_ready` or follow the returned `next_action`.

4. Ask two or three project-specific smoke-test questions with `get_project_context` or `get_project_docs`.
   - Use terms that should only appear in the expected docs.
   - Confirm the expected files are cited in `selected_sources`, `indexed_sources`, or result chunks.
5. If expected files are not cited, fix the source map instead of guessing:
   - add or correct links in `docs/INDEX.md` or root docs;
   - move maintained docs under `docs/`, `wiki/`, ADR, roadmap, or runbook-style locations;
   - update discovery configuration or `docmancer.docs.yaml` manifest entries if the docs are external dependency/public docs;
   - re-run sync and repeat the smoke test.

Suggested smoke-test questions:

```text
get_project_context(project_path, "What is the architecture decision for <unique ADR term>?")
get_project_context(project_path, "How do we deploy <unique service/module name>?")
get_project_docs(project_path, "<unique heading or phrase from docs/INDEX.md target>")
get_project_docs(project_path, "<unique module phrase>", module_path="<module>", scope="module")
get_project_context(project_path, "<module-specific question>", module_path="<module>", scope="module")
```

Agents should recommend this verification loop whenever docs were just added, refreshed, reorganized, or when a user expected a source that was not cited.

## Example response handling

Example: docs exist but are not indexed.

```json
{
  "reason_code": "project_docs_found_not_indexed",
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

The agent should call `sync_project_docs` with the provided arguments.

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
