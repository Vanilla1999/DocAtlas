# P0 public-truth closure scorecard

Status: **INCOMPLETE** — `2.0.0` is the owner-selected proposed candidate, not an approved release. No immutable `v2.0.0` tag or exact public PyPI artifact exists. The earlier `1.3.2` candidate was not published. The PyPI Trusted Publisher identity rejected in the two historical `1.3.1` attempts must be reverified and corrected if still mismatched before publication.

This document distinguishes proven public truth, pending public evidence, and explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

## Historical publisher evidence

The immutable annotated `v1.3.1` tag object `77bced8c530c88c57d2e6c5f58cb717bfe837a9f` targets exact reviewed commit `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`. Canonical workflow run `32587903026` passed build/release gates but PyPI rejected a valid GitHub OIDC token with `invalid-publisher` before upload. A controlled retry produced the same rejection with identical claims.

Attempts 1 and 2 prove that two canonical PyPI exchanges were rejected before upload. The external correction remains under PyPI `Your projects → doc-atlas → Manage → Publishing`.

The exact records are:

- [`release-evidence/v1.3.1-publish-attempt-1.json`](./release-evidence/v1.3.1-publish-attempt-1.json)
- [`release-evidence/v1.3.1-publish-attempt-2.json`](./release-evidence/v1.3.1-publish-attempt-2.json)

Expected existing-project publisher tuple:

```text
owner: Vanilla1999
repository: DocAtlas
workflow: publish.yml
environment: release-current
```

| Public-truth row | State | Evidence / closure requirement |
|---|---|---|
| Release source identity | `pending` | Source version, changelog, README ownership marker, and `server.json` agree on `2.0.0`. A reviewed release request must create immutable `v2.0.0` from the exact merged tree. |
| Branch protection | `accepted_risk` | Maintainer decision remains unchanged: release flow compensates by requiring the tag commit to be reachable from exact remote `main`. |
| Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, `~/.docatlas`, and the `docatlas` MCP registration identity. |
| Installed agent contract | `green` | The public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`. |
| Trusted Publisher identity | `pending` | Historical `1.3.1` attempts proved GitHub claims `Vanilla1999 / DocAtlas / publish.yml / release-current`; The existing `doc-atlas` project's current publisher settings must be verified against that tuple; prior attempts did not match. |
| Exact public artifact identity | `pending` | Publish exactly `doc-atlas==2.0.0` and prove gated SHA-256 = PyPI metadata SHA-256 = independently downloaded bytes for one wheel and one sdist. |
| Exact public MCP behavior | `pending` | No-cache install of `doc-atlas==2.0.0` must pass the exact three-tool Docs MCP stdio smoke. |
| Cross-platform public install | `pending` | The exact public package must pass Linux, macOS, and Windows smoke. |
| Official MCP Registry | `pending` | After all public-package smokes pass, GitHub OIDC publishes `io.github.Vanilla1999/docatlas` version `2.0.0` and the Registry API must return that exact name/version. |
| Product claim boundary | `green` | Public maturity remains **Beta**; no Context7 parity or unmeasured product-value claim is introduced. |

## Closure rule

P0 closes only when every `pending` row is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible. Historical `v1.3.0`/`v1.3.1` tags must never be moved or reused.
