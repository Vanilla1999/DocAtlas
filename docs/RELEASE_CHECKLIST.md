# DocAtlas release checklist

The DocAtlas release checklist is used before publication to verify a release artifact and its release gates. A source checkout passing tests is not enough: users install the built package.

Artifact/release correctness is necessary for every public release. A **Stable** product claim additionally requires the active public-truth, agent-truth, and product-truth gates in [`../roadmap/README.md`](../roadmap/README.md).

## Version and documentation

- [ ] `docmancer/_version.py`, release tag, and changelog heading name the same version.
- [ ] README install text matches the version that the installer actually resolves.
- [ ] README, product brief, [Docs MCP reference](./mcp-docs-server.md), wiki command/troubleshooting pages, and changelog agree that the public Docs MCP tools are `get_docs_context`, `prepare_docs`, and `docs_status`.
- [ ] Advanced Packs and patch constraints are labelled advanced/advisory.
- [ ] New active documentation is tracked by Git and does not duplicate the canonical Docs MCP workflow.
- [ ] The canonical user-facing release set (`README.md`, product brief, Docs MCP reference, capability reference, release checklist) is at most 1,000 lines, or this release records a reviewed exception and removal plan.
- [ ] Product claims remain inside the current evidence boundary: no Context7 parity, proven patch-improvement, or Stable claim is introduced without its named decision gate.

## P0 public-truth prerequisites

Before the next public release candidate:

- [ ] The release tag commit is reachable from remote `main`; the release workflow verifies this ancestry before building a dispatched release.
- [ ] The unprotected-`main` decision is recorded as `accepted_risk` in `public-truth-scorecard.md`; release documentation must not claim that branch protection is active.
- [ ] New DocAtlas state/integration identity is isolated from the active `docmancer` product namespace; clean installs do not implicitly write to foreign `~/.docmancer` state.
- [ ] Legacy state/config migration is ownership-checked, preview-first, fail-closed on ambiguous/foreign state, and covered by installed tests.
- [ ] Installed agent guidance and examples validate against the real three-tool public MCP schema.
- [ ] The active release identity note and changelog agree on the intended public version. Repository `1.2.0` is an unpublished milestone; the next intended public release is `1.3.1` unless a later reviewed release-preparation change supersedes it.
- [ ] The executable release decision is reviewable in `.github/release-requests/v1.3.1.json`; its exact base commit, allowed release delta, tag, publisher identity, and public tool inventory are validated before any tag is created.

## Built artifact

- [ ] Build wheel and sdist once from the release commit.
- [ ] Install the wheel in a clean environment for every Python version declared in package classifiers.
- [ ] Verify `doc-atlas --help`, `doc-atlas mcp --help`, package metadata, and bundled documentation from the installed wheel.
- [ ] Start the installed Docs MCP server through stdio and verify its public inventory is exactly `get_docs_context`, `prepare_docs`, `docs_status`.
- [ ] Run a deterministic temporary-repository smoke: `get_docs_context → prepare_docs(sync_project_docs) → get_docs_context` with a cited local source.
- [ ] Verify the installer resolves and health-checks the same published package version.
- [ ] Verify the installed default state/config/integration identity is DocAtlas-owned and does not modify foreign legacy state.

## Release controls

- [ ] CI is green for every claimed Python version.
- [ ] Merge one reviewed release-request PR. The controller waits for `required-ci` on the exact resulting `main` commit, verifies that `main` has not moved, creates or idempotently verifies the immutable annotated tag, and then dispatches the canonical `publish.yml`.
- [ ] The `release-current` environment approval is granted only after all artifact jobs pass; this is the explicit human publication authorization when environment protection is enabled.
- [ ] Publish has one explicit publication trigger (`workflow_dispatch`); neither tag pushes nor pull requests publish.
- [ ] Trusted Publishing is configured for owner `Vanilla1999`, repository `DocAtlas`, workflow `publish.yml`, environment `release-current`; no long-lived PyPI token is stored.
- [ ] For an existing PyPI project, add the publisher under **Your projects → doc-atlas → Manage → Publishing**. Do not configure only an account-level pending publisher, which is intended to create a project that does not yet exist.
- [ ] Download `release-manifest.json` and retain its wheel/sdist SHA-256 values with the release record.
- [ ] Public artifacts, tag, changelog, release metadata, and installed `doc-atlas --version` agree after publishing.
- [ ] Download the public wheel and sdist and verify their bytes/SHA-256 values match the gated artifacts before accepting the publication.
- [ ] Reinstall the exact public version with pip cache disabled and rerun the installed Docs MCP stdio smoke.
- [ ] Verify the exact public package on Linux, macOS, and Windows for the claimed primary MCP/install surface.
- [ ] Retain the controller's `reviewed-public-release-<version>-<run_id>` evidence artifact and move scorecard rows to green only through a separate reviewed closure PR.

### `invalid-publisher` recovery

When PyPI returns `invalid-publisher` after `required-release` succeeds:

- [ ] Record the exact workflow run/job, immutable tag object and target, non-secret OIDC claims, gated artifact hashes, and the fact that upload did not start.
- [ ] Do not move, delete, or recreate the release tag and do not introduce `PYPI_API_TOKEN` as a fallback.
- [ ] Open the **Publishing** page for the existing `doc-atlas` project and verify that owner, repository, workflow filename, and environment exactly match the claims printed by the failed action.
- [ ] Remove or replace stale/wrong publisher entries rather than adding another speculative workflow identity.
- [ ] Re-check that the public version is still absent and that the original run's tag target and artifacts remain exact.
- [ ] Retry only the failed jobs of the original canonical run so its source/provenance context remains unchanged; do not replace it with a dispatch from a newer `main` commit and call that the same reviewed release.
- [ ] Treat a second identical rejection as evidence that the external publisher still does not match; do not keep retrying without a visible configuration correction.
- [ ] If the public version appears before retry, stop publication and use verify-only handling; PyPI files are immutable and must never be overwritten.
- [ ] Keep P0.6 `INCOMPLETE` until exact public hashes, installed MCP behavior, and all three public platform smokes are green.

## Technical release evidence retained from the infrastructure roadmap

- [ ] Task 15 artifact-level evidence remains green for wheel/sdist/installer/MCP packaging.
- [ ] [Task 14](../roadmap/14_KOTLIN_PARTIAL_CRAWL_ACCEPTANCE.md)'s required live external-ingest evidence remains green for the bounded external-ingest claim.
- [ ] The explicitly approved post-publish verification of the exact public PyPI version is green.

These technical gates establish artifact and bounded ingest truth. They do **not** by themselves establish autonomous agent usability or real coding-task value.

## Stable promotion gate

Do not call the product Stable until all of the following are true:

1. P0 public truth is closed: release-source provenance is explicit, the unprotected-`main` residual risk is recorded rather than hidden, namespace/state isolation and contract consistency are green, and the exact public artifact plus cross-platform installed smoke are green.
2. P1 agent truth demonstrates that a real coding model can acquire the intended evidence through the installed public MCP contract under a frozen benchmark.
3. P2 product truth demonstrates real coding-task value or a material reduction in unsupported/wrong-version claims at acceptable total trajectory cost.
4. Context7 parity is claimed only if a separate comparable parity protocol demonstrates it; parity is not a prerequisite for Stable unless the active product decision makes it one.

Until then, public maturity remains **Beta** even when all artifact/release checks are green.
