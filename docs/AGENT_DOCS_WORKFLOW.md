# Agent documentation workflow

This is the maintained, public workflow for coding agents using the DocAtlas
documentation server.

## Repository questions

1. Call `inspect_project_docs(project_path)` for read-only discovery.
2. When reconciliation is requested and the preflight allows it, call
   `prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)`.
3. Query with
   `get_docs_context(project_path=..., question=..., mode="project")`.
4. Use only selected sources from the Trust Contract. If the response is
   navigation-only, read or search the suggested files before answering.

## Library and dependency questions

Call
`get_docs_context(question=..., library=..., ecosystem=..., version=..., mode="library", response_style="snippet-first")`.

Network access is opt-in. If documentation must be fetched or refreshed, ask the
user and then use `prepare_docs` with the returned action and arguments.

## Patch tasks

Documentation context is evidence, not proof that a patch is correct. For
patch-like tasks, retrieve context and constraints before editing, validate
advisory constraints after editing, and still run the project's tests and
linters.

## Tool boundary

Use the Docs MCP server for documentation and source-grounded context. The
advanced Packs gateway is a separate surface for explicitly installed API
action packs. Neither surface is a static analyzer or a test runner.
