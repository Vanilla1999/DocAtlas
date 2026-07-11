# Task 26 — extract the Pub project adapter

## Priority

P2 bounded architecture follow-up. Complete after task 25 in a separate PR.

## Goal

Move only Dart/Flutter Pub manifest and lockfile parsing out of `ProjectMetadataReader` so ecosystem changes stay within one small module.

## Required change

Create `docmancer/docs/pub_project.py` with one public adapter function following the established Python/Node/Cargo adapter shape. Move only:

- `pubspec.yaml` direct dependency/dev-dependency observation;
- `pubspec.lock` exact-version parsing;
- Dart/Flutter source-kind/version helper logic;
- Pub-specific warnings.

Keep `ProjectMetadataReader.read()` as the orchestrator and preserve ordering, warnings, duplicate behavior, and serialized output byte-for-byte for existing fixtures.

Before editing, add or identify a golden fixture that captures current Pub output. Include normal dependencies, dev dependencies, SDK/path/git sources, and a malformed entry warning.

## Non-goals

- Do not fix the curated `flutter_bloc` URL here; task 10 owns it.
- Do not add new Pub lock formats or workspace semantics.
- Do not refactor Cargo or application services.
- Do not rename public models or fields.

## Acceptance criteria

- `docmancer/docs/project.py` contains no Pub parser implementation.
- Existing and golden Pub metadata output is unchanged.
- The new module imports no CLI/MCP/application service.
- The diff is limited to the adapter boundary, imports, and focused tests.
- Focused metadata/exact-version tests and `git diff --check` pass.
