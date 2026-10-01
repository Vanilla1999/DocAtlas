# Ablation measurement report: diagnostic slice only

## Scope and outcome

Base `55637eb4d29a0d06c01714ee647a5b486a5be725`; implementation `d60a9c0d`;
post-review code `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9`.
Branch: `experiment/retrieval-ablation-t00-t04`.

**Quality outcome: INCONCLUSIVE / NOT_EVALUATED.** This delivery implements
measurement infrastructure for T00–T04, not a completed A–E quality experiment.
There is no causal retrieval-quality contrast, no independent holdout and no
new answer-model generation. Product simplification is not justified by these
results. See STAGE_REPORT.md for actual execution status and REVIEW.md for open
blockers; both are part of this report.

## What was measured

P calls the existing real handler through `baseline_probe.run`, with its existing
lexical development-fixture configuration, real audit and DTO token estimator.
It is not renamed BM25, nor a benchmark of every default installed provider.

A calls the existing native SQLite FTS5 frontend/filter compiler with unchanged
weights, active-generation joins and native ordering within each SQL list.
AND and OR lists remain distinct. A controlled exposure schedule, rather than
incomparable cost addition, merges them. The adapter bypasses custom ranking and
expansion, checks actual project/source/version filters and source policy before
exposure, and verifies mechanical snapshot/quote integrity. A's full-index policy
scan is counted, not treated as free. It remains an internal diagnostic and never
returns a model-visible packet or support/edit authorization.

| Quantity | Observed status |
|---|---|
| Declared P/A smoke runs | 2 on one synthetic English Markdown fixture; original-only panel |
| CI smoke execution | 2 EXECUTED; final raw results downloaded and verified |
| Independent quality cases | 0 |
| Semantically evaluated packets | 0 |
| Actual answer-model generations | 0 |
| Public A packet | BLOCKED_SAFE_PACKET_ADAPTER |
| Grounded answer evaluation | ANSWER_EVALUATION_NOT_RUN |
| Raw uncapped recall / first loss | NOT_MEASURED; original SQL caps retained and saturated lanes marked incomplete |
| Resource-matched P versus A | No; no causal quality or latency contrast is claimed |
| New B/D/E/hybrid arms | Not implemented in this first slice |

The fixture asks about retry budget and contains a short explicit rule. It tests
real invocation and artifact plumbing, not generalization. Its source, question,
labels and results are not a hidden evaluation set. Existing known API cases and
historical pilots were not relabeled as new data.

## Mechanical and regression evidence

Local Python 3.13.5 / SQLite 3.46.1: **72 PASS, 2 deselected**. The deselected tests
are the two full-handler tests that require locked dependencies absent locally;
CI executed the guard step including both successfully with Python 3.12 and the
unchanged lock. The local selected set includes 49 new experiment cases plus 23
existing native SQLite product tests. It is not 72 retrieval-quality examples.

The same 23 existing native product testcase IDs passed on the initial base and
on the implemented head, in one local environment. This small paired subset does
not supersede the subsequently completed CI gate: **74 guard tests passed**, but
the full workflow failed. Focused base/head each had 482 pass / 1 fail. Full
offline base had 5,048 pass / 20 fail / 10 skip; head had 5,097 pass / 22 fail /
10 skip. The 51 added tests all passed, while two existing cases newly failed on
head. There are 5,078 common full-suite IDs and no removed IDs. Both head-only
failures remain unresolved blockers; see PAIRED_REGRESSIONS.md for exact IDs,
assertions and changes in previously failing cases.

Raw completed P smoke output has `audit_errors=[]`, 323 DTO tokens, 10 SQL
searches and 10 raw hits. A exposes two raw hits, one unique candidate and two SQL
searches, with one policy-scan row (72 display bytes); it returns no public packet.
Both have `quality_status=UNJUDGED`. These are one-case plumbing observations,
not a retrieval-quality win or a fair performance comparison. The run's original
request, source hashes, actual packets, SQL lanes and installed package inventory
are retained. CI retrieval ran on Python 3.12.14 / SQLite 3.45.1.

A real behavioral RED exposed 16 native rows against an intended total quota of
4. The SQL-boundary quota made that same assertion GREEN. Review additionally
caught and corrected manifest-symlink handling, unjustified quality/holdout flags,
unfrozen offline/vector/hash-seed settings and a missing-arm denominator. Exact
commands and local logs accompany the delivered evidence archive.

An additional local adversarial check confirmed each of six disallowed sources
was actually the unfiltered native top hit before policy filtering: foreign
project, wrong version, stale, unsafe, stale index and superseded lifecycle.
With raw exposure limited to one, the allowed local source was returned instead.
These are synthetic mechanism checks, not six independent quality successes.

## Unchanged source identities

`uv.lock`: `c0f6d716e8ec5e442dc707995c134a152bc37122bf1a9217b020f86db80447ec`.
Native FTS producer: `e504fdad421cc1cd11fe15330e08b904487f8229ffe1af472fde928199572dd5`.
Evidence policy: `76426154516c9454942b7833c73060121c146b392602b5d6882e1206fdc6f4f1`.

Product code, public MCP schema, defaults, P0/frozen-v3 artifacts and MPNet
threshold remain unchanged. No merge, activation or PR creation was performed.

## Limits that prevent a simplification conclusion

The shared public packet adapter is not implemented: mechanical source checks
do not replace reference/API ownership, combined-window validation or final
answer/edit authority. A's diagnostic text must not be given to an answerer.
OS-enforced private-gold isolation is also not implemented; request allowlists
and explicit source staging are weaker guarantees and are described as such.

There is no independent data freeze, equivalent-evidence rubric, semantic judge,
provider-pinned answer generation, non-inferiority margin evaluation, paired
quality confidence interval, remove-one-on-P result, or production cost study.
Consequently every proposed deletion/replacement of a retrieval mechanism
remains NOT_EVALUATED. DECISION.md follows this evidence rather than selecting a
winner in advance.
