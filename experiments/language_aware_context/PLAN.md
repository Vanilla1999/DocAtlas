# TDD-план: language-aware context, отдельный PR от main

База: `58c7f37c2a5ef686bcd6562abbade91ba94e347a` (`main`, проверен 2026-09-30).
Рабочая ветка: `experiment/language-aware-context`. Статус: DRAFT.

Это адаптация согласованного T0–T9-плана к main, не перенос старой task-44 ветки.
Исполняемые примеры вынесены в `reference_core.py`, `baseline_probe.py` и тесты,
чтобы код не расходился с копиями в Markdown. Фактический прогресс — STATUS.json.

## 0. Задача, а не обещанный результат

H1: улучшает ли профиль языков выбранных источников уже существующие агентские
`lookup_queries`? H2: улучшает ли ограниченная сборка канонического контекста
доставку фактов при тех же запросах и бюджете? H3: улучшается ли настоящий ответ
основной модели агента?

Прежние 11/11 НЕ baseline и НЕ критерий завершения. Там были самописные поиск,
квалификация, упаковка, просмотренные вопросы, ручные lookups, EN-корпуса и
проверка эталона, изменённая после просмотра ответа. Grounded-like 6/7 тоже не
является запуском Grounded. Эти цифры не использовать в новых таблицах качества.

Допустимые итоги: полезен профиль; полезна сборка; полезны оба; усложнение не
полезно; INCONCLUSIVE; BLOCKED. Не добиваться заранее выбранного PASS.

## 1. Неизменяемые ограничения

- Не менять production default, публичный MCP surface, P0, dependency lockfile,
  frozen v3, его digests и исходные эталоны. Не снижать лексические пороги.
- Не переносить старые commits MPNet/BGE. Их `0.7453`/диагностический `0.01`
  не перекалибровывать и не использовать в новом эксперименте.
- `question` сохраняется посимвольно. `" /-S"` != `"/-S"`; регистр важен.
- Профиль/lookup/соседство не создают factual coverage, answer_supported,
  answer_available или edit_ready и не расширяют разрешённую область.
- Не обходить policy/reference/exact/local-witness veto. Все добавленные bytes
  проходят реальные проверки; нельзя заменить их `qualified=True`.
- `scope=all` — repository-local, не поиск по глобальному библиотечному кэшу.
  Не добавлять выдуманное поле library в get_docs_context.
- Не вводить скрытый предварительный docs_status. Не считать read_next первым
  пакетом. Cold/warm профиль — разные условия с отдельным учётом стоимости.
- Source corpus, labels, ответы и ключ слепой оценки раздельны. Никогда не
  индексировать целый каталог эксперимента вместе с разметкой.
- Нет новых моделей внутри сервера. Внешняя модель агента всё ещё нужна для
  измерения H1/H3. Ручной lookup разрешён как dev/plumbing, но не как live A/B.
- Разрешена эта отдельная ветка и draft PR к main. Merge, product activation,
  платные jobs, публикация приватных данных и изменение старой ветки не разрешены.

## 2. Что переиспользовать на main

| Точка | Назначение |
|---|---|
| roadmap/README.md | Действующий P0 и граница live/deterministic evidence |
| docmancer/mcp/agent_workflow_contract.py | Host lookups, неизменный вопрос, scope, один первый вызов |
| docmancer/core/structured_chunking.py | Настоящие parents/children, source spans, display/retrieval text |
| docmancer/core/_sqlite_store_part05.py | adjacent_section_ids; не создавать параллельный индекс соседей |
| docmancer/docs/domain/query_reference_binding.py | query_mentions и occurrence/reference binding |
| docmancer/docs/domain/evidence_qualification.py | Policy и квалификация |
| docmancer/docs/application/context_query_probes.py | Повторная квалификация |
| docmancer/docs/application/_docs_context_projection_core.py | Реальная граница финальной доставки |
| eval/evidence_quality_v2/runtime.py | write_project, isolated_service, index_project |
| eval/evidence_quality_v2/observer.py | observe_call настоящего handler |
| eval/evidence_quality_v2/run.py | audit_payload и замороженные исходники |
| docmancer/docs/application/model_visible_projection.py | docs_context_budget_tokens |
| tests/diagnostic_labels.py | Обязательная регистрация тестов |

Старые roadmap/44_CROSS_LINGUAL_RETRIEVAL_AND_BOUNDED_RELEVANCE.md,
experiments/crosslingual_relevance/FINAL_REPORT_V3.md и regression_compare.py
были на старой экспериментальной ветке, но НЕ являются зависимостями main.
Для исторического чтения использовать ref 3d5eae755147b0d866a22c7336087895431b8792.
Не сливать ту ветку ради этих файлов и не импортировать отсутствующий модуль.

## 3. Матрица до реализации

| Arm | Планировщик | Поиск и сборка |
|---|---|---|
| A | Настоящий агент с текущими lookup_queries, без профиля | Текущий lexical |
| B | Тот же агент + проверенный профиль | Тот же lexical |
| C | Байт-в-байт сохранённые запросы A | Lexical + сборка |
| D | Байт-в-байт сохранённые запросы B | Lexical + сборка |
| E | Тот же агент, общая инструкция RU/EN без процентов | Текущий lexical |

Сначала генерировать и сохранять запросы A/B/E; затем replay A/C и B/D. Не
вызывать планировщик заново для C/D. A0 без lookups — только dev-диагностика.
Разность B-A/D-C изолирует профиль, C-A/D-B — сборку, D-A — совместный эффект.
B-E проверяет, нужны ли проценты сверх простого двуязычного поиска.

Предлагаемый профиль v0 (ещё НЕ заморожен): максимум 3 lookups по 240 символов;
20 кандидатов на общей сравниваемой границе, 4 seeds, до одного предыдущего и
одного следующего фрагмента в том же parent. Новые кандидаты занимают места
в общем лимите. Более строгие существующие ограничения имеют приоритет.
`max_sections_per_source=2` одинаков во всех arms. Пакет <=800 настоящих DTO
токенов; len(text)/4 не замена. Hint отдельно <=128 токенов, с учётом его полной
стоимости в сценарии. Не расширять бюджеты после просмотра результатов.

Warm: sidecar из разрешённого снимка передаётся до вопроса в экспериментальный
вход планировщика. Это не доказывает доставку через реальный MCP клиента.
Cold/устаревший/неразрешённый profile: первый вызов как A; нет скрытого status.
Если рабочая предварительная доставка не установлена, записать
profile_delivery_in_product=BLOCKED. Позднее улучшение — не first-packet gain.

## 4. Правило TDD

Для каждого этапа: тест -> inventory -> первый запуск -> причина RED ->
минимальное исправление -> та же команда -> соседние регрессии -> отчёт.
Отсутствующая зависимость, collection/import error и отсутствие модели/data —
BLOCKED, не поведенческий RED. Уже работающий контроль — BASELINE_GREEN.
Не ломать baseline и не ослаблять assertion, чтобы получить красивый RED/GREEN.
Не прерывать отчётный прогон через -x. Не переписывать старые логи/артефакты.

## T0. Окружение и исходное состояние

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
.venv/bin/python --version
.venv/bin/python -m pip freeze --all
.venv/bin/python -m pytest --version
```

Проверить ancestry к указанному main. Не reset/clean/stash чужие изменения.
Зафиксировать baseline SHA, diff identity, Python/SQLite/dependencies, config,
corpus hashes, frozen hashes. Не печатать API keys или весь environment.
Проверить реальные импорты и `docmancer.__file__`, чтобы editable install не
отправил baseline в другой worktree. Gate: полный checkout/импорты доступны.
Если нет — T0 BLOCKED; независимые helper-тесты допустимы без E2E-утверждений.

## T1. Настоящий baseline и корректность оценки

Первое действие после T0 — opt-in `baseline_probe.py`; он вызывает настоящие
runtime/index/observer/audit, не имитирует BM25, qualification или projector.
Source manifest содержит только path/sha256, читаются лишь перечисленные .md.
Проверить битые hashes, path traversal, symlink, duplicate path и чужие labels.
Запрос содержит только исходный question и optional lookups. Нет policy overrides.
Отчёт новый, запись exclusive; NaN/Infinity запрещены. Handler failure остаётся
failure, а не отсутствие релевантных фактов. Audit failure отделён от качества.

Эта заготовка маркирует supplied lookups как unverified development. Она ещё не
принимает роль live A или независимого evaluation. Ни language-profile integration,
ни C/D adapter в ней не реализованы. Копия library docs в проектной fixture не
проверяет настоящий library resolver. У библиотечных тестов отдельный путь.

На известных вопросах получить A0 и A без изменения эталонов. Оценщик проверить:
полная каноническая цитата; потерянное условие; утраченная частица not;
правильная тема без ответа; неверный path/range; эталон отсутствует в canonical.
Разные факты могут иметь разные цитаты; отдельный связный факт должен иметь
полное свидетельство, а не слова, собранные из несвязанных мест.
Нет substring-оценки вида 'teardown AND lifespan -> complete'.

Gate: реальный handler/trace сохранены и assessment проходит позитивные и
негативные контроли. Невозможность этого запуска НЕ разрешает симуляцию.

### Inventory

Каждый новый test module зарегистрировать в отдельном
`tests/diagnostic_labels.language_aware_context.json`. Label должен соответствовать
проверке (behavioral/schema/artifact/serialization/compatibility). Hash node IDs:
SHA256 от '\n'.join(sorted(unique_nodeids_without_parametrization)). Проверять
pytest collection и реальный loader; не отключать inventory/conftest в checkout.
Изолированная проверка helpers вне checkout маркируется отдельно.

## T2. Язык прозы, не кода

Сначала тесты: EN prose; RU prose с большим Kotlin/code block; mixed prose;
только идентификаторы; короткий фрагмент; Markdown fences с отступами и незакрытые
fences; URL/inline code; украинский/польский/немецкий; повторённые headings.
Language != script: кириллица не доказывает RU, латиница не доказывает EN.

Реализовать извлечение неперекрывающихся prose ranges на каноническом snapshot.
Переиспользовать parser/atomization; не писать split по # без учёта code fences.
Код не входит в доли прозы, но остаётся неизменным поисковым свидетельством.
`classify_clean_prose` в reference — только draft для УЖЕ извлечённой прозы.
Это не Markdown parser и не подтверждённый многоязычный detector.

Агрегировать en/ru/und по одному знаменателю (prose letters), не смесь процентов
документов/chunks/токенов. Дедуплицировать повторные диапазоны. Unknown не
переименовывать в English; искусственной confidence нет. Не доверять frontmatter
language без проверки. Не выбирать языки по содержимому вопроса или gold.
Порог/правила detector менять только development, затем freeze до evaluation.

Gate: отдельно размеченные prose fixtures, confusion matrix и unknown coverage;
профиль не влияет на допуск документов. Кодовые имена не переводятся.

## T3. Binding и sidecar профиля

Тесты: разные scopes/версии/generations/catalog hashes; добавление, изменение,
удаление документа; denied источник не попадает в профиль; changed detector;
пустая/неполная/unknown-only выборка; Kotlin не становится глобальным профилем.

Ключ минимум: resolved scope_id + version + generation_id + allowed catalog hash
+ detector revision. Metadata из разрешённого снимка, не полного дискового кэша.
Профили scopes не усредняются. Несовпадение identity -> no hint, не guessed language.
Sidecar создаётся локально атомарно после успешного ingest; преждевременная запись
не должна создать видимость профиля нового, ещё не опубликованного поколения.
Проверить stale/read races и политику доступа для самих метаданных.

Сохранять minority languages (99% EN не запрещает 1% RU). Query languages — hint,
не query filter. `und` тоже учитывается в знаменателе. Полная стоимость hints
учитывается даже если warm profile был передан до первого get_docs_context.

Gate: версия, scope и доступ доказаны тестами; план продуктовой доставки отдельно.

## T4. Запросы основного агента и литералы

Использовать уже существующие lookup_queries, не вводить второе публичное API.
Сохранить оригинальные offsets через query_mentions. Защитить точные литералы
placeholders, проверить roundtrip и восстановить их без casefold/strip/нормализации.

Пример (unit fixture, не новый benchmark): вопрос 'Чем отличаются ` /-S` и `/-S`?'
должен сохранить оба литерала с разными offsets. Не всякая quoted phrase является
техническим литералом: adapter использует роли существующего parser.

Промпт (одинаковая основа A/B/E):

```text
Сформируй до трёх коротких lookup_queries для одного исходного вопроса.
Исходный вопрос не меняй. Сохрани отрицания, условия и стороны сравнения.
Профиль — подсказка, не фильтр или подтверждение ответа.
Не добавляй предполагаемые значения/API-ответы и guessed source paths.
Технические [[LIT_N]] сохрани без изменения. Верни JSON lookup_queries.
```

Тесты: whitespace/case literal roundtrip; missing/invented placeholders;
malformed JSON; duplicate original lookup; лимиты; extra scope/policy keys;
negative/conditional intent. JSON-validator НЕ доказывает семантическую
эквивалентность: это отдельный blinded review. Нельзя генерировать timeout=None,
если значение не было в вопросе/уже полученном свидетельстве.

До просмотра retrieval результатов сохранить model ID/revision/runtime/settings,
prompt, полные ответы и их hashes. Ручные исправления live lookups запрещены.
Для C/D сохранить ровно A/B. False flags значат no server certification, а не
обязательный отказ агента от допустимого частичного ответа.

Gate: корректные реальные запросы получены без доступа к gold. При отсутствии
агента helper-тесты возможны, но H1 BLOCKED, а не ручная подстановка ответов.

## T5. Ограниченная сборка после настоящего seed

Сначала positive control: seed реально квалифицирован рабочим кодом, есть в
актуальном index/trace. Запись 'admitted' в журнале или нарисованный trace недостаточны.
При нуле qualified seeds расширение ничего не добавляет. Context-only кандидат
не становится покрытием исходного вопроса из-за успешного host lookup.

Использовать существующий источник соседей, затем проверить same scope/version/
generation/source/parent, canonical bytes/ranges, актуальные policy/reference/exact/
local-witness ограничения. `adjacent_window` только предлагает окно; он ничего
не допускает. Stub callback в его unit test НЕ доказывает реальную source-policy.

Обязательные негативы: foreign project; wrong version; stale snapshot;
unsynchronized index; unsafe neighbor; риск возникает лишь в объединённом окне;
скрытое между фрагментами not; другой parent; overlap; forged bytes/hash;
слишком длинный сосед; не помещающаяся полная code/table atom; irrelevant neighbor.
В тесте unsafe сначала положительно доказать, что без риска тот же seed и
сосед действительно участвовали бы в доставке. Не использовать пустой корпус.

Новое окно — один срез оригинала либо несколько отдельно атрибутированных срезов,
не склейка несоседних bytes под одним range. Пересчитать ranges/hash/bindings и
повторно проверить объединённый текст: он может обнаружить новый риск.
Затем реальный DTO budget/projector; не обрезать условие, not или fence для fit.
Если не помещается, оставить допустимый seed; partial остаётся partial.

Каждый добавленный кандидат входит в общий K. Измерять вытесненные полезные
свидетельства и шум. Не подменять qualification, не обходить source-policy.
При отсутствии безопасной injection point — T5 integration BLOCKED с указанием
точной функции; нужен отдельный reviewed diff, а не снятие проверок.

Gate: proposal helpers и реальный adapter проверены раздельно. Внешние статусы
answer_supported/edit_ready и covered_query_ids не повышены новым механизмом.

## T6. Настоящий end-to-end

Сначала traced A: corpus -> index -> retrieval -> qualification -> selection ->
projection. Найти первую потерю нужного факта. Ни filename hit, ни index coverage,
ни read_next не доказательство first packet. Исходный HTTPX intro не объявлять
потерянным при chunking без подтверждения на актуальном parser/trace.

Тесты A/C и B/D используют одинаковые документы, queries и budgets. Требовать:
status не failed; exact original question; canonical path/range/bytes; <=800 по
реальному docs_context_budget_tokens; факты и условия полны; отсутствуют veto
violations. Проверять наши policy controls и реальные библиотечные scopes отдельно
от копий library docs как project fixtures. Не считать один get_docs_context
запуск доказательством качества ответа основной модели.

Authority test: сначала фактическая доставка нового фрагмента, потом проверка
отсутствия необоснованного support/edit/coverage повышения. Fallback mode и
ошибки handler имеют собственный статус. Не возвращать заранее собранный payload.

Gate: настоящие E2E тесты выполнены. Если protected production semantics нельзя
сохранить — NO_GO/BLOCKED, не невидимое изменение P0.

## T7. Независимые данные и freeze

Предложение для exploratory v0: development 18 вопросов/6 scopes; evaluation
36 вопросов/12 других scopes. В evaluation 12 RU, 12 EN, 12 mixed; scopes EN-only,
RU-only и mixed. Это дизайн, НЕ готовый dataset и НЕ power analysis.

Содержательные случаи: pure-RU -> EN; EN -> RU; shared API anchors; minority
language answer; mixed same document; code-heavy text; negative/conditional;
comparison sides; no answer; scope/version veto; cold/stale hint. Сначала
canonical sources и hashes, затем независимая task-level разметка complete/partial/
not helpful/source allowed. Не требовать фразы, отсутствующей в документе.

Typer/M1.5 уже просмотрены и остаются dev. Не включать их переводы в независимый
split. Не разделять один факт/переводы/почти дубликаты между splits. Реальный
corpus должен иметь полноценные distractors, а не один специально выбранный gold.

До запуска freeze source manifest, tasks/labels, scope resolver, detector,
prompts, model identity, budgets, code revision, metrics/criteria/order seeds.
Параметры protocol.proposed.json НЕ lock: freeze создаётся отдельно только после
проверки данных. Нет данных/независимой разметки -> DATA_BLOCKED, никаких процентов
качества из synthetic unit fixtures. Unjudged не объявлять нерелевантным.

Gate: hashes проверяются до/после; retrieval/planner не имеют доступа к labels.

## T8. Live A–E, oracle и слепая оценка

Одна закреплённая модель планировщика и ответчика, одинаковый prompt/runtime/
decoding. Провайдерная идентичность фиксируется честно; alias не exact revision.
Планировщик видит только исходный question, разрешённый scope и hint своего arm.
Не генерировать C/D запросы заново. Порядок arm executions заморозить/перемешать;
кеши и ресурсные лимиты одинаковы. Всегда хранить реальные provider responses.

Ответчик получает только вопрос и одинаково отформатированный контекст без
названий arms. Oracle содержит достаточную canonical цитату, не готовый ответ.
No-context prompt имеет ту же инструкцию. Судья не tested model, видит критерии,
эталоны и ответы с opaque IDs, но не ключ arm mapping. Автор, видевший arms,
не называет собственную ретроспективную оценку слепой. Раскрыть назначения после
фиксации judgments. Модельные ответы не заменять шаблонами.

Метрики раздельно по RU/EN/mixed и языку свидетельства:
- profile confusion/unknown, стабильность scope/minority routing;
- fidelity lookups: литералы, negation/conditions, отсутствие guessed answers;
- факт найден / доставлен / использован правильно — три разных показателя;
- full/partial packet и ответ, unsupported claims, citation correctness;
- добавленный irrelevant context, ошибочные допуски, потерянные прежние факты;
- source-policy/authority violations;
- все tool calls, input/output tokens, hint tokens, p50/p95 времени и cold/warm.

Ни query count, ни chars/4 не замена фактической стоимости. Token counts разных
провайдеров не смешивать. Ошибки/skip не исключать молча из знаменателя. Дать
парные исходы и uncertainty по независимым task families, не по повторным runs
одного вопроса. Показывать индивидуальные переходы и не скрывать регрессии средним.

Предлагаемый engineering gate (заморозить до evaluation): для совместной
рекомендации D vs A >=3 новых полных пакетов на разных families и >=2 новых
правильных ответа, без потерь прежних полных свидетельств и без новых trust/
authority нарушений. Это НЕ научная гарантия и не заменяет confidence intervals.
При широких интервалах INCONCLUSIVE. Если B не лучше A/E, не внедрять профиль ради
процентов; если полезна лишь C, рекомендовать только сборку.

Grounded — дополнительный контроль только реально установленной pinned версии
с зафиксированным корпусом/config. Отдельно одинаковый бюджет и native режим.
Не имитировать его splitter/FTS. Нет запуска -> COMPETITOR_BLOCKED. Наш A–E
эксперимент остаётся самостоятельным, но сравнения продуктов тогда нет.

Gate: реальные ответы и blind judgments, по каждому H1/H2/H3 независимый вывод.

## T9. Регрессии и завершение

```bash
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 .venv/bin/python -m pytest tests/ \
  -m 'not advanced and not live and not live_network' \
  --junitxml=/ABS/UNIQUE/RUN/regression.xml
```

Два worktrees, одна зависимостная среда и одинаковые параметры; проверить imports
в каждом. Сравнивать общие node IDs отдельно от новых tests. Сохранить команды,
stdout/stderr/exit. Статусы: NEW_REGRESSION, EXISTING_SAME, EXISTING_CHANGED,
FIXED, NEW_TEST, SKIPPED, NOT_RUN, ENVIRONMENT_ERROR. All skipped != completed gate.
Проверить защищённые hashes/MCP surface и отсутствие product activation.

В git только reviewed code/plan/tests/обезличенная сводка. Raw review_runs,
private corpus, model weights и credentials остаются локально. Итоговый отчёт:
baseline/candidate/protocol/corpus identities, warm/cold delivery, реальный
handler/live flags, null для не измеренных эффектов, регрессии, blockers,
PASS_EXPERIMENT/NO_GO/INCONCLUSIVE/BLOCKED. Ни unit count, ни 11/11 не даёт права
на product PASS. Отдельное решение мейнтейнера требуется для активации и merge.

## 5. Как работать слабому исполнителю

Один этап за цикл. Сначала прочитать README/STATUS и не повторять уже сделанное.
T0/T1 интеграция сейчас не доказана. Независимые helper checks можно выполнять,
явно сохраняя blocked статусы. Не копировать весь reference как production code.
В отчёте: Stage / tested boundary / RED или BASELINE_GREEN / diff / GREEN /
что не доказано / один следующий шаг. Нет безопасной точки интеграции — указать
точную функцию и ограничение, не придумывать API.

Исполняемые ориентиры: reference_core.py, baseline_probe.py. Тесты находятся в
`tests/docs/test_language_aware_context_reference.py` и
`tests/docs/test_language_aware_context_probe.py` от корня репозитория.
Их callbacks/fixtures — unit controls, не сравнение с Grounded и не весь DocAtlas.
