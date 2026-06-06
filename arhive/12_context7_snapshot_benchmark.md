# 12 — Context7 Snapshot Benchmark

## Problem

The current Context7 comparison still depends partly on manual inspection of Context7 tool outputs. That makes the comparison hard to repeat, hard to review, and easy to drift.

Docmancer needs machine-readable Context7 snapshots so both systems can be graded with the same benchmark schema.

## Goal

Persist Context7 outputs for the public-doc benchmark suite and grade them with the same expected-source/fact schema used for Docmancer artifacts.

The target outcome is a repeatable Suite A comparison:

> Docmancer and Context7 are evaluated from saved artifacts with the same grader.

## Scope

Start with the existing public-doc suites:

- Riverpod;
- FastAPI.

Artifacts to add:

- raw Context7 query outputs;
- normalized Context7 result snapshots;
- graded Context7 metric report;
- comparison report that reads Docmancer and Context7 artifacts.

Metrics:

- Hit@K;
- MRR;
- canonical-source Hit@1/Hit@5;
- snippet presence where visible in returned content;
- source diversity where result sources are available;
- latency if the tool reports or can measure it reliably.

## Non-Goals

- Do not require Context7 access for normal Docmancer tests.
- Do not make Context7 snapshots part of offline unit tests.
- Do not claim exact parity if source URLs or snippets cannot be normalized reliably.
- Do not fetch arbitrary hosted docs outside the benchmark fixture list.

## Implementation Notes

Use a two-stage design:

1. capture Context7 outputs into stable JSON fixtures;
2. run grading against the saved fixtures.

Keep the capture step manual or opt-in if tool/network access is not always available.

Suggested paths:

- `eval/results/context7_riverpod_results.json`;
- `eval/results/context7_fastapi_results.json`;
- `eval/results/public_docs_comparison.json`.

## Verification

Run the grader against saved artifacts without network access.

Expected checks:

- Context7 artifacts parse successfully;
- Docmancer artifacts parse successfully;
- both systems produce comparable metric objects;
- comparison report includes the same query IDs for both systems.

## Success Criteria

- Manual Context7 notes are replaced by saved machine-readable snapshots.
- The comparison can be rerun without querying Context7.
- Any manual judgment that remains is explicitly marked in the artifact.
- The report separates measured facts from interpretation.

## Current Status

Implemented MVP artifacts:

- `eval/results/context7_riverpod_results.json`;
- `eval/results/context7_fastapi_results.json`.

Implemented offline validation:

- `tests/test_context7_snapshot_benchmark.py`.

The snapshots are normalized machine-readable artifacts from prior Context7 tool output. They are explicitly marked with:

- `capture_method: manual_normalized_from_tool_output`;
- `review_status: manual_assessment_required_for_recapture`.

The validation checks:

- Context7 artifact schema version;
- Context7 source identity;
- dataset path;
- query count;
- `Hit@1`;
- `Hit@5`;
- `MRR`;
- snippet presence metric;
- locale contamination metric;
- item IDs match the golden dataset;
- item IDs match the saved Docmancer artifact for the same suite;
- Docmancer and Context7 artifacts expose comparable metric fields.

Verification completed:

```bash
uv run pytest tests/test_context7_snapshot_benchmark.py
```

Result:

```text
3 passed
```

Broader artifact verification:

```bash
uv run pytest tests/test_context7_snapshot_benchmark.py tests/test_public_docs_regression_gate.py tests/test_eval.py
```

Result:

```text
19 passed
```

This roadmap item is complete for the offline snapshot-comparison MVP.

Remaining future work:

- automate live Context7 recapture when tool access is available;
- store raw Context7 payloads in addition to normalized snapshots;
- generate a combined markdown/JSON comparison report from both systems' artifacts.
