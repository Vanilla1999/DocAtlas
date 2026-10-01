# Исправление поиска DocAtlas: короткий TDD-план

**Статус:** clean-Git recovery шага 01 исправлен; [проверки и ограничения](results/01-clean-project-recovery/README.md). Шаг 02 выполнен: [clear → rebuild и проверки](results/02-clear-rebuild-lifecycle/README.md). Шаги 03–10 не начаты. Выполнять по одному шагу, не весь план сразу.

## Порядок

| Шаг | Задача | Режим |
|---|---|---|
| [01](steps/01-clean-project-recovery.md) | P0: подготовка чистого неиндексированного проекта | Минимальная runtime-правка |
| [02](steps/02-clear-rebuild-lifecycle.md) | P0: clear → rebuild в одном MCP-процессе | Минимальная runtime-правка |
| [03](steps/03-public-docs-contract.md) | P1: согласовать текущие публичные инструкции | Документация и её тесты |
| [04](steps/04-corpus-authority.md) | P1: отделить текущие contracts от history/plans | Каталог и его тесты |
| [05](steps/05-evidence-evaluator.md) | P1: исправить оценку фактов и цитат | Только eval |
| [06](steps/06-multilingual-recall.md) | P1: проверить bilingual recall | Один эксперимент, без активации |
| [07](steps/07-candidate-admission.md) | P1: не терять найденный полезный факт | Только qualification/отбор |
| [08](steps/08-per-source-cap.md) | P1: не терять Typer-факт на раннем cap | Только отбор перед cap |
| [09](steps/09-packet-cost.md) | P1: сравнить full/lean packets | Один эксперимент, без активации |
| [10](steps/10-independent-gate.md) | Независимая проверка реальной пользы | Проверка, не новый tuning |

## Общие правила для coding-агента

- Работай в отдельной ветке от актуального `main`. Не трогай чужие незакоммиченные изменения. Без push/merge.
- **Red → Green → Refactor:** воспроизведи сбой и получи падающий regression test; сделай минимальную правку; необязательный refactor — только рядом с ней.
- Меняй только выбранный участок. Не совмещай поиск, оценщик, документацию и бюджеты в одном изменении; не меняй defaults, thresholds или зависимости без отдельного согласования.
- Не ослабляй тесты и source/project/version/snapshot/stale/scope/permission guards ради результата.
- Runtime-правки проверяй через настоящий installed MCP stdio из исправленной ветки: зафиксируй commit/version/import path. Прямой Python handler не заменяет эту проверку.
- В поисковых экспериментах сохраняй corpus bytes, вопросы, budgets и scorer одинаковыми для до/после. Frozen-80 — регрессия, не независимый success gate.
- Архив `audit/` не перезаписывай. Старые runners одноразовые; новый запуск должен писать в отдельные output/fixture paths.
- Если сбой уже исправлен на актуальном `main`, покажи подтверждающий тест и smoke, без искусственной правки. Если нужна смена policy или более широкий diff — остановись и объясни почему.

**Результат каждого шага:** воспроизведение до → изменённые файлы → проверки после → оставшиеся ограничения. Затем остановиться; следующий шаг — по отдельному запросу.

## Материалы

- [Анализ причин и ограничений](audit/ANALYSIS_RU.md).
- [Исходный общий план](audit/ACTION_PLAN_RU.md) — справочный архив; исполнительные задания находятся в `steps/`.
- [Оценки вопросов по проекту](audit/PROJECT_80_REVIEW_RU.md), [библиотекам](audit/EXTERNAL_80_REVIEW_RU.md), [сравнения](audit/COMPARATORS_RU.md).
- [Состав и оговорки аудита](audit/README.md). Все прежние файлы, включая raw, corpus, backup и runners, перенесены в `audit/` без изменения байтов. Его manifest относится только к архиву.

## Первый запрос агенту

> Прочитай этот README, audit/ANALYSIS_RU.md и steps/01-clean-project-recovery.md. Выполни только шаг 01 по TDD и общим правилам. Покажи до/после, изменённые файлы, проверки и ограничения. Не переходи к шагу 02. Без push/merge.
