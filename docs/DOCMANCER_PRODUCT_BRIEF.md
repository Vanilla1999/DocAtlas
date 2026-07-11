# DocAtlas product brief

## Product

DocAtlas is a **local-first documentation context layer for coding agents**. It indexes reviewable project documentation, detects dependency versions from the repository, and returns compact context with source attribution.

It is not a hosted replacement for every public documentation service today. Exact external-library context is an actively validated capability; no Context7-parity claim is made until the paired evaluation in `roadmap/18_CONTEXT7_PARITY_PROTOCOL_AND_CAPTURE.md` is complete.

## Primary user journey

```text
install → get_docs_context → follow returned prepare_docs action → retry original question → answer with sources
```

The public Docs MCP server exposes exactly three tools:

| Tool | Use it for |
|---|---|
| `get_docs_context` | The first call for project, dependency, library, or mixed documentation questions. |
| `prepare_docs` | Explicit lifecycle work such as syncing accepted project docs or fetching an approved external source. |
| `docs_status` | A returned job, freshness, health, or index-status question. |

`get_docs_context` is the normal entry point. The target contract is for it to return the exact `prepare_docs` action and arguments when preparation is required, then let the agent retry the original question. Task 11 hardens this boundary; until then, compatibility flags remain and agents must not use them for speculative lifecycle/network work.

## Product boundaries

- Repository Markdown and project files remain the source of truth. SQLite/vector data are derived indexes.
- DocAtlas does not silently author, commit, or push official project documentation.
- When docs are missing or stale, it gives the host coding agent a bounded evidence-gathering and file-editing brief. The host agent makes a normal reviewable Git change; DocAtlas then indexes the accepted file.
- Project code search answers implementation facts. DocAtlas supplies documentation context and provenance.
- Network acquisition is the target explicit lifecycle contract. Task 11 still has to remove hidden compatibility paths from normal retrieval.

## Current capabilities

- Sync and retrieve local project documentation with citations.
- Detect supported Python, Node/TypeScript, Dart/Flutter, Rust, and other project dependency metadata where available.
- Produce `docs-impact` reports that tell reviewers which maintained docs may need attention after code changes.
- Return compact source-attributed MCP context for coding agents.

For the detailed current contract, commands, response fields, and examples, use [the Docs MCP reference](./mcp-docs-server.md). It is the canonical detailed workflow document; this brief and `README.md` stay intentionally concise.

## Installation truth

The package distributed on PyPI is `doc-atlas`. The `main` branch can contain workflow changes that are not yet published. Check `doc-atlas --version`, use release documentation that matches that installed version, and do not assume a one-line installer for `main` has published every documented feature.

## Advanced and compatibility surfaces

MCP Packs, patch constraints, patch planning, Qdrant administration, USPTO ingestion, and legacy direct documentation APIs are advanced compatibility surfaces. They are not part of the beginner Docs MCP workflow.

Patch constraints are advisory/non-blocking evidence helpers. They do not prove that a patch is safe to merge and never replace tests or human review.

## Maturity

DocAtlas is currently **Beta** for the primary Docs MCP workflow. The project must not be described as Production/Stable until the built release artifact passes the primary stdio MCP smoke and the release checklist.

## Documentation maintenance rule

Keep active user/model documentation small and non-duplicated:

- `README.md`: first-screen product journey and install truth;
- `docs/mcp-docs-server.md`: canonical detailed Docs MCP workflow;
- this brief: product scope and claims;
- `wiki/`: navigation and compatibility reference.

The canonical user-facing release set — `README.md`, this brief, the Docs MCP reference, the capability reference, and the release checklist — must not exceed 1,000 lines without a recorded exception. Add links to the canonical guide instead of copying tool tables or workflows.
