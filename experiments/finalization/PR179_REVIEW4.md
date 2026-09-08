# PR #179 fourth review — canonical assignment identity

## Scope and exact baseline

Production baseline: `ede97c2c469d340ad8ec9ec0a48dc4cf4f242f6f`.
The source-export checkpoint `832ed9a5d050bdf592d6213e77d495dbe1d83b87`
only added a read-only snapshot workflow. Review, fixes and publication stay on
`fix/context-first-project-reads-finalization`. This pass reviews assignment
accounting and its visible projection consumers, with current acceptance
measurements; it is not blanket approval of the entire accumulated PR.

Published production fix: `77f71ca1656c51c4363fe57b9719f73dbd30af64`.
Locally tested, GitHub-tested and published source trees are identical:
`9a857e806978bf7157bfde06f0edfe9ae81b7fc9`.

## Findings and fixes

### P1 — Validating an assignment and then discarding its identity restores false coverage

The previous exact-span fix validated individual source/offset/hash tuples, but
`visible_assignment_hashes` returned only text hashes. Two consumers then joined
all canonical assignments back onto that lossy set:

- Component accounting used a global hash union across visible sources. A
  requirement assigned to a different source, or to an absent duplicate occurrence
  in the same source, could become covered and change `partial` to `full`.
- Fragment and final projection recovered requirement IDs by hash equality.
  Within one source this could label a public facet `covered` even when its
  assigned occurrence had been clipped away.

The reproduced case has equal witness text at an earlier and a current offset.
Only the current occurrence is delivered. Before the fix both requirements were
counted; afterward only the actual visible assignment survives. A second case
uses an entirely different source with the same witness text. This does not
require a cryptographic collision: equal text naturally has an equal hash.

`visible_assignments` now retains the verified assignment mappings, including
requirement, source and coordinates. Component accounting uses these records;
`bind_visible_assignments` supplies fragment, union and final requirement IDs
from them. Expansion also checks retention of actual assignments rather than a
set of hashes. The existing hash helper remains a diagnostic fingerprint, not
an authorization or coverage join key.

A positive control still permits two explicitly assigned requirements to share
one real occurrence. No text is stitched or rewritten, and public answer/edit
support remains false. The wire schema and retrieval/qualification thresholds
are unchanged.

### P2 — Boolean offsets pass an integer-coordinate test

`isinstance(True, int)` allowed Boolean character coordinates to satisfy a
one-character witness. Character coordinates now require exact integer types.
Malformed explicitly supplied unit coordinates do not fall back to another
coordinate pair. Valid unit-local and absolute character offsets remain tested.

### Tests and temporary infrastructure

Hash-only component fixtures now carry real source text, offsets and SHA-256
values; their coverage assertions are unchanged.

The first complete run exposed an observer test that relied on the old runtime
bug to manufacture an invalid full claim. It now explicitly injects a
source-blind claim into the stage being observed. Its original assertions that
the observer rejects foreign provenance remain unchanged. Actual production
fail-closed behavior is exercised independently by the new projection tests.
No evaluator, golden case, expected witness or protocol threshold was changed.

The already-applied review3 patch, obsolete review3 apply workflow, review4
snapshot, and review4 patch/publication infrastructure were removed in the
published source tree before the GitHub validation suite ran.

## TDD and verification

New module: `tests/docs/test_review_assignment_identity.py`, with a hash-bound
behavioral diagnostic manifest. It contains 17 parameterized scenarios.

- Unchanged production plus the new regressions: **13 failed, 4 passed**.
- Corrected new and neighboring checks, including the observer controls:
  **136 passed**.
- Preliminary complete local run: **1 failed, 4047 passed, 10 skipped**. The
  failure was the observer fixture described above; this result and its log
  are retained rather than discarded.
- Final complete local suite, after fixture repair and cleanup:
  **4048 passed, 10 skipped, 0 failures**, no deselection.
- Repeated complete GitHub Actions suite against the exact published tree:
  **4048 passed, 10 skipped, 0 failures**, no deselection.
- The 17 new regressions also pass separately with `PYTHONHASHSEED=1`.
- `compileall`, Python module-size gate and `git diff --check`: PASS.
  `docs_context_projection.py` is **983 lines**, below the 1000-line limit.
- P1.4, P1.5, P1.6, committed P1 closure and its four self-tests: PASS,
  without rewriting the evidence reports or closure.
- All tracked `eval/`, `scripts/` and project-document catalog hashes remain
  unchanged, checked both locally and in GitHub Actions.
- The frozen V2 request-flow case retains all four visible witnesses:
  MCP, application, gateway and selection, within its safety/source/token gates.

Validation/publication run:
https://github.com/Vanilla1999/DocAtlas/actions/runs/34127649044

Artifacts: `pr179-review4-validation` (JUnit, full log, gate logs, frozen-file
checks and tested tree) and `pr179-review4-published` (published revision/tree).
Publication required successful validation and exact tree equality, and used a
normal fast-forward push. This run is not a claim that every ordinary PR or
release workflow is green; the subsequent report checkpoint changes no runtime.

Local verification uses Python 3.13.5, frozen offline wheels and source imports;
GitHub validation uses Python 3.13 and `uv sync --frozen --extra dev`. No model
API, independent installed-agent harness or model download was used. A separate
foreground seed-1 boundary run hit the local command execution limit and is not
counted as a completed test run; the isolated new regressions were repeated
successfully as recorded above.

## Paired quality measurements — acceptance is still blocked

Both runs use Python 3.13, frozen dependencies, the canonical repository origin,
`PYTHONHASHSEED=0`, isolated temporary indexes and provider-free public retrieval.
They are not evaluations of an independent host model's final answer.

The per-case adjudications and aggregate metrics are unchanged before/after:

| Evaluation | Before | After |
| --- | --- | --- |
| Legacy live protocol verdict | FAIL | FAIL |
| Positive cases passing every check | 11/15 | 11/15 |
| Separately named `useful_result_count` | 12/15 | 12/15 |
| V2 natural semantic usefulness | 14/15 | 14/15 |
| V2 exposed paraphrase usefulness | 3/5 | 3/5 |
| V2 safety and budgets | 25/25 | 25/25 |
| V2 false-full | 0 | 0 |

V2 remains `REPORT_ONLY`; its exit code 0 is not release acceptance. Legacy
remains exit 1, with `ru-overview`, `ru-selection`, `ru-offline` and
`ru-server-command` failing at least one frozen check. The V2 gaps remain
`v2-natural-chunking:parents`, `v2-paraphrase-review-ready:test` and
`v2-paraphrase-search-trust:not_proof`.

The P1 closure was already refreshed before this pass. It was verified without
`--write` and still concludes `AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN`. Nothing in this
review promotes a report-only result or passing unit tests into agent/release
acceptance. PR #179 remains draft and unmerged.
