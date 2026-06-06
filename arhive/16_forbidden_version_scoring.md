# 16 — Forbidden-Version Scoring

## Problem

Exact-version retrieval is only useful if Docmancer can detect when a result comes from the wrong version.

Current public-doc metrics do not fully measure forbidden-version leakage.

## Goal

Add benchmark and query-trace support for identifying results that conflict with the expected project or requested version.

The strict benchmark outcome:

> If a query requires version X, results from version Y are counted as forbidden unless explicitly allowed.

## Scope

Eval additions:

- expected version fields;
- forbidden version fields;
- per-result version comparison;
- aggregate `forbidden_version_rate`.

Query trace additions:

- source version where known;
- version source, for example `project_lockfile_exact`;
- warning when returned version conflicts with requested/project version.

## Non-Goals

- Do not block normal exploratory queries from returning unversioned docs.
- Do not require all sources to have version metadata.
- Do not invent versions from page text when metadata is unavailable.
- Do not make this a hard runtime error outside strict benchmark mode.

## Implementation Notes

Treat unknown version and wrong version differently:

- unknown version: measurable uncertainty;
- wrong version: forbidden in strict exact-version suites.

The benchmark schema should allow both exact and range-based expectations if needed later, but start with exact strings.

## Verification

Add tests for:

- matching version passes;
- wrong version fails;
- unknown version is reported separately;
- aggregate forbidden-version rate is computed correctly.

## Success Criteria

- Eval can report forbidden-version leakage.
- Query traces can explain version conflicts when metadata exists.
- Exact-version benchmark suites can enforce `forbidden_version_rate == 0.0`.

## Current Status

Implemented MVP in:

- `docmancer/eval/runner.py`;
- `tests/test_eval.py`.

Eval now flags forbidden versions from two sources:

- text matches against explicit `forbidden_versions`;
- result metadata `version` / `resolved_version` that conflicts with `project_context.version` for exact-version items.

Eval also reports `unknown_version_hits` for exact-version items when returned results do not carry version metadata.

Verification:

```bash
uv run pytest tests/test_eval.py
```

This item is complete for scoring and reporting MVP.

Remaining future work:

- add aggregate `forbidden_version_rate` / unknown-version rate fields;
- integrate strict thresholds into exact-version benchmark gates.
