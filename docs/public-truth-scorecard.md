# P0 public-truth closure scorecard

Status: **INCOMPLETE** — the reviewed `1.3.1` source and immutable tag exist, but canonical publication was rejected before upload and no exact public PyPI or post-publish platform evidence exists yet.

This document is the P0.6 closure record. It distinguishes proven public truth, pending public evidence, and explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

## Current `1.3.1` attempt

The immutable annotated `v1.3.1` tag object `77bced8c530c88c57d2e6c5f58cb717bfe837a9f` targets exact reviewed commit `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`.

Canonical workflow run `32587903026` passed build, wheel 3.11–3.13, sdist/installer, `required-release`, and provenance attestation. PyPI then rejected the valid GitHub OIDC token with `invalid-publisher` before upload. The token claims were:

```text
repository: Vanilla1999/DocAtlas
workflow: publish.yml@refs/heads/main
environment: release-current
sub: repo:Vanilla1999/DocAtlas:environment:release-current
```

The exact failure, gated hashes, public-absence observation, and safe retry contract are retained in [`release-evidence/v1.3.1-publish-attempt-1.json`](./release-evidence/v1.3.1-publish-attempt-1.json).

## Superseded attempt

The immutable `v1.3.0` attempt at `42c3bf1fccc839dad4be4077b0b2c6a203f9bbac` reached canonical workflow run `32541487735`. Build, wheel/sdist/install gates and provenance passed, but PyPI rejected OIDC with `invalid-publisher` before upload. Its two gated SHA-256 values are recorded in `docs/release-identity.md`; they are not public-artifact closure evidence and the failed job must not be resumed.

| Public-truth row | State | Evidence / closure requirement |
|---|---|---|
| Release source identity | `green` | Source, changelog, build metadata, release docs, and immutable annotated `v1.3.1` agree on exact commit `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`; `v1.3.0` remains a superseded pre-public audit tag. |
| Branch protection | `accepted_risk` | Maintainer decision on 2026-08-21: do not activate remote `protect-main`. The release workflow instead requires the tag commit to be reachable from remote `main`. |
| Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, removes inherited `DOCMANCER_HOME`, checks `docatlas` MCP registration identity, and rejects implicit foreign `~/.docmancer` writes. |
| Installed agent contract | `green` | The default public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`; documentary support stays fail closed while bounded local-source recovery is explicitly separated from support. |
| Trusted Publisher identity | `pending` | Run `32587903026` proved GitHub claims `Vanilla1999 / DocAtlas / publish.yml / release-current`, but PyPI returned `invalid-publisher`. Correct the external PyPI project publisher to that exact tuple, then rerun only the failed jobs of this exact run while public `1.3.1` remains absent. |
| Exact public artifact identity | `pending` | Gated hashes are recorded, but PyPI has no `1.3.1` files. After publication, require gated SHA-256 = PyPI metadata SHA-256 = independently downloaded SHA-256 for exactly one wheel and one sdist. |
| Exact public MCP behavior | `pending` | No-cache install of `doc-atlas==1.3.1` from public PyPI must pass installed Docs MCP stdio smoke and exact three-tool inventory. |
| Cross-platform public install | `pending` | The exact public package must pass post-publish smoke on Linux, macOS, and Windows. Pre-public PR platform smoke is supporting evidence only. |
| Product claim boundary | `green` | Public maturity remains **Beta**. Autonomous live evidence planning, real coding-task improvement, and Context7 parity remain unproven and belong to P1/P2. |

## Closure rule

P0 closes only when every `pending` row is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible and does not become proof that protection exists.

A failed OIDC exchange does not authorize moving `v1.3.1`, introducing a token fallback, or treating gated local bytes as public evidence. After the PyPI publisher is corrected, the safe continuation is the exact-run retry documented in `docs/release-identity.md`.
