# Prompt 05 — Retrieval Quality, Evaluation and Observability

Ты — search/retrieval evaluation architect для documentation RAG и coding agents.

## Контекст

Docmancer использует:

- SQLite FTS5 lexical search;
- BM25 ranking;
- dense FastEmbed vectors;
- SPLADE sparse vectors;
- Qdrant;
- Reciprocal Rank Fusion;
- optional weighted RRF;
- hierarchical retrieval;
- query-aware routers;
- context packs with token budget;
- source attribution;
- `--explain` для per-source rank contributions.

Продукту нужно системно измерять retrieval quality, а не полагаться на demo cases.

## Задача

Спроектируй evaluation framework и observability слой для Docmancer retrieval.

## Что нужно выдать

1. **Query taxonomy for docs retrieval**
   - exact API signature;
   - config key / CLI flag;
   - conceptual guide;
   - migration/version-specific behavior;
   - error message;
   - code example;
   - multi-doc query;
   - project-aware dependency query.

2. **Golden dataset design**
   - Как собирать datasets.
   - Как размечать expected sources.
   - Как размечать expected answer / snippet.
   - Как учитывать versions.
   - Как избегать dataset bias.

3. **Metrics**
   - hit@k;
   - MRR;
   - nDCG if useful;
   - source attribution accuracy;
   - version correctness;
   - exact API signature correctness;
   - context pack compression quality;
   - task success rate;
   - latency;
   - token budget utilization.

4. **Evaluation of retrieval modes**
   - lexical;
   - dense;
   - sparse;
   - hybrid;
   - hierarchical;
   - routed retrieval.

5. **Reranker / query rewriting decision**
   - Когда нужен reranker.
   - Какие сигналы смотреть.
   - Как провести spike.
   - Как не усложнить local-first stack.

6. **Explain trace / observability schema**
   - Что должен возвращать query trace JSON.
   - Per-source scores/ranks.
   - Applied routers.
   - Expansion behavior.
   - Budget decisions.
   - Warnings/failures.

7. **Source health reports**
   - stale docs;
   - failed pages;
   - duplicate/canonical issues;
   - extraction quality;
   - empty/sparse pages;
   - vector/SQLite drift.

8. **CI quality gates**
   - Какие thresholds использовать.
   - Как не блокировать слишком агрессивно.
   - Как хранить baselines.
   - Как репортить regressions.

9. **Dashboard/report structure**
   - CLI report.
   - JSON report.
   - Optional dashboard/TUI.

10. **Implementation plan**
    - MVP.
    - v1.
    - v2.
    - Какие tests добавить.

11. **Risks and trade-offs**
    - Metric gaming.
    - Dataset bias.
    - Overfitting retrieval to benchmark.
    - Local-first constraints.

## Ограничения

- Не предлагай только LLM-as-judge без source-grounded deterministic metrics.
- Не ломай local-first/no-API-key default posture.
- Ответ должен быть применим к docs retrieval, а не generic web search.

## Формат ответа

Дай taxonomy table, metrics table, JSON schema examples и phased implementation plan. В конце дай `Must / Should / Could`.
