# PR211: оставшиеся output ceilings в Direct15 и continuation

Решение владельца: минимизировать объём, не отклонять результат за фиксированные 800 токенов или три источника. Этот slice применяет его к Direct15 и production-path continuation tests.

- Direct15 и его отдельный MCP workflow сохраняют исходные вопросы, fact groups, source-backed/citation, read-only, no-lookup и call-count проверки. Вместо output ceilings фиксируются число источников, UTF-8 bytes и reported token estimate; estimate должен быть неотрицательным integer.
- Frozen Direct15 sidecar с исходным baseline и историческими 800/3 остаётся неизменным архивом. Его старые source hashes/setup пока не мигрированы; отдельный workflow для ветки PR211 пропускается. Успешный Direct15 acceptance не заявляется.
- В test_docs_context_read_next четыре assertions по 800 заменены JUnit cost properties. Точные source spans/bytes/hash, project/generation, continuation reference, отзыв доступа и запрет answer/edit authority сохранены. Восемь свежих 2199002 failures останавливались на 874 > 800; новый runtime должен проверить и последующие assertions.
- Операционный предел отдельного resource read 600 сохранён. Три неиспользуемых max_tokens аргумента удалены только из вызовов validator. Test IDs и parametrization не меняются.

Независимое source review: Direct15 — docs_quality_impl APPROVE; continuation — question_recovery_impl APPROVE. AST/compile без исполнения и diff check PASS. Новый runtime ожидается из обычного PR CI; не утверждается, что все остальные исторические cost assertions уже убраны.
