# 05 — Retrieval Quality, Eval and Observability Plan

## Goal

Turn retrieval quality from subjective demo quality into measurable, reproducible, source-grounded quality gates.

Evaluate at three levels:

1. **Retrieval** — did we retrieve the right sections?
2. **Packing** — did the context pack preserve required evidence within budget?
3. **Task outcome** — can the agent/user solve the docs task grounded in sources?

## Query taxonomy

| Class | Examples | Main metrics |
|---|---|---|
| Exact API signature | method/function/tool schema | Hit@1, MRR, signature correctness |
| Config key / CLI flag | `query.default_budget`, `--allow-degraded` | Hit@3, MRR, snippet accuracy |
| Conceptual guide | when/why/how questions | nDCG@5, Hit@5, task success |
| Migration/version-specific | changelog/version behavior | version correctness, nDCG@5 |
| Error message | `needs_docs_url`, Qdrant mismatch | Hit@3, MRR, attribution F1 |
| Code example | JSON/example usage | Hit@3, snippet accuracy |
| Multi-doc query | compare/synthesize commands | nDCG@10, source coverage |
| Project-aware dependency | docs for project version | version correctness, task success |

## Golden dataset design

Each item should store:

- query id;
- taxonomy class;
- corpus snapshot;
- version policy;
- project context, if any;
- expected sources;
- expected support spans;
- required facts;
- forbidden sources/versions.

Use TREC-style pooling across lexical/dense/sparse/hybrid/hierarchical to avoid benchmark bias.

## Metrics

| Metric | Purpose |
|---|---|
| Hit@k | Recall proxy |
| MRR | Known-item lookup quality |
| nDCG@k | Graded multi-result quality |
| Attribution Precision/Recall/F1 | Source grounding correctness |
| Version Correctness | Prevent wrong-version answers |
| Exact API Signature Correctness | Exact reference/API tasks |
| Context Pack Support Coverage@B | Required evidence survived packing |
| Context Pack Redundancy Rate | Budget waste |
| Pack Utility | Support coverage × non-redundancy |
| Task Success Rate | End-to-end usefulness |
| Latency p50/p95 | Operational cost |
| Token Budget Utilization | Packing behavior |

## Explain trace MVP

Add `--explain-json` or equivalent local JSON artifact with:

- query normalization;
- selected mode;
- routers matched/applied;
- lexical/dense/sparse candidates;
- fusion contributions;
- expansion decisions;
- packing decisions;
- warnings/failures;
- timing.

## Source health reports

Track per source/version:

- stale docs;
- failed pages;
- duplicates/canonical issues;
- extraction quality;
- empty/sparse pages;
- vector/SQLite drift;
- embedder mismatch;
- router health.

## CI gates

Start with soft gates, then hard gates once baselines stabilize.

Initial soft gates:

- overall Hit@5 drop > 1.5 percentage points;
- MRR drop > 0.02;
- version correctness below target;
- attribution precision below target;
- p95 latency grows > 20%;
- trace schema invalid.

Hard gates later:

- trace schema invalid on release branch;
- vector/SQLite drift in test corpus;
- severe version correctness regression;
- severe attribution regression.

## Phased plan

### MVP

- Define taxonomy.
- Define dataset schema.
- Offline evaluator for Hit@k/MRR/latency.
- `--explain-json` trace MVP.
- Basic source health.
- CLI/JSON eval reports.

### v1

- Graded labels + nDCG.
- Attribution/version/signature metrics.
- Pack utility.
- Routed/hierarchical slices.
- CI soft gates.
- Baseline diffing.

### v2

- Optional local reranker spike.
- Deterministic query rewrite heuristics.
- Optional OTEL export.
- Held-out rotation.
- Task harness for coding-agent flows.

## Reranker/query rewrite policy

Only consider reranker if:

- Hit@50 high;
- Hit@5/MRR low;
- gold exists in union candidates;
- pack/task metrics improve, not just raw retrieval.

Only consider query rewriting if:

- manual rewrite strongly improves project/context-sensitive queries;
- deterministic normalization is insufficient.

Do not add hosted API requirement to default local-first stack.

## First tests

- metric formula unit tests;
- trace schema validation;
- tiny-corpus integration tests for retrieval modes;
- version-policy scorer tests;
- signature scorer tests;
- packer support-coverage tests.
