# Release identity

## Current public candidate

The current source release candidate is **DocAtlas 1.3.1**.

Canonical identity:

```text
product: DocAtlas
distribution: doc-atlas
source version: 1.3.1
intended tag: v1.3.1
maturity: Beta
```

The tag is created only after the release-preparation PR is merged and all required CI/release gates are green. It must point to that exact reviewed `main` commit and must never be moved.

No public `doc-atlas==1.3.1` release is claimed until the immutable tag, PyPI artifact bytes, and post-publish platform smokes exist.

## Historical repository milestone

Repository version `1.2.0` remains an unpublished historical milestone. It is retained only as repository history and is not reused as public release evidence.

## Superseded pre-public `v1.3.0` attempt

`v1.3.0` is retained as an immutable audit identity at commit `42c3bf1fccc839dad4be4077b0b2c6a203f9bbac`. Canonical workflow run `32541487735` built and validated the wheel/sdist, but PyPI rejected the OIDC publisher with `invalid-publisher` before upload. Therefore:

- no public `doc-atlas==1.3.0` release is claimed;
- the tag must not be moved, replaced, or reused;
- the failed publish job must not be rerun after configuring the replacement publisher;
- its artifact hashes are pre-public engineering evidence only, not public-release evidence.

Recorded gated artifacts from that failed attempt:

```text
doc_atlas-1.3.0-py3-none-any.whl
sha256 2e1a0f58e34ea9c175b8d93839a6dcc8a54a7e36d4329157f9378791a0341e26

doc_atlas-1.3.0.tar.gz
sha256 e5bb4eb1f2b3221bcd3e8e9db719fe8f11596a88bd000e3d922bd6826c6683ab
```

## Trusted Publisher identity for 1.3.1+

Configure the PyPI project `doc-atlas` with exactly:

```text
owner: Vanilla1999
repository: DocAtlas
workflow filename: publish.yml
environment: release-current
```

The new environment name intentionally differs from the failed `v1.3.0` run (`release`). Publication still uses GitHub OIDC/Trusted Publishing and no long-lived PyPI token.

## Claim boundary

Until the exact public version is downloadable and passes the post-publish Linux/macOS/Windows MCP smoke, release truth remains incomplete and product maturity remains **Beta**.

For clarity, no public `doc-atlas==1.3.1` release is claimed at this pre-public stage.
