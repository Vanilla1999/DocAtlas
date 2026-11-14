# Selection alternatives from main, with a shared 1.5 GB limit

## Contract frozen before inference

Base: main `439815771b96edc77a12f42f90f1fecb35f5e5d7`. This is not stacked on
#230, #231 or #232. Main already defaults to provisioned MiniLM plus
`facet-guarded-lexical-v2`; fixed-five is an explicit rollback, not the current
default. MiniLM is a local relevance scorer. LiteLLM is a provider SDK/proxy,
not this model and not a solution to evidence completeness.

No default changes, new dependencies, source rewriting, permission changes,
second critic, automatic downloads, hidden paid calls or new 3,000-token cap.
The existing native source validation, question limit and 12k machine-packet
boundary remain. In particular, the initial MiniLM query length check still
runs BEFORE these optional proposals; this experiment does not fix long-query
failures by silently shortening the original question.

## Five comparisons

| Policy | Selection decision |
|---|---|
| main | Existing provisioned MiniLM/facet-guarded-lexical-v2 |
| fixed | Existing fixed-five rollback (legacy grouping) |
| adaptive-gap-v1 | Existing gap-based Adaptive-k, with the same Markdown-owner grouping as main |
| facet-tiny-select-v1 | MiniLM initial score, then one Qwen3-0.6B proposal of original section IDs |
| facet-tiny-plan-v1 | MiniLM initial score, then one query-only English decomposition by Qwen3-0.6B; union of existing Adaptive-k selections per query view |

Tiny proposals have no semantic acceptance status. A plan is not a proof that
all question requirements have been found. The original full-question ranking
is retained in the query-plan union. There are no new product word lists or
query-specific score thresholds. Existing main lexical fallback remains
explicit when a proposal is unusable, invalid, incomplete or over capacity.
The existing scoring pair/time budgets still bound reranking; an abandoned
plan can consume that budget and can therefore still end in an explicit error.
The model sees supplied source provenance in select mode and only the question
in plan mode. Returned sources are the original main rows, revalidated after
selection. Generated queries are not turned into documentary evidence.

## Research motivation, not borrowed guarantees

- Taguchi et al., Adaptive-k, EMNLP 2025:
  https://aclanthology.org/2025.emnlp-main.1017/
  motivates query-dependent evidence counts instead of fixed top-k. We reuse
  main's existing gap code on MiniLM logits; this is not a calibrated probability
  or reproduction of the paper's embedding-model results.
- Khot et al., Decomposed Prompting:
  https://arxiv.org/abs/2210.02406
  motivates assigning question decomposition and retrieval to different
  components. Our one-pass query-only planner is a small adaptation, not the
  paper's complete iterative prompting framework or its reported accuracy.
- Official model and immutable GGUF revision:
  https://huggingface.co/Qwen/Qwen3-0.6B-GGUF
  `1eaf4d9657fe65ad10a51eab76a8db5b363bddaa`, Q8_0,
  SHA256 `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.

Learned token pruning/abstractive compression are not included: changing the
source representation would introduce a separate attribution contract. A
new calibrated stopping classifier needs independent training/calibration
labels; adding an uncalibrated score threshold is not that classifier.

## Memory is a whole-stack constraint

Every measured arm runs offline under one Docker cgroup with **1,500,000,000
bytes**, **zero swap** and **two CPUs**. This includes preparation, SQLite,
Python driver, MCP service, MiniLM and, in tiny arms only, llama-server. It is
not 1.5 GB per process, not a weights-file-size estimate, and not a virtual
memory limit. memory.max, memory.peak, memory.swap.max, memory.events, Docker
exit and OOM flags are retained. An OOM or killed subprocess is a failure, never
an efficient empty answer. Image building and downloads occur before runtime
and are not claimed to fit this working-memory limit.

Qwen is explicitly provisioned, not automatically installed by the library.
Main/non-tiny arms never start its server. The experiment uses one slot,
2,048-token model context, batch/microbatch 64 and 256 maximum output tokens.
This context limit protects local memory; it is not a new limit on DocAtlas
evidence delivery. Overlarge model requests fall back without truncation.
Startup time is recorded separately; per-request observations are warm-server
measurements, not a production latency guarantee. Deployments outside this
container must apply the same shared resource policy themselves.

## Evaluation

V40 and dependencies remain unchanged. Historical L10 (10 questions, 21
requirements) is copied byte-for-byte for regression. Fresh LM08 adds eight
same-author synthetic questions and 17 requirements, including languages,
conditions, cross-file prerequisites, versions and alternative witnesses. It
resembles the failure families already discussed: it is exploratory coverage,
NOT blind independent generalization. All input/gold hashes are frozen before
inference; expected facts are read only after delivery. No model tuning after
viewing the scores is part of this experiment.

Each arm uses an installed non-editable wheel, real public project preparation,
real SQLite and public stdio get_docs_context. Upstream admitted pool responses
are recorded to distinguish pool misses from selection/budget misses. Returned
source rows must equal admitted rows, with original bytes/coordinates and
provenance; source files and logical SQLite state must be unchanged. Gold
permits independently adequate alternatives, not mandatory redundant files.

All errors and their text tokens are retained. Token comparisons must use
matched successful requests and separately disclose failures, not reward
errors. A green measurement job means the infrastructure and source invariants
ran successfully; quality regressions remain failures in the report.

Measured: original-witness coverage, new losses versus main, complete MCP
model-view text in o200k tokens, latency, proposal/fallback rates and shared
cgroup peak/OOM. NOT measured by this offline workflow: generated paid-model
answers, correct unknowns, provider input/output/cached usage, billed savings
or autonomous OpenCode conversation time. Local generative tokens are diagnostic
only, not the optimization target. Unknown queries are never successful 0/0
answers. Actual paid tokens and end-to-end time remain a separate acceptance
requirement; source coverage cannot substitute for that experiment.

## Runtime opt-in

With an explicitly provisioned MiniLM directory and loopback llama.cpp server:

```sh
export DOCATLAS_SECTION_SELECTION=facet-tiny-plan-v1
export DOCATLAS_TINY_URL=http://127.0.0.1:8099
export DOCATLAS_TINY_MODEL=docatlas-tiny
```

Use `facet-tiny-select-v1` for the other proposal. Removing the policy restores
main's default. DOCATLAS_CONTEXT_COMPRESSION=off still disables the whole stage;
this experiment does not override that host choice.
