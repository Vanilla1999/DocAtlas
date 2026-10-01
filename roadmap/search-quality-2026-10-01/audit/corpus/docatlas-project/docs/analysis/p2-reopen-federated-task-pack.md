# P2 reopening — corrected federated 24-task candidate pack

Status: **v2 candidate inventory frozen; source attestations and model execution config pending**.

## Why P2 is being reopened

The previous Product Truth decision remains valid: the comparative experiment was not authorized because there were no 24 valid same-model-oracle-qualified tasks. This reopening does not rewrite that result and does not claim Product Truth.

The independently reviewed source packs now under qualification are exactly:

```text
Vanilla1999/DocAtlas
Vanilla1999/hermes-agent
Vanilla1999/lov
```

The earlier candidate catalog named `smart_glass`. That catalog is superseded for this experiment because it no longer matches the source repositories actually being audited. The target remains:

```text
3 repositories × 8 valid tasks = 24 valid tasks
```

## Candidate construction

Every candidate is bound to a real single-parent historical fix:

```text
broken base = first parent of fix commit
gold = exact historical production-only diff
       or an explicitly reviewed historical production projection
```

A task cannot become valid until its source repository proves all of the following:

1. historical fix/test provenance is authentic and hash-bound;
2. public test passes on the broken base;
3. evaluator-owned historical regression produces a real pytest test failure, not collection/setup/internal/no-test failure;
4. historical production gold applies with exact allowed surface;
5. public and hidden tests pass after gold;
6. the complete sequence succeeds in two independent clean worktrees;
7. report verification independently recomputes stage and provenance evidence;
8. a real coding model later passes the task under the same frozen model/tools/hard budgets used in the A/B experiment.

## Model/evaluator isolation

The model must receive only the exact broken source snapshot and explicitly allowed public material. The model workspace may not contain or reach:

```text
.git or future Git objects
.product-truth / benchmark manifests
evaluator-owned hidden tests
gold patches
artifacts / reports
evaluator implementation
parent repository mount
Docker socket
network / GitHub / browser access
```

The candidate production diff produced by the model must be transferred to a fresh evaluator-owned worktree before public/hidden scoring. The model execution configuration (exact model snapshot, prompts, tools, hard budgets and ordering) must be frozen in a reviewed artifact before any oracle run.

## Privacy boundary

`Vanilla1999/lov` remains private. The public DocAtlas aggregate may retain only:

```text
opaque task ID
full historical fix SHA
content/report hashes
bounded status
aggregate counts
```

LoV source paths, prompts, tests, patches and artifacts remain source-local.

## Frozen v2 inventory

`eval/product_truth_v2/federated-task-pack.json` is the authoritative candidate inventory for this reopening. It contains exactly the eight currently reviewed source-pack fixes from each of DocAtlas, hermes-agent and LoV.

Source gold evidence is not silently promoted into the public aggregate. `worker_attestation` and every task validity flag remain pending/false until a separate reviewed attestation update binds the source reports into the aggregate.

## Current decision

```text
candidate tasks                       24
aggregate source attestations          0
aggregate valid tasks                  0 / 24
model execution config frozen          false
real-model oracle authorized           false
canary authorized                      false
full pilot authorized                  false
Product Truth                          not proven
Product failure                        not proven
maturity                               Beta
```

The next boundary is to complete/merge the three source-repository qualification changes, import bounded hash-bound source attestations, freeze the exact model execution configuration, and only then consider the same-model oracle gate.
