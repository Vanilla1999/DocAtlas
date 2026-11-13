# DocAtlas 2.0.0 — release preparation, not publication

**Decision date:** 2026-11-14. The owner chose `2.0.0` instead of the earlier
`1.0` milestone label. The release version, if eventually approved, will be
`doc-atlas==2.0.0` with immutable tag `v2.0.0` and MCP Registry version `2.0.0`.
This is a preparation proposal, **not a claim that 2.0.0 is released or Stable**.

## Exact source boundary

- The preceding onboarding/documentation [PR #256](https://github.com/Vanilla1999/DocAtlas/pull/256)
  was merged into `main` as
  [`d7db88319e3267a62fd31bf0e316cfd19f1bc202`](https://github.com/Vanilla1999/DocAtlas/commit/d7db88319e3267a62fd31bf0e316cfd19f1bc202).
- This preparation PR is based on that exact merged source. Its changes stage
  version/registry metadata, a candidate changelog, and release readiness notes.
  It does **not** change retrieval, selection, default compression, source
  qualification, the Qwen model/runtime pins, or their no-fallback contract.
- Source version, `server.json` top-level and PyPI package versions, changelog
  heading, and this candidate version must all say `2.0.0` within the proposal.
- Package maturity intentionally stays **Beta**. A major number is not evidence
  of Stable quality, Context7 parity, superior answer accuracy, or a certified
  Qwen GPU runtime.
- The repository's historical `v1.3.0` and `v1.3.1` failed-publish evidence
  remains immutable. The earlier `1.3.2` candidate was not published and its
  version must not be repurposed as this release.

## Known gates as of preparation

The [last completed PR-head run](https://github.com/Vanilla1999/DocAtlas/actions/runs/43471505474)
for `c8e65205193208aba0a2bbde1f6f561c4deb4a13` ended with **13 successful,
8 failed, 1 skipped workflow**. This is the last completed pre-merge evidence,
not a claim about future 2.0.0 candidate CI.

| Boundary | Evidence | Release status |
| --- | --- | --- |
| Qwen/default installed onboarding | Five cases passed on Ubuntu, macOS ARM, and macOS Intel in [CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/43471505474) | Narrow onboarding PASS only |
| Wheel/sdist build, version gate, and pip installs | [Release artifact workflow](https://github.com/Vanilla1999/DocAtlas/actions/runs/43471505549) | Build/install passed before later failure |
| Installed Docs MCP stdio | Same release workflow; see [dated triage](release-readiness.md) | **BLOCKED** |
| Main/core integration tests | [CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/43471505474) | **BLOCKED**; prior main/PR comparison had the same 89 failing node IDs |
| Clean `scripts/install.sh` with a fresh `uv` cache | Not reached in earlier release job | **UNVERIFIED** |
| Live OpenCode, Claude Code, and Codex installed-client sessions | Fixture registration and bare stdio are not equivalent | **UNVERIFIED** |
| Full Qwen model download and a real pinned-GPU forward | `reranker check` is preflight, not inference | **UNVERIFIED** |
| PyPI Trusted Publisher and public artifact identity | Historical `1.3.1` attempts were rejected with `invalid-publisher` | **PENDING external confirmation** |
| Post-publish Linux/macOS/Windows and Official MCP Registry | No `2.0.0` public package exists | **NOT RUN** |

The installed-MCP failure cases must be classified against the real public
contract before acceptance: version-mismatch error shape, the unique-source
delivery expectation above 32 KiB, and cold preparation returning `truncated`
with one selected row out of 53 candidates. The 89-failure core baseline and
other red workflows are not automatically excused by identical failures on
the earlier `main` snapshot. See the [failure evidence](release-readiness.md).

## Qualification sequence before tag or publication

1. **Review candidate metadata and package contents.** Confirm the exact
   `2.0.0` version in package, `server.json`, changelog, identity note, and
   README ownership marker. Check public three-tool inventory and bundled
   assets; preserve the `docmancer` import namespace.
2. **Make required CI and installed-MCP checks pass on the exact candidate.**
   Diagnose each failure through installed public CLI/MCP behavior and actual
   delivered sources. Do not change the question, gold facts, budgets, or error
   expectations merely to green a job.
3. **Prove first-run behavior on the candidate artifact.** Build the exact
   wheel/sdist, use a clean managed-Python/`uv` cache and disposable configs on
   Linux/macOS, verify opt-in registration and consent, prepare a source, retry
   `get_docs_context`, and cite a source row. Separately exercise real clients.
4. **Decide Qwen release scope explicitly.** Maintain the optional experimental
   profile and exact model/runtime pins. A supported-GPU forward and CDN-based
   `prepare` still need evidence before advertising usable pinned inference;
   otherwise obtain the release owner's explicit acceptance of the unqualified
   experimental boundary. No silent lexical fallback or automatic downloads.
5. **Check external publication identity.** Verify the exact existing-project
   PyPI Trusted Publisher tuple `Vanilla1999 / DocAtlas / publish.yml /
   release-current` with the authorized project owner. Do not introduce a
   long-lived token workaround.
6. **Only after approval, create a separate reviewed release-request PR.**
   The request controller requires an `approved` request with the exact merged
   base/delta and `execute_on_merge`. A request is intentionally **not** part of
   this preparation PR, because that path can create an immutable tag and
   dispatch public publication. The final version cannot be inferred from an
   unreviewed draft or from a local build.
7. **Publish and verify only through the canonical controller.** After its
   required gates, verify the exact wheel/sdist SHA-256 against PyPI, do clean
   no-cache installed-MCP/public-platform checks, then publish and query the
   Official MCP Registry. Retain immutable release evidence.

## Deliberate non-actions in this proposal

- No `v2.0.0` tag, GitHub Release, PyPI upload, MCP Registry publication, or
  executable `.github/release-requests/v2.0.0.json` is created.
- No red test is deleted, skipped, or rewritten as a PASS.
- No default selection mode or `admission_only` semantics are changed.
- The historical Grounded graphs remain an observational comparison of older
  Qwen minimal-context with Grounded lexical; they are not 2.0.0 quality proof.

Release approval requires separate sign-off against the
[canonical checklist](RELEASE_CHECKLIST.md) and
[public-truth scorecard](public-truth-scorecard.md).
