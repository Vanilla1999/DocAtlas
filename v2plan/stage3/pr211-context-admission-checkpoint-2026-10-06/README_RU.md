# #211: точка возврата — допуск полезного контекста

Дата фиксации: 2026-10-06.
Исследованный SHA: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.
Интеграционная ветка: `integration/stage3-v2-identity-pr1`.

**Текущая точка продолжения: [CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md).**
Dictionary exit частично реализован в primary: 146 новых tests passed, actual stdio
MCP smoke PASS; quality gate red, полный milestone NOT DONE. Owner изменил порядок:
сначала удалить смысловые правила, затем улучшать полноту; replacement не prerequisite.
Полный журнал: [DICTIONARY_EXIT_EXECUTION_RU.md](DICTIONARY_EXIT_EXECUTION_RU.md).
P1 frozen approval сохранён; P0 archival debt отдельный. P2 prototype — история.

**Ниже исторический #211 diagnostic checkpoint до смены приоритета и реализации.**
Его old SHA, «product не изменён» и next steps не описывают текущий local diff.

## Простыми словами

Система находит документы, но не всегда правильно решает, какие фрагменты полезно
показать. Один и тот же факт в знакомой формулировке распознаётся, а в другой — нет.
Число другого компонента иногда проходит внутреннюю проверку как подходящий witness.
Это не доказанная ложная публичная авторизация ответа: answer/edit flags в
исследованных packets остаются false.

Запасной путь (late fallback) спасает часть полезных фрагментов после отказа
основной проверки, но также пропускает лишний текст. Его ограничение сделало один
adversarial case зелёным, однако потеряло правильный числовой факт в другом случае.

**Безопасное продуктовое исправление пока не найдено. Не доказана необходимость
переписывать всю систему.**

## Поможет ли lookup?

Lookup может помочь найти нужный документ или отдельный факт. Но в рассмотренных
случаях нужный текст уже был найден, а проблема возникала при проверке и отборе.
Поэтому добавление lookup само по себе не исправляет эту причину: найденный текст
может быть отвергнут последующей проверкой. Полезный explicit lookup не должен
автоматически считаться доказательством ответа на исходный вопрос.

## Что будет, если удалить проверки?

| Изменение | Что установлено |
|---|---|
| Убрать строгие проверки | Можно пропустить больше полезного текста, но и нерелевантного. Безопасность не доказана. |
| Отключить late fallback для strict attributes | Независимое review подтвердило потерю полезного числового факта. Кандидат A заблокирован. |
| Расширить запрет supporting-документов | Кандидат B не принят. Безопасность не доказана; потерю дополнительной строки нельзя выдавать за доказанную потерю необходимого ответа. |
| Добавить очередной alias/regex под конкретную фразу | Это не доказанное общее решение; может повторить цикл локальных исправлений. |

## Конкретный контрпример для возвращения к работе

Вопрос:

> How many retry attempts does ProjectRetryPolicy allow?

Полезный источник:

```markdown
# ProjectRetryPolicy

The retry policy allows at most two attempts.
```

Baseline доставляет heading и числовую фразу. Кандидат A с дополнительным
`and not strict_single_attribute` на late fallback возвращает отказ.

Диагностика показала: subject и `two` распознаются, но разделённые термы
`retry ... attempts` не признаются атрибутом `retry attempts`.
Обратный пример — `ProjectRetryPolicy delegates retry decisions to OtherWorker,
which allows nine retry attempts.` — проходит внутренний attribute proof, хотя
число относится к OtherWorker. Совместное наличие слов не доказывает принадлежность
числа нужному subject.

## Состояние на паузе

- **A — BLOCKED:** расширение strict-attribute veto теряет полезный контекст.
- **B — не принят:** расширение authority_duplicate не обосновано как безопасное.
- **C — ограниченные проверки атрибуции:** normal anchor-only packet проверен;
  миграция старого hint-теста требует отдельного согласования. Полный heterogeneous
  merge/crop attribution audit не завершён.
- Поиск упрощения дал только мелкое переиспользование cached roles. Оно не
  исправляет #211 и не выбрано для интеграции.
- Подготовлены 10 native control captures, не «10 PASS» всех желаемых требований.
- Кандидаты A/B не перенесены в #211 или main. Product code интеграционной ветки,
  существующие tests/gold, guards, budgets и workflows этими работами не изменены.
- По последним проверкам CI остаётся красным; разрешения на merge нет. На момент
  этой диагностической паузы документы ещё не были закоммичены и опубликованы.

## Исторический план продолжения #211 (superseded)

1. Не повторять отвергнутый однострочный veto и не отключать проверки целиком.
2. Взять подготовленные пары: отсутствие числа / реальное число; inline / heading;
   точная фраза / перефразировка; число нужного / другого subject.
3. Зафиксировать ожидаемые цитаты и запрещённые claims отдельно от внутренних
   detector verdicts. Согласовать спорное поведение partial context и explicit lookup.
4. Исследовать связь **subject → attribute → value**. Отсутствие распознанного
   witness не считать доказательством отсутствия факта.
5. Предлагать patch только с проверкой обеих сторон: не пропускать неподходящее
   и не терять полезное. Затем независимое review и обязательные проверки одного SHA.

## Навигация по материалам

- [План #211 → main с критериями завершения](MERGE_PLAN_RU.md)
- [Выполнение: актуальный CI и адресные проверки](EXECUTION_STATUS_RU.md)
- [Кандидат prefit fallback: patch, проверки и ограничения](PREFIT_PATCH_RU.md)
- [Удаление retrieval-словаря: зависимости, A/B и путь замены](RETRIEVAL_DICTIONARY_REVIEW_RU.md)
- [Общий план ухода от словарей RU/EN: этапы и критерии DONE](DICTIONARY_EXIT_PLAN_RU.md)
- [P0: read-path caller map, дополнительная D34 и static baseline](P0_READ_PATH_AUDIT_RU.md)
- [P0 slice 2: symbol decisions, policy provenance, диагностические probes](P0_SYMBOL_POLICY_AUDIT_RU.md)
- [P0 slice 3: patch/source/discovery и public-shard bridges](P0_NEIGHBOR_BRIDGE_AUDIT_RU.md)
- [Проверка перехода P0 → P1 и оставшиеся gates](P0_TO_P1_GATE_RU.md)
- [P1 preparation: RU/EN acceptance draft и decision/test migration ledger](P1_ACCEPTANCE_DRAFT_RU.md)
- [Реестр словарей и связанных правил: D01–D38](DICTIONARY_INVENTORY_RU.md)
- [Итог параллельной классификации и оставшаяся граница P0](P0_PARALLEL_RESULT_RU.md)
- [Статус выполнения dictionary-exit](DICTIONARY_STAGE_STATUS_RU.md)
- [Живое сравнение с Grounded MCP](GROUNDED_COMPARISON_RU.md)

- [Критическое ревью первоначального анализа](../PR211_RED_ANALYSIS_REVIEW_RU.md)
- [Сводка исходных доказательств](../PR211_RED_EVIDENCE_20261006.json)
- [Первые параллельные задачи и независимое review](../PR211_PARALLEL_TASKS_RU.md)
- [Пересмотр анализа после отклонения кандидатов](../PR211_POST_PARALLEL_REASSESSMENT_RU.md)
- [Поиск упрощения: задачи и итог](../PR211_SIMPLIFICATION_TASKS_RU.md)

## Обновление: завершённые ветки удалены, результаты архивированы

После разрешения владельца удалены 13 завершённых локальных веток последней
работы: 7 веток агентов и 6 старых stage3 веток. Действующая ветка #211 сохранена
на исходном SHA. На сервере из проверенных stage3/pr211 heads осталась только она;
удалена лишь устаревшая локальная tracking-ссылка `origin/pr211-merge`.

Отчёты, незакоммиченные patches, новые tests, scripts, captures и logs семи агентов
сохранены в [archives](archives/README_RU.md). SHA-256 всех архивов и содержимого
проверены до удаления worktrees. Исторические stage3 SHA сохранены существующими
archive tags либо историей #211; перечень — `archives/CLEANUP.json`.

Ниже **исторические, уже удалённые** worktree paths; их результаты доступны в
одноимённых архивах (`pr211-` опущен в имени архива):

- `/tmp/opencode/pr211-parallel-strict-attribute`
- `/tmp/opencode/pr211-parallel-authority`
- `/tmp/opencode/pr211-parallel-hint`
- `/tmp/opencode/pr211-parallel-review`
- `/tmp/opencode/pr211-simplify-routes`
- `/tmp/opencode/pr211-simplify-decisions`
- `/tmp/opencode/pr211-simplify-controls`

В каждом архиве есть `files/REPORT_RU.md`, также отчёты скопированы рядом отдельными
читаемыми Markdown-файлами. Controls содержит `controls_corpus.py`, `run_controls.py`
и `controls-final-baseline.json`. Неизменённые tracked files восстанавливаются из
записанного HEAD; Python/pytest caches не архивировались. Документы и архивы
подготовлены для публикации в #211 по отдельному разрешению владельца на commit/push;
это не разрешение интегрировать отвергнутые patches или выполнить merge в main.
