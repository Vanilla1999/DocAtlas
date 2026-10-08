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
