# Completed paired regression review

> Historical initial-slice report. Subsequent local implementation, exact measured
> revisions and still-open limits are recorded in [CONTINUATION_REPORT.md](CONTINUATION_REPORT.md).
> The original observations below are preserved, not relabeled as new execution.

Code `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9` versus base
`55637eb4d29a0d06c01714ee647a5b486a5be725`, CI run 36781801281.
Final workflow conclusion: **FAILURE — not merge-ready**.
Same locked environment, separate full worktrees, ordinary conftest and diagnostic
inventory. No test registration was bypassed. Full raw JUnit and the comparison
are included in the delivery evidence archive.

| Suite | Base | Head | Common IDs / added IDs |
|---|---|---|---|
| Focused product | 482 pass, 1 fail | 482 pass, 1 fail | 483 / 0 |
| Full offline | 5,048 pass, 20 fail, 10 skip | 5,097 pass, 22 fail, 10 skip | 5,078 / 51 |

The 51 added experiment tests all passed. Each full invocation deselected 622
advanced/live cases. There are no removed testcase IDs and no fixes of existing
failures in this pair. This comparison is of test execution, not QA quality.

## P1: two existing cases passed on base and failed on head

1. `tests/docs/test_context_completion_followup.py:70`,
   `test_priority_rule_available_in_first_packet_or_one_registered_read`.
   The first packet lacked the requested fact, and `read_next` was empty when
   the test required one registered read (`assert 0 == 1`).
2. `tests/docs/test_contiguous_seed_envelope.py:98`,
   `test_old_inspection_uri_survives_replacement_of_unissued_draft_locators`.
   The second request returned an empty `read_next` (`assert []`), so the test
   never reached its remaining old-resource validation assertions.

Both use the existing mkdocs-05 fixture. Do not call the second result a proven
broken old URI: its earlier assertion failed first. Do not treat these failures
as mere quality-score noise or claim that new guards make them irrelevant.

**Cause is unestablished.** No product source file changed, but collection-time
imports, process state, paths and non-deterministic identifiers can still affect
a suite. This run is evidence of two newly observed failures, not a causal proof
that the adapter caused them, nor proof that they are pre-existing flakes.
No assertion was weakened, skipped or marked xfail to clear this gate.

A next focused investigation should repeat these exact IDs on base/head in
isolated processes with controlled fixture paths and recorded raw DTOs; compare
collection side effects separately. That investigation was not executed in this
delivery. Until resolved, both remain blockers.

## Previously failing cases: keep reason differences visible

All 20 base full-suite failures also failed on head. Seventeen have identical
messages after only checkout/temp-root normalization. Of the remaining three:

- `test_frozen_request_flow_prefers_project_context_module_witnesses` has the
  same displayed assertion and evidence IDs; only a generator memory address
  differs. This is also the one focused-suite failure on both revisions.
- `test_request_flow_public_contract_remains_four_fact_fail_safe` changes from
  missing `flow_mcp` to missing both `flow_mcp` and `flow_gateway`.
- `test_project_query_does_not_return_non_project_docs_with_same_terms` displays
  different source hashes/evidence IDs. Its test ID was already failing, but the
  changed evidence content is not normalized away or asserted equivalent.

The raw comparator conservatively records three changed messages, including the
memory-address-only case; this manual distinction does not rewrite the raw data.
All 20 old failure IDs/messages, plus both new failures, remain in
`paired-comparison.json`. Full gate remains red even if an old failure is known.
