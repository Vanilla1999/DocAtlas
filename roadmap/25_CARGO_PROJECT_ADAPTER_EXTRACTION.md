# Task 25 — extract the Cargo project adapter

## Priority

P2 bounded architecture follow-up to task 01.

## Goal

Move only Rust/Cargo manifest and lockfile parsing out of `ProjectMetadataReader` so a model changing Rust support does not load unrelated ecosystem code.

## Required change

Create `docmancer/docs/cargo_project.py` with one public adapter function following the established Python/Node adapter shape. Move only:

- `Cargo.toml` dependency/workspace observation;
- `Cargo.lock` exact-version parsing;
- Cargo source-kind/version helper logic;
- Rust-specific warnings.

Keep `ProjectMetadataReader.read()` as the orchestrator and preserve ordering, warnings, duplicate behavior, and serialized output byte-for-byte for existing fixtures.

Before editing, add or identify a golden fixture that captures current Cargo output. Compare old/new output structurally and as deterministic serialized JSON.

## Non-goals

- Do not improve Cargo workspace resolution in this extraction.
- Do not move Pub code.
- Do not refactor docs discovery, CLI, MCP, or application services.
- Do not rename public models or fields.

## Acceptance criteria

- `docmancer/docs/project.py` contains no Cargo parser implementation.
- Existing and golden Cargo metadata output is unchanged.
- The new module imports no CLI/MCP/application service.
- The diff is limited to the adapter boundary, imports, and focused tests.
- Focused metadata/exact-version tests and `git diff --check` pass.
