# Semantic Sufficiency Checker: executed comparison, 2026-10-25

## Decision: keep the efficient `facet-guarded-v1` selector; do not enable QA automatically

The experimental local extractive-QA checker **works as a diagnostic** but did **not** improve independently required evidence coverage on either evaluation suite. Its attempts to rescue facts increased context and runtime without recovering a required witness. Its counterfactual pruning saved only ~1.1% of context across 76 questions, with much higher CPU time and no certified entailment. **Do not set any semantic QA policy as the default.**

This is an engineering negative result, not a demonstration that sufficient-context checking is impossible. The earlier SQuAD2 QA model in `answerability.py` was expressly observation-only after erroneous automatic refusals; it must not be used to grant or deny answers.

## Executed design

All four modes operate on the *same already admitted original source candidates*, after local MiniLM facet selection and before the final full-packet budget:

1. `facet-guarded-v1` — existing efficient selection baseline at pinned PR #226 product `cf8ed00b`, carried into this PR.
2. `semantic-audit-v1` — private QA-span comparison between selected and full admitted source context; **does not change selected text**.
3. `semantic-rescue-v1` — append a verified source group when a full-pool QA-span hypothesis differs from the selected-pool hypothesis.
4. `semantic-prune-v1` — remove up to two groups only when predictions at original source coordinates survive a limited counterfactual ablation. **This is not a proof that caveats or all required facts remain.**

The checker runs pinned `onnx-community/roberta-base-squad2-ONNX` on CPU from SHA-verified local assets; no paid selection model calls. At most three literal EN query probes and 45 seconds per request. Unscored or unsupported probes are **unknown**, not sufficient. No source permissions, project/snapshot bindings, citation origins, `answer_supported`, `answer_available` or corpus-absence claims change.

## First, 64 known regression questions (V40 + New16 + Fresh8)

Run **40231001028**: https://github.com/Vanilla1999/DocAtlas/actions/runs/40231001028
Exact paired summary artifact `12613832114`.

| Policy | Covered documented cases | Witness groups | Public model-visible `o200k_base` tokens | Added independently required facts | Strict empty-answer negatives |
|---|---:|---:|---:|---:|---:|
| `facet-guarded-v1` | 53/53 | 97/97 | **64,171** | control | 0/11 |
| `semantic-audit-v1` | 53/53 | 97/97 | 64,115 | 0 | 0/11 |
| `semantic-rescue-v1` | 53/53 | 97/97 | **71,975** (+12.1%) | **0** | 0/11 |
| `semantic-prune-v1` | 53/53 | 97/97 | **63,208** (−1.5%) | 0 | 0/11 |

The ~56-token audit-vs-baseline difference is run-to-run machine/identity formatting noise: audit made **no** changes to original source snippets. This is not optimization.

Cumulative MCP request seconds, each policy in separate CI jobs: baseline **337**, audit **531**, rescue **1,359**, prune **612**. Timing is runner-sensitive; do not interpret these as a fixed production multiplier. The local QA seconds in the run were audit ~343, rescue ~1,017, prune ~384.

The QA observer reported hypothetical answer differences in V40 despite the original selected packet already covering every frozen required witness. It cannot treat these differences as fact gaps. In two distinct full-pool experiments the V40 rescue policy selected different additional sections and had different latency (first 1,238 s for V40, second ~480 s), despite unchanged product code. Do not silently average this instability away.

## Second, a separately frozen, previously unexecuted 12-case SeleneMesh corpus

Inputs/oracle committed **before inference** at `0d7b205fed65aa610922ecf443d0bc466285585e`, execution revision `c44e7e34391d34d2283c59282f0aec5506b31245`. Same conceptual families as Fresh8 but distinct documents, values, queries, source bytes and expected witnesses; **not an out-of-domain generalization claim**. Nine full, one partial, two answer-absent; **36 documented witness groups**.

Run **40231394528**: https://github.com/Vanilla1999/DocAtlas/actions/runs/40231394528

| Policy | Documented cases | Witness groups | Public visible tokens | Sum of MCP seconds | Empty-source negatives |
|---|---:|---:|---:|---:|---:|
| `facet-guarded-v1` | **10/10** | **36/36** | **8,193** | **16.7** | 0/2 |
| `semantic-audit-v1` | 10/10 | 36/36 | 8,255 | 21.8 | 0/2 |
| `semantic-rescue-v1` | 10/10 | 36/36 | 8,514 | 61.4 | 0/2 |
| `semantic-prune-v1` | 10/10 | 36/36 | 8,360 | 63.1 | 0/2 |

The audit checker returned `unknown` on **all 12 questions**; this is an honest unknown, not a completeness certificate. Rescue added two irrelevant/not-required source groups (S03 and **S10, which has no documented answer**) and recovered no witness. Prune removed zero groups on the new corpus.

## Combined 76-question observed context (not provider billing)

| Policy | Required witness groups | Visible tokens | vs baseline |
|---|---:|---:|---:|
| `facet-guarded-v1` | **133/133** | **72,364** | control |
| `semantic-audit-v1` | 133/133 | 72,370 | ≈0% |
| `semantic-rescue-v1` | 133/133 | 80,489 | **+11.2%** |
| `semantic-prune-v1` | 133/133 | 71,568 | **−1.1%** |

Strict empty retrieval: **0/13** for all modes. No semantic answer refusal is validated. These 76 include previously inspected known questions and 12 newly frozen but template-similar questions; there are only **63** full/partial documented cases, not 76 fully answerable questions.

## Integrity, limitations, next acceptance gate

All completed installed-MCP experimental arms use real non-editable wheel, SQLite, CPU MiniLM and CPU QA, two CPUs, 1.5GB memory ceiling, offline network. Actual model-visible text is counted with `o200k_base`; independent gold is inspected after tool delivery, never supplied to the ranker or QA reader.

- The score `best_span_minus_null` is *not calibrated entailment* or a proof that all conditions/negations are present.
- This QA model fails to prove sufficiency on many technical questions; do **not** authorize automatic source deletion, no-answer or prompt decision.
- Short bounded question views may omit unspoken dependencies. In particular S10 returned extra unrelated material.
- End-to-end generated strong-model answer quality and actual provider `usage` were **not** measured: previous live replay attempted and was blocked by unavailable `OPENAI_API_KEY` (0 calls). No full-dialogue token savings are claimed.
- Common compact projection and source-native admission protections remain. Defaults and `main` unchanged; PR remains draft.
- Another two V40 diagnostic jobs in the full holdout-matrix repetition were still pending at the time of this summary; the **complete first-run V40 evidence** and **complete four-arm separately frozen SeleneMesh12 evidence** above are already available. Do not claim that redundant second V40 replay is complete until it is.

**Recommended next scientific step**: project-disjoint samples with human-reviewed per-requirement entailment labels; train/calibrate an NLI/sufficiency classifier that predicts `entailed / contradicted / unknown` for each requirement, and require no missing critical facts on blind datasets before any automatic deletions. A generic SQuAD2 answer-span model alone is insufficient.
