# Task 33 — Task 23 failure analysis and bounded context-delivery pivot

## Priority

P1 product decision follow-up. Complete before tasks 16–18 or any external-library parity claim.

## Problem

Task 23 completed 36 policy-clean runs but both repo-only and DocAtlas-recommended resolved 0/9 attempts. Recommended DocAtlas increased median tokens by about 143% and latency by about 37%. Evidence-marker recall did not translate into hidden-test correctness, so adding more retrieved documentation is not an acceptable response.

## Goal

Explain the failed patches requirement by requirement, then test one compact action-oriented context packet on the unchanged Task 23 fixtures.

## Required work

1. Preserve a tracked sanitized per-run bundle with every patch, normalized trajectory, scalar metric, policy result, and immutable fixture/oracle hash. Private raw provider events may remain outside Git only when the bundle is sufficient to rescore the report.
2. For every run, classify each visible requirement as found, used correctly, used incorrectly, or omitted. Hidden-only assertions must not be exposed to the agent and must be analyzed separately after scoring.
3. Separate failure causes: retrieval miss, low salience, wrong source of truth, incorrect implementation reasoning, incomplete cross-module propagation, missing verification, and task ambiguity.
4. Replace broad documentation output with one source-attributed action packet containing at most:
   - source-of-truth files and symbols;
   - required invariants;
   - forbidden edits or ownership boundaries;
   - likely target files;
   - post-edit checks.
5. Cap the packet at 2,000 estimated tokens and one pre-edit retrieval call. Return an explicit truncation/insufficient-evidence state instead of silently expanding context.
6. Measure real normalized tool-output characters/tokens and evidence coverage. Do not report useful-context ratio until chunk-level usage attribution exists, and do not alias required-evidence recall to it.
7. Freeze the rerun protocol before results. Keep the three tasks, four original lanes, three repeats, decision rule, starting fixtures, and model policy unchanged. Record any unavoidable runner-version change as a comparability limitation. Bootstrap by task cluster rather than treating task/repeat pairs as independent samples.
8. Add the bounded action-packet lane only as a separately named pivot candidate; do not replace or rewrite historical Task 23 results.

## Decision gate

The pivot may continue only if it improves resolved rate under Task 23's existing confidence rule while keeping median total-token increase at or below 10%, or preserves resolved rate while reducing median tokens by at least 25% without more than 10% latency regression. A floor-effect diagnostic may be reported separately but cannot replace the unchanged-task decision run.

## Non-goals

- Do not add more documentation sources before failure analysis.
- Do not tune fixtures, public tests, hidden tests, or oracles after inspecting lane outcomes.
- Do not resume tasks 16–18 based on retrieval metrics alone.
- Do not expose hidden tests or oracle patches to the coding agent.

## Acceptance criteria

- Every one of the 36 historical or replacement runs has independently inspectable sanitized evidence.
- Bundle generation fails closed on missing completed patches, missing valid-run trajectories, unsanitized paths or credential-like values, and records per-cell fixture/oracle hashes.
- Failure categories name the missed requirement and the evidence that was available to the agent.
- Tool-output and context-efficiency metrics have tested, non-aliased definitions.
- The compact packet is source-attributed, at most 2,000 estimated tokens, and invoked no more than once before editing.
- The frozen rerun is complete and produces `CONTINUE`, `PIVOT_REQUIRED`, or `INCONCLUSIVE` without post-result threshold changes.
- Runner and DocAtlas visibility canaries pass in the same causal invocation; missing, invalid, inconsistent, or exceeded input/output token budgets force `INCONCLUSIVE`.
- Product claims and Stage D status match the result; focused suites and `git diff --check` pass.
