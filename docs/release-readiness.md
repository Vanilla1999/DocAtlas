# Release readiness: dated checkpoint

> **2026-11-14 update:** [PR #256](https://github.com/Vanilla1999/DocAtlas/pull/256) was merged into `main` at `d7db88319e3267a62fd31bf0e316cfd19f1bc202`. The owner chose `2.0.0` for a separate, **unpublished** preparation PR. The 2026-11-13 CI evidence below remains a dated pre-merge observation, not a 2.0.0 sign-off. See the [2.0.0 candidate plan](RELEASE_2_0_0_CANDIDATE.md).

**As of 2026-11-13: not approved for publication.** This snapshot describes
existing CI evidence for onboarding PR [#256](https://github.com/Vanilla1999/DocAtlas/pull/256),
code head `1a52300c53f114b9889b049dd8c09cd2e2791b48`, compared with main
`39d893b4d8886b8bbaa446ba1414271a93604b3b`. It is not a live green badge;
later commits must pass their own required checks.

No new product/model runs were made for this documentation update. The README's
[historical Grounded comparison](benchmarks/grounded-meridian.md) is not a
qualification of the release candidate, the current default, or today's Qwen mode.

## What has passed, and what has not

| Boundary | Observed result | What it does not prove |
| --- | --- | --- |
| Build and artifact/version `release_gate.py` | PASS | Installed MCP behavior or a publishable release |
| Wheel pip install, Python 3.11/3.12/3.13 | PASS | Clean `uv` installer and client onboarding |
| Build wheel from sdist, then pip reinstall | PASS | Later installed-stdio checks, which failed |
| Platform wheel build/install on Ubuntu, macOS 15 ARM, macOS 15 Intel | PASS | Real client sessions |
| New installed reranker-onboarding/default-MCP suite | **5/5 PASS on each of those three platforms** | Full model download, supported-GPU inference, or the wider MCP contract |
| Disposable OpenCode config registration and real stdio launch | Executed | Registration and operation inside a user's live OpenCode client |
| Broader installed Docs MCP smoke | **FAIL** | Cannot be waived by the narrower onboarding pass |
| `scripts/test-install.sh` smoke | PASS with stubs | A clean-cache `uv` install of the exact candidate |
| Real `scripts/install.sh` step in release job | **SKIPPED** after stdio failure | Even the planned `DOCATLAS_AGENT=none` step would not qualify client registration |
| Required CI / required release | **FAIL** | Publication is not qualified |
| Publish, MCP registry publish, public-platform smoke | **SKIPPED** | No release was published by this run |

Evidence: [CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431),
[release workflow](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391067),
[Ubuntu onboarding](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849025847),
[macOS ARM onboarding](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849026058),
[macOS Intel onboarding](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849026080),
[wheel 3.12](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391067/job/131849313259),
[sdist and skipped installer](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391067/job/131849313213).

## Immediate blockers

The installed-stdio script reports three failing scenario labels, not three
pytest node IDs:

1. `version_mismatch`: `failed / bad_request / ValueError` instead of the expected
   contract outcome.
2. `>32KiB unique source evidence not delivered under unchanged acquisition`:
   the smoke's unique-source span requirement is not met.
3. `text cold preparation failed: AssertionError`: the response is `truncated`,
   with 53 candidate rows, one eligible/selected row, 52 pruned/omitted rows,
   and `budget_limited=false`.

See the [recorded failure](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391067/job/131849313259)
and the [smoke source at the reviewed head](https://github.com/Vanilla1999/DocAtlas/blob/1a52300c53f114b9889b049dd8c09cd2e2791b48/scripts/docs_mcp_stdio_smoke.py).
Each needs classification against the current public contract: product defect,
obsolete expectation, or harness defect. A blanket budget increase, deletion,
or changed expected answer is not evidence that delivery was fixed.

The Python 3.12 core runs also remain red:

| Snapshot | Failed | Passed | Skipped | Deselected |
| --- | ---: | ---: | ---: | ---: |
| [PR #256 / `1a52300`](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849025833) | 89 | 1,455 | 13 | 136 |
| [Main / `39d893b`](https://github.com/Vanilla1999/DocAtlas/actions/runs/43459044510/job/132000756971) | 89 | 1,450 | 13 | 136 |

The sets of all 89 failed test node IDs are identical. The PR adds five passing
scenarios and no new failed node IDs **in this comparison**; this is not proof
that every behavior is regression-free. Existing failures still block release.
Concrete follow-ups include the [missing `cli:reranker` support-policy inventory
entry](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849025833)
and a separate [retrieval-evidence harness failure](https://github.com/Vanilla1999/DocAtlas/actions/runs/43414391431/job/131849025642):
it patches the private `docs_context_projection._expand_selected_snippets` helper,
which is absent at the reviewed head. These do not explain away the other scope,
provenance, selection, or delivery failures.

## Remaining work, in order

1. **Resolve the installed-MCP failures and required-CI baseline.** Use existing
   public CLI/MCP scenarios and exact delivered source evidence. Where an old
   expectation conflicts with an approved contract, document that decision;
   do not silently weaken the guard or relabel a failing product behavior PASS.
2. **Run clean first-install checks.** Use isolated `uv` cache/configuration,
   the exact candidate artifact, Linux and macOS, and disposable client
   configurations. Verify installation, explicit registration choices,
   consent/no unintended writes, `get_docs_context`, a returned `prepare_docs`
   action, and the successful retry. Record real client E2E separately from
   config generation and bare stdio. Do not use latest PyPI as a substitute for
   an unreleased candidate.
3. **Qualify or explicitly keep unqualified the experimental Qwen path.** Keep
   the [documented pinned profile](../wiki/Reranker.md), local assets, explicit
   consent, and no silent lexical fallback. A fresh `prepare` needs a permitted
   connection to the model CDN; readiness and one real scorer forward need the
   exact runtime and a supported GPU. Check the documented dependency recipe
   from a clean environment. CPU/macOS onboarding tests and `reranker check`
   do not prove model inference. If this cannot be completed, retain an explicit
   experimental/unqualified boundary; do not advertise supported Qwen inference.
   Any exception to planned pre-release qualification needs explicit release-owner
   approval; documentation alone does not waive it.
4. **Verify the owner-selected 2.0.0 release identity.** At the 2026-11-13
   snapshot, the source was still **1.3.2**. On 2026-11-14 the owner selected
   **2.0.0**; it is prepared separately, not yet approved for publication.
   Reconcile version, changelog, package and registry metadata, and exact
   artifact contents before an immutable tag or publish run.
5. **Re-run required gates on the exact release candidate, then publish only
   with approval.** Merge, tag/publish, registry publication, and verification
   of the publicly installed artifact are separate boundaries. This checkpoint
   authorizes none of them and does not describe a completed release.

The ordinary lexical path must remain usable without Qwen/CUDA. Optional Qwen
qualification does not justify loosening source, access, version, or consent
guards for either path.
