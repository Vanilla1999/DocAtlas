# Patch request completion benchmark

Date: 2026-08-25

## Compared revisions

- Before: detached `HEAD` revision `ef7f958`.
- After: the current working tree implementing this completion plan.
- Corpus: the same 20 frozen cases in `cases.json` for both revisions.

## Parser results

| Metric | Before | After |
|---|---:|---:|
| Exact expected outcomes | 7/20 | 20/20 |
| Unsafe-success proxy on negative cases | 3/8 | 0/8 |
| Requested target declaration coverage | 19/24 | 24/24 |
| Parser exceptions | 1 | 0 |

An unsafe success is a negative case with an expected unresolved reason that
the parser instead accepts as a non-`none` operation without any unresolved
part. It is a conservative parser-level proxy for false edit readiness; public
authorization is separately protected by `test_patch_context_public.py`.

## Runtime comparison

The documented two-cell smoke is saved under
`eval/task_level/results/task43_smoke_run_20260825_091820/` and is explicitly
directional, exploratory, and non-causal.

| Condition | Correctness | Total latency | Packet tokens | Projection tokens |
|---|---:|---:|---:|---:|
| `repo_only_strict_offline` | public and hidden PASS | 29.797914 s | n/a | n/a |
| `docatlas_bounded_direct` | public and hidden PASS | 32.069058 s | 1962 | 1997 |

The bounded-direct cell used one retrieval call, retained mandatory evidence,
and stayed below the 2000-token packet and projection limits. The run used one
passing canary and exactly two cells. Its three provider event streams each
contain exactly one `thread.started` and one `turn.completed` event.

## Interpretation

- Exact frozen-surface correctness improved by 13 cases.
- Unsafe parser acceptance fell from three cases to zero.
- Declaration coverage reached 100 percent, including destination and parent
  declarations for rename and create operations.
- The current public contract is edit-ready only for fully resolved evidence;
  source-search recovery remains investigation-only and not edit-ready.
- Runtime numbers must not be interpreted causally because each condition has
  one exploratory observation.
