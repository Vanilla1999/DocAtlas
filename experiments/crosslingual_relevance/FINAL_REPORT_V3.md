# Task 44 — reranker experiment (not accepted)

The product remains lexical by default. RU/mixed M0 tests remain RED without
the experimental monkeypatch. No production activation or v3 protocol change.

## Measured pilot

- MPNet dense candidate retrieval + BGE-v2-m3 threshold rescue with K=256,
  deadline=300s and threshold=0.01: Typer 3/3; M1.5 dev 3/4.
- The threshold **was selected after seeing Typer results** and must not be
  used as independent acceptance evidence. M1.5 calibration scores overlap:
  minimum positive 0.0031, maximum negative 0.6242; cal+dev zero-FPR
  threshold ~0.9917 retains only 4/12 positives. No transfer established.
- The eight original pilot tests did not implement all ten Step 6 cases:
  wrong-project merely indexed HTTPX instead of planting a Typer foreign
  candidate; stale/version/unsafe, HTTPX inversions, negation and exact
  `" /-S"` vs `"/-S"` were not covered. Model-dependent tests skip without
  explicit local model configuration.
- `scorer_model_verified` previously reported true after merely reading a
  manifest. The adapter now checks manifest fingerprint and local file hashes
  before asserting identity. Scoring errors degrade BoundedScorer; an identity
  error rejects rescue with `context_relevance_degraded` in the trace.
- The reranker uses a separate experimental resource profile (K=256, 300s);
  success cannot be attributed to the original K=60, 10s pilot profile.
- Scoring now uses a stable sigmoid for finite large negative logits (no false
  execution failure from `exp(1000)`); session and tokenizer publish together
  after both load successfully. The authority test asserts an actual rescue
  decision before checking `answer_supported` / `edit_ready`.

## Still required for acceptance

1. Independent rescue-path calibration plus an untouched holdout; do not reuse
   the viewed Typer or M1.5 holdout as new calibration evidence.
2. Complete Step 6 RED→GREEN safety tests, including actual cross-project and
   stale/version/unsafe vetoes, short evidence, negation and exact literals.
3. Resolve m15-dev-01 packet chunking; execute independent M6 and
   weak-model/oracle controls with frozen parameters.
4. Full regression baseline/candidate comparison under identical dependencies,
   followed by separate maintainer decision on P0 freeze.

No push, PR, merge or production activation was performed.

## M6 diagnostic replay (inspected M1.5 tasks, not independent holdout)

`m6_holdout.py` previously ran dense requests while the lexical service's
process-global environment was active; the handler returned
`HybridRetrievalError`, which was then misreported as invalid projection.
The services now run sequentially and handler failures are reported separately.
A replay of the 16 conditions returned `status=ok` and no source-policy errors.
Dense baseline and dense rescue each delivered complete first packets for 3/4
tasks; lexical baseline and lexical rescue each delivered 4/4. Rescue evaluation
degraded on 6/8 rows under the original 10-second bound. These reviewed tasks
provide **no evidence of independent improvement**; no weak-model responses
were evaluated. Local output: `/tmp/opencode/task44-m6-replay.json`.
