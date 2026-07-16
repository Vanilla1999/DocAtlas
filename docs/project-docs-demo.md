# Project docs MCP demo

This demo shows the local-first workflow for answering repository-specific questions with DocAtlas project docs instead of generic hosted documentation.

## Setup

Start the MCP docs server:

```bash
doc-atlas mcp docs-serve
```

Inside the DocAtlas repository, ask the agent a repo-specific question such as:

> I thought DocAtlas was like Context7. What else does it do for this repo's own docs?

## Expected agent flow

Preferred public MCP happy path:

1. Call `get_docs_context(project_path=".", question="Context7 project-owned docs roadmap", mode="project")`.
2. If it returns `prepare_docs` as `next_action`, call the exact returned action and retry `get_docs_context`.
3. Use `docs_status` only when the user explicitly asks about health, freshness, index state, or a background job.
4. Answer using the returned Trust Contract, `next_actions`, and chunks that include `source_class`, `path`, `heading_path`, freshness metadata, and stale state.

Legacy compatibility note:

Older docs surfaces may expose direct inspection or project-doc verbs. Treat those as advanced/legacy compatibility tools. The default surface has exactly three tools: `get_docs_context`, `prepare_docs`, and `docs_status`.

## Success criteria

- The agent does not WebFetch before trying DocAtlas project docs.
- The answer cites repo-owned files such as `README.md`, `DOCMANCER_PRODUCT_BRIEF.md`, or `roadmap/08_project_docs/*.md`.
- If project docs are missing, not indexed, stale, or missing a high-level overview, the agent follows structured `reason_code`, `next_action`, `requires_confirmation`, and `arguments_patch` instead of guessing.

## Bootstrapping a repo with no docs

If `inspect_project_docs(project_path=".")` or `get_docs_context(mode="project")` reports `no_project_docs`, DocAtlas should return `next_action.type = "ask_user_to_create_project_doc"` with `suggested_file: "ARCHITECTURE.md"`, `requires_confirmation: true`, and `confirmation_reason: "repo_write"`.

Expected agent flow:

1. Ask the user before creating documentation: "No project docs were found. May I inspect the codebase and create `ARCHITECTURE.md` as a reviewable project doc?"
2. If approved, inspect the codebase and create `ARCHITECTURE.md` in the repository root.
3. Call `inspect_project_docs(project_path=".")` again; `ARCHITECTURE.md` should now be discovered as an `architecture` project doc.
4. Call `prepare_docs(action="sync_project_docs", project_path=".")`.
5. Answer future repo-specific architecture questions through `get_docs_context(mode="project")`, citing `ARCHITECTURE.md` instead of relying on hidden memory.

## Dependency docs are separate

If `inspect_project_docs` reports dependency metadata from `pubspec.lock`, `Cargo.lock`, or related manifests, dependency docs should be prefetched through the public lifecycle wrapper:

```text
prepare_docs(action="prefetch_project_dependency_docs", project_path=".")
```

Legacy compatibility surfaces may also expose:

```text
prefetch_project_docs(project_path=".")
```

Despite that historical name, it prefetches dependency documentation from manifests/lockfiles. It does not ingest project-owned README/docs/wiki files. Because dependency prefetch may use the network, the agent should ask for confirmation unless the user already approved it.

See also:

- [`mcp-docs-server.md`](./mcp-docs-server.md)
- [`project-docs-mcp-workflow.md`](./project-docs-mcp-workflow.md)
