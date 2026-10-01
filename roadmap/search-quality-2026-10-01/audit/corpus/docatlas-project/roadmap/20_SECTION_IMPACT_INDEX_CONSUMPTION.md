# Task 20 — consume section metadata for precise documentation impact

Status: Done for bounded section-impact scope (`a685767`).

## Completion evidence

- `ProjectSectionIndexReader` consumes stored section metadata only when its schema and document content hash match the repository file; stale or missing metadata is reparsed and reported through the existing `prepare_docs` refresh boundary.
- `changed_evidence_from_git()` derives bounded Python, TypeScript/JavaScript, and Dart symbol evidence from the exact base/head diff, preserving rename, deletion, move, parser-fallback, and truncation diagnostics.
- Every ranked section candidate carries a stable reason code, evidence, confidence, metadata source, and authority, separated into `must_update`, `review`, and `unlikely` groups.
- The default contract is bounded to 200 returned section candidates and 32 KiB serialized output, with deterministic totals, omission accounting, and continuation guidance.
- `tests/docs/test_docs_impact_task20.py` covers current/stale hashes, supported-language diffs, conservative fallbacks, ranking, bounds, continuation, and the 30-change quality corpus. The frozen gates require must-update recall at least 0.90 and precision at least 0.75.
- The `docs-impact` CI job checks out full history and invokes the installed CLI with the pull request's exact base and head SHA; `--changed-symbol` remains an explicit override/debug input.

The implementation was merged to `main` in `a685767b016219923139983a97f046a60ab395f1`. This audit closes the stale roadmap state; it does not broaden the implementation or claim automatic documentation editing.

## Priority

P1 local-project maintenance.

## Problem

Project-doc indexing stores section metadata, but production impact analysis reparses Markdown rather than reading the indexed metadata. Content hashes are not used to detect stale metadata, and CI normally passes only changed paths; symbol hints require manual input.

## Goal

Use the derived index as a fast, verifiable section-impact map and derive changed symbols from code diffs automatically.

## Required changes

1. Add one application-level reader for stored project document sections and their content hash/schema version.
2. Use stored metadata when the repository file hash matches. Reparse only missing/stale documents and refresh derived metadata through the existing preparation boundary.
3. Parse the Git diff for changed symbols in the currently supported languages, including added, modified, renamed, and deleted definitions.
4. Keep a conservative fallback when symbol parsing fails: report path/module impact with an explicit lower confidence, never silently return no impact.
5. Rank impacted sections using path/module ownership, symbol references, dependency/config relationships, and section authority.
6. Return reason codes and evidence for every impacted section. Separate `must_update`, `review`, and `unlikely` without claiming certainty unsupported by evidence.
7. Bound work for large diffs and large docs sets. Return at most 200 ranked section candidates and 32 KiB serialized output by default; report total/truncated counts and a continuation/manual command.
8. Extend CI to pass the actual base/head diff and use automatic symbols; retain explicit `--changed-symbol` as an override/debug input.

## Required fixtures

- Python, TypeScript/JavaScript, and Dart symbol rename/change/delete;
- matching versus stale document content hash;
- file rename and module move;
- parser failure fallback;
- large diff truncation;
- irrelevant nearby section versus a distant section with the changed symbol.

Measure section-level precision/recall on a labeled fixture corpus of at least 30 code changes. Freeze minimum must-update recall at 0.90 and precision at 0.75 before optimization; report both when a conservative fallback is used.

## Non-goals

- Do not edit documentation automatically.
- Do not build a full compiler for each language.
- Do not require a vector backend.

## Acceptance criteria

- A matching indexed hash avoids reparsing the Markdown file.
- Stale/missing metadata is detected and never used as current truth.
- CI derives symbols from the diff for supported fixtures without manual flags.
- Every recommendation includes a stable reason and evidence.
- At least 30 labeled changes meet must-update recall >=0.90 and precision >=0.75; output respects the 200-section/32-KiB bounds.
- Related tests and `git diff --check` pass.
