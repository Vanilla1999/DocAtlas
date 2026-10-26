# Semantic preservation follow-up: completed paired results

## Decision

Keep **`facet-guarded-v1` / `global-margin-envelope-v2` with `markdown-owner-v1` units** as the recommended experimental selection profile. The additional exact-span and strict NLI preservation stages did not remove any source group on this study. They therefore did not demonstrate useful context reduction. The NLI model is a separately trained classifier, not a general question-sufficiency oracle.

The QA `unknown` mutation defect is fixed and verified through actual public MCP calls. This is a concrete correctness improvement, not proof that sufficient-context prediction is solved.

Product tested: `60daed88ef190ad3caec65ab112a4a29f6818aad`.
Completed workflow: https://github.com/Vanilla1999/DocAtlas/actions/runs/40239358873

## What changed

1. `semantic_sufficiency.py`: stage QA proposals until the entire allowed check is complete. `unknown` or request-budget exhaustion restores the original selection. Do not perform action-mode inference when the query plan is already incomplete. Existing public authority/refusal flags remain untouched.
2. `semantic_budget.py`: one request-wide forward/token/time allowance and an exact question/source-window cache, instead of resetting the reader budget for each comparison. The deadline is checked between/after synchronous forwards; it cannot preempt an in-flight ONNX call and is not a hard wall-clock guarantee for all preprocessing.
3. `semantic_preservation.py`: compare deterministic same-source span-union preservation with a conservative NLI statement-preservation hypothesis. The latter checks every proposed source statement against retained same-source text, guards numbers/code/conditions/order tokens, protects supporting groups, does not silently truncate a model pair, and rolls back speculative removals if the shared budget is exhausted.

NLI assets are provisioned by an explicit host command, never downloaded during serving. They are pinned to `cross-encoder/nli-MiniLM2-L6-H768` at `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d`, quantized ONNX SHA-256 `44391a5241a62e0083c1a8899a71e69a092b95aea5ba89e14062925468eceac7`. Experiment thresholds 0.995 entailment / 0.001 maximum contradiction were frozen before inference and are NOT calibrated probabilities or a guarantee of correctness.

## Actual paired execution

84 distinct questions: V40 (40), New16 (16), Fresh8 (8), SeleneMesh (12), and newly authored QuillLedger (8). There are 70 full/partial documented cases and 14 unanswerable cases. The oracle contains 148 required witness groups; these are not uniform atomic facts. The previous 76 cases are known regression data. QuillLedger source/questions/alternative witnesses were frozen before the new NLI run, but are synthetic controls rather than real-user out-of-domain evidence.

17 arms: three policies over all five suites, plus repaired QA-rescue over SeleneMesh12 and QuillLedger8. Execution used non-editable installed wheels, actual SQLite, pinned local CPU models, public stdio MCP, no product mocks, network disabled, two CPUs and a 1.5 GB container limit. Gold was assessed after delivery. Questions, source documents and old gold were not rewritten.

| Policy | Complete documented cases | Required groups retained | Visible o200k_base tokens | MCP seconds summed | Actual removed groups | Extra checker forwards |
|---|---:|---:|---:|---:|---:|---:|
| Efficient facet control | 70/70 | 148/148 | 74,962 | 200.831 | n/a | 0 |
| Exact source-span preservation | 70/70 | 148/148 | 75,235 | 203.073 | 0 | 0 |
| Strict NLI statement preservation | 70/70 | 148/148 | 74,797 | 222.743 | 0 | 459 |

No individual control fact was lost or gained. Runtime/source-integrity errors were zero across all 17 arms. Strict empty-source no-answer checks remain **0/14** for the three all-suite policies. This is not a hallucination-rate or generated-answer accuracy measurement.

**The 165-token difference between NLI and control is NOT an optimization result.** Offline inspection of the exact archived public responses found identical source text, paths, lines and ordering in all 84 questions. The entire public wire is identical in all 84 after replacing only the random 16-hex-character nonce in short citation references with a common placeholder. Different random citation strings have different tokenization. Exact preservation has the same issue in the opposite direction. No source text was reduced.

### By suite

| Suite | Required groups | Control tokens | Exact tokens | NLI tokens | NLI removals |
|---|---:|---:|---:|---:|---:|
| V40 | 32/32 | 37,588 | 37,751 | 37,617 | 0 |
| New16 | 38/38 | 18,216 | 18,255 | 18,112 | 0 |
| Fresh8 | 27/27 | 8,341 | 8,355 | 8,263 | 0 |
| SeleneMesh12 | 36/36 | 8,325 | 8,360 | 8,291 | 0 |
| QuillLedger8 | 15/15 | 2,492 | 2,514 | 2,514 | 0 |

The strict NLI candidate did not even remove the deliberately paraphrased duplicate rules in QuillLedger. Passing the no-loss gate without any action does not validate useful semantic pruning. Its 459 executed classifications and extra processing time must not be described as a quality or token improvement.

## Verified QA safety fix

On 20 actual SeleneMesh/QuillLedger requests, repaired rescue reported unknown and changed the selection **0 times**. All 51 required witness groups were retained. SeleneMesh's incomplete plans triggered **0 QA forwards** rather than speculative rescue. On QuillLedger the reader used 49 actual forwards and 49 exact-window cache hits; no source was added or removed.

This verifies the non-destructive unknown contract, not a successful semantic completeness decision. The model/decoder can still be wrong when it does produce a hypothesis. Earlier QA-rescue results and failed hypotheses remain in `semantic-sufficiency-results.md`; they are not silently relabelled as passed.

## Provenance and reproducibility

- Exact paired artifact: `12616621445`, SHA-256 `0b1b10576c3831d8d2eb4bdd73910005968d9c1cd19a3a511e8741e2f686fe9b`.
- V40 artifact: `12616826886`, SHA-256 `e3d97b870087ab26eef386b1a8121626cdeaa1976af2b771c69bf4de944984d1`.
- New16 artifact: `12616306475`, SHA-256 `2d15fd12646ad2073ec9dbb633c08b125215bcb1b4726c17714a73e0caac3487`.
- Fresh8 artifact: `12616905590`, SHA-256 `d55171d83e10d117c3d2c9a8d084ff458fa2e3e4c3bb8e551706c339da28893f`.
- SeleneMesh12 artifact: `12616725458`, SHA-256 `847209018fbd1b28834763cef0c993f42e8cbb45496400ae8ced969b69a01668`.
- QuillLedger8 artifact: `12616195966`, SHA-256 `4ca03272cd0ed75e2933d08846cb94dab8105dc8d701024a4ceea501a6913da6`.

Recomputing `eval/compare_semantic_preservation.py` over downloaded summaries/assessments reproduced the CI PAIRED.json exactly. Original response packets and source-byte bindings remain in the per-suite artifacts. Execution comprised 272 stdio searches, 272 uncompressed public-handler acquisitions and 60 language preflights. Peak observed server RSS: NLI 705,540,096 bytes; repaired QA 743,985,152 bytes. Single CI timing observations are not a repeated production latency benchmark.

## Recommended profile and remaining boundary

For an already configured native-source pipeline with verified local MiniLM assets:

```sh
DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
DOCATLAS_MINILM_MODEL_DIR=/absolute/path/to/verified/minilm
DOCATLAS_SECTION_SELECTION=facet-guarded-v1
DOCATLAS_SECTION_UNITS=markdown-owner-v1
DOCATLAS_MCP_MODEL_VIEW=1
```

Keep QA/NLI modes experimental. No claim is made that the selected sources are globally minimal, that every user requirement was understood, or that corpus absence was proven. Preserving all already-selected statements is also a different objective from identifying which statements the question actually needs.

No answer model was called and provider usage is null. The original goal of lower total strong-model dialogue usage without answer degradation remains unverified. Neither random-reference token fluctuations nor successful local model loading establish that goal.

The continuation workflow completed successfully. On the tested product revision, Compact model context, Documentation language, MiniLM sections and Answerability observation safety workflows passed. Repository CI is NOT wholly green: the old Evidence coverage selector comparison fails before model execution because it freezes section_compression.py at the earlier 95c7bf4 revision, which predates the integrated facet selector; its historical harness needs reconciliation. The separate release-artifact gate also fails. These checks were not deleted, weakened or presented as passing. No main merge or global default switch occurred.
