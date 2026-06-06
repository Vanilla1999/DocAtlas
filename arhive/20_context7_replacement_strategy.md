# 20 - Context7 Replacement Strategy Overview

## Product thesis

Docmancer should not try to become a local clone of Context7 first.

The sharper positioning is:

> Docmancer is not docs search. Docmancer is repo-grounded context resolution for agents.

Or shorter:

> Context7 gives docs. Docmancer resolves trusted context.

Context7 is strong at zero-setup public-doc lookup. Docmancer should win when a coding agent is inside a real repository and needs to know which documentation the repository should trust now: project docs, pinned dependency versions, private/local docs, freshness, warnings, and next actions.

## Goal

Make Docmancer good enough that a coding agent does not need Context7 for normal repo-aware development work.

Docmancer can still lose at:

- first query setup time;
- hosted zero-config convenience;
- breadth of pre-indexed public libraries;
- one-off latest-doc questions where project context does not matter.

Docmancer must win at:

- project-owned documentation;
- exact or clearly labeled dependency versions;
- local/private/offline docs;
- repeated coding-agent loops;
- source provenance and freshness;
- token-aware compact context;
- safe next actions when docs are missing;
- explicit rejected/risky sources, not only selected sources.

## Decisive wedge

The flagship workflow is a high-level context resolver:

```text
get_project_context(project_path, question)
```

CLI equivalent:

```bash
docmancer context "How should I implement this here?" --explain
```

It should not answer like an LLM. It should return a compact trusted context pack plus a Trust Contract:

- selected project docs;
- selected dependency docs;
- version provenance;
- source freshness;
- why each source was selected;
- rejected or risky sources;
- warnings;
- executable next actions.

This replaces the agent workflow:

```text
ask Context7 for docs
then separately remember project constraints
then hope latest docs match the repo
```

with:

```text
inside a repo, ask Docmancer first
Docmancer resolves the trusted context for this repo and this dependency version
```

## Roadmap files

This strategy is split into implementation steps:

1. [`21_trusted_context_contract.md`](21_trusted_context_contract.md) - Trust Contract schema and source trust semantics.
2. [`22_get_project_context_mvp.md`](22_get_project_context_mvp.md) - first shippable `get_project_context`/`docmancer context` slice.
3. [`23_source_resolution_and_rejection.md`](23_source_resolution_and_rejection.md) - docs-source discovery with confidence and rejection reasons.
4. [`24_exact_version_and_project_context_benchmarks.md`](24_exact_version_and_project_context_benchmarks.md) - benchmarks proving Docmancer beats Context7 on pinned-version and project-context tasks.
5. [`25_snippet_and_explain_context.md`](25_snippet_and_explain_context.md) - snippet-first context packs and explainable CLI/MCP output.
6. [`26_platform_hardening_after_wedge.md`](26_platform_hardening_after_wedge.md) - packaging, backup, encryption, and other later platform work.

## Must-win scenarios

| Scenario | Why Docmancer should win | Acceptance target |
|---|---|---|
| Pinned dependency version | Latest public docs can be wrong for the repo. | The context pack uses the lockfile version or clearly warns when exact docs are unavailable. |
| Project conventions | Public docs do not know local architecture, ADRs, wrappers, or banned APIs. | The Trust Contract includes at least one project-owned source when project constraints are relevant. |
| Rejected risky docs | Agents need to know what not to trust. | Latest, unofficial, stale, or wrong-version sources are listed with rejection/warning reasons. |
| Multi-step coding task | The agent asks several related docs questions while editing code. | Warm queries reuse local docs and reduce repeated web/doc tokens. |
| Private or local docs | Hosted tools cannot index private files safely. | Local docs are queryable through the same flow as public docs. |
| Agent reliability | The agent needs source-grounded compact context, not raw pages. | Every result has source attribution, section metadata, token estimate, and confidence/explain data. |

## Assessment of a local Context7 clone proposal

A separate proposal suggested a local-first Context7 architecture with SQLite, optional SQLCipher, local service/CLI/UI, P2P/LAN sync, cloud backup, signed updates, OS packaging, and CI.

Useful lessons:

- local-first storage is right, and Docmancer already follows it;
- SQLite/FTS5 remains a good local metadata/index store;
- offline and repeated-query workflows are real differentiators;
- security, signed updates, and backup/restore matter later;
- first-run UX and packaging matter if Docmancer should become the default docs tool.

Deferred lessons:

- P2P/WebRTC/libp2p sync;
- LAN peer discovery;
- cloud backup/sync product surface;
- Electron/desktop UI;
- full SQLCipher integration for every install;
- broad local clone of a hosted public-doc catalog.

Reason: these improve platform completeness, but they do not directly answer the coding-agent question:

> Which docs should I trust for this repo and this dependency version?

## First shipped slice

Do not start with broad ecosystems or platform sync.

Start with one narrow, benchmarkable slice:

1. `get_project_context(project_path, question)` response schema.
2. Trust Contract with selected and rejected/risky sources.
3. Minimal orchestrator:
   - inspect project docs;
   - query indexed project docs;
   - resolve one dependency from one ecosystem, preferably Dart/Flutter or Rust;
   - query exact/best-effort dependency docs;
   - merge into one compact context pack.
4. `docmancer context ... --explain` output.
5. Benchmark where Context7-only fails or is weaker because it uses latest docs or ignores local ADR/project rules.

## Definition of done

Docmancer can be called a practical Context7 replacement when all are true:

- public-doc benchmarks show parity with Context7 after indexing;
- pinned project fixtures avoid wrong-version docs;
- project-context fixtures apply local repo constraints;
- agents can call one project-context tool instead of manually choosing between project docs, dependency docs, WebFetch, and Context7;
- every context pack exposes source class, version exactness, freshness, degraded state, and rejected/risky sources;
- missing docs produce executable next actions instead of silently pushing the agent back to Context7.
