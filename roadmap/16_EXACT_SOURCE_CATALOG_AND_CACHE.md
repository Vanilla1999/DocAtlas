# Task 16 — build an honest exact-source catalog and snapshot cache

## Priority

P1. Complete only after the external ingest gates are reliable.

## Problem

The curated manifest has broad library coverage on paper, but most rows point to rolling/unversioned documentation and are rejected for exact-version requests. `canonical_source_identity` is mostly metadata, preferred seeds are not proven useful, and there is no measured identity-plus-content-hash snapshot cache.

## Goal

Give priority libraries an explicit, validated source capability and make repeated exact-source preparation reuse immutable local snapshots.

## Source capability model

Every catalog entry must declare one of:

- `exact`: source content is bound to the requested exact version;
- `version_family`: source is bound only to a documented compatible family;
- `rolling`: current documentation with no exact-version claim;
- `unsupported`: no safe automatic source rule is known.

An exact request may use only `exact`, or a `version_family` rule when the compatibility mapping is explicit and returned to the user. It must never silently relabel rolling content.

## Required changes

1. Audit the libraries used by the parity dataset and record proof for each source rule: official owner, version locator, allowed domains/paths, seed type, and extraction format.
2. Validate every template and preferred seed offline with representative versions. Do not ship mechanically guessed URL paths.
3. Return `unsupported_source_version` with one explicit source-request action when no valid rule exists.
4. Define canonical identity normalization for scheme, IDNA/host, default port, fragments, safe query normalization, redirects, and source version. Do not lowercase case-sensitive paths.
5. Store fetched snapshots by canonical identity plus content hash. Keep provenance, fetch timestamp, validation state, and source capability alongside the snapshot.
6. Warm preparation/query for an unchanged identity must perform zero network calls.
7. A changed content hash creates a new immutable snapshot and atomically advances the active pointer; failed refresh leaves the last good snapshot usable and visibly stale.
8. Instrument cold and warm latency/network counts and publish p50/p95 results for a deterministic local benchmark plus an optional bounded public-source smoke. Freeze the local fixture target at cold p95 at or below 10 seconds and zero warm network calls; public-network latency is reported separately and cannot fail CI for internet variance.

## Non-goals

- Do not claim 30 exact sources merely to preserve a catalog count.
- Do not bundle a hosted Context7-sized corpus.
- Do not solve lockfile ambiguity in this task; task 17 owns dependency identity.

## Acceptance criteria

- Every priority entry has validated support-level evidence or is explicitly unsupported.
- Exact requests never fall back to rolling/latest content.
- Snapshot lookup is demonstrably keyed by canonical identity and content hash.
- Warm repeated preparation and retrieval make zero network calls.
- The deterministic supported-source benchmark has cold p95 at or below 10 seconds and zero warm network calls; public-source outliers are listed rather than hidden in an average.
- Catalog/cache tests and `git diff --check` pass.
