# Documentation Index

This is the canonical map of maintained DocAtlas project-owned documentation. Agents should start here when they need repository context before using code search or external documentation.

## Start here

- [README](../README.md) — product overview, quickstart, core commands, and high-level MCP docs-server workflow.
- [Project Map](./PROJECT_MAP.md) — repository map, product surfaces, code areas, docs map, core workflows, data flow, and safety boundaries.
- [Agent Docs Workflow](./AGENT_DOCS_WORKFLOW.md) — operational playbook for agents using DocAtlas to build, sync, and query documentation context.
- [Agent instructions](../AGENTS.md) — compact workflow summary that coding agents should follow inside this repository.

## MCP and project-docs workflows

- [MCP docs server](./mcp-docs-server.md) — full Context7-style MCP docs-server surface, tool lanes, response shapes, safety defaults, and implementation notes.
- [Project docs MCP workflow](./project-docs-mcp-workflow.md) — project-owned docs lifecycle, module docs, confirmation gates, and `sync_project_docs` guidance.
- [Project docs demo](./project-docs-demo.md) — example project-docs flow.

## Product and architecture

- [Capabilities](./capabilities.md) — product capability overview.
- [Context7 comparison](./context7-docmancer-comparison.md) — comparison with Context7-style hosted documentation lookup.
- [Product brief](./DOCMANCER_PRODUCT_BRIEF.md) — product positioning and scope.
- [Architecture](../wiki/Architecture.md) — architecture narrative for indexing, retrieval, Docs MCP, Packs runtime, registry, and version provenance.

## User-facing reference

- [Commands](../wiki/Commands.md) — CLI command reference.
- [Configuration](../wiki/Configuration.md) — configuration options.
- [Supported Sources](../wiki/Supported-Sources.md) — supported source types and fetch behavior.
- [Install Targets](../wiki/Install-Targets.md) — agent installation targets.
- [Troubleshooting](../wiki/Troubleshooting.md) — operational troubleshooting.

## MCP Packs

- [MCP Packs](../wiki/MCP-Packs.md) — installed API pack runtime, Tool Search pattern, safety, and operations.

## Evaluation and research

- [Task-level agent benchmark](./research/task-level-agent-benchmark.md) — benchmark design for measuring agent behavior with DocAtlas.
- [Eval task-level README](../eval/task_level/README.md) — task-level evaluation harness overview.
- [Eval results README](../eval/results/live/README.md) — live eval report notes.

## External docs manifest

- [docmancer.docs.yaml](../docmancer.docs.yaml) — repeatable manifest of external documentation targets for validation and prefetch.

## Maintenance rules

- Keep this index limited to maintained, reviewable documentation.
- Prefer links to repository-owned docs over generated hidden summaries.
- Update this file when adding architecture docs, runbooks, ADRs, workflow docs, or new user-facing references.
- After documentation changes, run the project-docs workflow: `inspect_project_docs`, `sync_project_docs`, then `get_project_context` for a question that should select the new docs.
