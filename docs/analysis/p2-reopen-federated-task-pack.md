# P2 reopening — federated 24-task candidate pack

Status: **candidate catalog frozen; source-repository controls pending**.

## Why P2 is being reopened

The closed P2 decision is still correct: the repository-local task inventory had
zero valid Product Truth tasks, so no comparative run was authorized. This slice
does not rewrite that result. It creates the missing cross-repository eligibility
path using the three repositories selected by the maintainer:

```text
Vanilla1999/DocAtlas
Vanilla1999/lov
Vanilla1999/smart_glass
```

The target remains the preregistered minimum:

```text
3 repositories × 8 valid tasks = 24 valid tasks
```

## Candidate construction

Each task starts from a real single-parent historical fix candidate:

```text
broken base = first parent of fix commit
gold patch = exact first-parent diff
```

A source-repository worker must still prove all of the following before the task
can become valid:

1. the fix commit and first parent are reachable and single-parent;
2. the regression test, when projected onto the parent, fails for the intended
   reason rather than an unrelated setup failure;
3. the exact gold patch passes public tests, hidden tests, semantic assertions
   and the allowed-path boundary in two independent clean worktrees;
4. hidden tests, gold patch and oracle evidence are not model-visible;
5. a real coding model solves the task from the minimal oracle-evidence packet
   using the same model snapshot, tools and hard budgets as the later comparison.

Until then all 24 rows remain candidates, not valid benchmark tasks.

## Federated privacy boundary

`Vanilla1999/lov` is private. Copying its source, prompts, tests, patches or file
paths into the public DocAtlas repository would turn the benchmark into a source
leak. Therefore task execution remains inside each source repository.

The public DocAtlas aggregate may retain only:

```text
opaque task ID
full commit SHA
content/report hashes
bounded status
aggregate counts
```

For the private repository, the candidate catalog deliberately contains no
source paths, task descriptions, prompts, test names or patch text. A later
source-repository attestation must be hash-bound and equally bounded.

## Frozen initial catalog

The catalog contains exactly eight opaque historical-fix candidates from each
repository. Selection is intentionally conservative: a large multi-purpose fix
may still be rejected by the source worker even though it appears in this first
catalog. Rejected candidates must be replaced through a reviewed manifest change;
thresholds or task validity must not be weakened to preserve cardinality.

## Current decision

```text
candidate tasks             24
worker attestations          0
clean gold controls          0
real-model oracle controls   0
valid tasks                  0
canary authorized            false
full pilot authorized        false
Product Truth                not proven
Product failure              not proven
maturity                     Beta
```

The next review boundaries are one source-local historical-task worker in each
repository, followed by a public aggregate attestation MR. Only a complete
24-task valid pack may reopen the 16-run canary.
