# 05. Исправить блокеры и завершить приёмку

Статус: TODO. Основание — результаты и анализ плана 04.
Prod не восстанавливаем. Выкладка не входит в этот этап.

## 1. Сократить public instructions

**Править:** `docmancer/mcp/_docs_server_tool_data.py`, `_docs_server_shared.py`
в том же каталоге.
Полное правило сохранить в existing quickstart; tool/schema описать кратко,
убрав повторы между ними. Не переносить все правила в непрочитанный ресурс.
Сохранить missing-part lookup, исходный вопрос и условия, sourced known facts,
stop без прогресса и разделение context / proof / edit permission.

**DONE:** tools/list ≤ 6144 bytes; footprint и workflow/schema tests проходят.
Лимит не повышен, правила не потеряны.

## 2. Исправить implicit intent routing

**Править:** `docmancer/docs/interfaces/mcp/context_intents.py`.
Project-only defaults добавлять только для project route, не для explicit
dependency/mixed/library. Согласовать условие с existing service routing.
Явные intents не удалять молча; invalid combinations отклонять на входе.
Сначала regression test на `project_path + mode="dependency"` без intents.

**DONE:** project/auto/dependency/mixed/library и explicit-intent controls
проходят; existing agent-developer и adversarial gates зелёные.
Project defaults и source/permission guards сохранены.

## 3. Проверить восемь ответов агента

**Использовать:** `eval/task_level/runners/opencode.py` и вопросы
`artifacts/next04/AGENT_QUESTIONS_RU.md`. Сначала проверить совместимость runner
и candidate MCP; при необходимости минимально адаптировать existing runner.
Не создавать benchmark engine. Использовать полные raw events, не обрезанные
normalized summaries; изолировать sessions и соблюдать existing call limits.
Агент сам выбирает lookup, без evaluator expectations в prompt.

**DONE:** сохранены model ID, инструкции, calls, packets и 8/8 корректных
ответов с поддержанными citations, честным unknown и остановкой без прогресса.
Ошибочные вопросы не заменены удобными. Нет доступа/совместимости — BLOCKED.

## 4. Разобрать красные проверки и перепроверить кандидат

Для каждого remaining failure определить: runtime bug, устаревшее expectation,
research prototype или environment. Устаревшую предпосылку заменить проверкой
того же публичного поведения; corpus witnesses сверять с действующим текстом,
не обновлять hashes/labels ради green. Реальные дефекты вынести отдельно.
Не возвращать aliases, compiler или fallback ради старых tests.

Повторить relevant tests, required release checks, 80 native cases и четыре
lookup controls после правок. Проверять каждый прежний claim, не только сумму.

**DONE:** все прежние 49 claims сохранены, controls проходят, required checks
зелёные. Остальные failures классифицированы с основаниями и дальнейшим действием;
research/environment failures не выданы за PASS. Новые facts посчитаны отдельно.
Нерешённый обязательный check остаётся блокером.

## Завершение

- **READY:** все четыре этапа DONE; результат записан здесь, кандидат определён.
- **REJECTED:** подтверждён неверный ответ, потеря обязательного факта или guard.
- **BLOCKED:** любой этап не выполнен либо required check красный.

Правки 1 и 2 выполнять раздельно. Admission/selection/budgets/thresholds не менять.
Итог: изменённые файлы, команды, counts, артефакты и одно решение.
Готовность на этом наборе не означает доказанного превосходства над prod.

## Результат

Пока не выполнено.
