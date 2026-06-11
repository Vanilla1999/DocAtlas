# Project Docs Onboarding Roadmap: Dependency Docs Prefetch

## Goal

Clarify and harden the dependency-docs path so agents understand the difference between project-owned docs and exact dependency documentation derived from manifests/lockfiles.

## Current naming issue

The existing MCP tool name `prefetch_project_docs` can be confusing because it does not index project-owned README/docs/wiki files. It reads project manifests/lockfiles and prefetches dependency documentation.

Project-owned docs path:

- `inspect_project_docs`
- `ingest_project_docs`
- `get_project_docs`
- `get_project_context`

Dependency docs path:

- `prefetch_project_docs`

## Proposed cleanup

Add one of the following:

1. Rename the tool in a breaking release to `prefetch_project_dependency_docs`.
2. Add a non-breaking alias `prefetch_project_dependency_docs` while keeping `prefetch_project_docs`.
3. Keep the current name but make descriptions and `next_actions` explicitly say “dependency docs from manifests/lockfiles”.

Preferred incremental option: add an alias and improve descriptions.

## Confirmation behavior

Dependency docs prefetch may use the network. Agents should ask before running it unless the user already approved dependency docs prefetch.

Suggested user message:

> I found dependency manifests/lockfiles. I can fetch exact documentation for the dependency versions used by this project. This may use the network. Proceed?

## Inspect integration

`inspect_project_docs` should surface dependency docs availability separately from project-owned docs readiness:

```json
{
  "dependency_docs_available": true,
  "dependency_docs_prefetched": false,
  "dependency_next_action": {
    "type": "ask_user_to_prefetch_dependency_docs",
    "tool_after_confirmation": "prefetch_project_docs"
  }
}
```

This should not override the primary project-docs `reason_code` unless the current user request specifically concerns dependency APIs.

## Ecosystem priorities

1. Flutter/Dart/pub.dev — already has a foundation and exact lockfile use cases.
2. Rust/docs.rs — deterministic versioned docs.
3. Python/PyPI/ReadTheDocs — high demand, harder discovery.
4. npm — high demand, messy package/docs identity.

## Acceptance criteria

- Agents can tell project-owned docs ingest from dependency docs prefetch.
- Dependency docs prefetch requires confirmation when network access is needed.
- Exact version metadata is preserved in context packs.
- Tool output makes it clear when dependency docs are optional vs required for the current question.
