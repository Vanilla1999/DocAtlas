# Решения текущей волны

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
