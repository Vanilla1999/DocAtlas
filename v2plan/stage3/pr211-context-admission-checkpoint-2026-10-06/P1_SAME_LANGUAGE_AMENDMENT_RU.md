# Поправка к P1: вопрос на языке документации

Основание — уточнение владельца: «Давай закрепим, я хочу задавать вопросы на
языке доки, mcp это возвращает».

## Целевое поведение

Пользователь задаёт вопрос на языке документации. MCP находит и возвращает
релевантные фрагменты с источниками, сохраняя исходный язык и текст документа.
Перевод вопроса/цитат и поиск между разными языками не являются обязательными
capabilities этого dictionary-exit milestone. Это не новый language-detection
router и не основание автоматически отказывать вопросу на другом языке.

P1 определяет **что должно работать и как проверить**; P2 определяет **каким
способом это реализовать**. Локальная multilingual model не является требованием.
Цель удаления ручных смысловых словарей остаётся; даже на одном языке нужно
проверить новые формулировки, partial context и отсутствие ложного proof.

## Изменение acceptance scope

- Обязательные language lanes текущего RU/EN набора: RU→RU и EN→EN,
  original-only и with-explicit-lookups отдельно. Original-only остаётся обязательным.
- RU→EN и EN→RU сохраняются как diagnostic lanes: их failures больше не блокируют
  этот same-language milestone и не объявляются исправленными.
- Frozen 224-case корпус и исходные manifests/review/results не переписываются.
  При следующем запуске runner должен явно указать эту поправку и разделить
  same-language gate и cross-language diagnostics в отчёте. Не фильтровать cases
  по успеху candidate. Старый freeze checker проверяет v1 bytes, не новую scope policy.
- Это явное изменение требования владельцем после first P2 development probe,
  а не улучшение метрик алгоритма и не новое independent review.
- Scope/version/freshness/hash/ranges, budget/resource ceilings, hostile/offline,
  truthful attribution, typed-proof positives и test-migration правила сохраняются.
  Existing release/gold/CI gates не отменяются; возможный конфликт с ними требует
  отдельного решения, а не автоматической правки thresholds/assertions.
- Языки кроме RU/EN в текущем corpus не оценены; поддержка всех языков не заявлена.

## Следующий шаг P2

Сравнить actual product baseline, no-alias ablation и dictionary-independent
candidate на одном snapshot и production budgets для same-language lanes.
Проверить доставку цитат, source guards, honest attribution и partial context;
найти first-loss. Простого совпадения названия продукта недостаточно.
Multilingual scorer больше не обязательный следующий шаг. Если простой поиск
достаточен — использовать его; если нет — выбирать replacement по обнаруженным
same-language потерям. Product aliases удалять только после проверки замены.

P1 contract дополнен этой scope-поправкой; P2 остаётся ACTIVE / NOT DONE.
