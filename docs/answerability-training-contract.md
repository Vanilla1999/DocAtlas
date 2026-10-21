# Decision: train for technical context, not extractive QA null prediction

Status: **historical proposal, paused; no training run is scheduled**.
The current direction is source-language preflight and evidence-based answers
without new model training; see `documentation-language.md`.
Baseline main: `f8e17489733798c731f6b9c555adaee48b92fbf3`.
Related: #217 and negative experiments #216/#218. Runtime inference limit remains
1,500,000,000 bytes for DocAtlas + both models + client, CPU and offline.
Training resource availability is not assumed; no paid service is authorized here.

## Decision and non-goals

Keep MiniLM whole-acquired-section selection and compact delivery. Remove the
failed generic QA reader's authority to delete sources; keep diagnostics for
reproduction. Do not try another checkpoint or another threshold on V40.
No keyword dictionaries, query-type rules, library exceptions, forced neighbors,
hindsight ensembles, or hidden fallback to a full unbounded context.

The next learning target is the information actually supported by a checked
technical source bundle, not whether an extractive reader can select a short
contiguous phrase. This is a hypothesis to test, not a guarantee of success.

## Labels and authority

Human-reviewed training labels: `supported`, `partial`, `unsupported_in_context`.
Labels refer only to the explicitly enumerated acquired source bundle. Missing
information in that bundle never proves absence from an entire repository.

- Supported: all requested facts are backed by original source spans.
- Partial: at least one requested fact has support, and at least one does not.
  Preserve useful sources; never train a partial case as an empty-answer target.
- Unsupported in context: no requested fact has supporting evidence in the
  enumerated bundle. A plausible but unrelated span is a hard negative.

`unknown` is an operational/uncertainty state, not a dishonest replacement for
missing gold labels. Runtime errors, unsupported language, incomplete scans and
unvalidated prediction confidence do not license a semantic refusal. Model
outputs never grant edit authority. Source/scope/version validation retains
precedence regardless of classifier prediction.

Annotation may include requested facts and their evidence. Those annotations
are training/evaluation targets, never extra runtime input. Do not introduce a
hand-written query splitter or pass hand-labelled claims into deployment.

## Required record (no fabricated annotations)

Each versioned record must include:

```json
{
  "id": "unique-id",
  "project": "canonical-upstream-project",
  "revision": "immutable-commit",
  "language": "en",
  "split": "train",
  "question_family": "shared-original-and-paraphrases-id",
  "question": "original query",
  "sources": [{"id": "s1", "path": "docs/example.md", "sha256": "...", "text": "..."}],
  "annotation": {
    "label": "partial",
    "requested_facts": [
      {"text": "fact requested by the query", "support": [{"source_id": "s1", "start": 0, "end": 10}]},
      {"text": "another requested fact", "support": []}
    ],
    "scope_review": "review of the entire supplied bundle",
    "reviewer": "actual reviewer identity",
    "review_status": "accepted"
  }
}
```

The example is a schema illustration, not accepted training data. Byte/span
checks can verify attribution but cannot create correct semantic labels. Reject
missing reviewer attribution or invented reviewer approvals. Author-generated
examples remain proposals until independent review; no such review is claimed.
Randomly pairing a query with another document is not automatically a validated
negative. In particular, numerical guarantees may be explicitly documented, so
words like "guarantee", "exactly", "maximum" cannot define refusal labels.

## Data separation before any optimization

Split by upstream project before generating windows/paraphrases. All versions,
translations, duplicated text and question variants of a source family remain
in one partition. Check source hashes, canonical projects and question-family IDs
across train, calibration and sealed test. Record exclusions and duplicates.
Include English and Russian records in each relevant held-out category before
claiming that language is supported. A Russian unknown/pass-through control does
not qualify as Russian semantic accuracy.

V40 questions, answers, source families, paraphrases and failure reports are
regression-only: exclude them from training and threshold/calibration selection.
V40 has been repeatedly inspected; it cannot be described as an unseen holdout.
Do not use the old QA/QNLI verdicts as gold for the new learner.

## Small model and reproducibility

Use a compact encoder and learned aggregation of evidence, trained against the
above targets. Independently ranked windows plus `max(score)` is not assumed to
solve multi-part questions. The model input is only the original question and
checked source text; preserve gaps and do not synthesize evidence.
Freeze the architecture, input coverage policy and data split before looking at
held-out predictions. Record seed, exact tokenizer/weight hashes, package lock,
CPU features, execution provider, graph options and model-input IDs. Compare
reference-precision and exported inference on identical inputs. Report any label
changes, rather than selecting an implementation based on the known answers.
Keep example-level inputs/logits under the approved data privacy policy.

First deliverable is a data/label audit and a reproducible training experiment,
not a production default. Actual model size, ONNX export and inference memory
must be measured; parameter count alone does not certify the 1.5 GB limit.

## Acceptance order

1. Dataset review/split audit, then one frozen training configuration on training
   data only. Calibrate only on a separate partition, not V40 or the final test.
2. Check export/runtime agreement before semantic testing. Resolve numerical
   drift or quantify it with repeatability tests; no runtime-specific V40 tuning.
3. Run installed public MCP with real SQLite and unchanged source validators.
   V40 must keep 24/24 positive and 8/8 partial while refusing 8/8 unsupported.
   Count operational errors separately; unknown is not a successful refusal.
4. Evaluate sealed project-disjoint EN/RU data. Report every confusion count,
   false-refusal rate, unknown rate and confidence intervals. Zero observed false
   refusals on a finite dataset is not a guarantee of zero future errors.
5. Prove CPU/offline peak memory <=1.5 GB, exact client token cost, source and
   permission invariants. Require explicit review for any production enforcement.

A successful observation-safety CI does NOT satisfy items 1-5. A model that passes
through everything still scores 0/8 for V40 refusal. A model that always refuses
fails the useful-context checks. Preserve both negative results without weakening
the benchmark. No new model is trained or certified by this document.

Research motivation (not a resource-compatible ready-made solution): Joren et al.,
*Sufficient Context: A New Lens on Retrieval Augmented Generation Systems*,
ICLR 2025, distinguishes sufficient from useful-but-insufficient context:
https://proceedings.iclr.cc/paper_files/paper/2025/hash/33dffa2e3d2ab74a783d1a8c292f66d9-Abstract-Conference.html
The three-label technical-data design and training gate above are our proposed
adaptation; the paper does not certify our classifier or memory envelope.
