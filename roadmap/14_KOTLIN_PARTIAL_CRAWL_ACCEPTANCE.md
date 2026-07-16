# Task 14 — close external ingest with partial provenance and a Kotlin smoke

## Priority

P0 acceptance closure for task 09. Complete after tasks 11–13, 28, 30, and 31.

## Implementation status

Done for the deterministic offline and PR merge gate. The real fetch boundary records
page-level requested/discovered/canonical/redirect/fetch provenance, preserves usable pages
under partial failure, reports skipped/failed pages through job status, and routes pinned
GitHub blob sources through an auditable raw fetch identity. The smoke harness and machine
schema require isolated execution, exact `1.8.1` provenance, and cited code-bearing evidence.

The separately owned live evidence gate remains pending. Task 09 and Stable promotion must
remain open until a successful sanitized pinned live artifact lands in an evidence-only PR.

## Problem

Fake-agent tests cover parts of ingest, but there is no end-to-end evidence for the reported Kotlin workflow. A crawl can discover a GitHub `blob` page, lose page-level provenance, or collapse one bad page into total `not_found`.

## Goal

Prove that real fetch/extract/index components produce queryable partial results and complete the exact Kotlin coroutine workflow within explicit bounds.

## Required changes

1. Record a per-page ledger containing requested, canonical, redirect, and discovered URL; fetcher used; outcome; safe reason; bytes/chunks; and elapsed time.
2. Report cross-domain/path-policy skips explicitly rather than following or hiding them.
3. Route supported GitHub `blob` URLs through the GitHub-aware/raw fetch path and preserve both displayed source and fetch identity.
4. Define terminal `partial`: at least one usable page committed and at least one page failed/skipped. It must be distinct from `success`, `failed`, and `not_found`.
5. Make successfully indexed chunks queryable after a partial job and surface the failed-page summary in status.
6. Add a deterministic integration fixture using the actual WebFetcher/extractor boundary: one valid code page, one broken page, one cross-domain link, and one GitHub blob mapping.
7. Add a manually runnable, bounded live smoke script for `kotlinx.coroutines` using an official URL pinned to a tag or commit rather than rolling `master`.

## Kotlin live-smoke protocol

The documented command must:

- use an isolated `DOCMANCER_HOME`;
- apply an overall timeout of at most 180 seconds;
- call `prepare_docs` asynchronously with an explicit pinned version/source;
- receive a `job_id` within one second and poll responsive `docs_status`;
- repeat the exact question `coroutines launch async example with code`;
- require at least one cited, code-bearing result containing `launch` or the `async`/`await` pair;
- record requested/resolved version and canonical source identity;
- store only a small sanitized result artifact with command, DocAtlas commit, source tag/commit, elapsed time, terminal status, and citations.

The live smoke is opt-in. Default CI must run the deterministic offline fixture, not the public Kotlin site.

## PR merge gate

- The offline good/broken/cross-domain/GitHub fixture passes through the real components.
- The live-smoke command has a testable dry/local-fixture mode, enforces the timeout, and writes a validated sanitized artifact schema.
- No successful public Kotlin run is required to merge code from an environment without outbound access.

## Task 09 closure gate

After merge, a maintainer with network access runs the pinned smoke and commits the small sanitized successful result in a separate evidence-only PR. Task 09 remains `Partial`, and a Stable release is blocked, until that artifact proves the repeated exact query returns the required cited code context. A network failure artifact is useful diagnosis but does not satisfy closure.

## Non-goals

- Do not crawl all Kotlin documentation.
- Do not make live internet a merge requirement.
- Do not label a network failure as unsupported or `not_found`.

## Acceptance criteria

- Good-plus-broken fixture ends `partial`; good code is retrievable and the failure remains visible.
- GitHub blob and cross-domain behavior are proven through actual fetch components.
- Kotlin smoke script, local-fixture artifact, and artifact-schema validation are committed in the implementation PR.
- The separately owned closure artifact records a pinned live run that reaches succeeded/partial and returns official cited code context.
- Public tool count remains three. Task 09 is marked closed only after the separate closure gate passes.
- Related tests and `git diff --check` pass.
