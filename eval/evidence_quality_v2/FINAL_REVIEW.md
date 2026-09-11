# P2–P6 provider-free implementation review

This review supersedes the **outstanding installed lifecycle matrix** note in
CHECKPOINT.md. That file intentionally retains the measured product-head results
and historical artifact identities. The current PR check runs, not a copied old
SHA's green badge, are the acceptance evidence for the latest branch HEAD.

PR #185 remains the single review surface. Do not merge automatically.

## What is implemented and exercised

- P2: 80 frozen real-document tasks from eight projects; 40/40 project-group
  split, 48 within-budget plus eight each partial/unanswerable/ambiguous/
  over-budget. It is exposed, not an independent hidden holdout.
- P3: executable one-factor matrix, exact same-call replay, native/controlled
  Grounded comparison and actual tokenizer accounting. Keep unknown semantic
  alternatives in review; do not credit them as successful answers.
- P4: safe hint-context preservation and exact-original deduplication, plus
  the explicit permission-condition ranking fix. Original-15 is unchanged and
  passes on the published product tree. Root/seed/isolation characterization
  required no additional runtime patch.
- P5: executed source-gap audit; approved Q05 witnesses already exist. No
  documentation edit is justified. Absence from the selected source set is not
  asserted as absence from every upstream document.
- P6: source-bound oracle/order inputs, provider-usage and claim/citation
  evaluators, existing installed agent harness and extended installed lifecycle
  smoke. No new host harness, public tool, runtime mode or permission bypass.

## Closing the installed lifecycle coverage gap

Commit `943e1029c1c1ab38c1b863a1a10bc11e0c6a8ad3` extends the existing
`scripts/docs_mcp_stdio_smoke.py`, already run by ordinary CI and wheel/platform
release checks. It does not change product code or the installed agent report's
privacy allowlist.

The same real installed stdio server now exercises:

1. Ready source-backed context and stopping without another discovery call.
2. Explicit clean-Git status inspection returning a concrete guarded prepare
   action, followed by permitted local synchronization.
3. Worktree drift invalidating that guard before an index write; fresh dirty
   status requires confirmation and the index remains empty. The fixture author
   explicitly commits the new snapshot before a new allowed action is requested.
4. Successful preparation followed by one unchanged original question retry.
5. A real asynchronous job returned by explicit local manifest prefetch and one
   public job-status call. The invalid manifest fails before any source fetch.
6. Terminal failure with retryable=false and zero fetched pages, followed by no
   further retry, cancel or polling request.

The job fixture has a bounded **read-only storage readiness barrier**, reported
separately from the single MCP status request. It is test setup, not a hidden
host operation, new agent poll budget or production latency measurement. The
barrier avoids a fixed-sleep scheduler race and never changes job state. Its
SQLite path must remain inside the temporary fixture root.

Local execution against the verified published wheel passed three consecutive
complete stdio smoke runs, including text fallback. Reviewed release request
self-tests passed 4/4. Latest-head Linux/macOS/Windows and Python matrix outcomes
must be read from the ordinary PR checks; local Linux alone does not prove them.

This is scripted protocol coverage, not evidence that a live model independently
chooses these actions. The clean preparation action comes from an **explicit
status/lifecycle request**; this test does not falsely assert that every initial
unindexed free-form question already returns that action.

## Latest published acceptance candidate

Product/fixture fixes were published at
`0d703f2d0e95a2fae351d50de081e7d3d37c4693` (`fix: isolate Git stdin and close
fixture handles while preserving context guards`). The previous guarded Linux
review had already passed offline core, frozen V2 and installed lifecycle; the
remaining blocker was Windows reporting the lifecycle fixture as dirty. The
0d703 fix is the current candidate for that blocker and keeps the context guards.

The pull-request workflows created automatically for 0d703 finished immediately
with GitHub's `action_required` conclusion and no jobs, so they are not counted as
passing or failing product evidence. This report-only commit exists to request a
fresh ordinary PR validation from a user-authored branch update without changing
questions, thresholds, runtime policy, source documents or token budgets.

## What the evidence does not establish

The exact published product validation at `5f7e70fa` includes 3660 passing offline
core tests, 10 skips and 593 marker exclusions; the 560-row matrix; P5 audit;
48 host-input controls; 8 robustness runs/40 questions; and the separate verified
installed scripted task. The runtime tree matches the locally checked tree on
which all 593 advanced tests also passed. These scopes stay separate until the
latest-head CI independently reruns them.

The audited 2026-09-11 same-path old/new comparison keeps primary recognized
sufficiency at 28/48. The earlier 29/48 transcription is corrected, not credited
as a runtime change. See ARTIFACT_AUDIT.json and CONTINUATION_AUDIT.md.
Ten non-success results move insufficient to needs_review; this is not credited
as a gain. The 2026-09-11 Grounded native replay is 22/32/32 at limits 1/3/5 with
substantially larger payloads. A poor common adapter is not evidence against
native Grounded. No equal-correctness end-to-end token saving is established.

The independent hidden holdout, blind human adjudication, live host repetitions,
provider-reported whole-task cost, hybrid comparison and actual answer/order
sensitivity are **NOT_MEASURED**. No real model answers means the answer outcome
matrix is empty and support ratio is N/A, not 100%. These are evidence limits,
not missing public runtime features to be filled with fabricated results.

There is no release, automatic merge, evaluation-data ingestion, source-doc
rewrite, public budget increase or certification/permission relaxation in this
cycle. Full raw public-fixture traces remain separate from the production index.
