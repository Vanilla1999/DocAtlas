# Agent documentation workflow

This is the maintained, public workflow for coding agents using the DocAtlas
documentation server.

## Repository questions

1. For coding and patch tasks, call `get_docs_context(project_path=..., question=..., mode="project", delivery_strategy="bounded_direct")`.
2. Follow `recommended_next_action`: ask its source-choice question, or obtain
   confirmation, call its exact typed action, and retry the same bounded request.
3. Use `docs_status` only for an explicit health, freshness, index, or
   background-job status request.
4. Inspect `action_packet.status`, cite `action_packet.source_of_truth` through
   factual `evidence_ids`, and do not edit when status is `insufficient_evidence`.
   Trust Contract and navigation fields belong to explicit unbounded exploration.

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
