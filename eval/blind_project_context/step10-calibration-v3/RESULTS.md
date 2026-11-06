# V3 closure-aware calibration: runtime results

## Frozen policy and contract

New schema2 calibration recipe `final-closure-all-useful-breakpoints-v3` changes
only threshold fitting: retain all independently labeled useful source bodies
and facts **after** unchanged structural closure, rather than demand every useful
body pass the ranker directly. Raw retention remains a metric. Source validity,
scope, full text, conditions, no-answer and emergency50000 are unchanged.
V1/V2 labels, recipes, gates and negative results are preserved. Default is off.
Scorer remains exhaustive V2 min(contextual MaxP, own-body MaxP).

- Input manifest: `00fc5fbe8df385ba5c14a4643e0841a37d16c00de934b2b9bb9b907df3495a14`.
- Threshold: **−3.352724552154541**, an actually observed calibration score.
- Policy SHA256: `5683d27c6ca11ed0181768c4a3d0f7f9f7f60d34f29c82260c70ff55ea746391`.
- Installed wheel: `9b95d2878c682815240221b0c03e2320b60d2e082a5880d67c458c0cfd806f11`.
- Exact 450 product files matched wheel/checkout/installed environment.

Detailed typed-closure monotonicity proof and leakage review: `DESIGN.md`.
This is implementing-agent review, not independent-agent signoff.

## Calibration feasibility and fresh validation

Eight old V2 calibration queries are explicitly reused development data.
New optics/seed-archive validation documents, eight queries and labels were
frozen before V3 inference. Existing V2 validation and T01 were excluded.

| Final public result | Calibration | Fresh validation |
|---|---:|---:|
| Required facts | 20/20 | 27/27 |
| Useful complete own bodies | 16/16 | 19/19 |
| Useful bodies missing direct admission | 5 | 10 |
| Empty no-answer | 2/2 | 2/2 |
| Delivered independently negative bodies | 7 | 10 |
| Total delivered rows | 23 | 29 |

Public source checks, canonical source-material hashes, source-file immutability
and logical database read-only checks passed. All model scores are finite and
match exhaustive independently inventoried source units through the V2 audit.
These small authored validation results are **local PASS**, not product-wide
acceptance or proof of corpus-wide relevance/foreign-scope denial.

The largest retention-feasible breakpoint is constrained by `C2-subtree`.
The next global observed score, −1.7263767719268799, loses five useful bodies
and five required facts there. Both no-answer tasks are empty at the chosen
breakpoint. Actual closure sets decrease monotonically across all local sweeps.
Thus this dataset admits a usable threshold without changing fact/output labels.

Runtime: **6 public preparations, 24 public queries, 16 scorer executions,
8 exact-input scorer memo hits, 238 model pairs, 200 forwards, 52 closure replays**.
Threshold exploration never repeats model inference. The eight final calibration
queries replay exact score results; validation uses fresh real model execution.
Real public delivery—not the offline closure calculation—determines local PASS.

Evaluator correction: initial global sweep union also contained each query's
empty-interval representative. Offline recomputation using only actual global
score breakpoints plus one global empty representative (45 total) selects the
identical tau and next-higher failure. `measurement/breakpoint-audit.json`
preserves this correction; no labels/policy/inference were changed or repeated.

## Installed original T01: negative transfer result

One exact original Russian L0/T01 request, no translation or source focus:
**0/3 required facts**, 34/157 seeds, 72 delivered rows, 26351 wire tokens,
35.003s. Source span/hash and raw source/DB read-only checks pass. Two historical
unresolved links remain explicit. This fails the original-only user output
contract despite local synthetic validation PASS; it is not a savings success.

Policy remained frozen. A separate original-plus-frozen-translation stdio probe
of the documented bilingual route also delivered **0/3 facts**, 34/157 seeds,
72 rows, 26354 wire tokens, 63.628s, 1780 model pairs. The original-only call
used 900 pairs. Neither packet contains any CONTRIBUTING.md row. Both packets
instead include 22 wiki/Architecture rows, 17 README rows and 33 rows from eight
other documents. Exact source text/hash and read-only checks pass on both calls.
This is a concrete **transfer FAIL**, not merely insufficient minimization or a
missing translation. Both original questions were exact; no quote normalization.

**No new Terra session was launched** because the installed original-task gate
failed on both lanes. No new answering-provider usage exists; wire tokens above
are not answer-model tokens or savings. The prior measured 61419 versus file5247
all-step comparison remains the last actual Terra evidence.

The diagnosis supported by these receipts is that raising the globally calibrated
threshold improves direct selectivity but does not generalize useful-evidence
retention to this held-out project question: no relevant seed/dependency reaches
the entire required contribution document. The receipts do not expose individual
installed raw scores, so no claim is made about a particular body score or the
amount tau would need to change. T01 cannot now become threshold-tuning data.
Next research would require a separately frozen, more representative relevance
calibration family or a justified different scorer, with independent validation;
the present small synthetic family does not support deployment. No alternative
scorer, larger training run or mass synthetic expansion was launched speculatively.

## Commands and artifacts

```sh
PYTHONPATH=. /tmp/opencode/step10-final-py313/bin/python eval/blind_project_context/step10-calibration-v3/runner.py run --work-dir /tmp/opencode/step10-calibration-v3-run-01
uv build --wheel --out-dir /tmp/opencode/step10-wheel-v3
/tmp/opencode/step10-v3-py313/bin/python eval/blind_project_context/probe_minimal_delivery.py --prepared /tmp/opencode/step8-corpora2/L0-0 --executable /tmp/opencode/step10-v3-py313/bin/doc-atlas --model-dir /tmp/opencode/step10-mini-assets --policy /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-calibration-v3/measurement/policy.json --recipe complete-own-body-gated-maxp-v2 --original-only --out /tmp/opencode/step10-v3-installed-T01-L0
/tmp/opencode/step10-v3-py313/bin/python eval/blind_project_context/probe_minimal_delivery.py --prepared /tmp/opencode/step8-corpora2/L0-0 --executable /tmp/opencode/step10-v3-py313/bin/doc-atlas --model-dir /tmp/opencode/step10-mini-assets --policy /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-calibration-v3/measurement/policy.json --recipe complete-own-body-gated-maxp-v2 --translated-only --out /tmp/opencode/step10-v3-installed-T01-L0-translated
```

Public packets, same-call scores, breakpoint sets, policy and counts copied to
`measurement/`. Build details in `build-provenance.json`. New installed venv
shares dependency paths through `.pth`; it is not hermetic. Initial pip build
failed before building because hatchling was absent; uv build succeeded.
No production threshold tuning, dictionaries, top-k, packet filling, default
enablement, source/question edits, commits or pushes.
