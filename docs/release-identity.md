# Release identity during P0

Status: active release-candidate truth note for P0.5.

## Current identity

As of 2026-08-21:

- the latest public PyPI release remains `doc-atlas==1.1.1`;
- repository source now reports release-candidate version `1.3.0`;
- repository `1.2.0` remains an unpublished historical milestone and must not be reused or retroactively published;
- no `v1.3.0` tag or public `1.3.0` artifact is evidence until the reviewed release flow creates and verifies them.

The existing changelog heading `## [1.2.0] - 2026-07-12` records the repository milestone date; it is **not** evidence that a matching PyPI artifact was published. P0.5 cuts a new `1.3.0` identity from current reviewed work rather than rewriting that historical milestone.

## 1.3.0 release candidate

The intended next public release is:

```text
doc-atlas 1.3.0
```

The source version and changelog are prepared in the P0.5 release PR. Tag creation and publication remain separate post-merge repository operations. For `1.3.0`, the maintainer explicitly accepts the residual risk of an unprotected `main`; [`public-truth-scorecard.md`](./public-truth-scorecard.md) records that decision. The manual release workflow still fails closed unless the tagged commit is reachable from remote `main`.

Before `1.3.0` is published, all of the following must be true:

1. the release commit is reviewed on `main` with `required-ci` and `required-release` evidence green before merge;
2. a maintainer creates immutable tag `v1.3.0` from a commit reachable from remote `main`;
3. `Release artifact gate and publish` is manually dispatched for exactly `v1.3.0` and authorized through the `release` environment;
4. publication uses the repository OIDC/Trusted Publishing path, not a long-lived PyPI token;
5. public wheel and sdist bytes match the gated SHA-256 values;
6. a no-cache install of exact public `doc-atlas==1.3.0` passes the three-tool Docs MCP stdio smoke on Linux, macOS, and Windows;
7. the P0.6 scorecard records the final public artifact/install evidence and retains branch protection as `accepted_risk`, not green.

Until those conditions are satisfied, `1.3.0` is a **release candidate in source**, not a completed public release.

## Release claim boundary

The next release remains **Beta**.

Publishing `1.3.0` may establish public artifact/install truth. It must not, by itself, create claims that:

- DocAtlas has Context7 parity;
- autonomous live evidence planning is solved;
- DocAtlas improves real coding-task correctness;
- the product is Stable/Production.

Those remain later agent-truth and product-truth decisions in P1/P2.

## Historical identity rule

Existing release tags are immutable evidence. Never move or reuse an existing release tag to make repository history match a later artifact.

If a `v1.2.0` tag exists, preserve it as historical identity and do not publish a different artifact under that version. If it does not exist, do not create one merely to fill the public-version gap. In both cases, `1.3.0` is the next public release candidate after the P0 prerequisites are satisfied.
