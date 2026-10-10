# Решения текущей волны

## Исполнение плана: решение владельца от 2026-10-09

Владелец поручил оценить, скорректировать и выполнить
`PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md`. Это включает предусмотренный планом
возврат к original-only paraphrase, multi-section/long selection и admission
полезных partial facts; прежняя отсрочка этих трёх направлений ниже заменена
этим более поздним поручением. Исправления следуют за проверкой текущего
контракта, catalog и исходных сценариев, с независимым review.

Порядок: причины FAIL/ERROR и независимые ожидания → contract/fixture/catalog
исправления → реальные retrieval/quality дефекты → доказанное сокращение повторов
и строгие mutation controls → совместный acceptance на конечном SHA.
Стабильные семейства можно сокращать параллельно после их собственного зелёного
baseline; общая карта оставшихся падений сохраняется до закрытия всех required gates.
Оптимизация повторного core CI не подменяет исправление обязательных блокеров.

Фиксированные output-cost ceilings 6144 bytes и 800 tokens отменены; оставшиеся
активные эквивалентные проверки стоимости в downstream мигрируют в измерения
и стремление к минимуму с явным policy diff. Это не отменяет operational
work/read/call/time bounds, полноту полезных данных, gold-смысл или source/consent
guards. Новые providers, model/client downloads и изменение пользовательских
индексов в эту волну не включены. Обычный fast-forward в существующий PR разрешён;
force-push, merge и release по-прежнему требуют отдельного поручения.

## Применение принятого ADR 0003: Legacy acceptance, 2026-10-10

Это уточнение реализации порученного плана на основании
[`docs/adr/0003-context-first-project-reads.md`](../docs/adr/0003-context-first-project-reads.md),
а не новое решение владельца. ADR требует source-attributed context для ответа
хостом, сохранения исходного вопроса и explicit lookups и независимой проверки
фактов по возвращённым источникам. Lookup credit не переносится в original query.

В отдельном reviewed diff блокирующая Legacy-метрика явно мигрирует с raw
`original_query_covered_count` на `verified_original_case_fact_count`: минимум
**12 из 15** исходных положительных cases с полными замороженными обязательными
фактами в допустимом содержимом реально выданных источников. Это сохранение
числового floor при смене проверяемого контракта; прежняя формулировка плана
«original coverage 0 < 12» больше не описывает новую acceptance-метрику.
Raw original coverage сохраняется как отдельное честное измерение с собственным
запретом lookup/parent credit. Название `original_case` означает исходный case,
а не доказательство нахождения через original-only retrieval.

Oracle независимо проверяет actual same-call source/snapshot, текущие bytes/hash,
владельца по captured host-selected root, project scope и точные line spans.
Факт только в heading/link/table header не получает credit. Подменённые rollups,
metadata-only ответы и согласованная подмена public source и snapshot отклоняются.
Все 16 вопросов, lookup strings, frozen gold, protocol lock, V2 thresholds и шесть
hard-zero safety gates сохранены. Отмена output-cost ceilings к этому floor
не относится. Code/review: `34913345f8f6f491fc707a9028c58d7d68319cd5`;
[crosswalk, guards и ограничения](pr211-execution/LEGACY_SOURCE_FACT_ACCEPTANCE_RU.md).

Новый runtime **PENDING**. Прежнее наблюдение полных фактов **8/15** всё ещё ниже
floor **12/15** и не становится PASS после миграции. Старый отчёт не содержит
новых persisted validator receipts и не сертифицирует новый oracle.

Дата: 2026-10-08. Дополняет исторический V4_PRODUCT_DECISIONS_RU.md
и NEXT_PARALLEL_IMPLEMENTATION_PROMPT_RU.md последующими указаниями владельца.

1. Законченные одобренные изменения собрать в одной существующей PR-ветке
   `integration/stage3-v2-identity-pr1`, PR #211. Обычный push разрешён,
   force-push, merge и release не разрешены. Временные агентские worktrees
   служат реализации/review, не отдельным PR.
2. Пока не исправлять upstream original-only paraphrase, diversity thinning
   multi-section/long и qualification/admission partial facts. Анализ сохранён
   в `after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md` для возвращения после релиза.
   Это не означает PASS этих сценариев или автоматическое изменение gates.
3. Новые числовые schema ceilings 22000/13000 НЕ одобрены. Правило о сохранении
   прежних catalog ceilings заменено позднейшим решением владельца ниже.
   Остальные schema/validation проверки сохраняются; увеличение числа не
   подменяет экономный интерфейс.
4. Разрешено сократить основной docs MCP interface: обычный поиск не должен
   рекламировать сложный patch-формат; patch остаётся в явно включаемом
   расширенном режиме. Использовать существующую конфигурацию, без нового
   registry или динамического загрузчика инструментов.
5. Короткий root skill и подробные инструкции по необходимости. Обычный вызов
   get_docs_context должен работать без обязательной загрузки skill. Сохранить
   доступность reference files в установленном skill, runtime validation,
   source binding, consent и отсутствие автоматической edit authority.
6. Schema bytes не равны фактическим model tokens. Catalog включает outputSchema;
   эти размеры нельзя складывать. Реальная client/model-visible стоимость
   остаётся предметом проверки, а не обещанным token savings.

## Уточнение владельца от 2026-10-08: catalog без фиксированного потолка

Владелец отменил фиксированный catalog limit 6144 bytes и указал стремиться
к минимуму. Для default `tools/list` больше нет
repository-wide числового merge gate: прежние target 6 KiB и hard 10 KiB из Task 35
сняты. Новый magic number, включая ранее предложенные 7168 bytes, не вводится.

Каждое изменение catalog должно сохранять или обоснованно сокращать ненужный объём
при сохранении discoverability, смысла guidance, полного input/output contract,
runtime validation, source bindings, consent и отсутствия automatic edit authority.
Canonical UTF-8 размер и attribution по tools/input/output/descriptions продолжают
измеряться и публиковаться для review. Рост оценивается по назначению добавленного
контракта, а не скрывается увеличением ceiling или удалением guards.

Нормальная поверхность по-прежнему содержит ровно get_docs_context, prepare_docs и
docs_status; подробный patch schema остаётся в существующем advanced mode.
Действующий отдельный output schema gate <1000 bytes не отменён этим указанием.
Локальный optional `--max-tools-list-bytes` остаётся явным выбором вызывающего
measurement CLI и не является default CI/merge requirement.

Это согласованное изменение catalog acceptance policy, а не исправление runtime
поведения. Оно не отменяет retrieval/work/read/acquisition bounds, gold, остальные
CI/downstream gates, client checks и запрет из пункта 2 исправлять deferred retrieval.
Исторические checkpoint/review reports с 6144/7168 сохраняют measurements и статус
своей даты; для текущего catalog gate применяется это более позднее решение.

Read-only измерение D delta c91af9b0: catalog 21409 bytes, docs output branch
860 bytes, patch branch 11993 bytes; весь outputSchema 12866 bytes. Гипотетический
catalog с одним docs output branch — 9403 bytes, до реализации это не результат.
Detailed patch branch включает mutation_intent (5816), requirements (2185)
и assignments (1126) bytes. Удаление всех description дало бы 17382 bytes;
главный объём — структура дополнительных форматов, не только пояснения.

Итог реализации и проверки фиксируется отдельно после integration на одном SHA.
Результаты компонентов не сертифицируют installed-wheel, реальные clients или CI.

## Продолжение от 2026-10-09: узкая миграция critical contract

После результата полного CI на `7a78c51` и конкретного предложения
`PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md` владелец указал продолжить работу.
Следующий slice реализует описанную миграцию retired normative-modality acceptance:
source-data fidelity, отсутствие implicit authority и действующая Python grammar.

- Сохраняются все 26 исходных fixture texts, legacy labels и concrete node IDs.
  Старые labels остаются историческими данными; текущий adapter проверяется как
  unknown. Полная доставка исходного текста и отрицательные controls обязательны.
- Устаревший normative mutant заменяется действующими проверками recognition
  Python declarations, unknown modality, whole-source fidelity и bound-window
  validation. Два прежних Task33/host-turn-limit mutants сохраняются.
- Baseline и mutants исполняются через существующий PR CI. Каждый новый mutant
  обязан изменить используемый source и упасть на конкретном ожидаемом assertion;
  collection/import errors, skips и случайный иной failure не считаются kill.
- Изменения проходят независимый review до ordinary push в существующий PR.
  Production retrieval, corpus/gold, другие thresholds/gates и отложенные
  направления из пункта 2 этим продолжением не изменяются.

Статический review уточнил предварительное предположение proposal о девяти
uniform partial packets. Два неизменённых вопроса содержат `PermissionService`
и `PermissionDecision.deferFollowUp`: текущий `build_requirements` создаёт для
них точные `query_exact_term` requirements, а действительный literal unit witness
может обеспечить `complete`. Для этих двух cases нужны exact requirement IDs,
values, provenance и bound assignment spans/hashes. Остальные семь prose cases
сохраняют `partial` и `visible_content_assignment_required`. Во всех девяти
случаях source остаётся `untrusted_data`, `edit_ready=False`, без inferred policy,
behavioral или validation authority. Question, source bytes и selector не меняются.

Основание уточнения: `evidence_requirements.py::build_requirements`, literal-only
`_witness_for_requirement`, assignment construction в `_evidence_selection_part03.py`,
`_action_packet_part03.py::build_action_packet`, bound validation в
`_action_packet_part04.py` и `action-packet-v4/CONTRACT.md` (completeness/assignments).
Результаты новой реализации фиксируются только после фактического CI на её SHA.

## Уточнение владельца от 2026-10-09: retrieval cost без потолка 800

Владелец отдельно отменил обязательный 800-token ceiling в `retrieval-evidence`:
стремиться к минимальному объёму, не задавать новый числовой потолок. Это последующее
решение заменяет сохранение именно этого ceiling в предыдущих checkpoint reports;
отмена catalog 6144 bytes и отмена retrieval 800 tokens — два явных решения.

`scripts/run_systemic_retrieval_plan_gate.py` сохраняет измерение полного публичного
DTO: canonical UTF-8 bytes, actual tokens по pinned offline tokenizer, распределения
и максимум. Размер становится метрикой минимизации при сохранении fidelity,
sufficiency и source safety. Превышение 800 само по себе больше не означает FAIL;
новый лимит, фиктивный budget PASS или оценка качества по одному размеру не вводятся.

Все 80 исходных cases, историческая группа из 48 `within_budget`, source manifests,
gold, quality floors, source binding и проверки ошибок сохраняются. Названия
`within_budget`/`over_budget` обозначают замороженные группы исходного эксперимента,
а не новый действующий потолок. Исторический 800-token selector/singleton control
остаётся явно подписанным diagnostic-only сравнением и не ограничивает приёмку
полного DTO. Report schema v3 объявляет эту границу вместо прежнего budget boolean.

Это изменение acceptance policy, а не сокращение фактически выданного ответа.
Production retrieval, work/read/acquisition bounds и отложенные направления из
пункта 2 не меняются. Запрос на сокращение тестов и разбор downstream/quality
на этой стадии означает анализ; массовое удаление cases, смена gold и подгонка
ожиданий под фактические failures не выполняются.
