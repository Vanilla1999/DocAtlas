# P0 public-truth closure scorecard

Status: **INCOMPLETE** — the `1.3.0` source release candidate is merged, but the exact public PyPI release and post-publish verification do not exist yet.

This document is the P0.6 closure record. It distinguishes proven public truth from an explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

| Public-truth row | State | Evidence / closure requirement |
|---|---|---|
| Release source identity | `green` | `main` reports source version `1.3.0`; the changelog has the `1.3.0` cut; pre-public release gates build one wheel and one sdist with matching metadata. |
| Branch protection | `accepted_risk` | Maintainer decision on 2026-08-21: do not activate remote `protect-main` for `1.3.0`. The release workflow instead requires the tag commit to be reachable from remote `main`. The canonical ruleset remains available for future hardening. |
| Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, removes inherited `DOCMANCER_HOME`, checks `docatlas` MCP registration identity, and rejects implicit foreign `~/.docmancer` writes. |
| Installed agent contract | `green` | The default public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`, with runtime-derived contract identity and installed guidance alignment. |
| Exact public artifact identity | `pending` | After publication, record immutable `v1.3.0`, PyPI wheel/sdist filenames, gated SHA-256 values, downloaded public SHA-256 values, and the successful publish workflow run. |
| Exact public MCP behavior | `pending` | No-cache install of `doc-atlas==1.3.0` from public PyPI must pass the installed Docs MCP stdio smoke and exact three-tool inventory check. |
| Cross-platform public install | `pending` | The exact public package must pass the post-publish smoke on Linux, macOS, and Windows. Pre-public PR platform smoke is supporting evidence, not a substitute. |
| Product claim boundary | `green` | Public maturity remains **Beta**. Autonomous live evidence planning, real coding-task improvement, and Context7 parity remain unproven and are deferred to P1/P2 or a separate parity protocol. |

## Closure rule

P0 is closed only when every `pending` row above is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible and does not block `1.3.0` under the maintainer's explicit decision.

When publication completes, update this file with exact tag, workflow-run identities, artifact filenames/SHA-256 values, and Linux/macOS/Windows public-smoke evidence before marking the overall status **CLOSED**.
