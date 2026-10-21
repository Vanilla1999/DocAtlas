# Answerability: reference parity and QNLI pilot

Base: `f8e17489733798c731f6b9c555adaee48b92fbf3` (merged #216). No product/default changes.

## Frozen before inference

1. Reference arm: use the current RoBERTa quantized ONNX reader, capture its real
   logits, and compare actual paired token IDs/masks with Transformers 4.57.1
   AutoTokenizer. Refuse to compare mismatched features. Apply that release's
   exact `utils_qa.py` (Git blob `b30322b0071fff2f919bb0b2c48a77513430b6b4`)
   separately to each existing contiguous source context. A QA example's windows
   are not confused with independent documents. Save all features and logits.
2. QNLI arm: `cross-encoder/qnli-electra-base`, revision prefix `c7dea87`, official
   `onnx/model_quint8_avx2.onnx`, Apache-2.0. Provisioning resolves the full immutable
   revision and freezes every file's size/SHA-256 before offline inference.
   The trained sigmoid classifier uses its native binary class boundary
   (argmax of logits `[0, z]`), not a threshold chosen from V40.
   An exact tie is unknown. Query/context are supplied directly, never converted
   into fabricated declarative claims for an unrelated NLI model.

Each arm scans all existing admitted contiguous contexts. QNLI uses native
512-token overlapping windows; QA reference retains current 384/128/30
postprocessing settings. These are explicit input/decoding policies, not hidden
question-specific rules. No query splitting, keyword rescue, library bonuses,
manual synonym dictionaries, top-k acquisition filtering, or V40 calibration.

## Execution boundary

Reuse `eval/answerability_integration.py` with a process-local experimental reader
adapter. This replaces the reader with an actual learned model/reference decoder,
not a mock. Installed wheel, SQLite, retrieval, source checks, final MiniLM section
compression and actual public MCP stdio delivery are unchanged. The production
answerability entry point is not edited. This does NOT ship a production reader.

Per arm: five real source/catalog preparations, 40 compression-only baseline
context requests, 40 experimental gated stdio requests. Original V40 gold is
loaded only after all results. Baseline equality, source integrity and read-only
checks remain mandatory. Native tokenization parity and original/reference
verdict differences are logged separately. No LLM answer generation is claimed.

All final wire replies are evaluated by the unchanged original oracle. Success
requires 24/24 positive, 8/8 partial and 8/8 strict-empty; no false refusals.
Every run's failure stays visible. A supported span/candidate only means not to
refuse; it does NOT prove completeness. No-answer never proves corpus absence.
The experiment cannot turn a binary model into a verified four-class
full/partial/unknown/absent classifier. Do not claim it has done so.

Inference runs CPU-only, network-disabled, hard 1,500,000,000-byte memory cap,
no extra swap; all time and memory measured including product/client. Build and
provisioning are separate online stages. No models/credentials are uploaded.
This is a known development regression set; passing it alone is not holdout or
multilingual acceptance. No default enablement or main merge is authorized here.

## Sources

- https://huggingface.co/cross-encoder/qnli-electra-base
- https://huggingface.co/cross-encoder/qnli-electra-base/tree/main/onnx
- https://github.com/huggingface/transformers/blob/v4.57.1/examples/pytorch/question-answering/utils_qa.py

The QNLI model card explicitly describes a question/paragraph task. It supplies
no guarantee of DocAtlas multi-part or corpus-wide no-answer accuracy.
