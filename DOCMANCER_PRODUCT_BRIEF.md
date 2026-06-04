# Docmancer: функциональная выжимка и контекст для планирования развития

Цель этого документа — дать сильной модели сжатый, но достаточно полный контекст по текущему состоянию Docmancer, чтобы она могла наметить дальнейший план развития продукта, архитектуры и UX.

## 1. Короткое позиционирование

**Docmancer** — локальный инструмент для превращения документации в компактный, source-grounded контекст для coding agents.

Он умеет:

- индексировать локальные файлы и публичные docs-сайты;
- искать по ним через CLI или MCP;
- возвращать не сырые страницы, а компактные context packs с атрибуцией источников и оценкой экономии токенов;
- работать локально без hosted query API;
- использовать гибридный retrieval: SQLite FTS5 + dense vectors + sparse vectors;
- устанавливать agent skills для популярных coding-agent окружений;
- отдельно предоставлять MCP runtime для version-pinned API tool packs.

Ключевая идея: **агент тратит контекст на работу с кодом, а не на перечитывание полной документации**.

## 2. Основные пользовательские сценарии

### 2.1. Локальный docs-RAG для coding agents

Пользователь индексирует документацию:

```bash
docmancer setup
docmancer ingest ./docs
docmancer add https://docs.example.com
```

Затем агент или пользователь задаёт вопрос:

```bash
docmancer query "How do I authenticate?"
```

На выходе получается компактный context pack:

- релевантные sections, а не целые страницы;
- source URLs / paths;
- heading paths;
- token estimate;
- token savings относительно сырых документов;
- agentic runway multiplier.

### 2.2. Индексация публичных docs-сайтов

Поддерживаются:

- GitBook sites;
- Mintlify sites;
- generic web docs;
- GitHub repositories;
- docs с `llms-full.txt`, `llms.txt`, `sitemap.xml`, nav crawling;
- опционально Playwright browser fallback для JS-heavy сайтов.

Команда:

```bash
docmancer add https://docs.pytest.org
```

Опции:

- `--provider auto|gitbook|mintlify|web|github`;
- `--strategy llms-full.txt|sitemap.xml|nav-crawl`;
- `--max-pages <n>`;
- `--browser`;
- `--fetch-workers`.

### 2.3. Индексация локальных файлов

Поддерживаемые форматы:

- Markdown;
- text;
- HTML;
- PDF;
- DOCX;
- RTF.

Команда:

```bash
docmancer ingest ./path/to/docs
```

Опции:

- `--include <glob>`;
- `--exclude <glob>`;
- `--format <format>`;
- `--recursive / --no-recursive`;
- `--skip-known`;
- `--recreate`;
- `--no-vectors`.

### 2.4. Agent integration

`docmancer setup` умеет устанавливать skill files / инструкции для агентских окружений.

В README заявлена поддержка:

- Claude Code;
- Cursor;
- Codex;
- Cline;
- Claude Desktop;
- Gemini;
- GitHub Copilot;
- OpenCode.

Agent guidance сводится к правилу: когда нужен контекст документации, агент сначала смотрит локальный индекс Docmancer, а не полагается на model memory или latest hosted docs.

### 2.5. Context7-style MCP docs server

Есть отдельный MCP режим для library docs:

```bash
docmancer mcp docs-serve
```

Инструменты MCP docs server:

- `resolve_library_id`;
- `get_library_docs`;
- `refresh_library_docs`;
- `prefetch_library_docs`;
- `prefetch_project_docs`;
- `list_library_docs`;
- `get_docs_job_status`;
- `list_docs_jobs`;
- `cancel_docs_job`.

Docs server использует тот же локальный ingest/index/query path, что и CLI, плюс registry библиотек в SQLite.

Особенности:

- stale docs считаются те, которые никогда не refresh-ились или старше 30 дней;
- `get_library_docs` refresh-ит stale docs перед query;
- `force_refresh: true` принудительно refresh-ит даже fresh docs;
- для unknown library нужно явно передавать `docs_url`; сервер не угадывает URL документации.

Пример:

```json
{
  "library": "pytest",
  "topic": "parametrize fixture",
  "docs_url": "https://docs.pytest.org/"
}
```

### 2.6. Versioned documentation

Docs MCP умеет хранить разные версии одной библиотеки как отдельные entries:

- `go_router@14.8.1`;
- `go_router@16.2.0`;
- `go_router@latest`;
- `flutter-api@stable`;
- `flutter-api@main`.

Для prefetch нескольких версий используется:

```json
{
  "library": "go_router",
  "ecosystem": "pub",
  "versions": ["14.8.1", "15.0.0", "16.2.0", "latest"],
  "docs_url_template": "https://pub.dev/documentation/{library}/{version}/"
}
```

Особенно важно для Flutter/Dart:

- можно передавать `project_path`;
- Docmancer читает `.fvmrc` для Flutter hints;
- читает `pubspec.lock` для exact package versions;
- explicit `version` всегда приоритетнее project metadata.

### 2.7. Dartdoc / Flutter docs support

Для Dartdoc targets есть специальный режим:

```json
{
  "library": "flutter-layout-widgets-api",
  "ecosystem": "flutter",
  "version": "stable",
  "source_type": "api",
  "doc_format": "dartdoc",
  "seed_urls": [
    "https://api.flutter.dev/flutter/widgets/SizedBox-class.html",
    "https://api.flutter.dev/flutter/widgets/Container-class.html"
  ],
  "allowed_domains": ["api.flutter.dev"],
  "path_prefixes": ["/flutter/widgets/"]
}
```

Рекомендация из README: для Flutter/Dart API лучше индексировать конкретные class/library pages, а не root pages, потому что root pages могут быть sparse или JS-heavy.

## 3. Retrieval architecture

Docmancer имеет локальный docs-RAG pipeline:

```text
GitBook / Mintlify / web / GitHub / local files
  -> normalization into semantic sections
  -> SQLite FTS5 sections
  -> Qdrant dense + sparse vectors
  -> hybrid retrieval
  -> compact context pack
```

### 3.1. Indexing

Документы:

1. fetch/read from source;
2. нормализуются в semantic sections по heading structure;
3. сохраняются в SQLite с metadata:
   - title;
   - heading level/path;
   - source URL/path;
   - content hash;
   - token estimate;
4. индексируются через SQLite FTS5;
5. сохраняются в inspectable markdown/json в `~/.docmancer/extracted/`;
6. дополнительно embedding-и отправляются в vector store.

### 3.2. Hybrid search

По умолчанию свежая установка использует:

- lexical search: SQLite FTS5 + BM25;
- dense search: FastEmbed dense vectors (`BAAI/bge-base-en-v1.5`);
- sparse search: SPLADE sparse vectors;
- fusion: Reciprocal Rank Fusion, vanilla или weighted.

Команда:

```bash
docmancer query "question" --mode lexical|dense|sparse|hybrid --explain
```

`--explain` показывает вклад сигналов, например `lexical#1, dense#3, sparse#2`.

### 3.3. Token budget

Query возвращает не всё найденное, а то, что помещается в budget.

Опции:

- `--budget <tokens>`;
- `--limit <n>`;
- `--expand` — соседние sections;
- `--expand page` — полная matching page в пределах budget;
- `--format json`.

Default config:

- `query.default_budget: 2400`;
- `query.default_limit: 8`;
- `query.default_expand: adjacent`.

### 3.4. Advanced retrieval

Есть дополнительные retrieval features:

- hierarchical retrieval: сначала выбирает top documents, затем top sections внутри них;
- query-aware routing: regex routers могут добавлять filters в retrieval;
- neighbor expansion в hybrid mode;
- `--allow-degraded`: разрешить fallback при проблемах vector retrieval.

Пример config:

```yaml
retrieval:
  fusion:
    method: rrf
    rrf_k: 60
  hierarchical:
    enabled: true
    documents_limit: 5
  routers:
    - match: "(?i)api reference|endpoint"
      filters:
        source_path_prefix: api
      description: prefer-api-reference
```

## 4. Storage, local-first и инфраструктура

Основные пути:

- `~/.docmancer/docmancer.yaml` — global config;
- `~/.docmancer/docmancer.db` — SQLite FTS5 index;
- `~/.docmancer/extracted/` — markdown/json extract каждого indexed section;
- `~/.docmancer/qdrant/` — managed Qdrant binary/storage/logs;
- `~/.docmancer/models/` — FastEmbed model cache;
- `~/.docmancer/embeddings-cache/` — cache embedding-ов по content hash;
- `./docmancer.yaml` — project-local config, если есть.

`DOCMANCER_HOME` меняет storage root.

Default retrieval stack не требует API keys:

- FastEmbed локально;
- Qdrant локально;
- SQLite локально.

Cloud embedding providers опциональны:

- OpenAI;
- Voyage;
- Cohere.

Если cloud provider выбран, но ключа нет, ingest fallback-ится в FTS5-only с warning.

## 5. Qdrant lifecycle

Docmancer умеет управлять собственным локальным Qdrant:

```bash
docmancer qdrant up
docmancer qdrant down
docmancer qdrant status
docmancer qdrant upgrade
docmancer qdrant logs
```

Особенности:

- pinned Qdrant binary `v1.14.1`;
- telemetry disabled;
- ownership sentinel;
- отказ трогать чужие Qdrant collections/processes;
- fallback на `sqlite-vec`, если платформа не поддерживается;
- защита от stale vectors после `ingest --recreate` и удаления источников;
- embedder metadata для detection mismatch provider/model/dimensions/sparse model.

## 6. MCP API tool packs

Помимо docs-RAG есть отдельная advanced поверхность — version-pinned API MCP packs.

Пакеты устанавливаются так:

```bash
docmancer install-pack open-meteo@v1
docmancer mcp serve
```

Agent видит не сотни tools, а две meta-tools:

- `docmancer_search_tools(query, package?, limit?)`;
- `docmancer_call_tool(name, args)`.

Tool Search pattern:

1. агент ищет подходящий tool;
2. получает name, description, safety info, input schema;
3. вызывает конкретный fully qualified tool;
4. dispatcher валидирует args и применяет gates.

### 6.1. Pack source standards

Поддерживаются источники:

- OpenAPI 3.0 / 3.1;
- GraphQL introspection JSON;
- TypeDoc JSON;
- Sphinx `objects.inv`;
- `python_import` opt-in executor.

### 6.2. Runtime safety

Dispatcher делает:

- slug resolve;
- JSON Schema validation;
- credential resolution;
- destructive-call gating;
- `--allow-execute` gating для executors, которые запускают код;
- idempotency key injection для non-idempotent operations;
- HTTP dispatch с auth/header/encoding handling;
- redacted logs в `~/.docmancer/mcp/calls.jsonl`.

Destructive operations blocked by default, пока pack не установлен с `--allow-destructive`.

Credential resolution precedence:

1. per-call override;
2. process env;
3. agent MCP config env;
4. `~/.docmancer/secrets/<package>.env`.

## 7. Команды верхнего уровня

Core docs commands:

```bash
docmancer setup
docmancer init
docmancer ingest <path>
docmancer add <url>
docmancer update [source]
docmancer query "<text>"
docmancer list
docmancer inspect
docmancer remove [source]
docmancer clear
docmancer doctor
docmancer fetch <url>
docmancer install <agent>
```

Vector lifecycle:

```bash
docmancer qdrant up|down|status|upgrade|logs
```

MCP pack commands:

```bash
docmancer install-pack <pkg>@<version>
docmancer uninstall <pkg>[@<version>]
docmancer mcp serve
docmancer mcp list
docmancer mcp doctor
docmancer mcp enable <pkg>
docmancer mcp disable <pkg>
docmancer mcp remove <pkg>[@<version>]
```

MCP docs server:

```bash
docmancer mcp docs-serve
```

## 8. Конфигурация

Resolution order:

1. `--config` flag;
2. `./docmancer.yaml`;
3. `~/.docmancer/docmancer.yaml`.

Ключевые блоки:

- `index`;
- `query`;
- `web_fetch`;
- `loaders`;
- `vector_store`;
- `embeddings`;
- `retrieval`.

Пример минимального config:

```yaml
index:
  provider: sqlite
  db_path: ~/.docmancer/docmancer.db
  extracted_dir: ~/.docmancer/extracted

query:
  default_budget: 2400
  default_limit: 8
  default_expand: adjacent

web_fetch:
  workers: 8
  default_page_cap: 500
```

## 9. Текущее состояние по версии / changelog highlights

Актуальные заметки из changelog:

### 0.5.2

- добавлен `docmancer clear`;
- embedder metadata для vector collections;
- `query --allow-degraded`;
- более строгие ошибки при vector/hybrid проблемах;
- doctor показывает collection point counts и drift;
- исправлены token metrics для hybrid output.

### 0.5.0

- local-first RAG pipeline расширен на PDF/DOCX/RTF/HTML;
- vector store abstraction;
- managed Qdrant lifecycle;
- local FastEmbed + cloud embedding stubs;
- hybrid retrieval;
- hierarchical retrieval;
- retrieval routers;
- eval harness;
- doctor стал диагностировать loaders/Qdrant/embeddings/vector drift.

### 0.4.6–0.4.9

- MCP runtime и install-pack;
- Tool Search pattern;
- OpenAPI pack builder;
- hosted/local/known registry fallback;
- `install-pack --from-url`;
- Open-Meteo keyless demo pack.

## 10. Наблюдения из живого использования

В ходе работы были проиндексированы docs targets:

- `plugfox` — 383 страницы с `https://plugfox.dev/`;
- `flutter-adaptive-responsive` — 90 страниц с `https://docs.flutter.dev/ui/adaptive-responsive`.

Было обнаружено поведенческое UX/API место:

- для custom web-sourced libraries `get_library_docs` может вернуть warning `needs_docs_url`, если вызвать его только с `library`, без `docs_url`;
- при этом library уже может быть в registry, но agent/tool caller не обязательно понимает, что надо повторить вызов с сохранённым `docs_url`;
- неправильный fallback: агент может уйти в direct WebFetch, хотя docs уже локально indexed;
- желаемое поведение: если docs target зарегистрирован как web source, `get_library_docs` либо сам использует stored `docs_url`, либо agent guidance явно требует сначала resolve/list registry и повторить запрос с `docs_url`, а не идти в WebFetch.

Это важный сигнал для планирования: **MCP docs UX должен минимизировать случаи, где агенту надо знать внутренние нюансы registry/docs_url**.

## 11. Сильные стороны продукта

1. **Local-first.** Нет hosted query API, default stack работает локально.
2. **No API keys by default.** FastEmbed + local Qdrant + SQLite.
3. **Agent-oriented output.** Context packs оптимизированы под token budget.
4. **Inspectable.** Extracted markdown/json можно проверить на диске.
5. **Hybrid retrieval.** Lexical + dense + sparse + RRF.
6. **Безопасность MCP packs.** Destructive gates, schema validation, idempotency, SHA verification.
7. **Versioned docs.** Особенно полезно для Flutter/Dart/pub.dev и package-specific agents.
8. **Agent integrations.** Skills для нескольких популярных agent tools.
9. **Support for many source types.** Local files, docs sites, GitHub, API specs.
10. **Good CLI surface.** Команды покрывают setup, ingest, query, update, inspect, doctor, qdrant, mcp.

## 12. Потенциальные слабые места / зоны развития

### 12.1. Product focus split

В продукте есть две довольно разные поверхности:

1. docs-RAG / context packs;
2. MCP API tool packs.

Они обе полезные, но требуют разного messaging, UX и roadmap. Нужна ясная продуктовая стратегия: это один продукт с двумя режимами или два продукта под одним брендом?

### 12.2. MCP docs server UX

Проблема `needs_docs_url` показывает, что агентский API может быть слишком требовательным к caller-у.

Возможные улучшения:

- `get_library_docs` должен сам использовать stored `docs_url`, если library resolved;
- `needs_docs_url` должен возвращать suggested remediation и candidates;
- `resolve_library_id` должен возвращать canonical id + stored docs_url + source_type;
- добавить explicit `inspect_library_docs` в стандартный happy path для agents;
- сделать fallback policy: never direct WebFetch while registered docs source exists.

### 12.3. Registry / source identity

Нужна максимально понятная модель:

- library name;
- canonical id;
- ecosystem;
- version;
- source_type;
- docs_url;
- docs_url_template;
- seed_urls;
- allowed_domains;
- path_prefixes;
- doc_format;
- exact snapshot flag.

Если это не прозрачно, agents будут путаться.

### 12.4. Quality evaluation

Есть eval harness, но для дальнейшего развития важно системно измерять:

- retrieval accuracy;
- answer grounding;
- context pack compression;
- precision/recall по API signatures;
- multi-version correctness;
- source attribution correctness;
- agent task success rate.

### 12.5. Docs crawling reliability

Generic docs crawling всегда сложен:

- JS-heavy sites;
- sparse root pages;
- nav structures;
- rate limits;
- duplicate pages;
- canonical URLs;
- sitemap quality;
- docs generated by Dartdoc / Sphinx / Docusaurus / VitePress / Nextra / MkDocs.

Возможно стоит развивать специализированные extractors/providers.

### 12.6. Developer experience

Возможные friction points:

- первый ingest скачивает Qdrant/model cache;
- пользователю нужно понимать `--no-vectors`, `DOCMANCER_AUTO_VECTORS`, Qdrant state;
- config migration / mismatch errors;
- agent skill installation может требовать restart;
- большое количество команд и режимов.

### 12.7. Observability

Уже есть `doctor`, `inspect`, `--explain`, logs. Можно усилить:

- richer ingest report;
- query trace UI/json;
- per-source quality diagnostics;
- duplicate/canonical analysis;
- stale docs dashboard;
- failed pages report with retry plan.

## 13. Вопросы для сильной модели при планировании roadmap

### Product strategy

1. Что должно быть главным positioning: local docs RAG, Context7 alternative, API MCP packs или all-in-one agent docs runtime?
2. Нужно ли разделить docs-RAG и API packs в messaging / CLI / docs?
3. Какой ICP: individual coding-agent users, teams, OSS maintainers, enterprise devtools?
4. Какие 3 use cases должны быть polished до уровня “wow”?

### Agent UX

1. Как сделать так, чтобы агент почти никогда не уходил в WebFetch при наличии indexed docs?
2. Как должен выглядеть ideal MCP docs workflow: resolve -> inspect -> query -> cite?
3. Нужно ли auto-resolve docs_url/version/ecosystem из registry без участия агента?
4. Как структурировать warnings так, чтобы LLM не ошибалась с remediation?

### Retrieval quality

1. Какие benchmarks нужны для docs retrieval?
2. Как сравнивать lexical/dense/sparse/hybrid/hierarchical?
3. Нужен ли reranker?
4. Нужна ли query rewriting / decomposition?
5. Как гарантировать exact API signatures для codegen tasks?

### Source ingestion

1. Какие docs frameworks стоит поддержать специализированно следующими?
2. Как улучшить Dartdoc / Flutter / pub.dev path?
3. Нужна ли автоиндексация package docs по `pubspec.lock`, `package.json`, `requirements.txt`, `Cargo.toml`, etc.?
4. Как лучше обрабатывать multi-page docs с плохой навигацией?

### Versioning

1. Как сделать version resolution максимально надёжным?
2. Нужно ли хранить exact snapshots и diff между версиями?
3. Нужно ли auto-discover available package versions?
4. Как показывать agent-у, что docs are not exact archived snapshot?

### MCP packs

1. Насколько MCP API packs стратегически важны относительно docs-RAG?
2. Нужно ли расширять GraphQL from `noop_doc` до live calls?
3. Как курировать registry и trust model?
4. Как сделать Tool Search более надёжным для больших tool surfaces?

### DX / Operations

1. Как упростить first run и устранить surprises со скачиванием моделей/Qdrant?
2. Нужен ли TUI/web dashboard?
3. Как сделать `doctor` actionable enough?
4. Какой minimal happy path должен быть для нового пользователя за 5 минут?

## 14. Возможные направления roadmap

Ниже не окончательный план, а направления, которые стоит оценить.

### A. Polish MCP docs server до agent-proof UX

- Автоматическое использование stored `docs_url`.
- Rich responses для `needs_docs_url` с candidates/remediation.
- Unified `resolve -> query` happy path.
- Strong agent instructions: never WebFetch registered docs before docmancer retry.
- Better `list/inspect_library_docs` output.

### B. Улучшить project-aware dependency docs

- Flutter/Dart уже частично есть: `.fvmrc`, `pubspec.lock`.
- Расширить на npm, Python, Rust, Go.
- Команда вида: `docmancer prefetch-project-docs .`.
- Auto version pinning и docs_url_template per ecosystem.

### C. Retrieval quality and evaluation

- Golden datasets для популярных docs.
- Metrics: hit@k, MRR, source accuracy, answer exactness.
- Query classes: API signature, conceptual guide, migration, error message, config key.
- Regression suite для hybrid/lexical changes.

### D. Better crawling/extraction providers

- Docusaurus;
- VitePress;
- MkDocs;
- Sphinx;
- Dartdoc;
- Next/Nextra docs;
- OpenAPI docs pages.

### E. UX visibility

- Ingest report: pages fetched/failed/skipped/duplicated.
- Stale docs list.
- Query explain JSON for agents.
- Health report per source.
- Suggested fixes for poor extraction.

### F. Product separation / packaging

- Clarify docs-RAG vs MCP packs.
- Возможно отдельные quickstarts:
  - “Index docs for your coding agent”;
  - “Use versioned package docs via MCP”;
  - “Install API tool packs”.

## 15. Самый важный контекст для планирования

Docmancer уже имеет сильную техническую базу: local indexing, hybrid search, source-attributed context packs, MCP integrations, versioned docs, Qdrant lifecycle, safety gates для API tools.

Основной риск не в отсутствии возможностей, а в **сложности UX и смешении нескольких мощных поверхностей**. Следующий этап развития, вероятно, должен быть сфокусирован на:

1. agent-proof workflows;
2. надёжном source/version resolution;
3. измеримом retrieval quality;
4. простом first-run experience;
5. ясном product positioning.

Если сильная модель будет строить roadmap, ей стоит просить её не просто “добавить features”, а выбрать стратегический фокус и превратить существующую мощную систему в predictable product для coding agents.
