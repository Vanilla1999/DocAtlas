# Release identity

## Current public candidate

The current source release candidate is **DocAtlas 1.3.1**.

Canonical identity:

```text
product: DocAtlas
distribution: doc-atlas
source version: 1.3.1
immutable tag: v1.3.1
tag object: 77bced8c530c88c57d2e6c5f58cb717bfe837a9f
tag target: cfa9ab5c365a28d1a4af63afe9f1d53b19532d89
maturity: Beta
```

The annotated `v1.3.1` tag exists and resolves to the exact reviewed merge of PR #133. It must never be moved, replaced, or reused.

No public `doc-atlas==1.3.1` release is claimed until the PyPI artifact bytes and post-publish platform smokes exist.

## Current `v1.3.1` publication blocker

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

### Safe retry boundary

After the existing-project publisher is visibly registered with the exact tuple above, retry only the failed jobs of canonical run `32587903026`. Before another retry, require that:

- public `doc-atlas==1.3.1` is still absent;
- `v1.3.1` remains an annotated tag targeting `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`;
- the original run's gated wheel and sdist artifacts remain available;
- no token fallback is introduced.

Do not move or recreate the tag. Do not start a replacement workflow from a newer `main` commit and present its provenance as the tagged source. If the public version appears before the retry, switch to verify-only handling and never overwrite it.

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

For clarity, no public `doc-atlas==1.3.1` release is claimed at this pre-public stage.
