# План ухода от ручных смысловых словарей — RU/EN

Дата: 2026-10-06. Ветка: `integration/stage3-v2-identity-pr1`, MR #211.
Baseline: `8d2381d8c9d18498483feaaab918d93dfee47969`.
Статус: **PLAN / NOT IMPLEMENTED / NOT MERGE READY**.

## 1. Цель и определение DONE

Убрать ручное кодирование смысла вопроса через списки слов, stem/phrase mappings,
тематические regex, product/API-specific rewrite и ranking rules. Поддерживаемые
языки этой работы — **русский и английский**, включая RU-вопросы к EN-документам
и EN-вопросы к RU-документам. Идентификаторы/пути могут содержать произвольные bytes;
это не обещание семантической поддержки других естественных языков.

Полезный источник допускается как retrieval-only context без доказанного полного
ответа. Источник, scope, provenance, freshness, цитата и budget проверяются независимо.
Отсутствие распознанного intent не должно само по себе означать отсутствие контекста.

**Общий DONE одновременно требует:**

1. В согласованном runtime scope нет активных hand-written query→topic/translation/
   expected-answer/source-policy правил, включая fallback, config и prompt обходы.
2. Все записи [реестра](DICTIONARY_INVENTORY_RU.md) закрыты как `REMOVED` либо
   `TECHNICAL-RETAINED` с конкретным основанием. `OPEN`, `C`, `BLOCKED`, `DEFERRED`
   не считаются общим DONE. Семантический словарь нельзя закрыть как technical только
   потому, что он называется grammar, policy или normalization.
3. RU/EN factual-context regression suite и заранее замороженный holdout проходят
   утверждённый контракт; нет новых потерь обязательных цитат или integrity violations.
4. Источник каждой query proposal и каждого public coverage/authority claim проверяем.
5. Required CI, независимое review и разрешение владельца относятся к итоговому SHA.

Удаление одного файла, ноль результатов grep, падение числа failures или переход на
LLM сами по себе не доказывают ни качество, ни отсутствие скрытого словаря.

## 2. Что уже доказано, а что ещё нет

| Основание | Установлено | Не установлено |
|---|---|---|
| A/B одного `instruction_trust` block | Ложный security hit исчезает; на 3 настоящих trust-вопросах теряется нужная цитата | Безопасность такого удаления как самостоятельного fix |
| A/B всех retrieval aliases | RU facts с lookups 12/15→10/15, без lookups 8/15→1/15; EN Direct-15 replay 11/15→9/15; отдельные случаи улучшаются | Качество dictionary-independent replacement: replacement ещё нет |
| Attribution A/B | Legacy original coverage 11→0, при этом useful facts остаются в 10/15 случаях | Что прежнюю метрику можно просто обнулить/снять без миграции |
| Adversarial ablation | Те же 27/28 и module-scope/380>300 violations | Что словарь объясняет/исправляет все CI-блокеры |
| Code audit | В 383 Python-файлах выполнен scan; первично отмечены 33 группы, включая core/retrieval/Packs/patch/proof | Полнота audit runtime/config/templates; причинный вред каждого найденного правила |

Подробные результаты, limitations и hashes архива:
[RETRIEVAL_DICTIONARY_REVIEW_RU.md](RETRIEVAL_DICTIONARY_REVIEW_RU.md).
Direct-15 штатный test сейчас останавливается на README hash; диагностический replay
не заменяет этот gate. Grounded probes не доказывают устройство его внутренних алгоритмов.

**«Доказанный план» здесь означает:** выводы привязаны к source/эксперименту, а каждый
ещё не проверенный переход имеет собственный gate. Успех будущего redesign не объявлен заранее.

## 3. Целевая цепочка

```text
original question (RU/EN, без подмены)
  + explicit project/library/version/module/path/mode
  + optional caller lookup_queries
  → bounded query proposals с provenance
  → lexical/exact + проверенный RU/EN semantic retrieval
  → проверка разрешённого source/snapshot
  → ранжирование passages и выбор проверяемых windows
  → final context + точная citation attribution в действующем budget
  → отдельная необязательная проверка typed answer/edit claims
```

### Правила целевой архитектуры

- Query proposal — original, явно заданный lookup либо предложение общего языкового
  механизма. У proposal есть origin, parent, версия механизма и trace; product facts
  и заранее известные command names не подставляются таблицей.
- Explicit lookups остаются **необязательными**. Нельзя объявить RU question-only
  поддержку сохранённой, заставив все tests и пользователей добавлять English lookups.
- RU/EN semantic retrieval — кандидатная технология, не готовый факт. На P2 сравнить
  существующий exact/lexical + caller lookups с общим bilingual retrieval и, если
  нужен, bounded query rewrite. Выбрать один production route по измерениям.
- Если используется model rewrite: исходный вопрос и literals сохраняются; модель
  не устанавливает scope, freshness, answer/edit flags или эквивалентность coverage.
  Exact identities, числа, versions, отрицания и условия нельзя незаметно заменить.
  Механически непроверяемая смысловая эквивалентность не выдаётся за доказанную.
- Raw retrieval/reranker score — сигнал релевантности, не source authority и не proof.
  Нужен положительный и отрицательный control на topical relevance; пропуск любого
  current документа по совпавшему product name не считается решением.
- Hard source policy задаётся явным request/catalog/authorization contract, а не
  словами «policy», «research», «command» в вопросе. Source metadata тоже имеет provenance.
- Lookup показывает, чем найден фрагмент. Его успешность автоматически не даёт
  `query-original=covered`. Full/partial semantic claims остаются отдельной проверкой.
- Typed proof может не поддержать вопрос, сохранив найденный partial context.
  Для операций доступа/изменения отсутствие proof не превращается в разрешение.
- Технический parsing путей, JSON, quoted spans, форматных меток и schema enums
  допустим после аудита. Это не разрешение перенести смысловые aliases в «технический» parser.

## 4. Этапы и критерии завершения

Каждый этап — отдельный проверяемый diff/эксперимент. Исполнитель отвечает за
код/артефакты, независимый reviewer — за проверку claims, владелец — за изменение
публичных контрактов, принятие limitations и merge. Независимое review не заменять
самопроверкой автора. Этот документ не даёт разрешения merge.

### P0 — закрыть инвентаризацию и зафиксировать baseline

#### Текущий статус и проверка курса — 2026-10-06

**P0 ACTIVE / не закрыт; P1 только PREPARATION, P2–P7 не начаты.**
Подробный gate: [P0_TO_P1_GATE_RU.md](P0_TO_P1_GATE_RU.md).

- Выполнены 383-file candidate scan и source hashes, D01–D38 inventory,
  157 frame audit decisions, package isolation, generated host/prompt surface audit.
- Сохранены четыре same-call diagnostic baseline lanes, actual isolated SQLite
  snapshot/config/generation identity. Проверены 134 indexed sources в каждом
  lane и 98 final citations; полезные факты RU original 8/15, RU lookups 12/15,
  EN Direct-15 11/15. Red baseline checks не сняты и не объявлены green.
- Wheel import defect `patch_review_service → eval` подтверждён и записан;
  исправление production packaging не выполнялось в P0.
- **Главный незакрытый критерий:** scan ещё не превращён в полный поэлементный
  classification ledger с проверенными consumers/default/fallback/bridge paths.
  Поимённые AST references и group-level review не равны resolved call graph.

**Не отклонились по scope и гарантиям:** новые смысловые словари не добавлены,
production/gold/test contracts не менялись в audit slices; прежний локальный trust
diff сохранён как непринятый кандидат. P1 approvals, independent review и merge
не имитировались. Generated-config/package/index probes предусмотрены P0.
Подготовленные P1 drafts не заменяют закрытие P0.

**Отклонение в ходе выполнения:** несколько slices повторяли baseline и
наращивали evidence, не закрывая основной classification gate. Это задержка
и недостаток последовательности выполнения, не разрешённое изменение плана.
Коррекция: дальше приоритет — единый candidate ledger и caller/bridge closure;
повторять baseline только при конкретной неполноте evidence, не вместо audit.

**Порядок закрытия остатка:**
1. Привязать каждый scan candidate к source hash, enclosing symbol и конкретному
   решению; структурные DTO/schema данные отличать от NL inference по consumers.
2. Для semantic/mixed symbols записать callers и default/fallback reachability;
   отдельно разрешить wildcard exports, facade synchronization и runtime dispatch.
3. Сверить ledger с D01–D38 и досканированными inline/substrings/config branches.
   Новые механизмы дописать в inventory; неизвестные не закрывать автоматически.
4. Проверить coverage ledger, named retained exceptions и воспроизводимость pinned
   baseline; затем обновить gate. До выполнения всех четырёх пунктов P0 не DONE.

Продолжение после status update: [P0_CANDIDATE_CLOSURE_RU.md](P0_CANDIDATE_CLOSURE_RU.md).
Единый 9874-node ledger содержит source/AST hashes и owners; 1440 candidates
классифицированы, 8434 требуют review. Девять actual class bridges/348 wrappers
проверены, 1273 nodes связаны с facade exports; все восемь dynamic parser entries
разрешились в ожидаемые classes. D38 добавлена по concrete source-root/corpus
consumers и helper probes. Эти результаты не объявляют resolved полный call graph.

Проверка grouped closure: [P0_TO_P1_GATE_RU.md](P0_TO_P1_GATE_RU.md).
9874 raw nodes сведены в 2624 symbol/assignment units; у 348 есть node-level
либо ранее recorded owner decisions, 2276 требуют classification reconciliation.
Это не число semantic dictionaries; неизвестные structural candidates не закрыты
blanket exemption. Прежняя оценка объёма «только завершающий аудит» была слишком
оптимистичной. Критерии DONE остаются прежними, P0 ACTIVE.

Latest classification: [P0_STRUCTURAL_CLASSIFICATION_RU.md](P0_STRUCTURAL_CLASSIFICATION_RU.md).
1856/9874 nodes classified; 438 grouped units complete и 102 с prior owner audit,
2084 grouped units требуют review. Новые technical решения узкие, mixed NL
modules — SPLIT; blanket exemptions и автоматического P0 DONE нет.

Последний slice: [P0_COMPLETENESS_SOURCE_MAP_RU.md](P0_COMPLETENESS_SOURCE_MAP_RU.md)
и [P0_RANKING_SNIPPETS_CLASSIFICATION_RU.md](P0_RANKING_SNIPPETS_CLASSIFICATION_RU.md).
2313 nodes classified; 568 grouped units complete, 102 prior owner decisions,
1954 units требуют review. Scope/source/budget guards отделены от NL rules;
P0 ACTIVE.

Итог parallel audit: [P0_PARALLEL_RESULT_RU.md](P0_PARALLEL_RESULT_RU.md).
Classification и named consumer maps в grouped scope завершены; retained
exceptions предложены, не approved. Остаток P0 — exact frozen execution provenance
и same-P0 required-control evidence linkage. Baseline red сохраняется; P0 ACTIVE.

**Сделать:**
- Проверить точные main/head/merge-base и local diff; сохранить SHA/lock/env/corpus hashes.
- Для D01–D33 выписать symbols, imports, consumers и default/fallback reachability.
  Проверять shard bridge globals, re-exports, monkeypatch adapters, installed package.
- Досканировать small inline sets, chained substring checks, generated regex,
  JSON/YAML routers, templates, prompts/skills и runtime imports из eval/tests.
- Разобрать смешанные/кандидатные строки по символам; назначить REMOVE либо
  ограниченный TECHNICAL-RETAINED с основанием. Не снимать source guards вместе с aliases.
- Сохранить публичный baseline: видимые факты/цитаты, source IDs/ranges, omissions,
  coverage/authority flags, stage counts, serialized tokens, latency/model/network cost.

**Артефакты:** полный symbol inventory, caller map, environment manifest, paired corpus,
baseline reports и перечень уже красных checks. Логи хешируются.

**DONE:** нет неклассифицированных кандидатов в заявленном scope; все retained
исключения названы; baseline воспроизводится из pinned tree. Если доказана только
часть call graph — отметить границу, P0 целиком не закрывать.

### P1 — заморозить RU/EN контракт качества и tests migration ledger

**Сделать:** согласовать матрицу из раздела 5 и минимальные видимые facts по case ID.
Сформировать независимый holdout до настройки replacement. Для каждого изменяемого
assertion записать его текущую гарантию и заменяющую behavioral гарантию.

**DONE:** владелец утвердил observable behavior и спорные migrations; benchmark
разделён на development/holdout, hashes сохранены. Нет оценки «красный тест устарел»
только потому, что он мешает удалить словарь. Baseline failures также имеют issue/решение.

### P2 — доказать работоспособность RU/EN replacement на отдельном прототипе

**Сделать:**
- Сравнить на одном snapshot и budgets: baseline; no-alias lexical ablation;
  dictionary-independent candidate. Original-only и with-lookups оценивать отдельно.
- Проверить bilingual candidate на RU→EN, EN→RU, RU→RU, EN→EN. Не скачивать/менять
  модель/lockfile молча; зафиксировать выбранный artifact и index compatibility.
- Измерить recall **до** qualification, после prefit и в final windows; локализовать
  первую потерю. Это различает слабый поиск и отбрасывание найденной цитаты.
- Отдельно проверить offline/model-unavailable поведение, cold/warm path, shared
  query budget и стоимость. Пределы latency/storage/model calls согласовать до final run.
- Если рассматривается query rewrite, логировать original/proposals и подтверждать
  отсутствие source-dependent product substitutions, неожиданных retries и scope expansion.

**DONE:** candidate проходит P1 по каждой language/input lane и обязательным controls;
выбор backend/prompt/model обоснован отчетом. Сохранён lexical/exact degraded mode
с честным статусом; degraded mode не засчитывается как успешный bilingual run.

**STOP:** если candidate не сохраняет полезные факты, не удалять старый механизм
под видом готового fix. Зафиксировать first-loss, исправить candidate или отдельно
согласовать изменение scope/capability. Возвращение/расширение словаря не является заменой.

### P3 — отделить поиск и context admission от proof и aliases

**Сделать:**
- Ввести/выделить внутренний контракт query proposal и независимые source eligibility,
  topical relevance, context admission, proof results; сначала без публичного DTO расширения.
- `original + explicit lookups` не должны вызывать alias policies и подставленные
  expected values для разрешения поиска. Отвязать optional schedule от длины legacy aliases.
- Сохранять разрешённый полезный candidate до final projection без обязательного
  typed answer witness; не повторить broad prefit patch, вытеснявший Pydantic quotes.
- Public attribution строить по реально показанной quote после crop. Не переносить
  `covered_original` из intent совпадения или из proposal origin.

**DONE:** при недоступном alias builder read path работает; Pebble и trust positive
controls доставлены; Pydantic/control quotes не вытеснены; negative, scope, provenance,
freshness и final DTO budget controls проходят. No-original-coverage control проходит.
Test, делающий alias builder недоступным, доказывает отсутствие вызова, не качество поиска.

### P4 — удалить тематические search/ranking/policy правила

**Сделать:** последовательно закрыть D01–D04, D06, D11–D20 и Docs routing часть D07.
Включая соседние concept queries, intent-based role bans, `fail_closed_workflow`
special window, FastAPI-specific boosts, low-trust language exceptions и lifecycle triggers.

Явные exact path/version/scope/metadata contracts сохраняются. Если интерфейс ещё
не умеет явно выразить historical/source class выбор, сначала проектируется и
согласуется такой контракт, затем удаляется NL inference — не наоборот.

**DONE:** `project_retrieval_intent.py` и его imports/эквивалентные replacements
удалены; в Docs read path нет ручной topic→query/filter/boost таблицы ни на default,
ни на fallback пути. Paired first-loss reports подтверждают отсутствие новых потерь.
Контекст доступен и для невиданных имён продукта, команд и формулировок RU/EN.

### P5 — удалить ручные смысловые подстановки в normalization/proof

**Сделать:** закрыть D05, D21–D28 и semantic части D04/D15/D17/D20.
Не оставлять «тайный словарь» в `question_surface_normalization`, `admission_grammar`
или `_attribute_aliases`. Ручное `timeout=deadline` не становится корректным proof
от того, что поиск теперь semantic.

Proof получает явно связанные question/source spans и проверяемые claims; expected
command/value берётся из source, не из известного имени проекта. Общий языковой
анализ может предложить interpretation, но не сам себе выдать answer authority.
Поддерживаемые typed proof операции/структурные проверки перечисляются явно.
Для неподдержанного semantic proof выдаётся context-only без ложного отрицания факта.

**DONE:** нет скрытого query→expected answer или ручной RU/EN semantic equivalence;
все сохранённые proof capabilities проходят paired positive/negative controls.
Другой субъект/значение/условие не получает чужой proof. Потеря ранее поддержанной
сертификации требует отдельного API/test migration approval; «все flags=false»
не считается автоматическим сохранением proof-функциональности.

### P6 — закрыть другие runtime lanes

**Сделать:** закрыть D08–D10, patch часть D07/D09/D27, D29–D33.
Проверить Packs search, code navigation, patch constraints/review, tool/action routing,
source discovery. Удалить `PHRASE_ALIASES`, synonym expansion и тематические triggers.
Символы выводятся из текущего source/catalog/schema, а операции выбираются явным
tool/request contract; свободный текст документа не назначает разрешения.

**DONE:** нет оставшегося runtime пути к отмеченным semantic dictionaries. Read request
не начинает mutation/network preparation из-за слов; authorized structured actions
сохраняют работоспособность. Tool/source registries retained только как explicit identity data.

### P7 — анти-регрессия архитектуры и финальная приёмка

**Сделать:**
- Повторить полный source/config/package audit и сверить закрытый реестр.
- Добавить архитектурную проверку запрещённых зависимостей и review правило для
  новых semantic tables/branching. Text/AST scan — сигнал для review, не всесильный detector.
- Проверить default/degraded/fallback/installed entry points. Разрешённый временный
  comparison switch удалить; old backend не должен оставаться скрытой страховкой.
- Выполнить frozen regression + holdout, итоговый required CI, независимое review.
- Обновить capabilities/limitations и инструкции caller для RU/EN и optional lookups.

**DONE:** все условия раздела 1 выполнены, артефакты привязаны к одному candidate SHA,
нет необъяснённых skipped/red required gates. Затем отдельное owner approval на merge.

## 5. Матрица приёмки: что именно проверять

### Языки и входы

Каждая factual family проверяется в **RU→RU, RU→EN, EN→RU, EN→EN**, с одинаковыми
source facts; отдельно original-only и original+caller-lookups. Включить mixed
RU/EN с literal identifiers. Third-language качество не входит в milestone.

### Обязательные группы

| Группа | Наблюдаемый критерий |
|---|---|
| Pebble / unknown topic | Полезная quote доставлена; quantum/name-only control не получает ложное topical/answer coverage. |
| Docs server command и trust | Команда находится без подмешивания trust темы; три настоящих trust-вопроса сохраняют instruction-trust quote. |
| Generalization | Переименование продукта/команды/модуля в query и corpus согласованно не ломает поиск. Нет зависимости от DocAtlas/FastAPI/`closeMenu` в коде. |
| Condition, negation, comparison | Exact names/values, отрицания, условия и обе стороны сравнения сохранены. Новый смысл не наследует coverage старого. |
| Partial/multi-fact | Поддержанная часть показывается с честной неполнотой; неизвестная часть не выдумывается. Не требовать полного proof для partial source text. |
| Own/other subject | `two attempts` собственного subject может быть context; `nine attempts` другого subject не сертифицирует requested value. |
| Source boundary | Чужой project/module/version, stale/unsynchronized, подменённый hash/range не допускаются. |
| Hostile document | Цитируемые инструкции — данные; они не расширяют scope, actions, network и permissions. |
| Budgets/ordering | Точный serialized DTO укладывается в действующие ceilings; нет скрытых retries или нового search fan-out. Pydantic quotes не вытесняются. |
| Offline/backend failure | Нет скрытого network/model fallback и fabricated proof. Сохранённый допустимый partial context не обнуляется из-за отказа необязательной стадии. |
| Existing release | Core matrix, advanced-contract целиком, adversarial, required-ci/release и применимые P1 gates проходят утверждённые contracts. |

### Численные и поэлементные правила

- Для фиксированных controls — **0** нарушений scope/provenance/budget/false authority;
  все заранее назначенные positive witness obligations выполнены.
- Для каждой language/input lane — не потерян ни один baseline visible fact,
  назначенный сохраняемым на P1. Aggregate score не маскирует выпадение одной группы.
- Сравниваются source-backed facts и пригодность partial context, а не обязательное
  совпадение слов/путей со старой выдачей. Альтернативный witness допустим после
  проверки source bytes и независимой оценки той же обязанности.
- Старые red cases не превращаются в новую низкую норму качества. Сохраняются
  действующие frozen release thresholds до конкретно согласованной миграции.
- Holdout: freeze до реализации; paired baseline/candidate report отдельно по RU/EN,
  original-only/with-lookups, positives/negatives. Не менять case text после просмотра
  результата; спорная разметка разбирается отдельно с сохранением исходного отчёта.
- Model-dependent route: зафиксировать model/prompt/index versions; повторить final
  holdout минимум 3 раза, показывать диапазон и худший прогон, а не best-of. Это
  предложенный protocol P1, не уже выполненное измерение. Финальные допустимые
  latency/cost ceilings утверждаются до candidate run и входят в gate.

Исходные наборы: `tests/evidence_quality_v2/test_readme_neutral_context.py`,
`tests/docs/test_unresolved_context_prefit.py`, `test_content_trust.py`,
`test_context_trust_gates.py`, `test_evidence_set_delivery_acceptance.py`,
`test_pydantic_direct_context.py`, `test_review_boundary_semantics.py`,
`eval/project_context_quality/`, `eval/direct_docatlas_questions_15/` и действующий
adversarial gate. Новые RU/EN pairs дополняют их, а не заменяют сложные cases.

## 6. Миграция tests/metrics без подгонки под green

Завести `TEST_MIGRATION_LEDGER` со строкой на каждый изменяемый assertion:

`test ID | old guarantee | why incompatible | replacement observable |
positive/negative controls | before/after | owner approval | reviewer | SHA`.

- Alias existence (`test_direct_question_retrieval_intents.py`,
  `test_context7_style_project_chat.py`, alias-planning tests) заменяется проверкой
  доставки факта/нейтральности поиска только после её появления. Просто удалить
  `assert aliases` и оставить пустой test нельзя.
- Legacy original-derived coverage: не ставить fake coverage и не понижать floor.
  Если новый контракт больше не заявляет semantic rewrite equivalence, отдельно
  согласовать замену gate на fact delivery + honest attribution с negative controls.
  Сохранить старый report для сравнения и явно объявить разрыв метрик.
- README hash drift Direct-15 разобрать отдельно: содержимое и изменение документа,
  сохранность witnesses, затем approval на обновление sidecar. Не смешивать это с
  оправданием потери retrieval quality.
- Diagnostic manifests обновлять вслед за согласованным inventory tests; не
  отключать label/collection guards. Budget, scope, provenance controls не ослаблять.

## 7. Объём релизов и связь с #211

Есть два явно именованных результата:

1. **RU/EN Docs read milestone:** P0–P4 и все затрагивающие read path части P5;
   отдельная приёмка его тестов/CI. Если proof parser продолжает скрыто управлять
   admission или expected values, этот milestone ещё не DONE.
2. **Общий dictionary exit:** P0–P7, включая patch/Packs/tool lanes и весь реестр.

Разбить на небольшие commits/PR slices по этапам, без одновременного blind delete
всех таблиц. Перед включением scope в #211 записать список принимаемых D-ID и tests
migrations. Если общий redesign больше текущего MR, оставшиеся этапы получают
явный follow-up; это не разрешает назвать #211 полностью dictionary-free.

Merge #211 по-прежнему требует [MERGE_PLAN_RU.md](MERGE_PLAN_RU.md): устранить
его самостоятельные CI-блокеры, green required checks, independent review и отдельное
owner approval. Выполнение этого исследования не заменяет ни одного из этих условий.

## 8. Артефакты, отчётность и ближайшие действия

Для каждого этапа хранить в этой папке: `stage-status.md`, candidate/base SHA,
patch/manifest, corpus/model hashes, before/after reports, case-level first-loss,
test migration decisions, commands/exit codes, review verdict. Использовать существующий
checkpoint index; не оставлять единственные evidence logs в `/tmp`.

Обязательная строка статуса:

`P# | D-IDs | hypothesis | evidence | code/test diff | checks | unresolved |
owner decision | next action | NOT STARTED/ACTIVE/BLOCKED/DONE`.

Текущее состояние:

| Этап | Статус | Основание |
|---|---|---|
| P0 | ACTIVE | Первичный реестр 33 групп и A/B сохранены; exhaustive consumer/config audit не завершён |
| P1 | NOT STARTED | Матрица/критерии предложены этим документом; test migrations не утверждены |
| P2–P7 | NOT STARTED | Replacement не реализован и не доказан |

**Ближайшие действия по порядку:**
Текущее выполнение P0: [caller map и manifest](P0_READ_PATH_AUDIT_RU.md).
Дополнительно выявленная D34 включена в P5 и общий scope; полный реестр пока OPEN.

1. Завершить P0: разобрать C/REVIEW и построить read-path caller map; отдельные
   source guards выделить из тематических условий.
2. Утвердить P1, зафиксировать RU/EN corpus/holdout и metric migration решения.
3. На P2 провести bounded prototype с одним bilingual backend, сохранив original-only
   lane. Первые обязательные потери для восстановления: trust quotes и RU recall.
4. Только после положительного P2 начать integration P3/P4 и физическое удаление D01.

Изменения документов не означают commit/push/merge. Локальное удаление trust block
остаётся исследовательским кандидатом с известной потерей recall.
