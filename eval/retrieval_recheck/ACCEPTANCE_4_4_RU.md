# Retrieval recheck acceptance through Task 4.4

Date: 2026-09-19

## Decision

The TDD cycle for the false `split/разбив -> index_chunking` routing is complete through Task 4.4.

The production treatment remains one causal change: ambiguous `split/разбив` no longer authorizes the `index_chunking` intent without an explicit chunk/section subject. Task 3 is `not_applicable` because Task 1 already fixed the native G21 endpoint on the exact frozen corpus.

No production tuning was performed after validation/holdout results were exposed.

## Frozen identities

- pre-fix baseline runtime: `7b92cc5e8a99ee7394fde93b46797c5bd0b162a8`
- candidate production runtime: `8cecc0e1355376699bd18d8eb7a720cff6868be0`
- frozen corpus/source ref: `95e61265656283d609bc1328c46c52b2bf1a069e`
- exact G21 proof: Actions run `35435030113`, artifact `10581559083`
- external80 / first sealed holdout run: `35435915709`, artifact `10581404583`
- shared-path sealed holdout replay: `35436382180`, artifact `10582685749`

## Task 4.1 — hermetic controls

Complete. The hermetic safety matrix completed successfully in Actions run `35435837777`.

Coverage includes:

- original and renamed ambiguous-split cases plus real chunking positives;
- foreign-project, stale, risk and lifecycle rejection;
- snapshot/change binding;
- exact-version isolation;
- current versus release-history authority;
- long structural units, no silent clipping, and fail-closed insufficient evidence;
- duplicate text and source-range integrity.

Exact mapping: `eval/retrieval_recheck/task41_coverage_map.json`.

## Task 4.2 — regression parity

Complete. Full-suite candidate versus pre-fix was compared by exact failed node IDs.

| Python | Baseline | Candidate | New failed node IDs |
|---|---:|---:|---:|
| 3.11 | 22 failed / 4020 passed | 22 failed / 4029 passed | 0 |
| 3.12 | 22 / 4020 | 22 / 4029 | 0 |
| 3.13 | 22 / 4020 | 22 / 4029 | 0 |

All 22 pre-existing failures are identical. Static-contract also retains the same pre-existing 1147-line module failure.

The exact-frozen focused proof additionally reported `123 passed` and retained the 800-token / 3-source public boundary.

## Task 4.3 — exposed development/regression sets

### Generic30

Complete. Only G21 changes after normalizing public path/line/snippet/status/token fields.

- root-only G21: irrelevant indexing/architecture context becomes fail-closed `insufficient_evidence`; semantic rating remains a miss;
- root + frozen project-blind lookups: G21 changes **miss -> sufficient**;
- other 29 cases: unchanged.

Aggregate:

| Lane | Baseline | Candidate |
|---|---:|---:|
| root-only | 9 sufficient / 2 partial / 19 miss | identical |
| with lookups | 20 / 3 / 7 | **21 / 3 / 6** |

Pairwise: **1 win, 0 losses, 29 unchanged**.

Details: `eval/retrieval_recheck/generic30_pair_assessment.json`.

### External80

Complete with the runner path limitation recorded explicitly.

A-current:

- within-budget sufficient: **31/48 -> 31/48**
- required supported: **35/88 -> 35/88**
- source-integrity / contract violations: **0 -> 0**
- project/family/split/answerability sufficiency slices: identical.

Static reachability: **0/80 questions contain a token beginning with `split` or `разбив`**, so the changed production branch is unreachable for this set.

The historical paired runner materialized baseline and candidate under different absolute project paths. Since project identity/source URI and serialized budget accounting include that identity, raw DTO byte differences from that run are not used for a causal claim. Acceptance is limited to **no score/safety regression observed; no external80 gain claimed**.

Details: `eval/retrieval_recheck/external80_pair_assessment.json`.

## Task 4.4 — sealed external holdout + weak reader

Complete.

Twenty new external-documentation questions, source-bound gold, runtime SHAs, reader model and prompt were frozen before execution. They cover FastAPI, HTTPX, Pydantic, Ruff, uv, Starlette, MkDocs and Typer. Retrieval is root-only with no lookup queries. Gold is not passed to retrieval or to the reader.

Reader:

- Ollama `qwen2.5:1.5b`
- temperature 0
- seed 0
- `num_predict=160`
- answer only from visible context, otherwise abstain.

A shared-path replay removes the absolute-path confound:

- exact baseline/candidate public-packet equality: **20/20**
- exact baseline/candidate reader-answer equality: **20/20**
- context wins/losses: **0 / 0**
- reader wins/losses: **0 / 0**

Manual context sufficiency:

- **17/20 sufficient**
- **2/20 partial**: H04, H07
- **1/20 miss**: H08

Weak reader:

- **12/20 correct**
- **1/20 partial**
- **7/20 incorrect**

Five cases have sufficient visible context but a wrong/unsupported reader outcome: **H01, H05, H14, H15, H16**. This demonstrates a reader/use-of-context bottleneck distinct from the fixed retrieval bug.

Holdout retrieval gaps are recorded without post-holdout tuning:

- H04: visible packet clips the `max_age` default value `600`;
- H07: complete `validation_alias` / `serialization_alias` type contract is not visible;
- H08: a requested strict alias such as `StrictInt` is not visible.

Details: `eval/retrieval_recheck/holdout20_manual_assessment.json`.

## Acceptance result

Tasks 0 through 4.4 of the reanalysis plan are closed.

The targeted fix:

1. fixes native G21 at 782/800 tokens and 3 sources;
2. preserves explicit chunking behavior;
3. preserves identity/version/freshness/risk/structural controls;
4. adds no full-suite failure on Python 3.11/3.12/3.13;
5. produces one targeted Generic30 gain and zero losses;
6. shows no aggregate/safety regression on external80;
7. is exactly neutral on all 20 sealed holdout packets and reader answers;
8. was not tuned after holdout exposure.

This is a narrow retrieval-defect acceptance, not a universal retrieval-quality claim and not a claim that the weak-reader problem is solved.
