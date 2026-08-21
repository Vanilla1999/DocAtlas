# Agent documentation workflow

This is the maintained public workflow for coding agents using the DocAtlas documentation server.

The advertised runtime `ToolSpec` objects for the default Docs MCP surface are the source of truth for tool names, descriptions, and schemas. `docatlas-agent-contract-v1` fingerprints those runtime specs plus the workflow policy; installed skills carry the resulting SHA-256 identity so stale guidance is detectable.

## Repository questions

1. For documentation questions and coding or patch tasks, call `get_docs_context(project_path=..., question=..., mode="project")` before the first edit.
2. Call `prepare_docs` only from `recommended_next_action`, or when the user explicitly requests documentation lifecycle work such as sync, refresh, index, or prefetch. After preparation succeeds, retry the original `get_docs_context` question unchanged.
3. Use `docs_status` only for an explicit health, freshness, index, or background-job status request, or when `get_docs_context` returns it as `recommended_next_action`; it is not discovery.
4. If the result is `insufficient_evidence`, do not claim documentation support. Follow at most one non-automatic `rephrase_question` recovery for parser/retrieval uncertainty; if it still fails and `hard_stop=false`, continue repository investigation with local source/tests while keeping the documentary claim unproved. Stop before an edit when `hard_stop=true` or when the task explicitly requires a documentary contract that remains unproved.

## Library and dependency questions

Call `get_docs_context(question=..., library=..., version=..., mode="library")`.

Network access is opt-in. If documentation must be fetched or refreshed, ask the user and then use the exact `prepare_docs` action returned by `get_docs_context`.

## Patch tasks

Documentation context is evidence, not proof that a patch is correct. Retrieve the required documentation evidence before editing and still run the project's source search, tests, linters, and review after editing.

## Tool boundary

The default Docs MCP surface consists only of `get_docs_context`, `prepare_docs`, and `docs_status`. Normal-agent guidance must use only arguments advertised by those runtime schemas; compatibility-only server fields are not part of this workflow.

Advanced inspection and patch-contract compatibility tools require `DOCMANCER_MCP_ADVANCED_TOOLS=1`. The advanced Packs gateway is a separate surface for explicitly installed API action packs. Neither surface is a static analyzer or a test runner.
