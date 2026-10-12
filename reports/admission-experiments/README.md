# Admission experiments — V1–V3

Архив завершённых исследований от 2026-10-12. Код экспериментов:
`6adc8e655fa69b5475adf613c8c446dd3a604b98`. Поведение V3 остаётся opt-in.

## Основные результаты

| Этап | Итог | Независимый review | Учёт стоимости |
| --- | --- | --- | --- |
| V2 | [RESULT_V2_RU.md](admission-selection-v2/RESULT_V2_RU.md) | [FINAL_REVIEW_V2_RU.md](admission-selection-v2/review/FINAL_REVIEW_V2_RU.md) | [COSTS_V2.json](admission-selection-v2/COSTS_V2.json) |
| V3 | [RESULT_V3_RU.md](admission-v3/RESULT_V3_RU.md) | [INDEPENDENT_REVIEW_RU.md](admission-v3/INDEPENDENT_REVIEW_RU.md) | [COSTS_V3.json](admission-v3/COSTS_V3.json) |

- [V3: результаты по сценариям](admission-v3/RESULTS_V3.json).
- [V2: checkpoint](admission-selection-v2/COMPACT_CHECKPOINT_RU.md).
- [V3: checkpoint](admission-v3/COMPACT_CHECKPOINT_RU.md).
- [V1: итоговый отчёт](admission-full-20261012/FINAL_REPORT_RU.md).
- [Методический аудит](admission-full-20261012/RESEARCH_METHOD_AUDIT_RU.md).

V2 подтвердил узкую пользу Mini, но его необходимость после V3 pool repair
не проверялась. V3 повысил полноту новых positive задач с 1/4 до 3/4;
empty-source контракт нарушен в 6/9 negative сценариев. Это не основание
для включения эксперимента по умолчанию. Coordinate citations дали 4/4
точные поддержанные цитаты при росте submitted prompt примерно на 99,7%;
это изменение presentation/generator contract, а не выигрыш ranker.

## Состав архива

V2 и V3 скопированы с сохранением структуры и содержимого: отчёты, протоколы,
reviews, JSON-результаты, costs, raw public packets, host answers/receipts,
citation evidence, скрипты и снимки baseline. Исключён только Python bytecode
(`__pycache__`, `*.pyc`). Для V1 включены все Markdown-отчёты верхнего уровня;
его runtime-каталоги, веса моделей и raw evidence в этот архив не входят.
Также сохранены общие Markdown-протоколы и review из корня evidence.

Исходный каталог: `/tmp/opencode/docatlas-review-evidence/`.
Исторические абсолютные пути внутри файлов сохранены для provenance;
V2/V3-файлы следует искать по тому же суффиксу пути внутри этой папки.
Ссылки на внешние runtime-каталоги отражают исходное окружение и не означают,
что эти каталоги опубликованы. Эксперименты при архивации не перезапускались.
