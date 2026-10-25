# Evidence selection comparison: development record

## First frozen comparison

Tested head: `f4a885a49494bedb65154af48403a378b1b8d208`.
Actual CI run: https://github.com/Vanilla1999/DocAtlas/actions/runs/40219786995
Comparison artifact: `12608963590` (SHA-256 `5f571113e0a41f5b7ac07dace40e257fdb218013ae2e187949bc512503dd7eb6`).

64 original questions, 53 with documented requested facts and 11 strict negative
cases. All three suites are known regressions. One search per question; source
pools matched across all policies. No source-integrity/runtime failures.

| Policy | Complete documented questions | Required witness groups retained | Actual model-context tokens |
|---|---:|---:|---:|
| fixed5 | 50/53 | 90/97 | 112334 |
| B1 | 49/53 | 92/97 | 110369 |
| lexical MMR | 49/53 | 93/97 | 110239 |
| literal facet cover | 48/53 | 91/97 | 40096 |
| literal guarded facets | 52/53 | 95/97 | 113911 |

Only guarded facets passed the no-lost-fact gate against BOTH controls. It
recovered N01 revocation, N03 publication and all six N05 procedure facts, but
N04 still lacked snapshot contents and export creation/access conditions.
These sources WERE in the admitted candidate pool (ranks 6 and 9).

N04 exposed a generic weakness of the literal probes: splitting a question
produces fragments such as `which data it includes` without the subject `export`.
All numerical thresholds and known sources stay unchanged in the refinement.
The next candidates retain the first sentence/question as context for each
literal view. A separate structural candidate treats all already-acquired text
from one short native source (at most 512 scorer tokens) as one indivisible unit.
No unacquired source text is added. Long sources keep their existing sections.
These are development candidates, not yet accepted results.

The first comparison's controls are reused, not re-executed. Their exact source
revision, unchanged upstream/scorer bytes, corpus/gold bytes and candidate-pool
fingerprints are checked in the refinement workflow. New variants remain opt-in;
no default promotion or main merge occurs.

Strict empty-evidence negatives: 0/11 for every policy. This is not a measured
hallucination rate: final strong-model answers were not generated. Context-token
costs exclude private metadata and are NOT provider billing. Guarded v1 costs
1.40% more context tokens than fixed5 and 3.21% more than B1. The first result is
an accuracy improvement, not an overall token-economy success.
