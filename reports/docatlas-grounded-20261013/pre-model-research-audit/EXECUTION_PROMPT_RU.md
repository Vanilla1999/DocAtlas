# Промпт: исправления API и доказательный аудит до отвечающей модели

## Контекст и цель

Ты работаешь в DocAtlas:

- Репозиторий: `/tmp/opencode/docatlas-heuristic-removal-20261013`.
- Ожидаемая ветка: `experiment/heuristic-removal-20261013`.
- Коммит исходного аудита: `304b56e1`; перед работой установи фактический HEAD.
- Обязательные правила: `AGENTS.md`, включая правила проверок и runtime.

Исправь два обнаруженных нарушения публичного API, затем проведи доказательный
аудит текущей цепочки до модели, составляющей ответ. Embeddings сами могут быть
нейросетевым этапом. Не считай удаление эвристик доказательством качества retrieval.

Разделяй допустимость источника, сохранность текста, релевантность, достаточность
набора фактов, соблюдение бюджета и качество конечного ответа.

## Начальное чтение

Проверь `git status`, ветку и HEAD. Сохрани незакоммиченные материалы и чужие
изменения. Прочитай:

1. `reports/docatlas-grounded-20261013/pre-model-research-audit/RESULT_RU.md`
2. `reports/docatlas-grounded-20261013/pre-model-research-audit/SDK_BUDGET_REPRO.json`
3. `reports/docatlas-grounded-20261013/heuristic-removal-legacy-proof/RESULT_RU.md`
4. `reports/docatlas-grounded-20261013/heuristic-removal/METHOD_CONFORMANCE.md`
5. `reports/docatlas-grounded-20261013/heuristic-removal/RESULT_RU.md`

Сначала установи действующие ограничения исполнения. Не запускай массовые
наборы, модели или сервисы. Если необходимая проверка превышает разрешённый
runtime, подготовь план и запроси разрешение. Не делегируй без отдельного запроса.

## Этап 1. Публичные limit/budget в SDK

Исходное воспроизведение: `DocmancerClient` при вопросе `Observatory`, `limit=1`,
`budget=100` вернул три фрагмента и форматированный контекст в247 o200k-токенов.
Документы и выдача зафиксированы в `SDK_BUDGET_REPRO.json`.

Путь для проверки:
`DocmancerClient → DocmancerAgent.query/query_context → SQLiteStore.query →
фиксированный acquisition ceiling → format_context`.

1. По коду, документации и существующим публичным сценариям установи контракт
   limit/budget: единицы, что учитывается, поведение слишком большого первого
   окна, пустой выдачи и параметров по умолчанию. o200k-измерение исходного
   воспроизведения само по себе не устанавливает договорённые единицы API.
2. Если меняются единицы или учёт форматирования, явно опиши изменение контракта;
   не представляй его как незаметное исправление.
3. Раздели внутренний acquisition-бюджет и публичное ограничение доставки.
   Исправь SDK, не уменьшая ранними delivery-отсечками внутренний пул MCP retrieval.
4. Сохрани порядок поиска, целые исходные окна и provenance. Не возвращай ручное
   relevance/utility ranking, source quotas или proof-completeness эвристики.
5. Проверь get_chunks и get_context на настоящем подготовленном индексе:
   маленький limit, тесный бюджет и вместимый бюджет. Ожидаемые факты и критерии
   зафиксируй до просмотра новой выдачи. Проверь текст, ограничения и состояние.

Файлы:

- `docmancer/client.py`
- `docmancer/agent.py`
- `docmancer/context.py`
- `docmancer/core/_sqlite_store_part03.py`
- `docmancer/retrieval/experimental_acquisition.py`
- `docmancer/retrieval/_dispatch_part01.py`

## Этап 2. Явно запрошенное lexical expansion

Исходный статический finding: lexical dispatcher передаёт `expand="none"`,
SQLiteStore.query принимает expand, но не использует его.

1. Проследи контракт none/adjacent/page и defaults через публичные entry points.
   Различай явно выбранный expansion, default и отключённый автоматический rescue.
2. Воспроизведи дефект публичным интеграционным сценарием до исправления.
3. Восстанови явно выбранное expansion по исходным координатам и структуре.
   Не возвращай автоматический parent rescue, graph boosts или source quotas.
4. Проверь доставку независимого соседнего факта, а не изменение metadata.
   Сравни none с adjacent/page там, где эти режимы предусмотрены контрактом.
5. Проверь исходный текст, hashes/spans, source/version/scope и конечный бюджет.
   Expansion не должно читать чужой источник или другую generation.

Файлы:

- `docmancer/core/config.py`
- `docmancer/agent.py`
- `docmancer/core/_sqlite_store_part03.py`
- `docmancer/retrieval/_dispatch_part01.py`
- `docmancer/retrieval/_dispatch_part02.py`
- `docmancer/core/structured_chunking.py`
- `docmancer/core/prepared_parent_sections.py`

## Правила проверки исправлений

Сначала переиспользуй существующие интеграционные сценарии:

- `tests/test_heuristic_removal_public_integration.py`
- `tests/test_prepared_retrieval_integration.py`

Для installed-проверок изучи:

- `eval/heuristic_removal/installed_stdio.py`
- `eval/heuristic_removal/installed_cli_context.py`

Средства изолированной подготовки и receipts:

- `eval/evidence_quality_v2/runtime.py`
- `eval/heuristic_removal/receipts.py`

Не добавляй unit-тесты. Не подменяй retrieval/storage/selection/validation.
Не меняй исходные документы, вопросы и критерии ради PASS. Проверяй конечный
результат и read-only состояние, а не только exit0 или внутренний флаг.
Installed SDK проверяй установленным пакетом, не импортом source tree;
installed CLI/stdio не заменяют проверку SDK. Не называй один уровень доказательством
другого. Не повторяй одинаковый набор без новой причины.

Проверь механизм `tests/diagnostic_labels.heuristic_removal.json`; если изменения
сценариев требуют обновления hash/manifest, обнови его по действующим правилам.

## Этап 3. Соответствие реализации основаниям

Для каждого существенного этапа составь цепочку:

**Требование → первичный источник/исследование → опубликованный метод →
фактическая реализация → отклонение → имеющееся доказательство → неизвестное.**

Покрой membership/access/scope/version/freshness, extraction, chunking,
query processing, lexical/dense/sparse acquisition, fusion, admission,
selection/dedupe, expansion, packing/serialization и достаточность контекста.

Разделяй исследовательское обоснование метода, инженерный контракт и локальные
параметры. Не требуй paper для каждого инженерного ограничения; не выдавай
локальный лимит за научно установленный. Цитируй методические разделы первичных
источников. Не переноси gains другой системы на DocAtlas и не называй heading
prefix воспроизведением Anthropic Contextual Retrieval, а native-order packing — SetR.

Релевантные материалы:

- `eval/heuristic_removal_holdout/research/`
- `reports/admission-experiments/prepared-retrieval/late-context-diagnostics-20261012/RESEARCH_RU.md`
- `reports/admission-experiments/admission-full-20261012/RESEARCH_METHOD_AUDIT_RU.md`
- `experiments/grounded-partial/contextual-late/SELECTION_RESEARCH_RU.md`
- `docmancer/docs/application/_evidence_selection_part02.py`
- `docmancer/docs/application/experimental_context_finalization.py`
- `docmancer/docs/application/docs_context_projection.py`
- `docmancer/docs/domain/original_body_discovery.py`
- `docmancer/retrieval/fusion.py`

## Этап 4. Установленные и неизвестные потери фактов

Сначала используй сохранённые результаты и открытые regression-сценарии.
Для каждого исследованного вопроса составь таблицу:

| Вопрос / обязательный факт | В исходном корпусе | В acquisition | После admission | После selection | В конечном контексте | Первая доказанная потеря / основание |
| --- | --- | --- | --- | --- | --- | --- |

Обязательные факты бери из независимых исходных документов и существующего
oracle, не вычисляй их проверяемым production-кодом. Перед новой выдачей фиксируй
ожидания. Для каждого результата укажи коммит, конфигурацию и границу исполнения.
Исторические results — основания гипотез, не измерение текущего HEAD.

Если трассы недостаточно, укажи неизвестный этап. Отсутствие записи в логе
не доказывает отсутствие факта. При необходимости выполни минимальный разрешённый
публичный сценарий на текущем коде. Диагностика должна включаться/выключаться,
не меняя результат, права, источники и число продуктовых вызовов; MCP stdout
не используй для логов. Проверка конечной выдачи остаётся независимой от трассы.

Отдельно учитывай полноту фактов, useful partial, неподтверждённые гарантии,
provenance/source restrictions, размер выдачи, реальные вызовы и время.
Право цитировать и answer_supported=false не являются метрикой достаточности.

## Границы и следующий эксперимент

Не добавляй модели и не меняй chunking/fusion в рамках API-исправлений.
Подготовь отдельный ограниченный план сравнения: фиксированные вопросы/документы,
код и конфигурация, общий конечный бюджет с явным учётом overhead, число реальных
вызовов, время, независимые критерии и условия остановки. Не запускай его без
необходимого разрешения. Старый NEW20 — уже просмотренный набор, не новый holdout.
Оценка конечного ответа требует отдельного одинакового model/prompt эксперимента.

## Итоговые артефакты и критерии завершения

Предоставь:

1. Исправления API с объяснением контрактов и отсутствия ранних MCP-отсечек.
2. Публичные воспроизведения до/после, команды, окружение, фактическую выдачу,
   hashes и результаты проверки read-only состояния.
3. Матрицу соответствия исследований и фактической реализации.
4. Таблицу потерь по вопросам с независимыми исходными основаниями.
5. Отдельные списки: подтверждённые дефекты; допустимые инженерные решения;
   гипотезы для сравнения; неизвестные свойства.
6. Для каждой существенной неизвестности — минимальную проверку, которая её разрешит.
7. Результаты выполненных проверок и точный список невыполненных, с причинами.

Не заявляй «всё правильно по исследованиям», «все эвристики удалены» или
«качество улучшилось» без соответствующего доказательства. Если исправления
завершены, но анализ заблокирован, явно раздели эти статусы.
Не выполняй commit/push/merge/deploy без отдельного разрешения пользователя.
