# P0 public-truth closure scorecard

Status: **INCOMPLETE** — the reviewed `1.3.1` source candidate is merged into `main`, but the immutable tag, exact public PyPI release, and post-publish verification do not exist yet.

This document is the P0.6 closure record. It distinguishes proven public truth, pending public evidence, and explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

## Superseded attempt

The immutable `v1.3.0` attempt at `42c3bf1fccc839dad4be4077b0b2c6a203f9bbac` reached canonical workflow run `32541487735`. Build, wheel/sdist/install gates and provenance passed, but PyPI rejected OIDC with `invalid-publisher` before upload. Its two gated SHA-256 values are recorded in `docs/release-identity.md`; they are not public-artifact closure evidence and the failed job must not be resumed.

| Public-truth row | State | Evidence / closure requirement |
|---|---|---|
| Release source identity | `green` | Source, changelog, build metadata, release docs, and workflow examples identify `1.3.1`; `v1.3.0` remains a superseded pre-public audit tag. |
| Branch protection | `accepted_risk` | Maintainer decision on 2026-08-21: do not activate remote `protect-main`. The release workflow instead requires the tag commit to be reachable from remote `main`. |
| Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, removes inherited `DOCMANCER_HOME`, checks `docatlas` MCP registration identity, and rejects implicit foreign `~/.docmancer` writes. |
| Installed agent contract | `green` | The default public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`; documentary support stays fail closed while bounded local-source recovery is explicitly separated from support. |
| Trusted Publisher identity | `pending` | Configure PyPI `doc-atlas` for owner `Vanilla1999`, repository `DocAtlas`, workflow `publish.yml`, environment `release-current`; do not rerun the failed `v1.3.0` job. |
| Exact public artifact identity | `pending` | After publication, record immutable `v1.3.1`, PyPI wheel/sdist filenames, gated SHA-256 values, downloaded public SHA-256 values, and the successful publish workflow run. |
| Exact public MCP behavior | `pending` | No-cache install of `doc-atlas==1.3.1` from public PyPI must pass installed Docs MCP stdio smoke and exact three-tool inventory. |
| Cross-platform public install | `pending` | The exact public package must pass post-publish smoke on Linux, macOS, and Windows. Pre-public PR platform smoke is supporting evidence only. |
| Product claim boundary | `green` | Public maturity remains **Beta**. Autonomous live evidence planning, real coding-task improvement, and Context7 parity remain unproven and belong to P1/P2. |

## Closure rule

P0 closes only when every `pending` row is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible and does not become proof that protection exists.
