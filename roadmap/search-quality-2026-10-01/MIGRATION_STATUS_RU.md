# Статус миграции языковых зависимостей

## Этапы

| Этап | Статус | Что требуется для закрытия |
|---|---|---|
| M0 | Закрыт: inventory | 58 static call sites, reviewed callbacks, guard ownership, controlled public branch trace; см. M01_ACCEPTANCE_RU.md |
| M1 | Закрыт: совместимый extraction | baseline и isolated M1: одинаковые 211 passed / 1 known failure; три packet/snapshot hashes совпали; см. M01_ACCEPTANCE_RU.md |
| M2 | Частично, начат раньше закрытия M0 | Unicode в четырёх местах; window и optional-lookup словари удалены; explicit intent и остальные NL gates остаются |
| M3 | Не начат | выбрать и зафиксировать multilingual retrieval candidate, corpus/protocol и измерить recall/precision/cost |
| M4 | Не начат | read-only qualification migration после M3; восстановить regression шага 07 и проверить actual public packet |
| M5 | Не начат | удалить obsolete callers/rules только после migration; security/certification отдельно |
| M6 | Не начат | installed MCP, реальные host ответы и независимый holdout |

Checkpoint плана закоммичен `d521b358`. Реализация и отчёты пока незакоммичены.
Push/merge не выполнены. Шаг 07 открыт; шаг 08 не начат.

## Следующее действие по порядку

M0/M1 закрыты в scope исходного плана, результаты в `M01_ACCEPTANCE_RU.md`.
Следующее — M2. Baseline equivalence M1 отделена от M2 через isolated worktree.
Не продолжать mechanical regex replacement вместо общего relevance решения.

Для M3 нужны фиксированные model/provider, доступность execution environment и
стоимость. Без actual retrieval/model runs нельзя выдавать локальные pytest PASS
за multilingual quality или host correctness. Эти решения не скрывать за default
активацией или непроверенным semantic threshold.

Сохранённый baseline self-host failure `flow_mcp` остаётся открытым, даже когда
локальные guard regressions проходят. Старые незакоммиченные installed wires
шага 07 не восстановлены: история разговора не является заменой raw artifacts.
