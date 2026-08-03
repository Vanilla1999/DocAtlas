# Task 14 — close external ingest with partial provenance and a Kotlin smoke

## Priority

P0 acceptance closure for task 09. Complete after tasks 11–13, 28, 30, and 31.

## Implementation status

Complete. The real fetch boundary records page-level requested/discovered/canonical/redirect/fetch
provenance, preserves usable pages under partial failure, reports skipped/failed pages through
job status, and routes pinned GitHub blob sources through an auditable raw fetch identity. The
smoke harness and machine schema require isolated execution, exact `1.8.1` provenance, and
cited code-bearing evidence.

The live closure evidence is `eval/kotlin_smoke/task14_live_1_8_1.json`, merged in PR #82 at
`cebda15c50e57dfa273a345213c9257b97a9f75c`. It records `terminal_status: succeeded`,
resolved version `1.8.1`, and `code_match: true`. The evidence landed as a separate commit
in the required proxy-fix PR rather than in a standalone evidence-only PR; this closure records
that reviewed exception explicitly. Task 09 is closed for its defined reliability scope. Stable
promotion still requires the separately approved exact-public-PyPI post-publish check.

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

The closure gate passed via `eval/kotlin_smoke/task14_live_1_8_1.json`, merged in PR #82 at
`cebda15c50e57dfa273a345213c9257b97a9f75c`. The pinned live run succeeded and the repeated
exact query returned official cited code context. Task 09 is therefore closed for its defined
scope. This does not replace the separately approved exact-public-PyPI post-publish Stable gate.

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
