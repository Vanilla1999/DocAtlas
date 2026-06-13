# Benchmark plan — Docmancer MCP vs Context7

## Цель

Сравнить **Docmancer MCP Docs** и **Context7** на задачах, которые реально выполняет coding agent: быстро получить релевантный, версионно-точный и компактный контекст из документации, не загрязняя ответ лишними страницами и не полагаясь на память модели.

Бенчмарк должен отвечать не на вопрос «кто нашёл хоть что-то», а на вопросы:

- какой инструмент чаще возвращает правильный источник в top-K;
- какой инструмент лучше помогает агенту ответить или написать код;
- где Docmancer выигрывает за счёт local-first, exact-version и project-aware контекста;
- где Context7 выигрывает за счёт hosted corpus, zero-setup UX и snippet presentation;
- какие продуктовые gaps Docmancer нужно закрыть, чтобы стабильно превосходить Context7 в своих wedge-сценариях.

## Основные гипотезы

### H1 — Public docs / quick lookup

На популярных публичных документациях Context7 будет силён за счёт готового hosted индекса и чистых snippets. Docmancer должен быть сопоставим по retrieval quality после ingest, но может проигрывать в first-run setup time.

### H2 — Project-aware exact versions

Docmancer должен выигрывать, когда вопрос зависит от версии зависимостей проекта, потому что MCP может читать lockfiles/manifests и выбирать документацию конкретной версии. Context7 чаще работает как latest/general docs lookup.

### H3 — Project-owned docs + library docs

Docmancer должен выигрывать, когда ответ требует объединить README/docs/ADR/wiki проекта с внешней библиотечной документацией. Это основной дифференциатор против Context7.

### H4 — Offline / repeated agent loop

После первичного indexing Docmancer должен выигрывать в repeated-query latency, offline readiness и стоимости повторного доступа к документации.

### H5 — Context efficiency

Docmancer должен выигрывать по token efficiency, если context pack отдаёт компактные, source-grounded sections вместо длинных raw pages. Это нужно измерять отдельно от hit-rate.

## Benchmark suites

### Suite A — Public docs retrieval parity

Проверяет честный baseline на популярных публичных документациях.

Кандидаты:

- Riverpod / Flutter Riverpod;
- FastAPI;
- Next.js;
- pytest;
- SQLAlchemy;
- Supabase.

Для каждого пакета подготовить 10–20 запросов:

- API usage: «как использовать X»;
- lifecycle/edge cases: «когда вызывается cleanup/dispose»;
- migration: «как мигрировать с old API на new API»;
- error handling: «почему возникает ошибка Y»;
- examples: «дай минимальный пример для Z».

Ожидаемый результат:

- expected source URLs;
- required facts;
- forbidden facts/version leaks;
- expected code/API symbols.

### Suite B — Exact-version dependency docs

Проверяет сценарий, где Docmancer должен иметь преимущество.

Пример на Flutter/Dart:

- взять проект с `pubspec.lock`;
- определить версии `flutter_riverpod`, `hooks_riverpod`, `riverpod_annotation`, `riverpod_generator`, core `riverpod`;
- индексировать конкретные Dartdoc pages по версии, а не только latest guides.

Примеры запросов:

- «какой API у `AsyncNotifier` в версии 2.6.1?»;
- «есть ли Riverpod 3.0 feature в текущем проекте?»;
- «как использовать `WidgetRef.listen` в версии из lockfile?»;
- «какой generator annotation доступен в `riverpod_annotation` версии проекта?».

Scoring должен штрафовать:

- ответы из latest docs, если версия проекта другая;
- ссылки на Riverpod 3.0 для проекта на 2.6.x;
- отсутствие version metadata в результате.

### Suite C — Project docs + library docs

Проверяет комбинацию локальной документации проекта и внешних docs.

Нужен fixture/project с:

- `README.md`;
- `docs/architecture.md`;
- ADR или roadmap;
- lockfile/manifests;
- внешней библиотекой, документация которой нужна для ответа.

Примеры запросов:

- «как в этом проекте добавить feature X с учётом нашей архитектуры и Riverpod?»;
- «какой слой должен вызывать API client согласно docs проекта и FastAPI/httpx docs?»;
- «какой testing подход использовать здесь, учитывая CONTRIBUTING.md и pytest docs?».

Scoring:

- ответ должен включать минимум один project-owned source и один library source;
- forbidden: ответ только из внешней документации без учёта проекта;
- required facts из project docs должны быть найдены в retrieved context.

### Suite D — Agent task completion

Retrieval metrics важны, но конечная цель — помогает ли инструмент агенту выполнить задачу.

Формат:

1. дать агенту одинаковую coding task;
2. разрешить использовать только один docs provider: Docmancer MCP или Context7;
3. агент меняет код;
4. запускаются tests/lints;
5. оценивается качество решения.

Примеры задач:

- добавить Riverpod provider с `autoDispose` и корректным keepAlive/cache lifecycle;
- написать FastAPI endpoint с dependency injection и error response;
- добавить pytest fixture parametrization;
- мигрировать deprecated API на актуальный API версии проекта.

Метрики:

- task success rate;
- tests passed;
- number of tool calls;
- total wall-clock time;
- docs tokens consumed;
- hallucinated API rate;
- number of correction loops.

### Suite E — Operations / DX / reliability

Проверяет не только retrieval quality, но и эксплуатацию.

Сценарии:

- cold start: первый запрос к новой библиотеке;
- warm start: повторные запросы после ingest/index;
- offline query после отключения сети;
- stale docs refresh;
- failed ingest diagnostics;
- multiple versions of same package;
- registered source lookup without повторного docs_url.

Метрики:

- setup time;
- index time;
- first useful answer time;
- p50/p95 query latency;
- failure clarity score;
- required user actions count;
- whether tool gives next_actions/candidates when source resolution is ambiguous.

## Metrics

### Retrieval quality

- **Hit@1 / Hit@3 / Hit@5** — expected source найден в top-K.
- **MRR** — насколько высоко первый релевантный результат.
- **NDCG@K** — если есть graded relevance.
- **Required facts recall** — доля обязательных фактов, найденных в retrieved context.
- **Forbidden facts leakage** — наличие версионно неверных или запрещённых фактов.
- **Unique sources@K** — разнообразие источников в top-K.
- **Redundancy rate** — сколько top-K секций повторяют одну и ту же страницу/идею.
- **Locale contamination rate** — доля результатов из нежелательных locale/translation paths.

### Agent usefulness

- **Answer correctness** — human или LLM-as-judge по rubric, но с обязательной проверкой источников.
- **Code example usability** — можно ли напрямую применить snippet.
- **API symbol accuracy** — не выдуманы ли классы/методы/параметры.
- **Task success rate** — прошли ли tests/lints после coding task.
- **Correction loops** — сколько раз агенту пришлось исправлять решение из-за плохого docs context.

### Performance and cost

- **Cold start time** — resolve + fetch/index + first answer.
- **Warm query latency p50/p95**.
- **Docs tokens returned**.
- **Raw docs tokens equivalent**.
- **Token savings %**.
- **Tool calls per answer**.
- **Network dependency** — online-only vs offline-ready.

### Product/DX

- **Zero-setup score** — насколько быстро пользователь получает первый полезный результат.
- **Diagnostics quality** — есть ли actionable next steps.
- **Version metadata quality** — requested/resolved/exact/stale.
- **Source attribution quality** — URL, title, section, version, project/file path.
- **Reproducibility** — можно ли сохранить snapshots и повторить прогон.

## Golden dataset format

Каждый benchmark item должен быть машинно проверяемым.

```yaml
- id: riverpod_ref_listen_261
  suite: exact_version_dependency_docs
  library: riverpod
  ecosystem: pub
  project_fixture: fixtures/flutter_riverpod_261
  query: "How should WidgetRef.listen be used in this project version?"
  expected_sources:
    - "https://pub.dev/documentation/flutter_riverpod/2.6.1/flutter_riverpod/WidgetRef/listen.html"
  required_facts:
    - "WidgetRef.listen observes provider changes"
    - "The answer must be valid for flutter_riverpod 2.6.1"
  forbidden_facts:
    - "Riverpod 3.0-only APIs"
  expected_symbols:
    - "WidgetRef.listen"
  version:
    requested: "2.6.1"
    must_be_exact: true
```

## Execution protocol

### 1. Prepare corpora

For each library/project:

1. register or prefetch Docmancer docs;
2. resolve matching Context7 library ID;
3. save source metadata:
   - library ID;
   - docs URL;
   - version;
   - page/snippet count if available;
   - ingest/index timestamp.

Important: for key packages, prefer concrete class/API pages as `docs_url` or seed URLs, not only package root pages. This is especially important for Dartdoc-like sites where root pages are weak entry points.

### 2. Run retrieval benchmark

For each golden query:

1. query Docmancer MCP with fixed `limit`, `tokens`, `version`, `project_path` where applicable;
2. query Context7 with comparable topic/query;
3. persist raw outputs as snapshots;
4. normalize results into a common schema;
5. score using the same evaluator.

Common result schema:

```json
{
  "provider": "docmancer|context7",
  "query_id": "...",
  "results": [
    {
      "rank": 1,
      "url": "...",
      "title": "...",
      "section": "...",
      "content": "...",
      "version": "...",
      "tokens": 900
    }
  ],
  "latency_ms": 1234,
  "tool_calls": 1,
  "failures": [],
  "degraded_mode": false
}
```

### 3. Run answer benchmark

Use одинаковый prompt template:

```text
Answer the user question using only the documentation context returned by <provider>.
If the docs do not contain enough information, say what is missing.
Question: <query>
```

Score:

- required facts present;
- forbidden facts absent;
- cites/uses correct sources;
- no hallucinated APIs;
- concise enough for agent use.

### 4. Run coding-agent benchmark

Use isolated repo fixtures and deterministic commands:

1. reset fixture repo;
2. run agent with Docmancer-only docs access;
3. collect patch, tests, logs;
4. reset fixture repo;
5. run same agent with Context7-only docs access;
6. compare outcomes.

To reduce noise:

- same model;
- same temperature/settings;
- same max tool calls;
- same time budget;
- no WebFetch fallback unless both providers get it explicitly.

## Fairness rules

- Context7 and Docmancer must receive semantically equivalent queries.
- If Docmancer is tested in project-aware mode, the benchmark must clearly label that Context7 does not have the same project metadata unless manually provided.
- If Context7 has hosted corpus ready and Docmancer needs indexing, report both cold-start and warm-start numbers instead of mixing them.
- Do not compare latest Context7 docs against exact-version Docmancer docs without scoring version mismatch explicitly.
- Persist all raw provider outputs for auditability.
- Use the same top-K and token budget where possible.

## Reporting template

For each suite:

| Metric | Docmancer MCP | Context7 | Notes |
|---|---:|---:|---|
| Hit@1 | | | |
| Hit@5 | | | |
| MRR | | | |
| Required facts recall | | | |
| Forbidden facts leakage | | | |
| Unique sources@5 | | | |
| p50 latency | | | |
| p95 latency | | | |
| Setup/cold-start time | | | |
| Tokens returned | | | |
| Task success rate | | | |

Then add qualitative findings:

- where Context7 wins;
- where Docmancer wins;
- which misses are corpus/source hygiene problems;
- which misses are retriever/reranker problems;
- which misses are product UX problems.

## Initial milestone plan

### Milestone 1 — Make Riverpod benchmark reproducible

- Convert existing Riverpod manual comparison into golden YAML + snapshots.
- Persist Context7 outputs instead of only manual notes.
- Score both providers with the same evaluator.
- Add metrics missing from the first report:
  - token counts per query;
  - unique sources@K;
  - locale contamination;
  - forbidden Riverpod 3.0 leakage.

### Milestone 2 — Add exact-version Dartdoc benchmark

- Build fixture around Flutter/Riverpod 2.6.x lockfile.
- Index concrete Dartdoc class/library pages for key packages.
- Add version-sensitive queries.
- Verify Docmancer returns exact version metadata and avoids latest-only answers.

### Milestone 3 — Add project-owned docs benchmark

- Create or select a project fixture with README/docs/ADR.
- Add queries requiring both project docs and library docs.
- Measure whether retrieved context includes both source types.

### Milestone 4 — Add coding-agent tasks

- Define 3–5 small deterministic tasks.
- Run same model with Docmancer-only and Context7-only docs access.
- Score with tests/lints and hallucinated API checks.

### Milestone 5 — Publish comparison report

- Produce `eval/context7_docmancer_benchmark_report.md`.
- Include raw artifacts under `eval/results/`.
- Turn findings into roadmap PRs.

## Known risks

- Context7 may not expose all metadata needed for exact version scoring.
- Hosted Context7 corpus can change over time; snapshots are required.
- LLM-as-judge can be noisy; prefer deterministic source/fact checks first.
- Coding-agent benchmarks are model-sensitive; report model/settings and repeat runs.
- Docmancer cold-start includes indexing cost; report cold and warm separately.

## Success criteria

The benchmark is useful when it can produce:

1. reproducible raw outputs for both providers;
2. objective retrieval and version metrics;
3. at least one public-docs parity suite;
4. at least one exact-version suite where Docmancer's core advantage is tested;
5. at least one project-docs suite where Context7 cannot trivially substitute local context;
6. a prioritized list of Docmancer fixes backed by measured failures.
