# Project docs MCP demo

This demo shows the local-first workflow for answering repository-specific questions with Docmancer project docs instead of generic hosted documentation.

## Setup

Start the MCP docs server:

```bash
docmancer mcp docs-serve
```

Inside the Docmancer repository, ask the agent a repo-specific question such as:

> I thought Docmancer was like Context7. What else does it do for this repo's own docs?

## Expected agent flow

Preferred happy path:

1. Call `bootstrap_project_docs(project_path=".", question="Context7 project-owned docs roadmap")`. This may inspect, ingest existing reviewable docs, refresh stale docs, and inspect again.
2. If `bootstrap_project_docs` returns `status = "confirmation_required"`, ask the user before taking the proposed action.
3. Call `get_project_context(project_path=".", question="Context7 project-owned docs roadmap", mode="auto")`.
4. Answer using the returned Trust Contract, `next_actions`, and chunks that include `source_class`, `path`, `heading_path`, freshness metadata, and stale state.

Explicit lower-level flow:

1. Call `inspect_project_docs(project_path=".")` first. This is read-only and discovers `README.md`, roadmap files, product brief, and other reviewable docs candidates.
2. If `reason_code` is `project_docs_found_not_indexed` or `project_docs_stale`, follow `next_action` and call `ingest_project_docs(project_path=".")`.
3. Retry with `get_project_docs(project_path=".", query="Context7 project-owned docs roadmap")` or `get_project_context(project_path=".", question="Context7 project-owned docs roadmap")`.
4. Answer from Docmancer project-docs results instead of guessing.

## Success criteria

- The agent does not WebFetch before trying Docmancer project docs.
- The answer cites repo-owned files such as `README.md`, `DOCMANCER_PRODUCT_BRIEF.md`, or `roadmap/08_project_docs/*.md`.
- If project docs are missing, not indexed, stale, or missing a high-level overview, the agent follows structured `reason_code`, `next_action`, `requires_confirmation`, and `arguments_patch` instead of guessing.

## Bootstrapping a repo with no docs

If `inspect_project_docs(project_path=".")`, `bootstrap_project_docs`, or `get_project_docs` reports `no_project_docs`, Docmancer should return `next_action.type = "ask_user_to_create_project_doc"` with `suggested_file: "ARCHITECTURE.md"`, `requires_confirmation: true`, and `confirmation_reason: "repo_write"`.

Expected agent flow:

1. Ask the user before creating documentation: "No project docs were found. May I inspect the codebase and create `ARCHITECTURE.md` as a reviewable project doc?"
2. If approved, inspect the codebase and create `ARCHITECTURE.md` in the repository root.
3. Call `inspect_project_docs(project_path=".")` again; `ARCHITECTURE.md` should now be discovered as an `architecture` project doc.
4. Call `ingest_project_docs(project_path=".")`.
5. Answer future repo-specific architecture questions through `get_project_docs`, citing `ARCHITECTURE.md` instead of relying on hidden memory.

## Dependency docs are separate

If `inspect_project_docs` reports dependency metadata from `pubspec.lock`, `Cargo.lock`, or related manifests, dependency docs should be prefetched with:

```text
prefetch_project_dependency_docs(project_path=".")
```

The existing compatible tool name is:

```text
prefetch_project_docs(project_path=".")
```

Despite that historical name, it prefetches dependency documentation from manifests/lockfiles. It does not ingest project-owned README/docs/wiki files. Because dependency prefetch may use the network, the agent should ask for confirmation unless the user already approved it.

See also:

- [`mcp-docs-server.md`](./mcp-docs-server.md)
- [`project-docs-mcp-workflow.md`](./project-docs-mcp-workflow.md)
