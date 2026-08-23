# P2 Product Truth preregistration

Status: **protocol frozen; Product Truth not yet proven**.

Protocol identity:

```text
78521ab7dfae4f51cc55d4225054a1b38375a80be1d76d894ba74d9c851cc367
```

## Question

P2 asks whether DocAtlas improves the outcome of real coding tasks. It does
not reuse retrieval recall, deterministic oracle trajectories, or a green
MCP transport as a substitute for a correct patch.

## Valid task boundary

A task enters a comparative lane only after two positive controls:

1. the reviewed gold patch applies in two clean worktrees and passes public,
   hidden, semantic, compile, and patch-surface gates;
2. the same frozen model can solve the task with evaluator-owned oracle
   evidence under the same coding tools and hard budgets.

A failed control invalidates the model/task pair before condition comparison.
It is not counted as evidence against DocAtlas.

## Comparative design

The full preregistered design is:

```text
3 repositories
× 8–10 valid tasks
× 4 evidence conditions
× 3 repeats
× at least 2 frozen model snapshots
= 576–720 scored runs
```

The four paired conditions are repo only, repo plus installed DocAtlas, repo
plus a frozen audited external-doc snapshot, and host code context plus
installed DocAtlas. Conditions are randomized inside each task/model/repeat
block while all budgets and the starting repository identity remain equal.

The 16-run canary checks isolation, scoring, schemas, and artifact capture.
It cannot support a product claim.

## Primary outcome

`correct_patch` is true only when all six gates pass:

- patch applies;
- public tests pass;
- hidden tests pass;
- task-specific semantic assertions pass;
- only allowed paths change;
- every forbidden path remains untouched.

## Decision paths

The correctness path requires at least a 10 percentage-point paired gain for
DocAtlas over repo-only, a 95% task-cluster bootstrap interval excluding zero,
median total-token ratio at most 1.5, p95 latency ratio at most 2, and no
safety-critical regression.

The safety path allows correctness non-inferiority down to -3 percentage
points only when unsupported or wrong-version errors fall by at least 25%,
the paired interval excludes no improvement, the same cost guardrails hold,
and there is no safety-critical regression.

Condition D is decided separately. The external-doc condition is a comparator,
not a requirement that DocAtlas win every metric.

## Claim boundary

This slice changes no production retrieval behavior or public MCP schema. It
freezes methodology, schemas, hashes, budgets, metrics, and decision rules.
Product maturity remains Beta until a full valid pilot and a separate P2.3
decision exist.
