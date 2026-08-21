# DocAtlas product brief

## Product

DocAtlas is a **local, version-bound documentation authority and evidence delivery layer for coding agents**.

It remains a local-first documentation context runtime at the transport/storage level, but its product responsibility is narrower and stricter: it turns reviewable repository documentation, dependency state from the repository, and approved dependency documentation into compact source-attributed evidence. DocAtlas keeps authority, scope, and version binding explicit and fails closed when mandatory evidence is unavailable.

The product is intentionally narrower than a general repository intelligence engine. Source-code search, LSPs, code graphs, test runners, static analyzers, web search, and coding agents remain complementary systems. DocAtlas supplies documentation/version evidence and provenance rather than claiming to replace those systems.

It is not a hosted replacement for every public documentation service today. Exact external-library context remains an actively validated capability; no Context7-parity claim is made until comparable evidence demonstrates it.

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

`get_docs_context` is the normal entry point. It returns the exact `prepare_docs` action and arguments when preparation is required, then lets the agent retry the original question. Retrieval remains read-only; lifecycle and network work stay behind the explicit `prepare_docs` boundary.

## Product boundaries

DocAtlas owns these evidence responsibilities:

- repository/project documentation authority and scope boundaries;
- dependency identity and exact-version evidence when repository state proves it;
- source authority and version-binding decisions;
- bounded source-attributed evidence delivery;
- fail-closed support decisions and typed recovery;
- explicit lifecycle/network boundaries for documentation acquisition and refresh.

DocAtlas does **not** replace:

- project source-code search or an LSP;
- call graphs or a complete repository semantic graph;
- tests, static analysis, or patch correctness review;
- a coding agent or its general reasoning loop;
- general web search or a complete hosted documentation catalog;
- agent memory/session-history products.

Repository Markdown and project files remain the source of truth. SQLite/vector data are derived indexes. DocAtlas does not silently author, commit, or push official project documentation.

When docs are missing or stale, it gives the host coding agent a bounded evidence-gathering or file-editing brief. The host agent makes a normal reviewable Git change; DocAtlas then indexes the accepted file.

Project code search answers implementation facts. DocAtlas supplies documentation/version evidence and provenance. Network acquisition is an explicit lifecycle action; normal retrieval does not silently fetch, crawl, index, or start a mutation job.

## Current capabilities

- Sync and retrieve local project documentation with citations.
- Detect supported Python, Node/TypeScript, Dart/Flutter, Rust, Go, Java, and other project dependency metadata where available.
- Resolve exact dependency versions only from repository evidence strong enough to prove the selected version; weaker declarations remain explicitly unbound or declared-only.
- Produce `docs-impact` reports that tell reviewers which maintained docs may need attention after code changes.
- Return compact source-attributed MCP evidence for coding agents.
- Return typed `insufficient_evidence` rather than authorizing unsupported claims or edits.

For the detailed current contract, commands, response fields, and examples, use [the Docs MCP reference](./mcp-docs-server.md). It is the canonical detailed workflow document; this brief and `README.md` stay intentionally concise.

## Evidence status and product claims

Different evaluation layers prove different things and must not be collapsed into one success claim:

- deterministic/oracle Agent Developer trajectories are strongly validated;
- live three-tool selection has a positive frozen result;
- autonomous live evidence planning is **not demonstrated** by the current evidence; the recorded model-backed Agent Developer result is 0/11;
- real coding-task improvement is **not demonstrated**; the historical Task 23 product decision is formally `INCONCLUSIVE`;
- Context7 parity is **not demonstrated**;
- infrastructure safety and reproducibility do not, by themselves, prove agent usability or patch correctness.

The next product-validation sequence is therefore public truth → agent truth → product truth. See [`../roadmap/README.md`](../roadmap/README.md) and [ADR 0002](./adr/0002-evidence-authority-direction.md).

## Installation truth

The package distributed on PyPI is `doc-atlas`. The `main` branch can contain workflow changes that are not yet published. Check `doc-atlas --version`, use release documentation that matches that installed version, and do not assume a one-line installer for `main` has published every documented feature.

At the 2026-08 roadmap reset, repository version `1.2.0` is treated as an **unpublished repository milestone**, not as the next public artifact to publish from current `main`. The next intended public release is `1.3.0` after the P0 public-truth work is complete. See [release identity](./release-identity.md).

## Advanced and compatibility surfaces

MCP Packs, patch constraints, patch planning, Qdrant administration, USPTO ingestion, and legacy direct documentation APIs are advanced compatibility surfaces. They are not part of the beginner Docs MCP workflow.

Patch constraints are advisory/non-blocking evidence helpers. They do not prove that a patch is safe to merge and never replace tests or human review.

## Maturity

DocAtlas is currently **Beta** for the primary Docs MCP workflow.

The existing technical release gates remain necessary. Task 15 proves the wheel/sdist/installer and installed stdio MCP artifact path; Task 14 owns the bounded live external-ingest acceptance evidence; and the exact public release still requires post-publish verification of the published package. Those gates protect artifact/release truth, but they are no longer sufficient by themselves for a Stable product claim.

Stable promotion now also requires the newer validation layers. P0 must make source protection, release identity, installed behavior, product namespace/state, and agent guidance internally consistent. P1 must then demonstrate that a real coding model can acquire the intended evidence through the installed public MCP contract. P2 must demonstrate real coding-task value or a material reduction in unsupported/wrong-version claims at acceptable total trajectory cost.

Until those gates are satisfied, `Stable`, `Context7 replacement/parity`, and `proven patch improvement` are out-of-scope public claims.

## Documentation maintenance rule

Keep active user/model documentation small and non-duplicated:

- `README.md`: first-screen product journey and install truth;
- `docs/mcp-docs-server.md`: canonical detailed Docs MCP workflow;
- this brief: product scope and claims;
- `roadmap/README.md`: active validation sequence and decision gates;
- `wiki/`: navigation and compatibility reference.

The canonical user-facing release set — `README.md`, this brief, the Docs MCP reference, the capability reference, and the release checklist — must not exceed 1,000 lines without a recorded exception. Add links to the canonical guide instead of copying tool tables or workflows.
