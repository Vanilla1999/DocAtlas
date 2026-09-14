# Real English-only semantic scoring: hard-admission screening failed

## Decision

Both real models were run: MiniLM-L6-v2 and Qwen3-Reranker-0.6B, 56 English pairs each, 112 predictions. This is not an unscored preparation or test-double result. Neither scorer passed the preregistered usefulness-admission screen. Do not replace current qualification with either tested scalar threshold. No new frozen-benchmark sufficiency gain, live-agent result, production change or merge is claimed.

The failure is not a Russian/English mismatch: no Russian questions or bodies entered either model. Both frequently score an unanswered repetition of the question very highly. Raising the cutoff removes much of the genuinely useful text as well.

This tests two scalar rerankers as usefulness classifiers. It does NOT test the earlier proposed JSON-generating judge that extracts supporting quotations, and is not a reproduction of the Sufficient Context autorater. No categories, reasons or quotations were fabricated from scores. The result does not reject semantic admission in general.

## English data and baselines

The previously prepared 64-pair dataset was filtered by removing 8 Cyrillic questions, without translating or rewriting the retained questions, bodies, labels or documents. The remaining 56 pairs cover eight fictional modules: four source/topic groups for calibration and four different groups for evaluation. Each split contains 12 useful and 16 non-useful pairs. Useful examples include paraphrases, partial answers and relevant refutations. Negative examples include wrong aspect, wrong subject, wrong meaning and question repetition without an answer.

This is a single-assistant-authored synthetic stress test, independent of frozen80/holdout20 but not independently human annotated or representative of actual traffic. Several formulations share a body within a topic. No broad statistical generalization follows from these small correlated groups.

Archived lexical decisions on exactly this English subset:

| Split | Useful admitted /12 | Non-useful admitted /16 |
|---|---:|---:|
| Calibration |3|7|
| Evaluation |7|6|

The separate original development benchmark has 67 English questions:35 within-budget positives and32 controls. The saved combined37 payloads score29/35 on this slice. This is a filtered historical control, not a new score improvement or degradation. The old bilingual37/48 is not the denominator for English-only comparison. No new model-scored67-question projector replay was run because the pair screen failed.

## Fixed scorer configurations

- `cross-encoder/ms-marco-MiniLM-L6-v2`, revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`: sigmoid of the relevance classifier logit.
- `Qwen/Qwen3-Reranker-0.6B`, revision `e61197ed45024b0ed8a2d74b80b4d909f1255473`: published chat prefix/suffix plus a fixed task instruction; sigmoid(yes_logit-no_logit), equivalent to the two-token softmax. Only logits are read; no answer or rationale generation.

MiniLM uses its standard query/body input. Qwen also receives the frozen instruction to accept substantive information answering at least one part, including useful partial answers and correct refutations, and reject question echoes. This compares two predeclared configurations, not an architecture-only ablation: prompting and tokenizers differ. A high sigmoid value is not a calibrated probability of correctness.

Inputs contain only question and exact body. Labels, split names and example types are not sent to either model. Source hashes and occurrences are independently checked. No truncation: maximum input lengths60 and195 tokens respectively. CPU FP32, two PyTorch threads, official local safetensors weights, no remote model code. Downloads occur separately; inference ran under the repository's verified kernel outbound-syscall denial.

## Calibration-only thresholds

The original75%-recall/zero-false-admission condition was retained proportionally: >=9/12 useful and0/16 non-useful admissions on BOTH splits. Threshold selection maximizes calibration true positives with zero false positives, lowest threshold on ties. Each threshold was written to a lock file before evaluation inference. No post-result threshold or prompt sweep was performed.

| Scorer | Calibrated threshold | Calibration useful /12 | Calibration false /16 | Evaluation useful /12 | Evaluation false /16 |
|---|---|---:|---:|---:|---:|
| MiniLM | No useful zero-FP threshold | Not eligible | 0 with reject-all | Not eligible | 0 with reject-all |
| Qwen |0.9997848868370056|2|0|1|0|

MiniLM's threshold=null explicitly means no useful zero-FP cutoff. Stored zero-admission counts are reject-all bookkeeping, NOT model accuracy or an accepted configuration. Four negative calibration question echoes rank above all twelve useful examples. Qwen's zero-FP cutoff preserves only2/12 calibration positives and1/12 evaluation positives, far below the recorded screen. This is not a useful safety improvement.

## Predeclared loose-cutoff diagnostic

| Scorer at0.5 | Calibration useful /12 | Calibration false /16 | Evaluation useful /12 | Evaluation false /16 |
|---|---:|---:|---:|---:|
| MiniLM |12|10|12|9|
| Qwen |12|12|12|12|

Across both parts: MiniLM admits24/24 useful and19/32 non-useful; Qwen24/24 useful and24/32 non-useful. Both admit all8 question echoes. This diagnostic was declared before scores; it is not a selected production threshold, and the models' score scales are not a common confidence scale.

Other0.5 errors: MiniLM admits5/8 other-subject answers and6/8 wrong-sense passages. Qwen admits7/8 in each category and2/8 wrong-aspect passages. These are stress-test observations, not real-traffic rates.

## Same-question counterexample on evaluation

Question: `Can an EmberWriter reader observe a half-written replacement file?`

Useful body: `EmberWriter writes the replacement into a separate temporary file and then renames it over the destination atomically. Readers see either the old file or the complete new file.`

Non-useful body: `EmberWriter question: Can an EmberWriter reader observe a half-written replacement file? See the interface-color guide for examples.`

| Model | Useful body score | Question echo score |
|---|---:|---:|
| MiniLM |0.9874117374|0.9999256134|
| Qwen |0.9987183809|0.9996353388|

The negative does not state whether partial writes are visible, but both models rank it above the actual answer to the same question. This is not solely a global-threshold calibration problem across different topics: no simple cutoff can keep this lower-scored answer while rejecting the higher-scored echo. It does not imply all queries or all rerankers behave this way.

## Cost and verification

Measured forward inference for56 pairs: MiniLM0.426s; Qwen54.901s. Including scorer initialization and integrity checks:2.06s and56.21s. Actual unpadded input-token totals:2,455 and9,993. Prompt and tokenizer differences account for some of the difference. These are single shared-host short-input measurements, not production latency guarantees, paid API costs, whole-task savings or costs measured on the earlier thousands-of-windows replay.

Code head: `47d484708c65f01210466fae2b468428c92cc3c1`.
Protocol head: `ca05ca3e95e1dd7f97c6698ccd3e6a858eac751a`, before inference.
Actions run34788358419, job103807889547:completed/success.
13 boundary tests passed locally and on the runner. An independent archive audit checked112 exact input/prediction associations, real-logit-to-score arithmetic, unchanged English data/labels, group separation, both calibration locks, calibration-only cutoff recomputation and all confusion counts. No discrepancies. Unit-test doubles are not counted among model predictions.

Artifact10327213274, ZIP SHA256 `50b875575bd64189a38340d6ddf49416761e6ede049192b6c9538ad48d478bb9`. Contains exact inputs, full logits/scores, labels outside model calls, model-file hashes, prompt, locks, code, dependency versions and logs. No weights included. Compact numerical outputs are preserved in SCORES.json and inputs in pairs.json.gz, so key findings do not depend on Actions retention14 days.

One pytest warning concerned the existing asyncio_mode option because this isolated experiment did not install pytest-asyncio. All13 synchronous tests completed. No fresh full project-suite or public MCP-handler validation is claimed.

## Recommendation and remaining limits

Do not substitute either tested scalar scorer as mandatory admission. Do not lower the cutoff merely to obtain more positives: the false admissions and same-question misorderings demonstrate the tradeoff. Do not add exceptions for EmberWriter or question echoes tuned on this now-exposed evaluation set.

A structured usefulness judge identifying an actual supporting body span remains a different, unmeasured hypothesis. A literal quote proves its occurrence, not automatically its usefulness; precision, partial/refutation handling, cost and downstream behavior still need evaluation. A softer reranking use of these scores is also not established here.

English-only scope is retained going forward; historical bilingual data/results remain unchanged. Holdout20 stays closed. No production model dependency, embedding/index change, automatic merge, new end-to-end sufficient count or universal conclusion about semantic models is justified.

## Reproduction

Python3.12, torch2.8.0 CPU, transformers4.56.2, huggingface-hub0.34.4, pytest8.4.2. Set PYTHONPATH to the semantic-english directory. Run test_screen.py, then screen.py --models /tmp/scorer-models --download. For strict reproduction use the recorded MiniLM revision rather than resolving main again. Invoke screen.py with --models and a fresh --output under the existing hypothesis5/no_network.py wrapper with HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1. The committed workflow records the full commands. A new model revision or prompt is a new experiment, not a replacement of these results.
