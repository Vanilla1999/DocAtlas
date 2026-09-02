# ADR 0003: Context-first project reads

## Status

Accepted.

## Decision

Free-form project and module documentation reads return bounded, attributed
`docs_context`. The MCP server retrieves and qualifies repository-owned sources;
the host agent writes the user-facing answer from those sources.

Project reads do not return server-authored `docs_answer`. Certification remains
available for explicit library and dependency evidence lanes, and mutation
requests continue to use fail-closed `patch_context`.

The public MCP surface contains only `get_docs_context`, `prepare_docs`, and
`docs_status`. `get_docs_context` accepts the original question, optional bounded
`lookup_queries`, project/library identity, version, and project scope. Retrieval
budgets and raw search controls remain server-owned.

## Invariants

- The original user request remains authoritative and unchanged.
- Host-supplied lookup queries contain one concept each and improve recall only.
- Exact identifiers, filenames, commands, and versions are preserved verbatim.
- Project context is retrieval-only: `answer_supported=false` and
  `edit_ready=false`.
- Partial retrieval coverage is reported honestly and does not prevent useful
  context from being returned.
- Stale or missing project indexes recommend
  `prepare_docs(action="sync_project_docs")`; ready indexes recommend no action.
- Cross-project, stale, historical, unowned, or otherwise disallowed sources are
  excluded before model-visible projection.

## Consequences

The agent, rather than the server, owns conversational synthesis for project
questions. This removes the duplicate answer-generation pipeline and its false
abstentions while retaining provenance, source isolation, bounded output, and
fail-closed mutation safety.

The frozen project-answer v1-v4 evaluators and direct `get_project_context` MCP
surface are retired. The committed RU/EN Context7-style corpus is the project
chat contract and live self-host gate.
