# Task 10 — validate every curated source target

## Priority

P0 correctness hotfix. Keep this PR small and complete it before expanding the source catalog.

## Problem

The curated `flutter_bloc` entry expands its documentation URL on `pub.dev`, but its `allowed_domains` contains only `bloclibrary.dev`. The target security layer correctly rejects the generated target. Existing tests materialize only selected entries, so an invalid manifest row can ship unnoticed.

## Goal

Make every committed curated source internally valid before any network request is attempted.

## Required changes

1. Add `pub.dev` to the `flutter_bloc` row's allowlist because its exact documentation template is already `https://pub.dev/documentation/flutter_bloc/{version}/`. Keep `bloclibrary.dev` only for declared seeds that are actually validated and used. Do not weaken global host validation.
2. Add one offline manifest validator that, for every row:
   - validates required fields and the declared support level;
   - expands at least one representative version for versioned templates;
   - checks seed and target URLs against the row's own domain/path policy;
   - rejects unresolved placeholders, URL userinfo, empty hosts, and unsupported schemes;
   - reports the library key and field in a stable validation error.
3. Run the validator in a focused test over the entire shipped manifest, not only hand-picked libraries.
4. Validate the current `exact`/`unversioned` schema only. Do not introduce the richer capability schema owned by task 16. The hotfix must not relabel an unversioned source as exact.

## Files to inspect first

- `docmancer/docs/curated_sources.json`
- `docmancer/docs/curated_sources.py`
- `docmancer/docs/application/docs_target_service.py`
- `docmancer/docs/domain/target_security.py`
- existing curated-source tests

## Non-goals

- Do not add new libraries.
- Do not crawl public sites in tests.
- Do not implement the snapshot cache or cold-start benchmark.
- Do not bypass `allowed_domains` for Dart packages.

## Tests

Add a regression test for `flutter_bloc@8.1.6` and a parametrized/full-manifest test. Both must be offline and deterministic.

## Acceptance criteria

- `flutter_bloc@8.1.6` produces an allowed target without an exception.
- Every shipped manifest row passes the same target/seed validator.
- A fixture with a target host missing from `allowed_domains` fails with a stable, library-specific message.
- No source support level is broadened to hide a validation failure.
- Focused tests and `git diff --check` pass.
