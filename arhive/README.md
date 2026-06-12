# Docmancer Roadmap

This roadmap focuses on improving how users and AI agents apply Docmancer correctly. Most core capabilities already exist: MCP tools, project-doc inspection, project context packs, dependency docs, manifests, stale-source detection, and generated agent instructions.

The remaining work is mostly about UX, wording, guardrails, examples, and verification flows.

## Roadmap files

- [01-agent-mcp-workflow.md](01-agent-mcp-workflow.md) — make the existing inspect-first workflow harder for agents to skip.
- [02-source-taxonomy.md](02-source-taxonomy.md) — explain and surface the existing separation between project docs, dependency docs, and source code.
- [03-documentation-index.md](03-documentation-index.md) — add canonical `docs/INDEX.md` guidance for projects with scattered docs.
- [04-curated-dependency-docs.md](04-curated-dependency-docs.md) — improve warnings and examples for exact official dependency documentation URLs.
- [05-stale-and-ignored-sources.md](05-stale-and-ignored-sources.md) — make source-status messages easier to understand and act on.
- [06-verification-loop.md](06-verification-loop.md) — document a smoke-test loop after ingesting or refreshing docs.

## Framing

Do not treat this roadmap as a list of missing core features. Treat it as a set of improvements to the existing system.

Each roadmap item should answer:

1. What already exists?
2. What still causes misuse or confusion?
3. What UX/documentation/guardrail improvement is needed?
4. How do we know the improvement worked?

## Expected outcome

After these items are completed, agents should be less likely to produce broad ungrounded summaries and more likely to:

1. inspect project documentation first;
2. query the correct source type;
3. explain stale or ignored sources accurately;
4. prefer exact official dependency docs;
5. verify that expected docs are retrievable after changes.
