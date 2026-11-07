# Independent calibration: measured result

## Current boundary: passive same-call observer

After the product moved diagnostic scores out of model-visible packets, the
runner was updated to `observe_minimal_context()` around each real public call.
The justified new run is preserved in **`measurement-observer/`**. It uses four
public preparations and **12 public context calls**, with no extra diagnostic
validation calls. Twelve observer receipts are stored separately from twelve
public packets; every query produced exactly one observation. Policy-mode
observations were checked against the frozen policy SHA256. Scores never entered
the public `source_selection` object.

The threshold and policy bytes are identical to the preceding run. An offline
comparison also found identical delivered source snippets and line spans for
every task. Validation findings therefore remain **14/14 facts delivered,
11/12 direct useful units retained, and one noisy no-answer result**. This
comparison is not a separate observer ON/OFF runtime test.

Current serialized public JSON counts: calibration 10108 tokens, validation
7783 tokens. These are not dialogue/client token counts. Total recorded task
time is approximately 5.00 seconds. Current receipts:
`measurement-observer/receipt-manifest.json`, SHA256
`430da17d566ed8bc9fba7bdc55bab839afc8f0f79af52a010c0763189187f237`;
32 byte-for-byte artifacts, all hashes verified. Use
**`measurement-observer/policy.json`**. Frozen inputs and all historical receipts
remain unchanged.

## Historical pre-observer-boundary measurement

2026-11-06. Inputs frozen before inference, manifest SHA256:
`5ffbba341931285ae76a538b1b3eaa88d163f2ab19477516ac1a3b0c82c81d0c`.

The completed run used real in-process public `prepare_docs` (4 calls) and
`get_docs_context` (18 calls), real isolated storage/source validation, and the
pinned local multilingual MiniLM. No retrieval/model/validation mocks. Calibration
used six keep-all diagnostic calls; validation used six diagnostic calls and six
policy-mode calls. The latter diagnostic calls measure direct score retention
without exposing rejected scores in deployed policy packets. They never change
the threshold. This is not installed stdio, a real client, or an answering-model
evaluation.

Frozen policy: [`measurement/policy.json`](measurement/policy.json).
Raw threshold `-7.280395030975342`, the minimum of all 12 calibration-positive
own-body scores. Policy SHA256:
`327fc69db2c97e6d44abbe83118b01fad15a308c071fd5226880c14ee7679a4c`.

| Measure | Calibration | Validation |
|---|---:|---:|
| Tasks / labeled units | 6 / 34 | 6 / 34 |
| Direct useful units retained | 12/12 | 11/12 |
| Direct false positives | 8/22 negatives | 7/22 negatives |
| Delivered required facts | 13/13, diagnostic | 14/14, policy |
| Delivered useful units | 12/12, diagnostic | 12/12, policy |
| Delivered negative units | 22, diagnostic | 10, policy |
| Nonempty no-answer results | 2/2, diagnostic | 1/2, policy |

Validation retained 9801 of 11764 source characters across six query/document
pairs: a 16.69% reduction. Its serialized public JSON totals 7765 tokenizer
tokens, **not** actual model-visible client or whole-dialogue tokens. Calibration
keep-all packet sizes do not measure filtered-policy savings. Task timings total
approximately 6.78 seconds, including both kinds of validation call.

The direct miss is the `Loom service hall` scope introduction in `V-tail-ru`
(score `-8.648924827575684`). Structural closure restores it, so the fact and
delivery checks pass. `V-tail-noanswer` nevertheless returns the complete loom
document, and selecting broad parents adds unrelated sections to other answers.
Thus **direct retention validation fails and minimization remains weak**. The
threshold was not adjusted after seeing this result. This small authored
synthetic set cannot establish external benchmark quality or statistical coverage.

Every final source was checked against independent document bytes and native line
spans, scope/authority, identity/fingerprint presence, and source continuation
snapshot hashes where exposed. All read calls preserved logical SQLite contents
and document bytes. Fingerprint presence is not an independent reconstruction of
the product's projection hash algorithm. No final answering-model fact claim is
made.

`measurement/` preserves 26 byte-for-byte JSON artifacts (18 query packets, four
preparation receipts, frozen input receipt, policy, detailed results, summary).
`receipt-manifest.json` binds those bytes; its SHA256 is
`98edf5d35eb178e3ec5c9ba25b0748de71cabf4c30622695cda871e577160422`.
Prepared paths in receipts refer to the original isolated run; documents are
available separately in this artifact's frozen split directories.

The first attempted run remains at `/tmp/opencode/step10-calibration-run-01`:
it failed after inference on a product canonical-snapshot schema error and
emitted no policy. The completed run was justified by main's snapshot fix.
No successful scenario set was rerun.
