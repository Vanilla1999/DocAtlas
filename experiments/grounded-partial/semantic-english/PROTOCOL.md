# English-only semantic admission: protocol before model scores

Base: PR #189, experiment/contextual-late-sufficiency, 49e9f3a4992b1b072f4106a1f65f098e83360795. The user explicitly excludes Russian-language evaluation going forward. Keep historical bilingual results unchanged; do not translate old Russian questions into new test cases or count language filtering as a gain.

## Dataset and comparable control

Use the previously prepared synthetic semantic-admission pairs (original SHA256 9f20435b5c3214e8b5e323076ffac3f376842601181501eb6b8b26274eefaec0), excluding every pair whose question or body contains Cyrillic. This gives 56 unchanged pairs: 28 calibration and 28 evaluation, each with 12 useful and 16 non-useful examples. Source/topic groups remain disjoint. Data are single-assistant-authored synthetic examples, independent of frozen80/holdout20 but not independently human adjudicated. Keep useful partial answers and correct premise refutations positive. Preserve all English negative examples, including question restatement without an answer, wrong aspect, wrong subject and wrong sense of a shared term.

The original model-score preparation used structured generative categories and quoted spans; this experiment instead tests scalar rerankers. It does NOT fabricate generated categories, quotes or reasons, and does NOT claim to implement that JSON scorer or the paper's sufficient-context autorater. The exact document body is provided without truncation. An immutable input digest binds each score to its question/body; provenance remains separately checked.

Frozen development benchmark after the same language exclusion: 67 questions = 35 within-budget positives + 32 controls. The last combined37 control is 29/35 on this English slice. These are filtered archived counts, not a new product gain. Old 37/48 is not the denominator for this experiment.

## Two fixed scorer candidates, no post-result prompt/model sweep

1. cross-encoder/ms-marco-MiniLM-L6-v2: small English passage reranker; query/body pair, raw relevance logit and sigmoid. Resolve and record immutable Hub revision before inference.
2. Qwen/Qwen3-Reranker-0.6B, revision e61197ed45024b0ed8a2d74b80b4d909f1255473: official yes/no final-token scoring, FP32 CPU, fixed custom instruction about substantive information for at least one part, useful partial/refutation, and rejecting mere question echoes. Use the published chat prefix/suffix. No generated answer or rationale. Record actual prompt, weights/file digests, token counts, raw yes/no logits, scores and runtime.

Primary sources: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 and https://huggingface.co/Qwen/Qwen3-Reranker-0.6B . These models rank relevance; their scalar outputs are NOT calibrated probabilities of answer correctness or universal admission guarantees.

Model calls receive only question and literal body, not split, label, test-kind, expected category or benchmark gold. Score calibration first; select and write the threshold before scoring evaluation. No truncation: oversized input is an explicit experiment error. No outside-fact answer generation, external paid API, new index, embedding generation, runtime dependency or production modification.

## Threshold and gates

Maintain the previous 75% positive-recall / zero-negative-admission screen, adjusted only for the predeclared English slice: at least 9/12 useful admissions and 0/16 false admissions on calibration AND on evaluation. Choose a threshold from calibration scores only: maximum true positives with zero false positives, lowest threshold on ties. No suitable threshold is an explicit failure, not a secretly relaxed target. If calibration has no useful zero-FP threshold, still retain raw evaluation scores for diagnostic inspection; do not invent a passing certificate.

Also report the old lexical decisions on exactly these 56 pairs, per-type errors, paired changes, and the result of the fixed 0.5 score threshold as a declared diagnostic (not promotion). Evaluate each model separately without tuning it on the other model's failures. Do not run a broad model sweep.

Only a scorer passing both parts is eligible for a separately frozen actual-visible-window replay on the 67 English benchmark questions, using previous source/project/version/exact-subject boundaries, the current selector and <=800 full-DTO tokens / <=3 sources. A failed pair screen is a completed negative screening result: no end-to-end gain is then claimed. Never infer a new frozen67 score from pair accuracy. Holdout20 remains closed in this pass even after a screening success.

## Evidence and integrity

Publish exact inputs, scores, calibration locks and evaluation decisions, dependency/model provenance, timing and input-token workload, source-span checks and tests. Preserve source text and all prior results. Any code or infrastructure failure is separate from a negative model finding. Do not manufacture scores or label test doubles as model outputs. Download model assets during explicit preparation; inference uses local weights. No automatically scheduled work or automatic merge.
