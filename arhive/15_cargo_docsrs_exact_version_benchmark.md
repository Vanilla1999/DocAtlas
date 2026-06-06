# 15 — Cargo docs.rs Exact-Version Benchmark

## Problem

Rust projects depend on exact crate versions from `Cargo.lock`, but the current benchmark does not verify version-specific docs.rs retrieval.

Without this, Docmancer's exact-version story is incomplete outside Dart/Flutter.

## Goal

Create a Cargo/docs.rs benchmark that verifies Docmancer can discover crate versions from `Cargo.lock`, generate version-specific docs.rs targets, and retrieve matching documentation.

## Scope

Inputs:

- fixture `Cargo.lock` files;
- selected crates with stable docs.rs pages;
- golden queries for crate APIs.

Required behavior:

- parse crate/version pairs from `Cargo.lock`;
- generate docs.rs targets like `https://docs.rs/<crate>/<version>/`;
- store `ecosystem=cargo`, `library`, `version`, and lockfile metadata;
- grade forbidden-version leakage.

Candidate crates:

- `serde`;
- `tokio`;
- `axum`;
- another crate with stable API docs and examples.

## Non-Goals

- Do not solve feature-flag-specific docs in the first pass.
- Do not require compiling Rust projects.
- Do not prefetch network docs without explicit user action.
- Do not build package registry mirroring.

## Implementation Notes

docs.rs pages can differ by feature/platform. The first benchmark should avoid APIs whose docs are heavily feature-gated unless the fixture explicitly models that behavior.

Keep the first version strict but narrow.

## Verification

Add tests for:

- `Cargo.lock` parsing;
- docs.rs URL generation;
- version metadata propagation;
- forbidden-version scoring.

Add eval artifacts for at least one crate/version pair.

## Success Criteria

- Exact crate versions are read from `Cargo.lock`.
- Generated docs targets include version-specific docs.rs URLs.
- Retrieved results carry matching version metadata.
- Strict benchmark mode reports forbidden-version rate `0.0` for passing fixtures.

## Current Status

Implemented MVP coverage in:

- existing project metadata and docs service code;
- `tests/test_exact_version_benchmark_mvp.py`.

The MVP verifies that `Cargo.lock` crate versions are read as `lockfile_exact` and can generate a version-specific docs.rs URL such as:

```text
https://docs.rs/serde/1.0.228/
```

Verification:

```bash
uv run pytest tests/test_exact_version_benchmark_mvp.py
```

This item is complete for lockfile parsing and target-generation MVP.

Remaining future work:

- add full network/prefetch benchmark artifacts;
- avoid feature-gated APIs in first docs.rs golden set;
- connect this to strict forbidden-version scoring in an end-to-end suite.
