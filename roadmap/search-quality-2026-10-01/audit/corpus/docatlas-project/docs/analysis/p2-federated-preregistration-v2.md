# P2 federated Product Truth preregistration v2

Status: inventory correction only; real-model oracle and A/B comparison remain **NOT AUTHORIZED**.

## Why this follow-up exists

The independent audit remediation established that the source packs actually under qualification are:

1. `Vanilla1999/DocAtlas`
2. `Vanilla1999/hermes-agent`
3. `Vanilla1999/lov`

The older federated catalog still named `smart_glass` and carried stale historical candidates. Keeping that catalog would make a later oracle/comparison non-preregistered even if the three source repositories became individually green.

## Immutable inventory target

This change updates the federated candidate catalog to exactly eight source-local historical fixes from each of the three repositories above. It does **not** copy hidden tests, issue prompts, source paths, gold patches, artifacts, or private LoV source into DocAtlas.

For LoV the public aggregate remains restricted to:

```text
opaque task id
full historical fix SHA
bounded stage/validity state
```

## Oracle isolation requirements

A future real-model oracle is authorized only after an execution configuration separately freezes the exact model snapshot, prompts, tool set, hard budgets, and ordering, and the executor proves all of the following per attempt:

- exact broken-source snapshot;
- no `.git` or future objects;
- no `.product-truth`, benchmark manifest, hidden test, gold patch, artifact, or evaluator implementation;
- no parent-repository/Docker-socket mount;
- no network/GitHub/browser access;
- candidate production diff is evaluated in a fresh evaluator-owned worktree;
- same model/tools/hard budgets are used for oracle and later A/B comparison.

## Claim boundary

Updating this catalog proves only that the aggregate inventory matches the source packs being qualified. It does not turn pending source controls into valid tasks, does not execute a model, does not authorize a canary/pilot, does not prove Product Truth/failure, and does not change Beta maturity.

## Review gate

Before merge:

1. federated self-test must reject repository-set drift, private-source leakage, premature validity, claim inflation and manifest/report tampering;
2. exact catalog must contain 3 repositories × 8 unique full fix SHAs;
3. source pack identities must match the currently reviewed source manifests;
4. no task threshold or Product Truth gate may be weakened.
