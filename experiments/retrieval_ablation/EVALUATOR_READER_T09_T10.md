# T09/T10 bounded development evaluation

Reused existing `eval.evidence_quality_v2.semantic.assess_context` and
`answers.assess_answer`, rather than creating another evaluator. Existing
measurement/answer-control suites: **42 passed**. They cover scope/version,
opposite stance, invalid citations, incomplete answers with explicit gaps,
unrecognized extra claims and unjustified refusal. No frozen evaluator, lock,
product code or matching normalization was changed.

Applied source-grounded contract+condition witness annotations to the six
synthetic mechanism questions and actual saved B/D_L/B_HEADING_ONE packets.
Every packet passed the actual canonical projection validator first. Annotation
parts include the API declaration together with the behavior, and the separate
condition paragraph in case 5; generic matching keywords are insufficient.
The annotations were written posthoc after inspecting the development sources
and earlier results. They are not pre-registered gold for those earlier runs.

## Evidence versus answers

| Arm | Sufficient evidence | Saved supported answers | Saved refusals |
|---|---:|---:|---:|
| B | 1/6 | 1/6 | 5/6 |
| D_L | 1/6 | 1/6 | 5/6 |
| B_HEADING_ONE | 6/6 | 6/6 | 0/6 |

Evidence assessment retains one review item in each arm (unrelated gamma prose);
recognized supporting alpha evidence does not erase that review queue. B/D
case 4 is `needs_review`, not silently a known semantic negative.

Saved **18 actual answer texts authored by the current interactive assistant**
after seeing packets AND annotations, with manually supplied claim/citation
annotations. The alpha rule's negative case preserves `does not` and `even when
enabled`; missing/irrelevant B/D evidence receives an explicit gap/refusal.
The existing answer evaluator checks those annotations against only cited,
mechanically validated evidence. It is not an independent free-text semantic
judge and does not prove annotations exhaust every possible assertion.

These deliberately straightforward development reader examples exercise the
pipeline, not a blind model capability benchmark. There were no separate agent
or provider API requests, no random sampling, no usage/latency measurement and
no independent reviewer. Do not report these counts as comparative model accuracy,
hallucination rates, general citation correctness or holdout acceptance. Tests
with deliberately bad citations/stance are evaluator controls, not generated
model failures. Refusal support ratio remains N/A, never a perfect score.

Artifacts: `/tmp/opencode/ablation-evaluator-replay/{annotations,assessment,
development-answers}.json`; drivers `/tmp/opencode/ablation-evaluator-replay.py`
and `/tmp/opencode/ablation-development-reader.py`; test log
`/tmp/opencode/ablation-existing-evaluator-tests.log`.

**Completed bounded deliverable:** existing evaluator validated and applied to
saved evidence, plus separate saved development reader outputs/annotation review.
**Not completed:** T09/T10 independent multi-source question freeze, blind agent
answer generation with model/usage identity, and independent semantic/citation
review. The currently inspected corpus cannot be relabeled as independent.
No retrieval tuning or product activation is warranted by this exercise.
