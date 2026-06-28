# Decisive Real-Project Task-Level Benchmark Report

Generated: 2026-06-28T08:20:58Z

## Executive verdict

INCONCLUSIVE

## Direct answer

Can we say DocAtlas is better than asking the agent without it?

Inconclusive, because accepted task pool is insufficient.

## Candidate pool

- total candidates mined: 12
- recommended candidates: 7
- implemented candidates in this decisive cycle: 0
- accepted candidates: 0
- rejected_too_easy in this decisive cycle: 0
- rejected_unfair in this decisive cycle: 0
- needs_redesign: 7 recommended candidates still require fixture implementation and strict-offline screening

The candidate pool is recorded in:

- `eval/task_level/results/task_selection/decisive_candidate_pool.md`
- `eval/task_level/results/task_selection/decisive_candidate_pool.json`

The pool includes generated-file, dependency-version, cross-module-contract, historical-fix, ADR-mismatch, private-local-workflow, migration/version-mismatch, and multi-doc architecture candidates. It is a useful next-step pool, but it is not benchmark evidence by itself.

## Accepted tasks

None.

Existing NBO real-project fixtures remain smoke/regression tasks, not differentiating proof-of-value tasks, because earlier strict-offline screening/pilots showed `repo_only_strict_offline` could solve them. They do not count toward the accepted decisive pool.

## Pilot

pilot not run because:

- accepted tasks: 0
- missing requirement: at least 3 accepted real-project tasks are required before the full 4-condition pilot
- no decisive candidate fixture was implemented, validated, and accepted by strict-offline screening in this cycle

## Metrics

No decisive pilot runs were executed. Therefore the following causal deltas cannot be computed for the decisive pool:

- policy-clean resolved delta
- contract-score delta
- network leakage delta
- token/time overhead
- fallback rate
- DocAtlas call/use rate

## Evidence supporting the verdict

- Baseline task-level test suite passed before this cycle: `108 passed`.
- A decisive candidate pool with 12 sanitized candidates was created.
- Recommended candidates exist, but none has yet passed the required pipeline:
  - fixture template
  - public tests
  - hidden tests
  - oracle patch
  - context.json
  - fairness review
  - validation artifact
  - strict-offline screening
- The prior implemented NBO candidates were already rejected as too easy and retained only as smoke/regression fixtures.

## Evidence weakening any stronger claim

- Accepted task count is 0, below the required minimum of 3.
- No full 4-condition decisive pilot was run.
- No decisive run-level metrics exist for DocAtlas retrieval/use, fallback dominance, or contract-score improvement.
- Candidate-pool creation alone cannot establish that DocAtlas improves patch quality.

## Claims

Can claim:

- A sanitized decisive candidate pool has been prepared for the next benchmark iteration.
- The current evidence does not support a positive DocAtlas-over-repo-only claim.
- The correct current benchmark verdict is `INCONCLUSIVE`.

Cannot claim:

- DocAtlas improves coding agents on real patches.
- DocAtlas beats `repo_only_strict_offline`.
- DocAtlas beats Context7.
- DocAtlas vector retrieval is robust for this benchmark.
- The decisive real-project benchmark has completed a causal pilot.
