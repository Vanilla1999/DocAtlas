# Project docs MCP workflow

Project docs are the reviewable documentation files that belong to a repository: `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, ADRs, runbooks, roadmap files, and similar files. Docmancer can discover, index, stale-check, and query those files through MCP so coding agents answer from the repo's own docs before falling back to generic public documentation.

## Use this workflow when

Use project-docs MCP tools when the user asks about:

- how this repository works;
- architecture, conventions, runbooks, ADRs, or roadmap;
- repo-specific implementation guidance;
- project-owned docs as context for a code change;
- a Context7-like docs workflow but grounded in the local repository.

## Preferred happy path

For most agents, the simplest safe flow is:

```text
bootstrap_project_docs(project_path, question?)
get_project_context(project_path, question)
```

`bootstrap_project_docs` is intentionally conservative. It may:

1. inspect project docs;
2. ingest existing reviewable docs if they are found but not indexed;
3. refresh existing indexed docs if they are stale;
4. inspect again and return the current state.

It will not:

- create or edit repository files;
- create `ARCHITECTURE.md` automatically;
- fetch dependency documentation from the network.

When those actions are needed, it stops with `status = "confirmation_required"`, a `next_action`, and an `arguments_patch`.

## Explicit low-level flow

Agents that need precise control can use the lower-level tools directly:

```text
inspect_project_docs(project_path)
```

Then follow the returned `reason_code`:

| `reason_code` | What it means | Agent action |
|---|---|---|
| `project_docs_ready` | Project docs are discovered and current. | Call `get_project_context` or `get_project_docs`. |
| `project_docs_found_not_indexed` | Reviewable docs exist but are not indexed. | Call `ingest_project_docs`. |
| `project_docs_stale` | Indexed docs changed on disk. | Call `ingest_project_docs` to refresh. |
| `no_project_docs` | No reviewable docs were discovered. | Ask before creating a reviewable `ARCHITECTURE.md`. |
| `architecture_doc_creation_recommended` | Some docs exist, but no high-level overview/architecture doc was found. | Ask before creating `ARCHITECTURE.md`. |
| `no_project_docs_results` | Indexed docs did not answer the query. | Inspect docs and refine/remediate instead of guessing. |

After `ingest_project_docs`, call `inspect_project_docs` again or proceed to:

```text
get_project_context(project_path, question)
```

`get_project_context` returns a compact Trust Contract with selected, rejected, and risky sources, plus `next_actions` for missing, stale, non-exact, or unmatched docs. Use `mode` when the agent should constrain sources explicitly: `auto`, `project-only`, `deps-only`, or `public-docs`.

or, for project docs only:

```text
get_project_docs(project_path, query)
```

## Confirmation gates

Project-docs onboarding has explicit safety gates.

| Gate | `confirmation_reason` | Why it exists |
|---|---|---|
| Repository write | `repo_write` | Creating or editing `ARCHITECTURE.md` changes official project docs and must be reviewable by the user. |
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
3. call `inspect_project_docs` again;
4. call `ingest_project_docs`;
5. answer future repo-specific questions from `get_project_context` or `get_project_docs`.

Do not store generated architecture only in hidden memory. Official project knowledge should remain a file humans can review and edit.

## Dependency docs are separate

`inspect_project_docs` also reports dependency metadata from supported manifests and lockfiles. That metadata is useful for exact-version docs, but it is not the same as project-owned docs.

Use:

```text
ingest_project_docs(project_path)
```

for repository files such as README/docs/wiki/ADR.

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

## Example response handling

Example: docs exist but are not indexed.

```json
{
  "reason_code": "project_docs_found_not_indexed",
  "requires_confirmation": false,
  "next_action": {
    "type": "ingest_project_docs",
    "tool": "ingest_project_docs"
  },
  "arguments_patch": {
    "project_path": "/path/to/repo"
  }
}
```

The agent should call `ingest_project_docs` with the provided arguments.

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
