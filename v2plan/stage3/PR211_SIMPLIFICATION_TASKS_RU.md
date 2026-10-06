# #211: поиск обоснованного упрощения

**Обновление после завершения:** временные ветки и worktrees удалены по разрешению
владельца; отчёты и диагностики доступны в
[архиве точки возврата](pr211-context-admission-checkpoint-2026-10-06/archives/README_RU.md).
Приведённые ниже worktree paths теперь исторические.

Дата: 2026-10-06. Разрешение пользователя: найти упрощение и поручить задачи агентам.
Общий baseline: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.
Основание: `PR211_POST_PARALLEL_REASSESSMENT_RU.md`.

Цель — уменьшить повторные решения и сложность, не считать уменьшение строк
доказательством улучшения. Не повторять заблокированный A и отклонённый B.

| Агент | Задача | Worktree / ветка | Session |
|---|---|---|---|
| Routes | Повторные вычисления и трактовки; не более одного кандидата удаления дублирования | `/tmp/opencode/pr211-simplify-routes`, `diagnostic/pr211-simplify-routes-20261006` | `ses_eefaabd57ffebWTICtSPrJgEln` |
| Decisions | Границы source eligibility / read relevance / proof / attribution; таблица решений и возможность малого упрощения | `/tmp/opencode/pr211-simplify-decisions`, `diagnostic/pr211-simplify-decisions-20261006` | `ses_eefaa770effeetATYzUpWFlUKK` |
| Controls | Небольшой независимый native corpus: numeric, heading, paraphrase, чужой subject, explicit lookup; наблюдения и acceptance отдельно | `/tmp/opencode/pr211-simplify-controls`, `diagnostic/pr211-simplify-controls-20261006` | `ses_eefaa3fabffeBp1gyz0h6Buxc1` |

Каждый возвращает `REPORT_RU.md` в корне своего worktree и при необходимости
standalone read-only диагностику. Product, existing tests, manifest, gold,
guards, budgets и workflows не редактируются. Никаких commit/push/merge.

Требование к предложению:

1. Конкретно назвать, что удаляется/переиспользуется и какие решения остаются.
2. Отделить сохранение поведения от изменения продуктового контракта.
3. Обосновать и положительные, и отрицательные случаи до реализации.
4. Не вводить новые keyword/regex exceptions, DTO-архитектуру или новый read-pipeline.
5. Если безопасное упрощение не найдено — вернуть этот вывод, не выпускать patch
   ради результата задачи. Семантически разные contracts не объединять по сходству полей.

После получения результатов — сводная оценка и независимое review выбранного
предложения перед реализацией. Этот этап не обещает исправления красного CI;
безопасное устранение дублирования может улучшить сопровождение без изменения failures.

## Статус

- Decisions завершён: безопасное малое упрощение A/B не доказано. Исполнитель
  подготовил таблицу решений, remove/reuse-разбор, вопросы продуктовой политики
  и условия приёмки; шесть native baseline captures сохранены в его worktree.
  Отчёт: `/tmp/opencode/pr211-simplify-decisions/REPORT_RU.md`.
  Это вывод исполнителя; сводная оценка и независимое review ещё не выполнены.
- Routes завершён: предложено переиспользование `query_constraint_roles(text)` —
  3 → 1 cache lookup на probe. По отчёту исполнителя, 82 парных сравнения совпали,
  26 baseline tests PASS. Безопасного сокращения main/late маршрутов не найдено;
  cleanup не исправляет #211. Product patch не применён, независимое review
  предложения не выполнено. Отчёт: `/tmp/opencode/pr211-simplify-routes/REPORT_RU.md`.
- Controls завершён: 10 native captures, не aggregate «10 PASS». Числовые
  контрпримеры подтверждены; настоящий projection crop 772 → 462 chars сохраняет
  запрошенный факт. Это не проверка anchor-only attribution после удаления witness.
  B-пара не принята: supporting естественно выбирается первым, поэтому условие
  authoritative-first не испытано. Отчёт:
  `/tmp/opencode/pr211-simplify-controls/REPORT_RU.md`.
- Предложение для product implementation не выбрано; product/tests/manifest
  не изменялись, commit/push/merge не выполнялись.

## Сводный вывод после чтения трёх отчётов

Все исполнители завершили работу. Это сводка координатора, не новый независимый
replay и не независимое ревью возможного patch.

1. Малого изменения, одновременно упрощающего main/late маршруты и исправляющего
   известные failures без потери полезного контекста, не найдено. Это ограничение
   исследованных предложений, не доказательство невозможности будущего исправления.
2. Единственное механическое предложение — reuse cached roles — не меняет
   eligibility/qualification/selection и не ремонтирует CI. Не выбирать его как
   очередной этап ремонта #211; отдельная интеграция сейчас не предлагается.
3. Read eligibility, context, proof и attribution уже представлены разными
   структурами. Добавление новой общей структуры само по себе не устранит проблему:
   no-value и полезная numeric paraphrase получают одинаковый missing witness,
   чужое число в той же фразе получает положительный proof. Нужно различение этих
   случаев, а не новое имя boolean или отключение одной проверки.
4. Сохранён небольшой native corpus для следующего действительного кандидата:
   `/tmp/opencode/pr211-simplify-controls/controls_corpus.py`, `run_controls.py`,
   `controls-final-baseline.json`. Это наблюдения и предложенные acceptance-пары;
   no-value/foreign-number/independent-lookup policy не превращена в новый gold.
5. B всё ещё не имеет request-relevant authoritative-first positive control.
   Успех нового crop не закрывает прежние ограничения C по attribution/merge.

Продуктовый кандидат для независимого review не выбран: очередного агента для
реализации или приёмки micro-cleanup не запускаем. Следующий содержательный этап —
зафиксировать на этих парах контракт полезного partial context/explicit lookup и
проверить конкретный способ source–attribute–value binding. Если это требует
расширения qualification, считать отдельной задачей проектирования, не выдавать
за доказанное безопасное упрощение или новый read-pipeline внутри #211.

Ни один отчёт не является full CI или merge readiness. Временные worktrees и
доказательства сохраняются; исправления A/B не перенесены, hint gold не обновлён.
