# 19 — Qdrant Version Warning Policy

## Problem

Eval and test runs currently show a Qdrant client/server compatibility warning when the local client and server minor versions are outside the recommended range.

The warning does not currently block the public-doc quality lane, but it adds noise and can hide more important warnings.

## Goal

Decide and implement a clear policy for Qdrant version compatibility warnings in local tests, eval runs, and user-facing commands.

## Scope

Options to evaluate:

1. align Qdrant client and server versions in the development/test environment;
2. suppress compatibility checks only in controlled local eval/test flows;
3. keep the warning but classify it clearly in eval logs;
4. document the supported version matrix and remediation steps.

## Non-Goals

- Do not hide real vector-store failures.
- Do not suppress warnings globally without understanding impact.
- Do not require users to change Qdrant versions for unrelated offline/FTS-only workflows.

## Implementation Notes

Prefer alignment over suppression if the project controls both client and server versions.

If suppression is chosen, limit it to controlled local clients and document why it is safe.

## Verification

Run representative tests/evals and confirm:

- no sparse/vector errors are hidden;
- compatibility warning policy is applied consistently;
- degraded-mode logging still reports real retrieval component failures.

## Success Criteria

- Test/eval output is not polluted by expected compatibility warnings.
- Real Qdrant errors remain visible.
- Users have clear remediation guidance when their local Qdrant version is unsupported.

## Current Status

Policy MVP completed without changing Qdrant client behavior.

Decision:

- do not suppress Qdrant compatibility warnings globally;
- keep real vector-store failures visible in `failures` and explain-trace degraded warnings;
- treat version alignment or scoped suppression as future environment work.

Current supporting implementation:

- dense/sparse/vector failures remain visible in retrieval result `failures`;
- explain traces now emit structured degraded warnings when failures are present.
- async Pub/Dartdoc prefetch jobs skip blocking live seed discovery and reach indexing promptly; detailed seed discovery remains on the synchronous path.

Verification:

```bash
uv run pytest tests/test_retrieval_features.py tests/test_eval.py
```

Remaining future work:

- align Qdrant client/server versions in the dev/test environment, or document exact supported versions;
- if suppression is required, scope it to controlled local test/eval clients only;
- keep real vector-store failures unsuppressed.

This item is complete as a policy and trace-visibility MVP, not as an environment-version fix.

Full-suite verification completed:

```bash
uv run pytest
```

Result:

```text
643 passed, 1 skipped, 9 warnings
```

Known remaining warning:

```text
Qdrant client version 1.18.0 is incompatible with server version 1.14.1.
```

The warning remains visible intentionally until the project aligns Qdrant versions or chooses scoped suppression for controlled local test/eval clients.
