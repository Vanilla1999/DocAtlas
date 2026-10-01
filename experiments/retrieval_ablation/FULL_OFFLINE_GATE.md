# Full offline regression gate — 2026-10-01

## Completed paired baseline follow-up

Latest full run after saved-pool and HTML provenance implementation:
**5771 passed, 28 failed, 10 skipped**, 270.58 seconds. Same 28 shared failures,
zero candidate-only failure node IDs versus unchanged HEAD worktree. Log:
`/tmp/opencode/ablation-t06-full-offline-tests.log`; comparison:
`/tmp/opencode/ablation-t06-full-gate-comparison.json`. This run predates the
subsequent P ratio-phase instrumentation; focused tests cover that follow-up.

Archive baseline was unsuitable for the final comparison: absence of `.git`
introduced unrelated failures. Repeated baseline from a real detached git
worktree at unchanged HEAD `39347d29`, with the identical full command:

| Checkout | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Unchanged HEAD worktree | 5750 | 29 | 10 |
| Candidate | 5764 | 28 | 10 |

**28 shared failure node IDs, zero candidate-only failures.** The one baseline-only
failure is `test_d_l_reuses_b_candidate_pool_and_search_count`, repaired by using
the same fixture root. The candidate also has added/renamed tests; count differences
are not a count of fixed product bugs. Existing witness/namespace/projection
failures remain real acceptance blockers. This is not a green full gate.

Baseline: `/tmp/opencode/docatlas-ablation-head-worktree/`; log:
`/tmp/opencode/ablation-head-worktree-tests.log`; comparison:
`/tmp/opencode/ablation-worktree-gate-comparison.json`. No baseline commits or
product files changed. Historical pending notes below describe the first run.

Candidate command: `DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0`
with existing Python environment, `python -m pytest -q`.

Result: **5764 passed, 28 failed, 10 skipped**, 274.31 seconds. Log:
`/tmp/opencode/ablation-full-offline-tests.log`. This is a FAILED gate, not final
acceptance. No failing assertions or frozen witness hashes were weakened.

Eight failures concern unavailable OS namespaces (`uid_map: Operation not
permitted`). Others include source witness revision locks, query planning,
projection and real-service expectations. Their baseline attribution is pending;
do not call them environment-only or regressions without comparison.

An unchanged local HEAD archive (`39347d29`) was extracted to
`/tmp/opencode/docatlas-ablation-head-baseline/` and the identical full command
launched with the same environment. Baseline log:
`/tmp/opencode/ablation-head-baseline-tests.log`. This preserves all uncommitted
work and does not change the working branch. Baseline comparison is pending.
Separate source roots may affect project identity or path-sensitive tests; paired
failure inventory alone does not establish equal product quality or performance.

Direct immutable witness comparison already confirms two mismatches in BOTH
candidate and unchanged HEAD: `README.md` and `docs/project-docs-mcp-workflow.md`.
Expected lock hashes and actual file hashes are identical between checkouts.
Thus this particular witness-lock precondition failure predates the current
uncommitted implementation. Raw comparison:
`/tmp/opencode/ablation-witness-lock-comparison.json`. Locks remain untouched.

The candidate suite was launched before the final additional hook safety
assertions were added; those assertions passed separately (9 structure tests).
No product source changes occurred during the full run.
