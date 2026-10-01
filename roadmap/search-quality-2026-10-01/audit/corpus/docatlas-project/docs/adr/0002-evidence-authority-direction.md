# ADR 0002: DocAtlas is the documentation authority and evidence delivery layer

## Status

Accepted

## Context

DocAtlas started as a local-first alternative for library-documentation retrieval. The product has since accumulated a stronger set of boundaries: reviewable project documentation stays in Git, dependency identity is resolved from repository state, source authority and version binding are explicit, model-visible output is bounded, and missing mandatory evidence fails closed.

At the same time, the project has two important negative product signals. The historical Task 23 decision did not demonstrate a resolved-task gain and recorded materially higher token/latency cost, while the current model-backed Agent Developer report records 0/11 autonomous evidence trajectories despite deterministic/oracle trajectories being green. These results do not invalidate the evidence engine, but they mean additional retrieval breadth or hardening is not justified without first proving agent usability and patch-level value.

The surrounding ecosystem also has capable code-search, code-graph, repository-memory, and public-documentation systems. Reimplementing all of those surfaces would broaden DocAtlas before its distinctive value is demonstrated.

## Decision

DocAtlas is a **local, version-bound documentation authority and evidence delivery layer for coding agents**.

Its primary responsibility is to turn repository-owned documentation, repository dependency state, and approved dependency documentation into bounded evidence with explicit authority, scope, version binding, provenance, and support status.

The core product contract is:

```text
repository docs + lockfiles + approved dependency docs
                         ↓
                      DocAtlas
                         ↓
 authority + version + scope + bounded evidence
                         ↓
          supported | insufficient_evidence
                         ↓
                    coding agent
```

DocAtlas owns:

- project-document authority and scope boundaries;
- dependency identity and exact-version evidence when repository state proves it;
- source authority and version-binding decisions;
- bounded source-attributed evidence delivery;
- fail-closed support decisions and typed recovery actions;
- lifecycle/network boundaries for acquiring or refreshing documentation.

DocAtlas does **not** try to replace:

- source-code search or an LSP;
- a call graph or full repository semantic graph;
- a coding agent, test runner, static analyzer, or patch correctness proof;
- general web search or a hosted public-documentation catalog;
- agent memory/session-history products.

Those systems may provide implementation facts or external discovery. DocAtlas should compose with them and adjudicate documentation/version evidence rather than duplicate their entire scope.

## Product success criteria

Infrastructure correctness is necessary but no longer sufficient. New product work is judged in this order:

1. **Public truth:** protected source, published artifact, installed behavior, and documentation agree.
2. **Agent truth:** a real coding model can acquire the intended evidence through the installed public MCP contract.
3. **Product truth:** DocAtlas improves real coding outcomes or materially reduces unsupported/wrong-version claims at acceptable total trajectory cost.

The primary future product KPI is patch/task correctness. Supporting metrics include unsupported claims, wrong-version claims, cross-source attribution errors, files unnecessarily touched, tests passed, model-visible tokens, total system tokens, tool calls, and latency.

## Roadmap consequences

Until the P0 public-truth baseline is complete, do not:

- add public MCP tools;
- expand Context7 parity work;
- add a new retrieval/reranking stack;
- build a first-party code graph;
- weaken `insufficient_evidence` to improve pass rates;
- reinterpret deterministic/oracle benchmark success as live-agent product value.

After P0, the next R&D work is an installed-MCP live benchmark and a first-divergence analysis of the historical 0/11 Agent Developer result. Agent Contract v2 changes are hypotheses to test after that analysis, not assumptions to merge first.

## Release consequences

DocAtlas remains **Beta** until agent and product evidence justify a stronger maturity claim. Context7 parity and correct-patch improvement remain explicitly unproven claims.

The repository `1.2.0` state is treated as an unpublished repository milestone. The next intended public release is `1.3.0`, after P0 release truth, namespace/state isolation, contract synchronization, and exact public-artifact verification are complete.

## Consequences

- The existing local-first, Git-source-of-truth, exact-version, provenance, bounded-context, and fail-closed architecture remains the foundation.
- The active roadmap becomes a short validation roadmap rather than a historical construction log.
- Historical benchmark failures are retained as evidence; they are not rewritten or hidden by later infrastructure work.
- External-library expansion becomes conditional on measured product bottlenecks.
- Wider context engines are integration candidates, not features DocAtlas must immediately reproduce.
