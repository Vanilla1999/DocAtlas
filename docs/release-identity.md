# Release identity

## Current public candidate

The current source release candidate is **DocAtlas 1.3.2**. It supersedes the unpublished `1.3.1` candidate because the public-launch README and Official MCP Registry ownership metadata were added after the immutable `v1.3.1` tag.

Canonical intended identity:

```text
product: DocAtlas
distribution: doc-atlas
source version: 1.3.2
planned immutable tag: v1.3.2
maturity: Beta
MCP Registry name: io.github.Vanilla1999/docatlas
MCP package: doc-atlas==1.3.2
MCP command: uvx doc-atlas==1.3.2 mcp docs-serve
```

No `v1.3.2` tag or public `doc-atlas==1.3.2` artifact is claimed by this preparation change. The tag must be created only by the reviewed release-request controller after this launch tree is merged and after the external PyPI Trusted Publisher is corrected. `server.json`, the source version, changelog, and hidden PyPI README ownership marker are kept version-aligned so the exact public package can be verified by the Official MCP Registry.

The Registry publication path uses GitHub OIDC and runs only after the canonical PyPI publish job and exact Linux/macOS/Windows public-package smokes succeed.

## Historical `v1.3.1` publication blocker


Canonical workflow run `32587903026` used the immutable `v1.3.1` source. Build, wheel tests on Python 3.11–3.13, sdist/installer validation, `required-release`, and build-provenance attestation passed. The publish job then failed before upload at `pypa/gh-action-pypi-publish` with:

```text
invalid-publisher: valid token, but no corresponding publisher
```

The OIDC token exposed these exact non-secret claims:

```text
sub: repo:Vanilla1999/DocAtlas:environment:release-current
repository: Vanilla1999/DocAtlas
repository_owner: Vanilla1999
repository_owner_id: 41183994
workflow_ref: Vanilla1999/DocAtlas/.github/workflows/publish.yml@refs/heads/main
job_workflow_ref: Vanilla1999/DocAtlas/.github/workflows/publish.yml@refs/heads/main
ref: refs/heads/main
environment: release-current
```

This proves the repository-side GitHub identity and narrows the remaining blocker to the external PyPI project configuration. Private project publisher settings are not exposed by PyPI, so the repository cannot prove which stored field is wrong.

Recorded gated artifacts:

```text
doc_atlas-1.3.1-py3-none-any.whl
sha256 6b82e37ec8ac2a3d415f30aa51e48830afecd04386d34dab694ee6b6c697b6b0

doc_atlas-1.3.1.tar.gz
sha256 6cbcdf8d947ca4f494fa3052d5012703c29386ec3e8f8629d7cabba58bb62aff
```

The first bounded machine-readable failure record is [`release-evidence/v1.3.1-publish-attempt-1.json`](./release-evidence/v1.3.1-publish-attempt-1.json).

### Controlled retry result

After confirming that public `1.3.1` was absent and that the immutable tag and original artifacts were unchanged, only the failed jobs of run `32587903026` were retried.

Run attempt 2:

```text
source commit: cfa9ab5c365a28d1a4af63afe9f1d53b19532d89
publish job: 97075492467
attestation: success
PyPI exchange: invalid-publisher
upload: rejected before upload
claims: identical to attempt 1
```

The second attestation is `42346600`, with Rekor log index `2567983694`. The repeated failure with identical claims weakens the transient lookup hypothesis and confirms that the external publisher still does not match.

The bounded second-attempt record is [`release-evidence/v1.3.1-publish-attempt-2.json`](./release-evidence/v1.3.1-publish-attempt-2.json).

### Required external correction

Because `doc-atlas` is an **existing PyPI project**, configure the publisher inside that project:

```text
PyPI → Your projects → doc-atlas → Manage → Publishing
```

Do not rely on an account-level **pending publisher** intended to create a new project. Add or replace the GitHub Actions publisher with exactly:

```text
owner: Vanilla1999
repository: DocAtlas
workflow filename: publish.yml
environment: release-current
```

Environment is optional in PyPI generally, but this workflow deliberately uses `release-current`; a publisher configured with a different environment does not match these claims.

### Superseded retry boundary

The two `v1.3.1` failures remain immutable audit evidence. They are no longer the active publication path: the launch and Registry ownership metadata were added after that tag, so the next public candidate is `1.3.2`. `v1.3.1` must never be moved, replaced, or reused. Do not move or recreate `v1.3.1`, and do not present a newer tree as that tag.

After the existing-project PyPI publisher is visibly corrected, create and approve a reviewed `v1.3.2` release request from the exact merged launch tree. No long-lived token fallback is permitted.

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

## Claim boundary

Until the exact public version is downloadable and passes the post-publish Linux/macOS/Windows MCP smoke, release truth remains incomplete and product maturity remains **Beta**.

For clarity, the failed `1.3.1` attempts remain historical pre-public evidence; no public `doc-atlas==1.3.2` release is claimed until the new exact release is published and verified.
