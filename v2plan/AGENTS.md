# Research: обязательная граница упрощения

## Текущее состояние — прочитать до старых шагов плана

Ветка `next07-feasibility-audit`, НЕ main.
Актуальное закрытие технических задач и граница следующей работы:
[NEXT_07_VERIFIED_STATE_RU.md](NEXT_07_VERIFIED_STATE_RU.md).
Оно имеет приоритет над устаревшими текущими статусами и командами повторного
старта в плане 07. Исторические NOT_RUN/BLOCKED/REJECTED не переписываются.

Настоящий run 37231552540 на ea7eef38 подтвердил wiring, scope transport в
проверенных current-read сценариях, empty DTO, line-range audit, снятие output
800/3, LeaseClient P1/P2/P3 и исполнение 80/80 N/C пар. Эти технические задачи
закрыты; не переписывать их ради следующего эксперимента. Регрессионная проверка
после изменения потребителя допустима. Это НЕ принятие качества или rollout.

Пользователь разрешил следующий порядок: source-owner fix → review → запуск
без N10. Заменяется только формирование и проверка delivery unit после прежнего
retrieval order. Подробности и критерии до кода:
[owner protocol](artifacts/next07/owner-delivery-20261004/PROTOCOL_RU.md).
N10 = EXCLUDED_BY_USER / NOT_RUN в этой работе; исторический REJECTED сохраняется.
Не удалять его test/gold, не добавлять allowlist и не объявлять PASS по исключению.

## Неизменные границы

- Новая правка заменяет названную ответственность, не добавляет fallback/rescue.
- Read context — материал для чтения. Отсутствие semantic/applicability proof
  само по себе не запрещает источник; unknown не означает applicable.
- Source/security/identity/scope/version/freshness/lifecycle/snapshot/hash/span/
  request/exact guards обязательны. Проверенное несоответствие не становится unknown.
- Subject, условия и отрицания сохраняются в исходных цитатах. Полный Markdown
  owner не доказывает все смысловые зависимости. Не приписывать ему такую гарантию.
- COMPACT_READ_LIMITS / --compact-read — caller-owned отсутствие фиксированного
  output лимита tokens/sources/snippet chars. Метаданные источника не выбирают
  политику. Измерять фактический размер, не заменять лимит большим числом.
- Краткость: исходные цитаты без точных дублей, не semantic compression.
  Retrieval/hydration/call/resource caps не повышать автоматически.
- Нет LLM, embeddings, нового natural-language parser, aliases, library-specific
  словарей, threshold tuning, generated lookups, guessed answers или hidden rescue.
- Не менять ранжирование под отдельный пример. Routing IDs, lexical match,
  retrieval/BM25 score не являются смысловым witness или вероятностью правильности.
- Не добавлять проценты confidence без независимой калибровки. Доли измеренного
  покрытия с явным знаменателем — другая метрика, не confidence.
- Retrieval/read/packing изменения разделять. Source-owner materialization и
  проверка её canonical bounds — одна обязанность producer/consumer, не новая policy.
- Frozen corpus/labels/ожидания, factual positives, security negatives и прежние
  evidence не изменять. Gains не компенсируют lost IDs; needs_review не равен supported.
- Заимствование upstream кода только с лицензией/copyright/SHA. Нормализованный
  текст не выдавать за точные original bytes. Grounded run — только actual package.
- Production/defaults/main, proof/edit budgets, public schema и release/CI policy
  не переключать. Isolated workflow измерения не является новым required gate.
- Никакого reset/stash/clean пользовательской работы, git add . или force-push.
  Коммитить только относящиеся к задаче файлы; не включать secrets и случайные DB.

## Порядок проверки

Перед runtime запуском сохранить scope, frozen baseline/inputs и review diff.
Review авторский, не выдавать его за независимый внешний аудит. После meaningful
failure не менять алгоритм/ожидания в том же замере и не спасать его частью II.
В отдельной диагностике quality FAIL записывается и не обрывает другие случаи.
Case-local invalid сохраняется отдельно при восстановленной изоляции; изменение
замороженного кода/данных или повреждение изоляции прекращает затронутый замер.
Ошибки технического стенда исправлять отдельной revision с сохранением raw outputs;
не называть отказ алгоритма ошибкой harness и не превращать пустую выдачу в guard PASS.

Закрытые обязанности, локальный успех новой правки, полнота диагностики и общая
продуктовая приёмка — разные verdicts. False answer/edit flags не гарантируют
правильность ответа downstream reader. Полный rollout требует отдельного решения.

## История, не очередь повторного исполнения

[План 07](NEXT_07_READ_PIPELINE_OWNERSHIP_RU.md) и его journal сохраняют прошлые
попытки; не начинать снова с I.0 только из-за старого заголовка статуса.
[Прежний compiler-only план](NEXT_07_SCOPE_TRIAL_HISTORY_20261004_RU.md) завершён
BLOCKED. Не возобновлять event-condition/compiler маршрут и не создавать план 08.
[Compact fix](artifacts/next07/compact-read-20261004/SUMMARY_RU.md) и
[scope rebuild](artifacts/next07/scope-rebuild-ef6a4980/SUMMARY_RU.md) описывают
границы своих старых запусков, а не отменяют более позднее evidence.
