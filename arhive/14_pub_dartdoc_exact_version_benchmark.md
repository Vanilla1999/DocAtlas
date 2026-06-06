# 14 — Pub Dartdoc Exact-Version Benchmark

## Problem

Docmancer's strongest product wedge is exact-version documentation from project dependency metadata, but the current public-doc benchmark does not prove that wedge.

For Dart and Flutter projects, this means resolving package versions from `pubspec.lock` and retrieving docs for those exact package versions.

## Goal

Create an exact-version Pub/Dartdoc benchmark that verifies Docmancer can retrieve version-specific package documentation from a project lockfile.

The target behavior:

> Given a Dart/Flutter project, Docmancer can identify package versions and answer API-doc queries from matching Dartdoc pages without leaking newer or older versions.

## Scope

Inputs:

- fixture `pubspec.lock` files;
- selected packages with stable Dartdoc pages;
- golden queries that mention package APIs/classes.

Required implementation or fixtures:

- parse package/version pairs from `pubspec.lock`;
- generate Pub/Dartdoc documentation targets;
- prefer concrete class/API seed pages for key packages;
- store `ecosystem=pub`, `library`, `version`, and `version_source=project_lockfile_exact`;
- evaluate forbidden-version leakage.

Candidate packages:

- `riverpod` or `flutter_riverpod`;
- `go_router`;
- another package with stable class-level Dartdoc pages.

## Non-Goals

- Do not silently prefetch network docs during project inspection.
- Do not support every Pub package edge case in the first benchmark.
- Do not replace existing public website docs ingestion.
- Do not require Flutter SDK execution unless parsing lockfiles needs it.

## Implementation Notes

Dartdoc package roots can be too broad. Prefer concrete seed URLs for known important APIs where possible, for example class/library pages rather than only package index pages.

The benchmark should separate:

- dependency discovery;
- docs target generation;
- optional network prefetch;
- retrieval grading.

## Verification

Add tests for:

- lockfile parsing;
- target URL generation;
- version metadata propagation;
- forbidden-version scoring.

Add eval artifacts for at least one package/version pair.

## Success Criteria

- Exact package versions are read from `pubspec.lock`.
- Generated docs targets include version-specific Pub/Dartdoc URLs.
- Retrieved results carry matching version metadata.
- Strict benchmark mode reports forbidden-version rate `0.0` for passing fixtures.

## Current Status

Implemented MVP coverage in:

- existing project metadata and docs service code;
- `tests/test_exact_version_benchmark_mvp.py`.

The MVP verifies that `pubspec.lock` package versions are read as `lockfile_exact` and can generate a version-specific Pub/Dartdoc URL such as:

```text
https://pub.dev/documentation/go_router/14.8.1/
```

Verification:

```bash
uv run pytest tests/test_exact_version_benchmark_mvp.py
```

This item is complete for lockfile parsing and target-generation MVP.

Remaining future work:

- add full network/prefetch benchmark artifacts;
- add concrete class/API seed-page fixtures for selected packages;
- connect this to strict forbidden-version scoring in an end-to-end suite.
