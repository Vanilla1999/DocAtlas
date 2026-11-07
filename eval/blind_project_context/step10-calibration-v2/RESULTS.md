# V2 body-only relevance gate: fresh independent measurement

## Result

The gate reduces some direct false positives, but **does not validate sufficient
minimization** on this fresh synthetic split. Validation delivers all **22/22
required facts** and **16/16 useful bodies**, while direct semantic retention is
**15/16**. Closure delivers **12 negative bodies**, and one of two no-answer
requests receives an entire irrelevant document.

No threshold or label was changed after seeing scores.

## Frozen inputs and public execution

- Four independently authored fictional manuals, disjoint calibration/validation
  families, 16 tasks, 88 exhaustive usefulness labels.
- Input manifest SHA256:
  `7c7399ce4f257a383b158ad30132742a9a89083f6dc7ba8bf335dc450e96a539`.
- One successful run: `/tmp/opencode/step10-calibration-v2-run-01`.
- Four real public `prepare_docs` calls and 16 real public `get_docs_context`
  calls, real source/storage/model/validation components, no mocks.
- Scores observed passively on the same calls, outside model-visible packets.
  Labels were evaluator-only; only document files entered the prepared projects.
- Exact component rule checked for every unit:
  `score = min(contextual_score, own_body_score)`. Both branches exhaust all
  windows/lanes. The independent branch uses exact ancestor/current heading
  lines without ancestor introductory bodies. Structural closure is unchanged.

Policy: [`measurement/policy.json`](measurement/policy.json).
Recipe `complete-own-body-gated-maxp-v2`;
threshold **-6.489150047302246**; policy SHA256:
`5eb8d93aabd318bf24505383ed54c14733a8900eaf19a783f8f078cc953520ff`.

The threshold is the minimum score of all 16 useful calibration units. Its
attaining unit is `C2-subtree / Trolley paint`: contextual score
`-2.8770947456359863`, own-body score `-6.489150047302246`. That question explicitly
asks for every subsection, so the seemingly peripheral subsection is genuinely
positive. It cannot be removed to obtain a higher threshold.

## Metrics

| Metric | Calibration | Fresh validation |
|---|---:|---:|
| Tasks / labelled units | 8 / 44 | 8 / 44 |
| Useful / negative units | 16 / 28 | 16 / 28 |
| Direct useful units retained | 16/16 | 15/16 |
| Direct false positives | 3/28 | 5/28 |
| Delivered useful units | 16/16, diagnostic | 16/16, policy |
| Delivered negative units | 28/28, diagnostic | 12/28, policy |
| Required facts delivered | 20/20, diagnostic | 22/22, policy |
| Nonempty no-answer results | 2/2, diagnostic | 1/2, policy |

Calibration delivery is deliberately keep-all diagnostic; its delivered size
and no-answer rows are **not filtered-policy measurements**.

Validation retains 18348 of 21172 source characters across eight task/document
pairs: **13.34% reduction**. Serialized public JSON totals 11199 tokenizer tokens;
this is not actual client presentation, answering-model usage or dialogue cost.
Task times total approximately 8.65 seconds across both splits on the supported
local environment. Long-tail bodies exceed 512 model tokens and are evaluated
through the real complete-window route.

## What the gate changes—and what closure restores

At the **same frozen v2 threshold**, contextual scores alone admit 7 negative
validation units; combined gated scores admit 5. The gate therefore removes two
direct false positives and zero direct positives. This is a diagnostic comparison
between same-call components, not a separately calibrated v1 policy or a causal
closure ablation.

The two directly rejected negative units are nevertheless delivered:

- `V2-radio / Membership forms`: contextual `-5.8649821281433105`, gated
  `-7.696876049041748`. Selected broader structure brings the sibling back.
- `V2-long-negative / Customer receipts`: contextual `-3.5249545574188232`, gated
  `-9.02161693572998`. The no-answer request still selects parent/body material
  and closure delivers the complete fermentation document.

The direct useful-unit miss is `V2-tail-ru / Community bakery notebook`, score
`-6.565833568572998` in both passes. Ancestor closure supplies the scope paragraph,
so final delivery and required facts pass. The threshold was not retuned to this
fresh validation miss.

| Validation task | Direct kept | Delivered useful | Delivered negative | Outcome |
|---|---:|---:|---:|---|
| V2-radio | 7 | 5 | 3 | All facts; unrelated labels/forms and generic root included |
| V2-own-child | 1 | 1 | 2 | Requested labels plus ancestor bodies |
| V2-subtree | 6 | 6 | 1 | Requested full subtree plus generic root |
| V2-noanswer | 0 | 0 | 0 | Correctly empty |
| V2-tail-ru | 1 | 2 | 0 | Scope intro missed directly, restored by closure |
| V2-long-negative | 2 | 0 | 3 | Incorrect nonempty whole-document result |
| V2-narrow-office | 2 | 1 | 2 | Narrow receipt question still delivers whole document |
| V2-building-log | 1 | 1 | 1 | Correct long own-body block plus irrelevant introduction |

## Verification, portability and limitations

All delivered source snippets were independently checked against frozen bytes
and line spans, scope and authority, identity/fingerprint presence, and exposed
continuation raw-source hashes. Persistent SQLite state and document bytes were
unchanged by queries. The public projection fingerprint was not equated with
`sha256(snippet)`. Labels, questions and recipe hashes were verified before
runtime import, and the policy hash was checked throughout validation.

`measurement/` preserves 40 exact JSON artifacts: 16 public packets, 16 passive
observations, four preparation receipts, frozen-input receipt, policy, detailed
results and summary. Receipt-manifest SHA256:
`44ff7514155afef878dd54c9ac0cd97eec47ed796cb0aedcbfe008950bce78f0`.
All input and output hashes were verified without repeating inference.

This is a small synthetic in-process public-pipeline evaluation, not installed
stdio, a real client, an external benchmark, formal coverage guarantee or an
answering-model experiment. Its mirrored structural challenge patterns limit
generalization. It cannot establish the behavior of large production corpora.

The main agent separately reported provider `429 usage_limit_reached` for
`/tmp/opencode/terra-step10-batched`. No Terra calls were made here and no local
model quota error occurred. The provider blocker is not a relevance-policy result.
