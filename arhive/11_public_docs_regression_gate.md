# 11 — Public Docs Regression Gate

## Problem

The public-docs quality lane now has saved Riverpod and FastAPI artifacts with strong metrics, but nothing prevents future retrieval, ingest, or eval changes from regressing them.

The current results are only durable if they become an automated check.

## Goal

Add a small soft regression gate that validates saved public-doc benchmark artifacts without requiring network access or reindexing.

The gate should answer one question:

> Did the current code preserve the public-doc quality bar captured by the saved artifacts?

## Scope

Inputs:

- `eval/results/docmancer_riverpod_results.json`;
- `eval/results/docmancer_fastapi_results.json`.

Checks:

- Riverpod `Hit@1 == 1.0`;
- Riverpod `Hit@5 == 1.0`;
- Riverpod `MRR == 1.0`;
- Riverpod `locale_contamination_rate == 0.0`;
- FastAPI `Hit@1 == 1.0`;
- FastAPI `Hit@5 == 1.0`;
- FastAPI `MRR == 1.0`;
- snippet metrics exist;
- `snippet_present_at_5_rate > 0.0` for both suites.

## Non-Goals

- Do not fetch docs from the network.
- Do not re-run Context7.
- Do not make this a hard CI gate until thresholds are stable.
- Do not add broad benchmark orchestration in this task.

## Implementation Notes

Prefer a small test or script over a large benchmark framework.

Possible options:

1. add a focused pytest file under `tests/` that reads saved JSON artifacts;
2. add an eval command that checks artifact thresholds;
3. use both only if the CLI command is already needed by maintainers.

Start with option 1 unless a CLI command is explicitly required.

## Verification

Run:

```bash
uv run pytest tests/test_public_docs_regression_gate.py
```

Then run the broader relevant suite:

```bash
uv run pytest tests/test_eval.py tests/test_retrieval_features.py tests/test_public_docs_regression_gate.py
```

## Success Criteria

- Saved Riverpod and FastAPI artifacts are validated by an automated local check.
- The check is deterministic and offline.
- Failure messages identify the exact metric that regressed.
- The check does not require Qdrant, network access, or live docs indexing.

## Current Status

Implemented as:

- `tests/test_public_docs_regression_gate.py`.

The gate reads saved JSON artifacts directly and checks:

- dataset identity;
- query count;
- `Hit@1`;
- `Hit@5`;
- `MRR`;
- `locale_contamination_rate`;
- `snippet_present_at_5_rate` exists and is positive;
- `snippet_sections_at_5_avg` exists and is positive.

Verification completed:

```bash
uv run pytest tests/test_public_docs_regression_gate.py
```

Result:

```text
2 passed
```

Broader related verification:

```bash
uv run pytest tests/test_eval.py tests/test_retrieval_features.py tests/test_public_docs_regression_gate.py
```

Result:

```text
33 passed
```

This roadmap item is complete for the current offline soft-gate objective.
