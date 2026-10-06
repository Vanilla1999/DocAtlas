# #211: изолированная параллельная проверка

**Обновление после завершения:** временные ветки и worktrees удалены по разрешению
владельца; все новые/изменённые файлы и отчёты сохранены в
[архиве точки возврата](pr211-context-admission-checkpoint-2026-10-06/archives/README_RU.md).
Указанные ниже worktree paths — исторические.

Повторный анализ после завершения всех задач и review:
[PR211_POST_PARALLEL_REASSESSMENT_RU.md](PR211_POST_PARALLEL_REASSESSMENT_RU.md).
Он уточняет причины отклонения и заменяет исходную рекомендацию перенести A/B.

Дата: 2026-10-06. Общий baseline: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.
Основание: `PR211_RED_ANALYSIS_REVIEW_RU.md`. Исполнение разрешено владельцем.

| Задача | Ветка | Worktree | Агент |
|---|---|---|---|
| A: strict-attribute / fallback | `diagnostic/pr211-strict-attribute-20261006` | `/tmp/opencode/pr211-parallel-strict-attribute` | `ses_eefcc5efdffeJqFLpf3tS4Kp7T` |
| B: authority / supporting safety, первоначально HOLD | `diagnostic/pr211-authority-20261006` | `/tmp/opencode/pr211-parallel-authority` | `ses_eefcc36acffe9S74U6cNWTmE0x` |
| C: hint / final public attribution | `diagnostic/pr211-hint-20261006` | `/tmp/opencode/pr211-parallel-hint` | `ses_eefcc0e7bffeA6RZNMT9i7gvN3` |

Каждый агент оставляет diff и `REPORT_RU.md` в корне своего worktree:
обоснование, точные команды, результаты baseline/candidate, ограничения и вердикт.
Обоснованное отклонение кандидата — допустимый результат.

Не разрешены commit/push/merge, изменения main или интеграционной ветки агентами,
ослабление tests/gold/guards/бюджетов/workflows и новые эвристики для целевых примеров.
Для C существующие assertions не переписываются без отдельного согласования;
разрешены дополнительные проверки и предложение миграции в отчёте.

Четвёртый независимый агент проверяет готовые diffs, свидетельства и вердикты.
Ревью B/C начато после их завершения; A будет добавлен после завершения A.
До проверки соответствующего результата результаты не считаются
прошедшими независимое review. Одновременное изменение общего selector в разных
worktrees допустимо, но их diffs нельзя объединять автоматически.

Интеграция в #211 только после оценки результатов; последовательный перенос,
общие проверки одного SHA и обязательный CI. Merge требует отдельного разрешения.
Временные ветки/worktrees сохраняются до принятия или архивирования результатов.

## Текущий статус

- A: исполнитель завершил работу; однострочный strict-attribute patch и 13 новых
  tests оставлены в изолированном worktree. По отчёту: adversarial 27/28 → 28/28,
  парный core сохраняет 17 прежних FAIL без новых, новые tests 13/13 PASS,
  advanced 622 PASS. Отчёт: `/tmp/opencode/pr211-parallel-strict-attribute/REPORT_RU.md`.
  Независимая проверка завершена: **BLOCKED**, обнаружена потеря числового контекста.
- B: исполнитель отклонил кандидат — authoritative-first probe теряет полезный
  supporting-факт. Product diff отсутствует; независимый вердикт ожидается.
  Отчёт: `/tmp/opencode/pr211-parallel-authority/REPORT_RU.md`.
- C: product patch отсутствует; 6 final-public checks PASS, старый hint FAIL
  оставлен. Предложение изменения assertions требует отдельного согласования.
  Отчёт: `/tmp/opencode/pr211-parallel-hint/REPORT_RU.md`.
- Независимый reviewer B/C: `ses_eefc1d15effe1uvUKcnciJ241j`, ветка
  `diagnostic/pr211-independent-review-20261006`, worktree
  `/tmp/opencode/pr211-parallel-review`. A явно PENDING, незавершённые изменения A
  reviewer не проверяет. Итоговый отчёт будет `REPORT_RU.md` в reviewer worktree.

## Независимое ревью B/C

Reviewer завершил первый этап. Отчёт:
`/tmp/opencode/pr211-parallel-review/REPORT_RU.md`.

- B: перенос кандидата в продукт отклонён. Потеря текста воспроизведена, но
  необходимость добавленного факта для исходного вопроса не доказана. Поэтому
  нельзя повышать результат до доказанной потери обязательного факта; безопасность
  предлагаемого изменения по-прежнему не установлена.
- C: настоящий публичный seam подтверждён, 6 новых checks PASS. Crop проверяет
  фактически удаление newline, а merge только дубликаты — полноценная проверка
  содержательного crop и heterogeneous merge не подтверждена. Миграция старого
  hint-теста остаётся предложением, требует отдельного approval.
- На момент первого этапа A был PENDING. После завершения исполнителя тот же
  reviewer продолжил независимую проверку A; окончательный вердикт **BLOCKED**.

## Независимое ревью A: BLOCKED

Контрпример: heading `ProjectRetryPolicy`, тело
`The retry policy allows at most two attempts.` Baseline цитирует числовой факт;
кандидат отказывает. Поэтому перенос strict-attribute veto на late fallback
не является принятым исправлением, несмотря на зелёный adversarial.

Reviewer независимо воспроизвёл targeted 121 PASS / 1 прежний FAIL,
adversarial 27/28 → 28/28, advanced 622 PASS, guards 21 PASS. Одноусловный diff
и manifest подтверждены; эти результаты не отменяют новый содержательный
контрпример. Нужны regression control на heading-bound subject и отдельное
согласованное решение recall tradeoff. Full CI не подтверждён.

Итог: A BLOCKED, B отклонён, C — предложение миграции с ограниченным покрытием.
Ни один product patch не одобрен для переноса. Далее требуется диагностика
расхождения subject/witness binding на основном и позднем путях, а не
автоматическое принятие veto или добавление keyword-исключения.

Ничего не перенесено в #211; commit/push/merge не выполнялись.
