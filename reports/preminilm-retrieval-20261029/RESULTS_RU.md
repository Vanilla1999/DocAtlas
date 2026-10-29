# Pre-MiniLM retrieval: paired experiment

## Статус

Сравнение качества пока **NOT ASSESSABLE**: первая попытка неполна из-за
завершения диагностического worker, а не признана улучшением или регрессией
поиска. Исправляется только CI collector; алгоритмы, параметры, документы,
вопросы, oracle и downstream MiniLM остаются зафиксированными.

- Baseline: `main@542900e573835aa17a3a21da924a0f7ed400bece`.
- Retrieval implementation freeze: `d38322439f3bf8d561c933ff6021d046d280d413`.
- Ветка: `experiment/preminilm-retrieval-20261029`; default и main не переключены.
- [Основания, ограничения и предварительно зафиксированный дизайн](../../docs/preminilm-retrieval-research.md).

## Попытка 1: collector failure, не quality verdict

[CI 40954589560](https://github.com/Vanilla1999/DocAtlas/actions/runs/40954589560)
на `d38322439f3bf8d561c933ff6021d046d280d413`.
[Полный сохранённый artifact](https://github.com/Vanilla1999/DocAtlas/actions/runs/40954589560/artifacts/12933662046),
ZIP SHA-256 `9f2e2adfa14cc8cd065775cd01147ec5d917440a59a77efaef1d12b9b30465fc`.

| Arm | Завершённые benchmark calls | Public-handler preparations | Scope controls | Причина остановки |
| --- | ---: | ---: | ---: | --- |
| main | 16 | 2 | 1 | Нет `poetry/STATE.json` после закрытия stdio |
| retrieval_text | 16 | 2 | 1 | Нет `poetry/STATE.json` после закрытия stdio |
| rrf | 40 | 5 | 1 | Нет `eslint/STATE.json`; `NATIVE.json` остался пустым |
| Всего | 72 | 9 | 3 | 75 context calls; полный paired run не завершён |

MCP SDK `1.29.0` даёт процессу 2 секунды на закрытие после EOF, затем завершает
дерево процессов. Verbose native receipts одного семейства составили 60–77 MB;
сохранение в `finally` не успело закончиться. В доступных `MEMORY_EVENTS` всех
arms `oom=0`, `oom_kill=0`. Пики памяти: main 1 256 583 168 bytes,
retrieval_text 1 227 452 416, rrf 1 475 825 664 при пределе 1 500 000 000 bytes.
Это профиль инструментированного стенда, не production memory benchmark.

Дополнительно host не мог записать `CONTAINER.json` в созданный container-root
каталог arm. Путь переносится на host-owned верхний уровень evidence; права
продукта и каталоги источников не ослабляются.

NEW20 до остановки не открывался. Никакого подбора параметров по ответам или
oracle не проводилось. Повтор имеет конкретную причину: исправление сохранения
receipts до закрытия транспорта. Первые 75 context calls и 9 preparations не
исчезают из учёта. Paid answering-model calls: **0**.

## Границы будущего результата

Collector исправлен после независимого статического review. Parent запрашивает
flush через отдельный CI-only сигнал уже после последнего tool response; worker
потоково и атомарно сохраняет четыре receipts и выдаёт ACK с SHA-256 до закрытия
MCP. Во время измеряемых calls дополнительного polling нет. После завершения
worker parent отдельно проверяет реальные DB/files против исходных fingerprints;
отсутствующая DB считается ошибкой. Private fixture живёт до этой проверки и
удаляется вместе с изолированным CI container. Продуктовый код, oracle, модель,
query settings и resource caps между попытками не изменены.

- Только installed public-handler preparation и настоящий MCP stdio/SQLite;
  автономная сессия OpenCode/Terra не проверяется.
- Original witness и negative-критерии сохраняются; `source_fact_contract_pass`
  не равен полному прежнему budget/answer acceptance.
- Token counts относятся к фактическим MCP packets, не к usage платной модели.
- Отсутствующий MiniLM receipt означает неизвестную стоимость, не ноль.
- Один последовательный запуск с диагностикой не доказывает статистически
  значимое ускорение. Более короткая ошибка не считается экономной доставкой.
