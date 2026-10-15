# Local answerability gate (experimental, OFF by default)

This change distinguishes an operational failure from a learned prediction of no
answer in acquired, source-checked context. It does not prove corpus-wide absence,
validate an LLM answer, or promise that partial/multi-hop questions are complete.

`DOCATLAS_CONTEXT_ABSTENTION=observe` records a host-only diagnostic;
`enforce` applies the learned no-answer verdict, and `off` preserves all behavior.
Model assets must be explicitly provisioned before queries with
`python -m docmancer.docs.application.answerability_model /private/qa-model`.
Set `DOCATLAS_ABSTENTION_MODEL_DIR` to that absolute private directory.
Provisioning uses a fixed upstream revision. No network, training or model downloads
occur during queries. SHA-256 and file sizes are verified before ONNX loading.
The generated model manifest is trusted host configuration; protect it like the
existing local model directory. No arbitrary model paths are accepted from tools.

The CC-BY-4.0 tinyroberta SQuAD2 model is from deepset, converted by ONNX Community:
https://huggingface.co/deepset/tinyroberta-squad2
https://huggingface.co/onnx-community/tinyroberta-squad2-ONNX
SQuAD2 specifically includes unanswerable questions. This implementation compares
its null/CLS prediction against the best valid extractive span, using a fixed zero
logit margin, 384-token input, 128-token overlap and a 30-token maximum answer.
This policy is not tuned on V40 and is not a calibrated correctness probability.

All acquired, checked contiguous intervals participate, before MiniLM top-five
selection. Source gaps are not filled or crossed. A non-null candidate keeps the
original context unchanged; it never grants answer or edit authority. Only when
all evaluated intervals prefer null does enforcement emit empty sources/read_next
with `answer_not_found_in_acquired_context` and `corpus_absence_proven=false`.
Existing access/confirmation/source failures retain precedence. Limit/model errors
are distinct tool errors, never silent no-answer responses. No fallback to an
unbounded full-pool answer is introduced. The original gold remains unchanged.

English-only model. `DOCATLAS_ABSTENTION_LANGUAGE` is a host-declared language,
not automatic detection; languages other than `en` produce diagnostic `unknown`
and preserve context. This is not a claim of Russian answerability support.

The new real installed-MCP suite records positives, partials and strict-empty
negatives separately and requires every one of the forty unchanged cases to pass
before claiming semantic acceptance. RAM is measured with MiniLM and the server;
the test container enforces 1.5 GB with no extra swap. A quality failure blocks
promotion, not reporting. Do not enable by default based on a successful process
exit or on a handful of empty responses.
