# Docmancer: функциональная выжимка и контекст для планирования развития

Цель этого документа — дать сильной модели сжатый, но достаточно полный контекст по текущему состоянию Docmancer, чтобы она могла не повторять уже выполненный roadmap, а найти следующий стратегический рычаг развития продукта, архитектуры и UX.

Важно: предыдущий roadmap уже был частично/в значительной степени реализован. Следующий запрос к сильной модели должен быть не “составь roadmap с нуля”, а “сделай gap-analysis текущего Docmancer против Context7 и предложи следующий wedge, который делает Docmancer заметно лучше, а не просто сложнее”.

## 1. Короткое позиционирование

**Docmancer** — локальный инструмент для превращения документации в компактный, source-grounded контекст для coding agents.

Более точное текущее позиционирование:

> **Docmancer is a local, version-aware docs runtime for coding agents.**

Основной продуктовый слой — **Docmancer Docs**: локальный runtime для документации проекта, приватных docs, публичных docs-сайтов и version-aware library docs. **Docmancer Packs** — advanced слой для version-pinned API action tools; он важен, но не должен быть hero narrative.

Он умеет:

- индексировать локальные файлы и публичные docs-сайты;
- искать по ним через CLI или MCP;
- возвращать не сырые страницы, а компактные context packs с атрибуцией источников и оценкой экономии токенов;
- работать локально без hosted query API;
- использовать гибридный retrieval: SQLite FTS5 + dense vectors + sparse vectors;
- устанавливать agent skills для популярных coding-agent окружений;
- отдельно предоставлять MCP runtime для version-pinned API tool packs.

Ключевая идея: **агент тратит контекст на работу с кодом, а не на перечитывание полной документации**.

Ключевое отличие от Context7, которое стоит развивать: Context7 хорошо даёт публичные docs библиотек; Docmancer должен давать агенту docs, которые реально относятся к проекту: local/private project docs + exact/project-aware dependency docs + source/version metadata.

## 2. Основные пользовательские сценарии

### 2.1. Локальный docs-RAG для coding agents

Пользователь индексирует документацию:

```bash
doc-atlas setup
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
```

Затем агент или пользователь задаёт вопрос:

```bash
doc-atlas query "How do I authenticate?"
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
doc-atlas add https://docs.pytest.org
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
doc-atlas ingest ./path/to/docs
```

Опции:

- `--include <glob>`;
- `--exclude <glob>`;
- `--format <format>`;
- `--recursive / --no-recursive`;
- `--skip-known`;
- `--recreate`;
- `--no-vectors`.

### 2.3.1. Project-owned docs: документация самого проекта

Docmancer можно использовать не только для library docs, но и как локальный docs layer для конкретного проекта.

Типичный набор source-of-truth файлов:

- `README.md`;
- `docs/**/*.md`;
- `wiki/**/*.md`;
- `ARCHITECTURE.md` / `docs/Architecture.md`;
- ADR / roadmap / onboarding / runbooks;
- generated docs, если они лежат в проекте и reviewable.

Рекомендуемый принцип: **официальная архитектура и проектная документация должны жить как файлы в repo**, потому что это даёт git history, diff, review, blame, rollback и переносимость. Docmancer не должен заменять такие файлы внутренними SQLite-записями; он должен индексировать их и делать удобными для агента.

Правильная схема:

```text
нейронка/человек создаёт или обновляет docs/Architecture.md
  -> Docmancer ingest/index
  -> агент спрашивает через query/MCP
  -> получает compact grounded context с source attribution
```

Docmancer-only записи могут быть полезны для временной/local memory: session summaries, investigation notes, приватные заметки пользователя, гипотезы агента. Но архитектура, security model, API contracts, onboarding и ADR почти всегда должны быть version-controlled файлами.

Возможный будущий продуктовый flow: `write_project_doc(..., mode="propose_patch")` или `project docs memory`, где Docmancer помогает создать/обновить файл и сразу переиндексирует его, но не прячет официальный source of truth в базу.

Текущее MCP-состояние project-owned docs уже стало first-class workflow, а не только ручным `ingest ./docs`:

- `inspect_project_docs(project_path)` — read-only discovery project docs candidates, indexed/stale/ignored sources и dependency metadata;
- `ingest_project_docs(project_path)` — индексирует только reviewable project docs candidates (`README`, `docs/`, `wiki/`, `ARCHITECTURE`, ADR, roadmap), не source code, dependency directories или build outputs;
- `bootstrap_project_docs(project_path, question?)` — safe high-level onboarding flow: inspect -> ingest/refresh existing reviewable docs -> inspect again, но останавливается перед repo writes и dependency network fetch;
- `get_project_docs(project_path, query)` — query по indexed project-owned docs с project-scoped filters, source attribution, heading paths и stale metadata;
- `get_project_context(project_path, question, ...)` — high-level context pack, который может объединять project docs и dependency docs и возвращает Trust Contract;
- `prefetch_project_docs(project_path, ...)` — несмотря на название, это dependency-docs path: читает manifests/lockfiles и prefetch-ит exact dependency documentation, где поддерживается;
- `prefetch_project_dependency_docs(project_path, ...)` — non-breaking alias, который делает эту границу явной для агентов и пользователей.

Agent-discoverable onboarding теперь закреплён не только в prose/tool descriptions, но и в response schemas:

1. `inspect_project_docs` и project-docs query fallbacks возвращают stable `reason_code`, structured `next_action`, `requires_confirmation`, `confirmation_reason`, `arguments_patch`, а также agent/user messages;
2. если docs candidates найдены, но не indexed — `reason_code = project_docs_found_not_indexed`, `next_action.tool = ingest_project_docs`;
3. если indexed docs stale — `reason_code = project_docs_stale`, `next_action.tool = ingest_project_docs`;
4. если project docs отсутствуют — `reason_code = no_project_docs`, remediation path: спросить разрешение на создание reviewable `ARCHITECTURE.md`, затем coding agent изучает repo и создаёт файл, после чего Docmancer снова делает `inspect_project_docs -> ingest_project_docs -> get_project_docs/get_project_context`;
5. если docs есть, но нет high-level overview/architecture doc — `reason_code = architecture_doc_creation_recommended`, тот же безопасный repo-file remediation path;
6. если project docs готовы — `reason_code = project_docs_ready`, `next_action.tool = get_project_context`;
7. если lockfiles/manifests дают exact dependency versions — `dependency_sources.dependency_next_action` предлагает `prefetch_project_docs` / `prefetch_project_dependency_docs`, но это network fetch и требует confirmation.

Ключевые reason codes текущего project-docs onboarding:

- `no_project_docs`;
- `project_docs_found_not_indexed`;
- `project_docs_stale`;
- `project_docs_ready`;
- `architecture_doc_creation_recommended`;
- query fallback: `no_project_docs_results`.

Важная граница текущего продукта: Docmancer **не пишет архитектуру сам** и не должен сохранять official architecture в hidden memory. Он направляет агента через `next_actions`; создание `ARCHITECTURE.md` выполняет coding agent как обычный reviewable file change после согласия пользователя.

Ключевой UX-риск уже снижен: tool descriptions и response shapes теперь явно ведут модель к `inspect_project_docs -> ingest_project_docs/bootstrap_project_docs -> get_project_docs/get_project_context`, а при `no_project_docs` / `architecture_doc_creation_recommended` — к запросу разрешения на создание `ARCHITECTURE.md`. Оставшийся риск — проверить это в реальных agent loops разных клиентов и закрепить в setup-installed skills/README.

### 2.4. Agent integration

`doc-atlas setup` умеет устанавливать skill files / инструкции для агентских окружений.

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
doc-atlas mcp docs-serve
```

Инструменты MCP docs server:

- `resolve_library_id`;
- `get_library_docs`;
- `refresh_library_docs`;
- `prefetch_library_docs`;
- `prefetch_project_docs`;
- `prefetch_docs_targets`;
- `prefetch_docs_manifest`;
- `list_library_docs`;
- `inspect_library_docs`;
- `get_docs_job_status`;
- `list_docs_jobs`;
- `cancel_docs_job`.
- project docs tools: `inspect_project_docs`, `ingest_project_docs`, `bootstrap_project_docs`, `get_project_docs`, `get_project_context`;
- dependency-docs project helpers: `prefetch_project_docs` и более явный alias `prefetch_project_dependency_docs`.

Docs server использует тот же локальный ingest/index/query path, что и CLI, плюс registry библиотек в SQLite.

Особенности:

- stale docs считаются те, которые никогда не refresh-ились или старше 30 дней;
- `get_library_docs` refresh-ит stale docs перед query;
- `force_refresh: true` принудительно refresh-ит даже fresh docs;
- для unknown library нужно явно передавать `docs_url`; сервер не должен угадывать arbitrary docs URL без источника/registry;
- registered docs могут query-иться без повторной передачи `docs_url` — stored source locator должен использоваться автоматически.

Пример:

```json
{
  "library": "pytest",
  "topic": "parametrize fixture",
  "docs_url": "https://docs.pytest.org/"
}
```

### 2.6. Versioned documentation и registry identity

Docs MCP умеет хранить разные версии одной библиотеки как отдельные entries:

- `go_router@14.8.1`;
- `go_router@16.2.0`;
- `go_router@latest`;
- `flutter-api@stable`;
- `flutter-api@main`.

В более строгой текущей модели используются canonical ids вида:

- `pub:go_router@14.8.1:api`;
- `pub:go_router@16.2.0:api`;
- `pub:go_router@latest:api`;
- `flutter:flutter-api@stable:api`;
- `web:riverpod-guides@latest:guides`.

Responses должны явно показывать:

- `canonical_id`;
- `source_id` / source identity, если применимо;
- `requested_version`;
- `resolved_version`;
- `docs_snapshot_exact`;
- source/version confidence;
- stored docs locator: `docs_url`, `docs_url_template`, `seed_urls`, `allowed_domains`, `path_prefixes`, `doc_format`.

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

Возможный следующий wedge: **Project-aware Docs Autopilot**. Агент не угадывает library id/version/docs URL, а передаёт `project_path`; Docmancer читает lockfile/metadata, выбирает exact dependency docs, prefetch-ит их при необходимости и возвращает answer с source/version exactness. Это может стать главным отличием от Context7: “docs your project actually uses”.

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
doc-atlas query "question" --mode lexical|dense|sparse|hybrid --explain
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
doc-atlas qdrant up
doc-atlas qdrant down
doc-atlas qdrant status
doc-atlas qdrant upgrade
doc-atlas qdrant logs
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
doc-atlas install-pack open-meteo@v1
doc-atlas mcp serve
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
doc-atlas setup
doc-atlas init
doc-atlas ingest <path>
doc-atlas add <url>
doc-atlas update [source]
doc-atlas query "<text>"
doc-atlas list
doc-atlas inspect
doc-atlas remove [source]
doc-atlas clear
doc-atlas doctor
doc-atlas fetch <url>
doc-atlas install <agent>
```

Vector lifecycle:

```bash
doc-atlas qdrant up|down|status|upgrade|logs
```

MCP pack commands:

```bash
doc-atlas install-pack <pkg>@<version>
doc-atlas uninstall <pkg>[@<version>]
doc-atlas mcp serve
doc-atlas mcp list
doc-atlas mcp doctor
doc-atlas mcp enable <pkg>
doc-atlas mcp disable <pkg>
doc-atlas mcp remove <pkg>[@<version>]
```

MCP docs server:

```bash
doc-atlas mcp docs-serve
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

- добавлен `doc-atlas clear`;
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

Было обнаружено поведенческое UX/API место, которое стало одним из главных inputs для roadmap:

- для custom web-sourced libraries `get_library_docs` может вернуть warning `needs_docs_url`, если вызвать его только с `library`, без `docs_url`;
- при этом library уже может быть в registry, но agent/tool caller не обязательно понимает, что надо повторить вызов с сохранённым `docs_url`;
- неправильный fallback: агент может уйти в direct WebFetch, хотя docs уже локально indexed;
- желаемое поведение: если docs target зарегистрирован как web source, `get_library_docs` либо сам использует stored `docs_url`, либо agent guidance явно требует сначала resolve/list registry и повторить запрос с `docs_url`, а не идти в WebFetch.

Это важный сигнал для планирования: **MCP docs UX должен минимизировать случаи, где агенту надо знать внутренние нюансы registry/docs_url**.

Судя по текущему состоянию README/тестов/кода, этот roadmap уже был существенно продвинут: появились `inspect_library_docs`, `prefetch_docs_targets`, `prefetch_docs_manifest`, canonical ids, version/exactness metadata, regression tests вокруг `needs_docs_url`, async job progress и richer diagnostics. Поэтому сильной модели не нужно снова советовать “убрать needs_docs_url trap” как основной следующий milestone; теперь нужно проверить, что это действительно стабильно в агентском loop, и найти следующий leverage point.

Новый live product question из обсуждения: **может ли Docmancer быть docs layer не только для libraries, но и для project-owned docs?** Ответ: да, через `ingest`/`query`, но UX пока не выражен так явно, как Context7-style `get_library_docs`. Это может быть важным направлением: сделать project docs first-class для агента, не заменяя файлы в repo.

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
11. **Project-owned docs support.** Можно индексировать README/wiki/docs/architecture/ADR конкретного проекта и отвечать по ним как по grounded local knowledge.
12. **Potential Context7 wedge.** Context7 силён в public library lookup; Docmancer может быть сильнее в комбинации “project docs + exact dependency docs + private/local docs”.

## 12. Потенциальные слабые места / зоны развития

### 12.1. Product focus split

В продукте есть две довольно разные поверхности:

1. docs-RAG / context packs;
2. MCP API tool packs.

Они обе полезные, но требуют разного messaging, UX и roadmap. Нужна ясная продуктовая стратегия: это один продукт с двумя режимами или два продукта под одним брендом?

### 12.2. MCP docs server UX

Историческая проблема `needs_docs_url` показала, что агентский API может быть слишком требовательным к caller-у. Значительная часть remediation уже реализована или запланирована в деталях; следующий риск — не наличие одного warning, а общий MCP flow: понимает ли агент, когда использовать registered docs, когда prefetch, когда inspect, когда query, и когда WebFetch действительно допустим.

Возможные улучшения:

- `get_library_docs` должен сам использовать stored `docs_url`, если library resolved;
- `needs_docs_url` должен возвращать suggested remediation и candidates;
- `resolve_library_id` должен возвращать canonical id + stored docs_url + source_type;
- добавить explicit `inspect_library_docs` в стандартный happy path для agents;
- сделать fallback policy: never direct WebFetch while registered docs source exists.

Новая формулировка UX цели: агент должен предпочитать Docmancer автоматически, потому что tool descriptions и response shapes ведут его к полезному следующему вызову. Если docs есть локально или могут быть получены из project metadata, агент не должен угадывать URL и не должен уходить в WebFetch до Docmancer retry/inspect.

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

### 12.8. Project docs UX gap

Сейчас документация самого проекта поддерживается не только технически через `doc-atlas ingest ./docs` и `doc-atlas query`, но и через отдельные MCP tools: `inspect_project_docs`, `ingest_project_docs`, `bootstrap_project_docs`, `get_project_docs`, `get_project_context`. Это уже close-to-first-class workflow для агента.

Главный недавний прогресс: workflow теперь имеет stable reason codes, structured next actions, explicit confirmation gates и safe bootstrap. API разделяет:

- `inspect_project_docs` / `ingest_project_docs` / `get_project_docs` — project-owned docs;
- `bootstrap_project_docs` — safe onboarding orchestration для project-owned docs;
- `prefetch_project_docs` / `prefetch_project_dependency_docs` — dependency docs по lockfile/project metadata;
- `get_library_docs` — library docs.

Это правильно архитектурно; теперь оно стало намного более agent-readable, но всё ещё требует README/skill polish и проверки в реальных клиентах.

Уже реализованные/текущие элементы:

- auto-detect docs candidates: `README.md`, `docs/`, `wiki/`, `ARCHITECTURE`, ADR, roadmap;
- inspect output показывает found/indexed/stale/ignored docs, stable `reason_code` и structured `next_action`;
- `ingest_project_docs` индексирует только reviewable docs candidates;
- `get_project_docs` возвращает source class, file path, heading path и freshness/stale metadata;
- `get_project_context` возвращает compact context pack и Trust Contract;
- `bootstrap_project_docs` выполняет safe inspect/ingest/reinspect flow и останавливается перед unsafe actions;
- при missing/not indexed/stale/no-results docs поведение — возвращать structured remediation, а не generic failure;
- missing overview/architecture detection: если docs есть, но нет high-level overview, возвращается `architecture_doc_creation_recommended`;
- dependency-docs state отделён от project-owned docs state через `dependency_sources` и `dependency_next_action`;
- `prefetch_project_dependency_docs` добавлен как явный alias к dependency-docs prefetch path.

Оставшиеся улучшения:

- documented lane: “Project-owned docs”;
- stronger agent-facing onboarding для пользователей, которые “вообще не знают, что делать”;
- README/skill updates для `bootstrap_project_docs` и `prefetch_project_dependency_docs`;
- возможно добавить higher-level docs quickstart вокруг exact happy path: `bootstrap_project_docs -> get_project_context`;
- local project memory как secondary layer, но official docs остаются файлами.

Критический продуктовый принцип: **Docmancer не должен превращаться в скрытую CMS для официальной архитектуры проекта**. Он должен индексировать и обслуживать файлы, а для write flows — предлагать patches/files, которые можно review-ить в git.

### 12.9. Context7 comparison gap

Context7 всё ещё может выигрывать по:

- perceived coverage популярных библиотек;
- простоте mental model: resolve id -> get docs;
- отсутствию setup/ingest friction;
- hosted/public docs availability;
- привычности для агентов и пользователей.

Docmancer не должен пытаться стать hosted clone Context7. Более сильная стратегия — выиграть там, где Context7 структурно слабее:

- private/local docs;
- project-owned docs;
- exact project dependency versions;
- offline/local-first;
- inspectable extraction;
- source/version exactness;
- eval/trace/doctor;
- ability to combine project architecture + dependency docs in one grounded context.

## 13. Вопросы для сильной модели при планировании roadmap

Важное изменение framing: не просить сильную модель “придумать roadmap Docmancer” заново. Нужно просить её провести **gap-analysis текущего состояния против Context7** и выбрать следующий leverage point после уже выполненного roadmap.

Рекомендуемый главный вопрос:

> Как сделать Docmancer заметно лучше Context7 для coding agents, сохранив local-first модель и не превращаясь в hosted public docs clone?

Гипотеза, которую нужно проверить: следующий strongest wedge — **Project-aware Docs Autopilot**: Docmancer отвечает не просто по публичной библиотеке, а по docs, которые реально относятся к проекту: project-owned files + exact dependency docs from lockfiles + source/version exactness.

### Product strategy

1. Где Context7 всё ещё явно лучше Docmancer с точки зрения агента/пользователя?
2. Где Docmancer может стать meaningfully better, а не просто equal?
3. Должен ли главный positioning быть “Context7 alternative” или “docs your project actually uses”?
4. Какие 3 use cases должны быть polished до уровня “wow”?
5. Какие anti-goals нужны, чтобы не размазать фокус?

### Agent UX

1. Как сделать так, чтобы агент почти никогда не уходил в WebFetch при наличии indexed docs?
2. Как должен выглядеть ideal MCP docs workflow: resolve -> inspect -> query -> cite?
3. Нужно ли auto-resolve docs_url/version/ecosystem из registry без участия агента?
4. Как структурировать warnings так, чтобы LLM не ошибалась с remediation?
5. Нужен ли first-class `get_project_docs({ project_path, topic })`?
6. Как tool descriptions должны объяснять разницу между project-owned docs, project dependency docs и library docs?

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
5. Нужно ли автообнаружение project-owned docs: README, docs, wiki, ADR, architecture?
6. Как сделать write/update project docs flow безопасным: propose patch to file, then ingest?

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

### Project docs / local memory

1. Должны ли official project docs всегда оставаться файлами в repo?
2. Есть ли место для local-only Docmancer memory: session summaries, investigation notes, private user notes?
3. Как объединять official docs + local memory + dependency docs в одном query result без путаницы доверия?
4. Нужно ли явно маркировать source class: `project_file`, `local_memory`, `dependency_docs`, `public_docs`, `pack_docs`?
5. Как сделать так, чтобы агент не записывал архитектурные галлюцинации в hidden DB вместо reviewable file?

## 14. Возможные направления roadmap

Ниже не окончательный план, а направления, которые стоит оценить. Первые пункты старого roadmap уже частично/существенно реализованы, поэтому их нужно рассматривать как stabilization/verification, а не как новый главный стратегический milestone.

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

Это кандидат на следующий основной wedge, если сильная модель подтвердит, что он лучше конкурирует с Context7: “Docmancer gives agents docs for the dependencies your project actually uses”.

Приоритет экосистем может быть таким:

1. Flutter/Dart/pub.dev — уже есть база, нужно polish/hardening.
2. Rust/docs.rs — deterministic и хорошо подходит для exact version docs.
3. Python/PyPI/ReadTheDocs — высокий спрос, но сложнее discovery.
4. npm — огромный спрос, но messy; лучше после стабилизации identity/discovery.

### B2. Project-owned docs as first-class agent workflow

- Явный quickstart/lane: “Index this project’s docs for your coding agent”.
- Auto-detect docs candidates: `README.md`, `docs/`, `wiki/`, `ARCHITECTURE.md`, `adr/`, `roadmap/` — уже есть в MCP discovery path.
- `get_project_docs({ project_path, topic })` или аналогичный MCP wrapper поверх local query — уже есть как `get_project_docs(project_path, query)`.
- `inspect_project_docs({ project_path })`: какие файлы indexed, stale, missing, excluded — уже есть.
- `ingest_project_docs({ project_path })`: отдельный safe ingest только reviewable project docs — уже есть.
- Stable reason codes + structured next actions for project-docs onboarding — уже есть.
- `bootstrap_project_docs({ project_path, question? })`: safe inspect/ingest/reinspect orchestration — уже есть.
- Missing/no-overview remediation через `ARCHITECTURE.md` как reviewable repo file — уже есть как response contract, без silent Docmancer write.
- Dependency-docs prefetch separation и alias `prefetch_project_dependency_docs` — уже есть.
- `get_project_context({ project_path, question })`: high-level context pack + Trust Contract — есть в текущем MCP surface и должен стать главным onboarding/happy-path tool.
- Следующий фокус: задокументировать и отполировать happy path так, чтобы агент почти всегда выбирал `bootstrap_project_docs -> get_project_context`, а при confirmation gates корректно спрашивал пользователя.
- `write_project_doc(..., mode="propose_patch")`: если добавлять write flow, он должен создавать reviewable file diff, не hidden DB mutation.
- Unified query может возвращать source classes: project file, dependency docs, local memory.

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

### G. Context7 comparison / coverage strategy

- Не строить hosted query plane как основной путь.
- Не пытаться вручную покрыть весь npm/Python ecosystem до стабилизации project-aware discovery.
- Вместо “global hosted registry” развивать local manifests, docs_url templates, ecosystem adapters и user/project-specific prefetch.
- Минимальная curated registry может быть полезна для demos и popular libraries, но не должна стать главным продуктовым dependency.
- Coverage success лучше измерять не числом известных библиотек, а долей successful grounded docs sessions в реальных проектах.

## 15. Самый важный контекст для планирования

Docmancer уже имеет сильную техническую базу: local indexing, hybrid search, source-attributed context packs, MCP integrations, versioned docs, registry identity, Qdrant lifecycle, eval/doctor foundations и safety gates для API tools.

Основной риск не в отсутствии возможностей, а в **сложности UX и смешении нескольких мощных поверхностей**. Следующий этап развития не должен просто добавлять features. Он должен выбрать wedge, который делает Docmancer очевидно полезнее Context7 в реальном агентском workflow.

Старый roadmap-фокус:

1. agent-proof workflows;
2. надёжном source/version resolution;
3. измеримом retrieval quality;
4. простом first-run experience;
5. ясном product positioning.

Этот фокус остаётся важным, но многие части уже реализованы или начаты. Новый planning prompt должен просить сильную модель:

1. оценить текущий Docmancer против Context7;
2. определить, где Context7 всё ещё выигрывает;
3. определить, где Docmancer может выиграть структурно;
4. выбрать один next 30-day milestone;
5. разложить его на PR sequence;
6. назвать anti-goals.

Наиболее перспективная гипотеза: **Project-aware Docs Autopilot**.

```text
Context7 gives agents public library docs.
Docmancer should give agents the docs this project actually uses:
  - project-owned docs from repo files;
  - private/local docs;
  - exact dependency docs from lockfiles;
  - source/version exactness;
  - compact context packs with attribution.
```

Если сильная модель будет строить дальнейший roadmap, ей стоит просить её не просто “добавить features”, а выбрать стратегический фокус и превратить существующую мощную систему в predictable product для coding agents.

## 16. Рекомендуемый prompt для сильной модели

```text
You are a senior product + engineering strategist for developer tools and coding-agent infrastructure.

We are building Docmancer.

Current positioning:
Docmancer is a local, version-aware docs runtime for coding agents. It indexes project docs, private docs, public docs sites, package references, and serves compact source-grounded context packs through CLI and MCP. It is local-first and does not require a hosted query API by default.

The strategic comparison target is Context7:
- Context7 is very easy for agents: resolve library id, then get library docs.
- It has strong perceived coverage and low-friction MCP UX.
- It is good at public library docs lookup.
- It is less focused on private/local docs, project-owned docs, project-specific dependency versions, offline usage, and source/version exactness.

Docmancer current capabilities:
- CLI setup, ingest, add, query, list, inspect, doctor, fetch, update, clear.
- Local project docs ingestion: README, docs, wiki, architecture, ADR, roadmap, private docs.
- Project-owned docs MCP onboarding: inspect_project_docs, ingest_project_docs, bootstrap_project_docs, get_project_docs, get_project_context.
- Structured project-docs reason codes and next actions: no_project_docs, project_docs_found_not_indexed, project_docs_stale, project_docs_ready, architecture_doc_creation_recommended, no_project_docs_results.
- Safe project-docs bootstrap: automatically inspect/ingest/reinspect existing reviewable docs, but stop before repo writes or dependency-docs network fetch.
- Public docs fetching: GitBook, Mintlify, generic web docs, GitHub, llms.txt/llms-full.txt, sitemap, nav crawl, optional browser fallback.
- Hybrid retrieval: SQLite FTS5 + dense vectors + sparse vectors + RRF, with explain/explain-json.
- Local Qdrant lifecycle with sqlite-vec fallback.
- MCP docs server: resolve_library_id, get_library_docs, refresh_library_docs, prefetch_library_docs, prefetch_project_docs, prefetch_project_dependency_docs, prefetch_docs_targets, prefetch_docs_manifest, list/inspect library docs, docs jobs.
- Registry/versioning: canonical ids, requested/resolved version, docs_snapshot_exact, stored docs_url reuse.
- Flutter/Dart project-aware docs path: .fvmrc and pubspec.lock.
- Eval/doctor foundations.
- Advanced Docmancer Packs layer for version-pinned API action tools, but Packs are not the hero product.

Important product principle:
Official project architecture/docs should remain files in the repo, not hidden records in Docmancer DB. Docmancer should index and serve them. Write flows should propose file patches and then ingest, not silently mutate hidden knowledge.

Previously planned roadmap items included:
1. Kill needs_docs_url trap.
2. Stabilize registry/source identity.
3. Split Docs vs Packs narrative.
4. Project-aware version resolution.
5. Retrieval eval and observability.
6. First-run DX / doctor.

Many of these are now partially or mostly implemented. Do not repeat this roadmap as if starting from zero.

Task:
Perform a sharp strategic gap analysis of current Docmancer vs Context7 and recommend what to do next.

Focus questions:
1. Where does Context7 still clearly beat Docmancer from an agent/user perspective?
2. Where can Docmancer become meaningfully better than Context7, not just equal?
3. Is Project-aware Docs Autopilot the right next wedge?
4. Should project-owned docs become a first-class MCP workflow, e.g. get_project_docs({ project_path, topic })?
5. How should Docmancer combine project-owned docs, local/private memory, and exact dependency docs without confusing trust/source boundaries?
6. What MCP tool UX changes would make agents prefer Docmancer automatically?
7. What coverage/registry strategy should Docmancer use without becoming a hosted Context7 clone?
8. What should we explicitly NOT build yet?
9. What metrics should decide success?
10. What is the concrete PR sequence?

Constraints:
- Keep Docmancer local-first.
- Do not require hosted query API.
- Do not make Packs the hero product.
- Avoid broad schema rewrites unless justified.
- Prefer small PRs with tests.
- Optimize for coding agents actually using MCP tools correctly.
- Optimize for trust: source attribution, version exactness, no silent wrong docs.
- Optimize for first useful answer.
- Official project docs should be reviewable files, not hidden DB-only knowledge.

Please return:
A. One-sentence strategic thesis.
B. Top 5 gaps vs Context7.
C. Top 5 unfair advantages Docmancer should lean into.
D. Recommended next 30-day milestone.
E. 10 concrete PRs in order.
F. 3 demo scenarios that would convince users.
G. MCP tool/API changes, if any.
H. Registry/coverage strategy.
I. Evaluation metrics and thresholds.
J. Risks and anti-goals.
K. If you had to choose only ONE thing to build next, what is it and why?
```
