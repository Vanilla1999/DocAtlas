# Agent documentation workflow

This is the maintained, public workflow for coding agents using the DocAtlas
documentation server.

## Repository questions

1. For coding and patch tasks, call `get_docs_context(project_path=..., question=..., mode="project", delivery_strategy="bounded_direct")`.
2. If the response returns `recommended_next_action`, obtain any required
   confirmation, call that exact action, and then retry the same bounded request.
3. Use `docs_status` only for an explicit health, freshness, index, or
   background-job status request.
4. Use only selected sources from the Trust Contract. If the response is
   navigation-only, read or search the suggested files before answering.

## Library and dependency questions

Call
`get_docs_context(question=..., library=..., ecosystem=..., version=..., mode="library", response_style="snippet-first", delivery_strategy="bounded_direct")`.

Network access is opt-in. If documentation must be fetched or refreshed, ask the
user and then use `prepare_docs` with the returned action and arguments.

## Patch tasks

Documentation context is evidence, not proof that a patch is correct. For
patch-like tasks, retrieve context and constraints before editing, validate
advisory constraints after editing, and still run the project's tests and
linters.

## Tool boundary

The default Docs MCP surface consists only of `get_docs_context`,
`prepare_docs`, and `docs_status`. Advanced inspection and patch-contract
compatibility tools require `DOCMANCER_MCP_ADVANCED_TOOLS=1`.

Use the Docs MCP server for documentation and source-grounded context. The
advanced Packs gateway is a separate surface for explicitly installed API
action packs. Neither surface is a static analyzer or a test runner.
