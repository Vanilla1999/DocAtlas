# Сокращение тестов минимум на 40%: критический разбор

Дата: 2026-10-10. Исходники: `c518359f`. Выполнен анализ, не удаление тестов.
Основание: новое поручение владельца о −40%, начиная с красных семейств.
Общие правила: `../AGENTS.md`. [Промпт для исполнения](TEST_REDUCTION_40_MULTIAGENT_PROMPT_RU.md).

## 1. Вердикт

**Текущий подход «мигрировать десятки assertions и добавлять доказательства к
каждому» не даст нужного сокращения. Нужна смена единицы работы: пользовательское
поведение целиком, а не отдельная test-функция.**

В наборе одновременно проверяются отменённая семантическая архитектура, её
отсутствие, внутренние представления нового pipeline и публичные результаты.
Каждый слой получает свои fixtures, параметризации, snapshots и receipts.
Это создаёт работу по обслуживанию тестовой конструкции независимо от качества
продукта. Зелёные тесты тоже требуют отбора на полезность.

При этом **сейчас не доказано, что конкретные 3068 случаев можно удалить**.
Есть численная цель, точные данные о красных модулях и приоритеты разбора.
Выдать их за уже разрешённый deletion manifest было бы подгонкой под метрику.

## 2. Сколько нужно удалить

Сохранённый CI136, HEAD `a9fba17d`, core одной Python lane:

| Метрика | Число |
| --- | ---: |
| Собрано | 7669 |
| PASS / FAIL / SKIP | 6052 / 1607 / 10 |
| Минимальное чистое сокращение на 40% | **3068** |
| Максимальный остаток с учётом новых случаев | **4601** |
| Доля всех FAIL | **20,96%** |
| Ещё нужно, даже если убрать все 1607 FAIL | **1461** |

Формула: `removed - added >= ceil(0.40 * N_before)`.
Переименование теста — не удаление. Перенос core → advanced, `skip`, фильтр
collection, укрупнение циклов или вывод старого набора из required CI не даёт
кредита сокращения. Повторные Python/platform/workflow executions не входят в
N_before несколько раз: их сокращение — отдельная экономия.

**7669 — core, не доказанное число всех активных тестов.** Для исполнения
зафиксировать актуальный unique roster core+advanced и посчитать общий target
по той же формуле. Отдельно показать core, advanced и самостоятельные gate
scenarios. Новые calls/циклы внутри gates не должны компенсировать исчезнувшие
pytest node IDs скрытым ростом работы.

Свежий `gh pr view 211` в этой сессии вернул HTTP401. Поэтому эти числа не
объявляются текущим CI `c518359f`. Перед удалениями нужен актуальный полный
JUnit/collection; ограничения локального runtime из checkpoint сохраняются.

## 3. Что дают именно красные модули

Источник: `pr211-execution/RUNTIME_EVIDENCE_a9fba17d.json`, массив
`selected_records`, записи `record_type=JUNIT_MODULE`.
216 записей относятся к 216 разным модулям, суммы **1607 FAIL + 2098 PASS**.
Значит, в файлах с падениями находится **3705 случаев**, включая зелёные.
Ещё **3954 PASS** находятся вне этой карты красных модулей; 10 SKIP — отдельно.
Это полная сумма ошибок того core, но не полная поузловая классификация:
запись модуля содержит только первый failure message.

Разложение этих 216 модулей на непересекающиеся области для планирования:

| Область | Модули | FAIL | PASS | Всего |
| --- | ---: | ---: | ---: | ---: |
| A. Внутренняя семантика вопроса/плана/ролей | 33 | 315 | 178 | 493 |
| B. Docs service / unified / routing | 19 | 247 | 195 | 442 |
| C. Retrieval, admission, selection, delivery: смешанные проверки | 25 | 426 | 272 | 698 |
| D. Dictionary-exit: смешанные проверки | 7 | 26 | 203 | 229 |
| E. Остальные красные модули | 132 | 593 | 1250 | 1843 |
| **Итого** | **216** | **1607** | **2098** | **3705** |

Это группировка по путям, **не доказательство устаревания или unit-уровня**.
Даже полное удаление областей A–D дало бы только1862 случая и потеряло бы
действующие guards. Следовательно, −40% нельзя честно получить только
«почистив obvious legacy». Нужен разбор зелёных повторов во всём наборе.

Границы групп для воспроизведения:
- A: question_plan_v4, documentation_query_plan, query_planning*,
  query_reference_roles, context_constraint_roles, hyphenated_query_identity,
  russian_inquiry_intent, enumeration_request_terms, requested_need_partition,
  project_query_intent, comparison_treat_frame, comparison_relation_query_planning,
  evidence_set_{compositional_frames,need_composition,private_plan,query_schedule,parse_cache},
  patch_{request_plan,plan_context,requirements}, action_packet_semantic_density,
  project_answer_contract_v{2,3}, project_answer_outline, answer_units_v{2,3},
  normative_language, governance_value_proof_p0, residual_paraphrase_query_planning.
- B: docs_service и part02–10, docs_service_characterization, unified_docs_context
  и его MCP/part variants, project_context_service и part02, project_docs_service,
  library_docs_service.
- C: evidence_selection и part02/v2, evidence_qualification,
  evidence_admission_sufficiency, model_visible_projection и part02,
  context_loss_boundaries, document_local_rescue, generic_context_workflows,
  reference_{behavior_matrix,projection_retention,transfer_regressions}, admission_*,
  source_locator_resolution, bound_table_qualification, compact_context_{blocks,selection},
  relation_preserving_projection.
- D: test_dictionary_exit_*; E: остаток. Только модули из JUNIT_MODULE136.

## 4. Конкретный старт: что удалить, заменить или сохранить

Числа FAIL/PASS ниже — CI136. Вердикты основаны на прочитанном коде и
существующих retirement notes, не только на именах файлов.

| Файл/семья | FAIL/PASS | Рекомендация |
| --- | --- | --- |
| `tests/docs/test_question_plan_v4.py` | 26/2 | Первым завершить подготовленное удаление26: ожидания inferred obligations/aliases отменены. Соблюсти уже описанные условия; два keeper не удалять вместе с файлом. |
| `tests/docs/test_query_reference_roles.py` | 23/17 | Начать с подготовленных19 role cases. Это не разрешение удалить все23 FAIL: offsets, collision, literal identity и scope-resolution имеют самостоятельный смысл. |
| `tests/docs/test_documentation_query_plan.py` | 13/24 | Удалить подготовленный один default3/800 case после своего proof. Остальные12 FAIL классифицировать отдельно. |
| `tests/docs/test_query_planning_budget_regressions.py` | 16/0 | Кандидат на retirement существенной части старых auto-query expectations. Проверяет concept_alias/exact_anchor и конкретные автоматически составленные строки. Сохранить исходный вопрос/explicit lookups/точные литералы через public scenario. |
| `tests/test_unified_docs_context.py` | 15/43 | Сжимать вместе с зелёными cases: FakeFacade + call names/support flags дают слабое доказательство выдачи. Реальные project/library/scope/consent сценарии должны заменить уникальные обязательства. |
| `tests/test_docs_service_part02.py` | 25/8 | Не удалять по PermissionError. Первый сценарий проверяет реальные rename/delete и сохранность посторонних документов, но использует старую mutation entrypoint. Перенести через действующую явную транзакцию; mock vector-call assertions разбирать отдельно. |
| `tests/docs/test_document_local_rescue.py` | 41/11 | Смешаны искусственный Dispatcher, fabricated metadata, прежний answer_supported и важная потеря исходного факта. Заменить проверки внутреннего маршрута сценарием реальной выдачи; не выбрасывать задачу «полезный факт не потерян». |
| `tests/docs/test_reference_behavior_matrix.py` | 23/1 | Нельзя назвать unit-мусором: есть public capture, два реальных проекта, filename collisions. Сократить матрицу 8 имён×2 языка до различных рисков; сохранить scoped delivery и collision. |
| `tests/docs/test_docs_context_read_next.py` | 8/23 | Сохранять проверку continuation/fidelity. Красный результат не разрешает удаление: в follow-up уже были исправления продукта. Сверить новый runtime. |
| `tests/test_mcp_delivery_member_transaction.py` | 1/115 | Красный файл не делает115 guards лишними. Не первый пакет удаления; объединение допускается после public transaction proof. |
| `tests/test_dictionary_exit_delivered_surfaces.py` | Не в карте красных модулей136 | Кандидат на сокращение зелёной maintenance-нагрузки: hashes старого schema snapshot и обратное восстановление pre-slice структуры. Установленный catalog + реальные valid/invalid вызовы должны защищать актуальный контракт. |
| `tests/test_action_packet_v4_contract.py` | Не в карте красных модулей136 | Внутренние constructors/serialization checks можно объединять; adversarial source/hash/authority проверки переносить на реальную advanced boundary, а не терять. |

## 5. Главный дополнительный источник сокращения — зелёные повторы

Текстовая инвентаризация `c518359f` нашла4910 test-definitions в513 файлах.
В том числе42 `test_dictionary_exit_*` файла с486 определениями,
12 `test_action_packet_*` файлов с178,14 основных docs_service/unified файлов
с360. Это **definitions, не expanded cases и не готовый объём удаления**.

Разбирать зелёные проверки в следующем порядке:
1. Один и тот же результат проверяется у builder, facade, handler, schema,
   serializer и повторно в installed runner. Оставить наиболее внешний
   достоверный сценарий; уникальные существенные отказы добавить в его case data.
2. Snapshot/hashes исторического устройства без текущего пользовательского
   обязательства. Историю хранит Git, не требуется исполняемый «музей» каждого slice.
3. Матрицы имён/слов/языков, которые проходят одну ветвь и не различают риски.
   Сохранить representative Unicode/quotes/path/collision cases, а не все комбинации.
4. FakeFacade/SimpleNamespace/MagicMock call assertions, не проверяющие реальный
   результат. Заменять реальным integration, а не новыми моками другого слоя.
5. Несколько scripts/workflows проверяют один producer/scorer на том же artifact.
   Один producer и один независимый результат; reuse вместо повторного исполнения.

Не считать snapshots и mocks автоматически бесполезными: решение принимается
по тому, обнаруживает ли оставляемый сценарий тот же пользовательский дефект.

## 6. Как не превратить удаление в ещё большую бюрократию

Для QP26 уже записан аудит2128 blobs /54 373 209 UTF-8 bytes в
`QUESTION_PLAN_V4_CONSUMER_AUDIT_130_134_RU.md`. Это выполненная историческая
работа; **повторять такой аудит для каждого следующего семейства не нужно**.

На семейство достаточно одной строки в общем manifest и короткого обоснования:
старые node IDs → действующее свойство/отмена → existing successor → evidence.
Искать реальные imports/reexports/selectors/labels затронутых файлов, затем
проверять collection через разрешённый CI. Не создавать новую серию документов,
hash snapshots, архивных `.py.txt` и отдельный mutation subprocess на каждый дубль.
Существующие исторические документы не удалять в рамках сокращения тестов.

Для отменённого требования не нужна успешная старая проверка: она может
закономерно быть красной. Нужны решение об отмене и действующий публичный
контракт. Для уникального действующего свойства нужна здоровая интеграционная
замена. Уже подготовленные46 retirements завершаются по их прежним условиям.

## 7. Решение об удалении: пять классов

- **DELETE_OBSOLETE:** требование отменено документированным решением;
  удаляем старое ожидание. Не возвращаем старую production-логику ради PASS.
- **DELETE_DUPLICATE:** тот же действующий риск покрывает существующий
  интеграционный сценарий. Удаляем повтор без написания замены1:1.
- **REPLACE_INTEGRATION:** действующее уникальное свойство проверяет private/mock
  тест; сначала доказываем его через публичную границу, затем удаляем старый.
- **KEEP_PRODUCT_FAILURE:** пользовательская задача реально не решается;
  сохраняем воспроизводимость. Можно перенести failing reproduction в общий
  integration, но нельзя объявить его PASS из-за удаления старой оболочки.
- **UNRESOLVED:** причины/покрытие не установлены. Не засчитывать в approved deletions.

Модуль может содержать несколько классов. Признак FAIL задаёт порядок разбора,
а не итоговый класс. Первый stack trace не классифицирует весь файл.

## 8. Критерии завершения

- Чистое сокращение актуального полного unique roster не менее40%; новые
  integration cases входят в остаток. Отдельно показан core target.
- Реальные scenario/product-call/mutation executions не выросли за счёт
  скрытых циклов; время и artifacts измерены, а не обещаны по количеству names.
- Каждый удалённый case имеет manifest-класс и successor либо решение об отмене.
- Прежние реальные product failures либо исправлены, либо остаются явно
  воспроизводимыми; красный quality gate не исчезает из отчёта.
- Нет новых unit-тестов, ослабленных источников/consent/authority и переписанных
  frozen вопросов/фактов. Исполняется production-путь с переключаемыми логами.
- Merge readiness и −40% — разные результаты; завершение сокращения не
  заменяет required CI и реальные client checks.

**Ближайший пакет:** актуальная карта → retirement46 + крупные группы
устаревших планов → зелёные layer/snapshot/mock дубли. Одновременно разбирать
один реальный падающий вопрос с трассой. Не тратить волну на косметическое
переименование1607 красных ожиданий и не объявлять −40% достигнутыми заранее.
