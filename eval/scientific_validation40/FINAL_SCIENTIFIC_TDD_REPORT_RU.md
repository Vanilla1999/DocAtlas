# DocAtlas scientific TDD cycle — final report

Date: 2026-09-19

## Final status

- **Structural integrity treatment:** `structural_fix_validated`
- **Reader presentation treatment:** `reader_view_rejected_on_independent_validation`
- **Reader view production integration:** **not performed**
- **New phrase / synonym rules:** **none**
- **New retrieval backend / embeddings / reranker:** **none**
- **Public project-context budget:** unchanged at <=800 admission tokens and <=3 sources

The cycle deliberately ends with one accepted deterministic integrity correction and one rejected presentation hypothesis. The independent validation result was not used to tune either candidate after exposure.

## Scientific basis used

The implementation follows the methodological consequences of the cited work rather than claiming that any paper prescribes a DocAtlas-specific patch:

- Sufficient Context: context sufficiency and reader correctness are measured separately.
- CheckList: structural behavior is tested through entity/value changes, negation, ordering, noise and negative controls rather than one question string.
- Prompt-format sensitivity / FormatSpread: presentation is tested as a separate fixed-arm experiment and is not assumed to transfer.
- RECOMP / Dense X Retrieval: preservation and granularity of useful source material are evaluated by downstream usefulness and source integrity.
- Robustness to irrelevant context: high-overlap distractors are included as behavioral controls.
- Adaptive data analysis / holdout reuse: production and reader candidates are frozen before independent validation and are not repaired against the opened validation set.
- AIS-style attribution: a model answer is counted correct only when the requested claim is supported by the visible frozen evidence.

## P0 — measurement boundary

The cycle freezes runtime/source identities, records exact public packets, separates context sufficiency from reader outcome, and binds reader records to case IDs and model-input hashes.

The original loss classes remain separated:
- H04: a full list item existed but its trailing default could be lost in projection.
- H07: complete requested alias-type evidence is lost earlier than the final structural variant choice.
- H08: a useful strict-type fragment can exist but fail final selection.
- H01/H05/H14/H15/H16: the visible packet can be sufficient while the stress reader still fails.

No H07/H08-specific treatment was added.

## P1 — structural item integrity

### RED

Initial generic test, with no library or benchmark names:

- three prefixes ending at a sentence boundary inside one list item were incorrectly classified complete;
- two positive controls were already green.

Observed first run: **3 failed / 2 passed**.

The tails represented three semantic classes without keyword rules:
- a numeric/default value;
- a prohibition;
- a precondition.

### GREEN

Production changes are limited to:
- `docmancer/docs/domain/context_windows.py`
- `docmancer/docs/application/_docs_context_projection_core.py`

The implementation reuses existing Markdown structural alternatives, distinguishes complete list-item boundaries from sentence punctuation, and carries exact candidate occurrence offsets internally through projection.

Duplicate source text is fail-closed without a bound occurrence; projection uses the actual candidate span rather than a first-match `.find()` guess for completeness and union construction.

Property tests cover:
- entity rename and value changes;
- `-`, `+`, `*`, `1.`, `1)` markers;
- indented/nested list content;
- neighboring complete items;
- tail negation;
- source-order changes;
- high-overlap distractors;
- insufficient corpus;
- instruction-like source text as data.

Existing suites continue to cover wrong version, stale/risk/lifecycle, snapshot binding, partial/fail-closed behavior and source-range integrity.

## P2 — native H04

Frozen native public-path validation succeeds without a new selection/ranking mechanism.

H04 visible packet:
- all four requested defaults visible, including `max_age = 600`;
- **627 admission tokens**;
- **2 sources**;
- public source ranges and validator remain valid;
- retrieval-only flags remain false for answer authorization/edit readiness.

Focused structural/native gate:
- **15/15** structural tests green;
- **64/64** extended native/focused tests green.

Artifact:
- Actions run `35441889886`
- artifact `10584172655`
- digest `sha256:2ce5b4184abcdef59cfdb5cb7b391a78fd29884431efcf89c94c2e7840efed96`

No additional P2 ranking treatment was needed.

## P3 — fixed reader-view experiment

The reader experiment is eval-only and keeps retrieval packets/snippets unchanged.

Arms were frozen before inference:
1. `raw_json`
2. `view_json`
3. `view_text`

Model:
- `qwen2.5:1.5b`
- digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`
- Q4_K_M
- Ollama 0.34.2
- 3 independent draws per arm/case

Opened H20 stress-set result:

| Arm | grounded-correct | false abstain | unsupported/wrong | majority-correct cases |
|---|---:|---:|---:|---:|
| raw_json | 33/60 | 15 | 12 | 11 |
| view_json | 43/60 | 6 | 11 | 14 |
| view_text | **48/60** | **0** | 12 | **16** |

`view_text` was therefore preselected for independent validation. It was **not** integrated into product code.

Artifact:
- run `35442352688`
- artifact `10584620931`
- digest `sha256:9e22e67d7e45eb5942b67460d17013cb50a71d20974969d1e589792049a3b9f4`

## P4 — finite behavioral matrix

The accepted structural mechanism passes behavioral controls for:
- rename/value invariance;
- condition/negation retention;
- evidence position changes;
- high-overlap noise;
- insufficient evidence;
- source text resembling an instruction.

Version/snapshot/stale/risk and fail-closed controls are covered by existing suites and were not duplicated with benchmark-specific tests.

Run `35442410451` completed successfully.

## P5 — independent 40-task validation

Validation was frozen before the first result:
- 5 new project families: Black, Poetry, Textual, Vite, ESLint;
- 40 tasks;
- 24 answerable / 8 partial / 8 unanswerable;
- root-only; no lookup queries;
- source bytes and source-bound gold spans frozen separately.

### Structural candidate

Result:

- full witness on answerable tasks: **6/24 baseline -> 6/24 candidate**;
- wins: **0**;
- losses: **0**;
- documented partial claims: **2/8 -> 2/8**;
- new source/budget audit violations: **0**.

Decision: **`structural_defect_fix_validated_no_general_retrieval_gain`**.

The fix generalizes as an integrity correction and does not damage the new projects. It is not a general recall improvement.

Artifact:
- run `35445797151`
- artifact `10585058639`
- digest `sha256:9b03da69ac80da8b869958090706b39f5fa8e68f2dd6bc07195f2015ca12ff5a`

The observed **6/24 root-only witness rate** is a separate future retrieval problem. Under the anti-tuning rule it is not repaired in this cycle.

### Reader presentation candidate

The preselected `view_text` arm was compared only with raw JSON on the exact same frozen candidate packets.

240 independent inferences:
- 40 cases;
- 2 arms;
- 3 independent draws per case.

| Arm | grounded-correct | rate | unsupported/wrong |
|---|---:|---:|---:|
| raw_json | **76/120** | **63.33%** | 30 |
| view_text | 74/120 | 61.67% | **28** |

Correctness delta: **-1.67 percentage points**.

Project-cluster bootstrap:
- clusters: 5 project families;
- 10,000 resamples;
- seed: 20260919;
- mean delta: -0.01667;
- 95% interval: **[-0.05, 0.00]**.

Frozen rollout gate required:
- >= +5 percentage-point grounded-correct improvement;
- cluster-bootstrap lower bound > 0;
- no increase in unsupported answers.

The candidate satisfies only the unsupported-answer condition. It fails both correctness requirements.

Decision: **`presentation_not_supported_for_product_rollout`**.

The opened H20 stress-set improvement did not transfer. Reader views remain eval-only; the public MCP contract and host boundary are unchanged.

Artifact:
- run `35445870945`
- artifact `10585389177`
- digest `sha256:c75ea424fd7d82c61b84a09652b17b0624ef675d16fdbef73acbc13eba620aa2`

## Regression gates

### Existing external80

Baseline and candidate reused the exact same corpus/state identity.

- sufficient: **31 -> 31**
- wins: 0
- losses: 0
- public payload changed IDs: **0**
- safety violations: **0 -> 0**

Run `35446008277`; artifact `10585409011`.

### Fresh paired full suite

Pre-structural baseline `b07dc52bd7ba02a449477bc534cc84dc1d276ffd` versus frozen structural candidate `e5e1bec980caa1b66758f655940d519f0ba2fa04` under the same environment:

- baseline: **36 failed / 4015 passed / 10 skipped / 622 deselected**
- candidate: **36 failed / 4050 passed / 10 skipped / 622 deselected**
- exact failed node IDs: **identical**
- candidate-only failures: **0**

The repository remains baseline-red; this scientific cycle adds no observed full-suite failure.

Run `35446290434`; artifact `10585279610`; digest `sha256:09677ae2557695c0976c9aa0055fbff7552a410ff4c39ea89ed6ca3608f6e8bf`.

## Product integration decision

Only the deterministic structural integrity correction is accepted as product behavior.

The presentation experiment is rejected for rollout. `reader_views.py` and `reader_experiment.py` remain evaluation code only. No production module imports them, and DocAtlas does not currently own a universal MCP-client model-facing renderer that would justify silently changing how every external host sees `structuredContent`.

## Review ruling

**Deferred limitation:** unsupported Markdown directives such as `???` / `!!!` are marked `structure_unverified` by the structural-block parser, but ordinary rolling snippets can still reach the pre-existing punctuation fallback used only as a projection ranking preference.

Ruling: do not modify the frozen candidate after independent validation in this cycle. No observed path turns that preference into answer proof, source authorization, version bypass, or safety bypass.

Cost if wrong: an unsupported-syntax rolling snippet could receive a completeness preference that it should not receive. This must be isolated by a new generic RED before any future production change; fixing it now would invalidate the frozen P5 candidate and require a new validation cycle.

## Final conclusion

This cycle demonstrates the intended anti-patch-loop workflow:

1. reproduce a general structural defect without target-library terms;
2. fix the structural invariant, not a question phrase;
3. prove the native target case;
4. test renamed/value/negation/noise controls;
5. freeze the candidate;
6. open new project families only after freeze;
7. **accept the structural fix because it transfers without losses**;
8. **reject the reader-view idea because its promising development result does not transfer**;
9. do not tune against the opened validation set.

The next retrieval cycle must not use these 40 validation cases as a development benchmark. Their low root-only coverage is evidence for a new research question, not a list of forty conditions to add.
