# P2 Product Truth benchmark audit remediation v2

Status: implementation in progress; real-model oracle remains NOT AUTHORIZED.

## Scope

This remediation follows the independent benchmark audit and does not change benchmark thresholds, Product Truth claims, product maturity, or the requirement for two independent clean gold attempts.

The benchmark foundation spans three source repositories, so GitHub requires one physical pull request per repository. They form one logical remediation set:

- `Vanilla1999/DocAtlas`
- `Vanilla1999/lov`
- `Vanilla1999/hermes-agent`

No real-model oracle, release, publish, production deployment, live game/account mutation, Flutter build, or Gradle build is authorized by this plan.

## Invariants

A gold attempt is valid only when all six predicates hold:

1. public test on broken base returns `0`;
2. evaluator-owned historical hidden test on broken base returns exactly pytest code `1`;
3. historical production-only gold patch applies;
4. changed production paths equal the expected historical production surface;
5. public test after gold returns `0`;
6. hidden test after gold returns `0`.

Pytest codes `2`, `3`, `4`, and `5` are setup/infrastructure/collection outcomes and must never be accepted as defect RED.

A report verifier must recompute the attempt result from stage evidence and fail closed when any claim, summary, oracle flag, provenance field, or Product Truth boundary is inconsistent.

## Workstream A — DocAtlas

1. Harden `.product-truth/real_task_pack.py` to require hidden-base code `1`.
2. Recompute every attempt from stage evidence instead of trusting `attempt["passed"]`.
3. Validate both oracle flags and all claim-boundary fields.
4. Bind reports to the authoritative manifest and Git provenance: repository, frozen head, task identity, first parent, production surface, hidden-test digest, gold-patch digest and manifest digest.
5. Add report-tampering regression tests.
6. Add a hermetic model-workspace materializer/validator that creates the exact broken source snapshot without `.git`, `.product-truth`, hidden tests, gold/report artifacts, future objects, parent-repository mounts or evaluator implementation.
7. Keep evaluator full-history checkout separate from the model workspace.

Proof gate: existing eight tasks still produce 16/16 clean valid attempts and every required semantic/provenance mutation is rejected.

## Workstream B — LoV

Python emulator/pytest only. Flutter and Gradle are explicitly out of scope.

1. Harden changed-path accounting to include tracked changes, deletions, renames and untracked production files.
2. Add authoritative report verification equivalent to the DocAtlas/Hermes strict contract.
3. Repair or replace `lov-real-004` without weakening thresholds. The replacement/projection must have a public node that exists on the broken base and two clean attempts with `0 -> 1 -> gold -> 0/0`.
4. Strengthen `lov-real-005` with historical behavioral evidence so a registry-only `code=stat` implementation cannot pass without the bounded growth policy/routine/postcondition behavior.
5. Preserve diagnostic output as non-authoritative and preserve the real runner exit status.
6. Re-run all eight tasks locally and obtain a GitHub-hosted run with actual executed steps before qualification.

Proof gate: 8/8 tasks, 16/16 clean attempts, hidden-base code `1` in every attempt, exact surface in every attempt, and registry-only STAT_GROWTH mutant rejected.

## Workstream C — Hermes

1. Extend the existing strict semantic verifier with provenance binding to the authoritative manifest/history.
2. Make explicit non-local terminal configuration fail closed when config bridging cannot be established; never silently fall back to host-local execution.
3. Bind persisted Docker reuse to a normalized security fingerprint covering at least image, network posture, mounts, relevant environment/proxy posture, DNS/extra args, profile/task identity and egress label. A mismatch must reject/remove the stale container.
4. Pin benchmark execution to `persist_across_processes=false` and `network=false` until the reuse contract is proven.
5. Narrow any whole-file hidden task selector to the historical regression node when such a stable node exists.

Proof gate: the previous 16/16 gold sequence remains valid, forged provenance is rejected, explicit Docker-config failure cannot execute a host sentinel, and stale-container security-fingerprint mismatches cannot be reused.

## Workstream D — oracle isolation

The evaluator owns history and hidden evidence. The coding model receives only:

```text
exact broken source snapshot
+ explicitly allowed public tests/config
+ issue text
```

The model workspace must not contain or reach:

```text
.git
.product-truth
hidden tests
benchmark manifests
gold patches
artifacts/reports
fix SHA / future commit objects
branches/tags/reflogs/alternates/worktree metadata
evaluator implementation
parent repository mount
Docker socket
network/GitHub/browser access
```

After a model run, only the candidate production diff is transferred into a fresh evaluator worktree. Public tests, hidden tests, evaluator configuration and scoring files are restored from evaluator-owned pristine sources before scoring.

## Required evidence before real-model oracle

- all three remediation PR heads reviewed independently;
- exact-head CI green for repository-owned checks;
- DocAtlas: 8 tasks / 16 valid clean attempts;
- Hermes: 8 tasks / 16 valid clean attempts;
- LoV: 8 tasks / 16 valid clean attempts, including an actual GitHub-hosted execution;
- no accepted semantic mutation;
- no accepted provenance mutation;
- hermetic model-snapshot attestation passes;
- no pytest `2/3/4/5` accepted as hidden RED;
- Product Truth remains unproven and maturity remains Beta until the separately preregistered real-model experiment succeeds.
