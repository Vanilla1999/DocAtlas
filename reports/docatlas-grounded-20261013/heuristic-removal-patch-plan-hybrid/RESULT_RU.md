# Patch-plan, identifier admission и настоящий hybrid

Продолжение изменений поверх `b9ef424d` и незакоммиченного этапа
`heuristic-removal-vector-patch`. Ни один из двух новых этапов не пушился.

## Удалённые правила

- Из patch-plan удалены веса basename/symbol/import/usage 100/80/50/20,
  boost для changed file, score-based дедупликация, inferred snake/Pascal
  варианты в активном поиске, graph seed thresholds, graph-neighbor expansion
  и переранжирование по накопленным graph boosts.
- Поиск code context теперь буквальный OR по словам исходного вопроса и
  явно переданным symbol_queries внутри существующей конечной membership.
  changed_files выбирают только разрешённые literal members. Выдача сохраняет
  порядок декларации. Совпадение пути даёт исходный source window, не
  выдуманный символ. Boundary/source policy не ослаблялись.
- Patch-plan получает content_hash и буквальные refs с координатами. Его
  current_behavior использует уже прочитанные окна и hashes, без повторного
  чтения файлов и отдельного лимита first-five. Поведение остаётся unknown.
  Упаковка удаляет целые хвостовые записи под общим бюджетом, без field/topic
  preferences. Слишком маленький бюджет не гарантирует вместимость фиксированного
  envelope; это не скрывается как точная token-cap гарантия.
- Удалён identifier-prefix conflict из patch admission. Строковый префикс
  больше не выбрасывает допустимый исходник; проверки identity/scope/version,
  freshness и rejected sources остаются, assignment/readiness не подменяются.
- Удалены `_run_hierarchical` и `_fuse_and_hydrate`, а также их dispatch branch:
  document-score aggregation/top-documents больше не ограничивают pool,
  в том числе при старом `hierarchical.enabled=true`. Config DTO сохранён
  только для чтения старых конфигураций; docstring явно описывает это изменение.
- Из SQLite hydration убран выдуманный score `1 - rank * 0.05`. Само чтение
  секции не назначает relevance; dispatcher передаёт действительный fusion score.

Стандартные BM25, vector similarity и настраиваемый RRF/weighted RRF не
заменялись другой ручной системой весов. Явный adjacent/page expansion и
конечные runtime/candidate budgets сохранены как параметры retrieval метода.

## Проверки

### Source-tree public integration

`patch-plan-final.log/xml`: **12 passed in 12.44s**:

```
tests/test_heuristic_removal_public_integration.py
tests/test_prepared_retrieval_integration.py
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_finds_relevant_source_files_by_exact_terms
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_normalizes_snake_case_and_pascal_case
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded
```

Три ранее существовавшие source-bound интеграции оставлены без изменений
вопросов, исходников и assertions. В сценарии с названием `normalizes` обе
формы уже явно переданы пользователем: PASS не доказывает наличие генерации aliases.

Новый публичный MCP сценарий содержит три запроса: полный literal result,
ограниченный его prefix и explicit member. В нём usage до declaration не
вытесняется старым definition score, graph-сосед не добавляется автоматически,
snake-case alias без буквального match не добавляется, undeclared source и
`../outside.py` не доставляются. Проверены тексты, hashes, line refs,
read-only action и отсутствие изменения файлов.

Расширен существующий library/version сценарий advanced patch-запросом
`Explain Navigation route registry` с Navigation в backticks: исходный факт о
NavigationRegistry доставляется без ложной edit authority и без подмены версии.
Это positive repro прежнего prefix conflict, а не признание ответа достаточным.

### Реальные sparse и hybrid

Отдельный opt-in сценарий:
`eval/heuristic_removal/hybrid_native_integration.py`.

Production ingest + retrieval runtime; **ни retrieval, ни provider, ни storage,
ни validation не подменяются**. Изолированный Qdrant 1.19.2, настоящие модели
`BAAI/bge-small-en-v1.5` (dense) и `Qdrant/bm25` (sparse).
Две проверки через один runtime: sparse и hybrid. Это один stateful сценарий
с двумя retrieval-вызовами, не два дополнительных pytest-теста.

`real-hybrid-final/RESULT.json`: PASS. Final run использовал уже загруженный
отдельный cache с `HF_HUB_OFFLINE=1`. Модели/бинарник не добавлены в repository.

- sparse: 3 candidates, 3 доставленных окна;
- hybrid: lexical=3, dense=4, sparse=3; 3 доставленных окна;
- errors/fallback отсутствуют; hybrid действительно задействует три канала;
- три независимых факта (73 mm, 19 seconds, 41 nights) доставлены из
  `observatory.md`, несмотря на legacy source quota=1/hierarchical.enabled=true;
- `secret.md`/HIDDEN_97 отсутствуют; source text, content/source SHA-256,
  char/byte spans проверены по исходной строке;
- после каждого чтения проверены SQLite logical snapshot и полный небольшой
  Qdrant points snapshot (payload + dense/sparse vectors);
- Qdrant завершён в finally; final log содержит SIGTERM/graceful shutdown.

Четвёртый dense candidate — служебная ownership sentinel с hydration id 0,
видимая в contributions, но не превращённая в source window. Candidate counts
не следует интерпретировать как количество доставляемых документов.

Команда воспроизведения после явной подготовки бинарника и model cache:

```
HF_HUB_OFFLINE=1 python -m eval.heuristic_removal.hybrid_native_integration \
  --qdrant-binary /path/to/qdrant \
  --model-cache /isolated/models \
  --output /new/output/directory
```

Требуются production dependencies и tiktoken cache. Сценарий сам владеет
временным storage и процессом на свободном loopback HTTP-порту; gRPC отключён.
Новый endpoint не публикуется как рабочий сервис приложения.

## Разбор логов и неуспехов

- `patch-plan01`: 2 PASS / 1 FAIL. Для literal basename без текстового match
  не было refs. Исправлен продукт: path match теперь возвращает whole-source
  window без выдуманного символа. Старый oracle не менялся.
- `patch-plan02`: исправленный старый сценарий и новый публичный — PASS.
- `patch-plan03`: 12 PASS до устранения synthetic hydration score.
- `patch-plan-final`: 12 PASS после изменения score.
- `real-hybrid01`: Qdrant не применил JSON config-path и поднялся по умолчанию
  на 0.0.0.0:6333/6334, с включённой telemetry. Storage был в отдельном cwd;
  процесс остановлен finally. Ни ingest, ни retrieval в этот запуск не дошли.
  В telemetry логе — TLS error. Это ошибка harness, не успешная изоляция.
- Исправление harness: YAML config и продублированные env overrides для host,
  HTTP-port, storage, snapshots и telemetry. Последующие логи подтверждают
  loopback, выбранный отдельный порт, отключённую telemetry и shutdown.
- `real-hybrid02`: первый успешный real-model запуск.
- `real-hybrid-final`: дополнительный запуск после усиления независимых
  hash/span и Qdrant state checks; PASS без сетевого получения моделей.

В `patch-plan-final.log` восемь включённых request-end событий. Трасса не
является полным ledger всех вызовов: остальные запросы без tracing.
`LOG_ANALYSIS.json` содержит итоговые counts, события и SHA-256 всех логов/XML.
Проверки конечных фактов, источников и состояния независимы от логов.

## Границы и остаток

- Unit не запускались. Старые private-helper unit imports не мигрированы.
- Это не installed-wheel/stdio/client/production smoke; SDK/CLI/mixed-context
  последствия обязательного live receipt по-прежнему не доказаны этим набором.
- Library upstream diagnostics gap остаётся; source-tree public output проверен.
- Policy/authorization checks сохранены. Полный аудит всех proof/witness
  assignment и альтернативных legacy entry points не завершён; отсутствие
  эвристик во всём продукте не заявляется.
- Sparse/hybrid runtime coverage из прошлого отчёта теперь дополнено настоящим
  backend/model прогоном; standalone OpenAI dense-индекс по-прежнему получает
  предусмотренный отказ hybrid без sparse_model.
- Качество relevance на большом корпусе и скорость не измерялись.

`git diff --check` — PASS. Изменения остаются в рабочем дереве.
