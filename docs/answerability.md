# Local answerability gate (experimental, OFF by default)

This change distinguishes an operational failure from a learned prediction of no
answer in acquired, source-checked context. It does not prove corpus-wide absence,
validate an LLM answer, or promise that partial/multi-hop questions are complete.
**Do not enable enforcement in production without a passed semantic gate.**

`DOCATLAS_CONTEXT_ABSTENTION=observe` records a host-only diagnostic;
`enforce` applies the learned no-answer verdict, and `off` preserves all behavior.
Model assets must be explicitly provisioned before queries with
`python -m docmancer.docs.application.answerability_model /private/qa-model`.
Set `DOCATLAS_ABSTENTION_MODEL_DIR` to that absolute private directory.
Provisioning uses a fixed upstream revision. No network, training or model downloads
occur during queries. SHA-256 and file sizes are verified before ONNX loading.
The generated model manifest is trusted host configuration; protect it like the
existing local model directory. No arbitrary model paths are accepted from tools.

The CC-BY-4.0 RoBERTa-base SQuAD2 model is from deepset, converted by ONNX Community:
https://huggingface.co/deepset/roberta-base-squad2
https://huggingface.co/onnx-community/roberta-base-squad2-ONNX
The upstream revision prefix is fixed to `6d1aeed`; explicit provisioning records
its full revision and exact file hashes before inference. The quantized ONNX
model is evaluated under the same 1.5 GB process-container ceiling as the first
reader. Training and quantization are not performed in normal requests.

SQuAD2 includes unanswerable questions. The reader compares the null/CLS
prediction against the best valid extractive span, using a fixed zero margin,
384-token input, 128-token overlap and 30-token maximum answer. This policy is
not tuned on V40 and is not a calibrated correctness probability.

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

The installed-MCP suite records positives, partials and strict-empty negatives
separately and requires every unchanged V40 case to pass. Portable independent
controls cover positive/absent answers, observer transparency, declared Russian
unknown/pass-through, missing assets, empty acquisition and model-input overflow.
Linux/Python 3.11/3.13 and macOS/Python 3.12 controls do not stand in for the full
V40 matrix. Only Linux's container run enforces a hard 1.5 GB memory ceiling.

## Preserved negative result and next comparison

The initial distilled tinyroberta profile (tested code `336d6c43`) completed
all 40 real requests with zero operational errors: 8/8 correct refusals, but
17/24 positive and 6/8 partial cases retained their required evidence. There
were nine false refusals. Server/container peaks were 722/751 MB. This result
is NOT accepted and is not described as a product success. Artifact
`12009978017`, run `38813964649`, SHA256
`2d201d1d07c167313bcc62a0088f47e63e37dafa431f3bf9868827bfb66622aa`
preserves all responses and diagnostics; the old model receipt remains in
`answerability-model-receipt.json` and is historical, not the current profile.

A second comparison changes only the reader to the full RoBERTa-base SQuAD2
checkpoint. Query/corpus/source windows, margin zero, limits, expected spans
and evaluation rules stay fixed. Its result must be measured, not inferred
from model size or previous empty responses. It is a second development run
on known V40, not a fresh holdout. No threshold fitting or question rewriting.
