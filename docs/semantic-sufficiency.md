# Local Semantic Sufficiency Checker: experiment, not evidence authority

This PR combines the lower-cost pinned `facet-guarded-v1` selector (product baseline from PR #226 at `cf8ed00b`) with a separate **local extractive QA** checker. It is opt-in, does not modify default product behavior, and is NOT a trained general sufficient-context entailment classifier.

## Threat model and hard limits

- The input is **only the current request's verified, admitted original source rows**. Full-pool comparison is against the same authorized pool, never against arbitrary filesystem paths or new searches.
- The model is the existing separately provisioned, SHA-verified `onnx-community/roberta-base-squad2-ONNX`, running CPU ONNX offline. No remote inference or model download at serving time.
- QA answer-span agreement/difference is a **hypothesis**, not semantic entailment, proof that every condition is covered, absence in the corpus or permission to answer.
- The checker does **not** change `answer_supported`, `answer_available`, refusal decisions, scope, citations or user-facing source text.
- A missing/corrupt model causes an explicit operational failure only if the experimental checker is enabled.
- At most 3 literal English question views are scored, with existing QA 64-token query bound, 45-second per-request control and explicit unknown for unscored/unsupported views. Exceeding the budget is **not** silently treated as complete.
- Older QA enforcement attempts #216 and #218 removed useful evidence and failed acceptance. **This checker must not be enabled as answer/no-answer authority.**

## Variants and mechanism

Configure the existing section compression and verified model paths, with the strict model view:

```sh
DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
DOCATLAS_MINILM_MODEL_DIR=/absolute/path/to/verified/minilm
DOCATLAS_SUFFICIENCY_MODEL_DIR=/absolute/path/to/verified/qa
DOCATLAS_MCP_MODEL_VIEW=1
DOCATLAS_SECTION_SELECTION=semantic-audit-v1
```

Compare the modes:

- `facet-guarded-v1`: **recommended control**. The pinned #226 facet selector, no QA call. It already preserves 53/53 documented cases on the known 64-question regression data with substantially lower context than fixed5.
- `semantic-audit-v1`: assess best answer-span hypotheses for a bounded number of query views on the already-selected context vs all permitted candidates. No selection change; only private diagnostic observations. The model might find a different plausible span despite full factual coverage.
- `semantic-rescue-v1`: if the QA hypotheses differ, append the source group containing the full-pool QA answer; admitted sources only. This can add irrelevant material and must be rejected when no independent fact gain occurs.
- `semantic-prune-v1`: limited counterfactual removal for at most two selected groups, only when source-coordinate QA spans for all checked views remain stable and none were unscored. A stable short answer span does NOT prove preservation of caveats or exceptions; never deploy without a strong independent no-regression gate.

The preexisting `facet-bundled-cover-v1` remains as an independent control/rollback from earlier #227, but had +11.19% known-data context vs fixed5. It does not establish semantic sufficiency.

## Evaluation (independent of the model)

- Existing V40, New16, Fresh8: 64 questions with **97 previously defined witness groups**, 53 documented (full or partial), 11 no-answer.
- Newly authored **SeleneMesh12**, committed with frozen source and oracle *before first model execution* at `0d7b205`: 9 full, 1 partial, 2 no-answer, **36 independent required witness groups**. This is a new byte-distinct synthetic project but shares several technical question templates with Fresh8; it is not real-world out-of-domain validation.
- Real installed wheel, pinned MiniLM and QA models, real SQLite, offline public stdio MCP, no mocks, independent original-span and citation checking.
- Quality gate: **no individual required witness loss** vs the same selected-source baseline; then complete-answer evidence rate, strict no-answer, o200k model-visible text tokens and per-request CPU latency. Gold is never provided to selection or QA.
- Full provider token usage and end-to-end generated strong-model answer quality **remain unmeasured**. A previously prepared replay was blocked by missing OPENAI_API_KEY. No such results may be inferred from visible-context token counts.
- Experiment links:
  - Known data: https://github.com/Vanilla1999/DocAtlas/actions/runs/40231001028
  - Frozen new data: https://github.com/Vanilla1999/DocAtlas/actions/runs/40231394528

Do not merge or switch defaults on these diagnostic results alone. If QA does not improve independent witness completeness enough to compensate for CPU/time/token overhead, keep the original compact facet selector. Never confuse an empty QA answer span with proven documentation absence.
