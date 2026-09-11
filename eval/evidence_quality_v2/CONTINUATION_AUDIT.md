# Continuation audit — 2026-09-11

## Identity and scope

Single PR #185, branch `fix/evidence-quality-v2-20260910`; no automatic merge.
This audit independently rechecks published artifacts and the clean tree
`c8fcd428c2d90a46caf890de4c547e88e359416e` (parent `e6772b94`).
Its only difference from that parent removes a spent publication workflow.
It does not certify a later concurrent runtime patch or an unobserved platform.

Reconstruction used the downloaded CI Git bundle and exact release source;
Git trees and commit identities were checked, not invented with a new git init.
The local Python 3.13.5 environment used MCP 1.30.0, pydantic 2.13.5 and
`tiktoken==0.11.0 / o200k_base`. All project/config/state locations were isolated
public fixtures. No developer's personal index or API credential was used.

## Immutable artifact recount: an evaluator-report defect, not a runtime gain

Artifact `10192554093`, source `5f7e70fa9d205c19d8d1e6f116b2526f7a7b0e59`:
SHA256 `23daa238070d22ac5312bbb68af0c641eaac37108e382fd6cc409cc0326437a0`.
Both primitive rows and their saved summary show **28/48**, not 29/48, for
A/B/C/explicit/duplicate/nearby; without expansion they show **18/48**, not 19/48.
The error was transcription in CHECKPOINT/FINAL_REVIEW, not an inconsistent
saved summary. These Markdown counters are corrected without changing any
query, gold witness, source document, evaluator threshold or runtime rule.

`ARTIFACT_AUDIT.json` records verification of 560 unique case/variant rows,
14 manifest-bound documents, 551 final cited source spans, every native payload
file, all actual tokenizer recounts and exact equality of summary with rows.
Verification uses the existing final source validator and same-call snapshots.
It does not derive answer support from the mere existence of a hash or path.

## Fresh executed checks on c8fcd428

All commands below exited zero, with full logs, raw outputs and driver code in
the continuation evidence bundle. "Full core" has an explicit marker scope.

| Check | Result | Boundary |
| --- | --- | --- |
| New evidence-quality tests + unchanged direct-15 regression | 87 passed | Targeted, not full suite |
| Offline core | 3660 passed, 10 skipped, 593 deselected | Excludes advanced/live/live_network |
| Existing six-scenario installed stdio lifecycle smoke | PASS including text fallback | Scripted Linux, no live host |
| Installed original-15, direct | 15/15 structured and 15/15 fallback, 48/48 facts each | 30 direct calls, unmodified questions and no host lookups |
| Installed assisted diagnostic | 11/15 in each mode | Another 30 calls; not an autonomous host claim |
| Full seven-variant matrix | 560/560 rows, 0 operational errors, 0 observed integrity/contract violations | 400 handler calls + 160 same-candidate projector replays |
| Same-path baseline/new A replay | 160/160 calls; primary 28/48 in both | Runtime origins, source, config, path and hash seed controlled |
| Grounded 3.1.0 lexical stdio | 240/240 calls; all 14 documents ingested, no non-null embeddings | Native output, not hybrid or an equal-budget comparison |
| P5 selected-source audit | 64 of 88 required records have approved source witnesses; 24 not established | No global upstream absence claim; Q05 witnesses exist |
| Host-input/oracle/order controls | 48 inputs, all four oracles sufficient, source/budget checks pass | No model answers; several order variants are degenerate |
| Root/seed/ingest/format/isolation fixture | 8 runs, 40 questions, all 3 baseline facts preserved | No new production change; not independent real-world validation |

The installed original-question driver verified the server package comes from
venv site-packages, with empty PYTHONPATH and no editable package. It selected
one actual model-visible wire channel, not a sum of structured and text output.
The extended lifecycle test uses the existing bounded read-only storage readiness
barrier, separately from its one public job-status call. No polling budget was
silently redefined or mutation guard bypassed.

## Comparative results, with unsuccessful tasks retained

The fresh 560-row run reproduces every historical sufficiency label. Identity
metadata changes token sizes, so the new sizes are not attached to the old run.
The primary denominator is 48 within-budget questions, not 80 or fact groups.

| Fresh series | Sufficient / 48 | Actual tokens p50 / p95 over all 80 |
| --- | --- | --- |
| DocAtlas A-current | 28 | 357 / 631 |
| B-no-canonical | 28 | 357 / 631 |
| C-lexical-replay | 28 | 357 / 631 |
| D-no-expansion-replay | 18 | 324 / 609 |
| L-explicit | 28 | 357 / 631 |
| L-duplicate | 28 | 357 / 631 |
| L-nearby | 28 | 341 / 636 |
| Grounded native limit 1 | 22 | 433 / 1669 |
| Grounded native limit 3 | 32 | 1219 / 3072 |
| Grounded native limit 5 | 32 | 1848 / 4684 |

A/B/C and the lookup variants show no recognized primary improvement here.
Removing source-local expansion loses ten sufficient results; that supports
retaining the existing expansion on this exposed corpus, not a universal rule.
Grounded delivers more recognized facts at larger native sizes. The simplistic
common first-whole-paragraph adapter gives 8/48 for Grounded and 28/48 for
DocAtlas. That is evidence against this adapter, NOT proof of native-system
superiority or savings at equal correctness. Earlier unbound Grounded prose is
not pooled with this separately saved replay.

Same-path old/new code keeps primary sufficiency 28/48 -> 28/48. Ten other
verdicts change insufficient -> needs_review, never to sufficient. They are
not counted as useful-answer wins. Comparative superiority is INCONCLUSIVE;
a reproduced narrow regression fix can still be useful without increasing this
particular exposed benchmark. No corpus growth or threshold tuning occurred.

Latency records include the expanded DocAtlas observer or Grounded's different
stdio stack; they are not a matched production-throughput comparison. Detailed
SQL operation counts were not instrumented. No claim equates one service call
with one SQL statement. Provider usage, cached/reasoning usage and whole-task
financial cost remain NOT_MEASURED, not zero or a chars/4 estimate.

## Documentation, live model and hidden-validation boundaries

P5 concludes NO_DOCUMENTATION_EDIT_JUSTIFIED: no source-doc patch was made.
Without a new-document treatment, a four-cell editorial old/new-doc experiment
is not applicable. Absence from our selected source inventory cannot establish
absence from every official source.

The 80-case benchmark is exposed and grouped 40/40 by project. An independent
hidden holdout and blinded adjudication have NOT_MEASURED status. Approved
witness recognition is deliberately conservative; needs_review is not success.
The oracle is never offered to native retrieval, and the host-input exercise is
not a live-model test. With no model answers, the context/answer-outcome matrix
is empty and assertion support ratio is N/A. Hybrid retrieval, autonomous model
behavior and positional sensitivity have not been measured.

## Acceptance status at this checkpoint

Local Linux checks do not override failing ordinary CI. On c8fcd428,
CI run 34585449488 and P1 stack 34585449554 are red: Windows installed lifecycle
and the frozen V2 negative-query gate block acceptance. Other core/Python,
installed-harness, static/docs/installer/macOS checks passed; downstream gates
skipped after V2 are not relabeled green.

Concurrent review carrier da4d8ffa contains a name-only hint guard and fixture
changes. Run 34586355797 passed Linux core, frozen V2 and installed lifecycle,
but Windows lifecycle still failed with git_worktree_not_clean; publication was
correctly skipped. Diagnostic 0629d1a6 is read-only. These carrier results are
not yet proof of published production fixes. Do not merge until a finished
published HEAD passes the ordinary platform/frozen gates. This report correction
must preserve concurrent runtime work and must not weaken cleanliness or safety.
