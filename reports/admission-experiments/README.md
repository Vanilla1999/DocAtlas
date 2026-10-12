# Admission experiments — V1–V3 и prepared retrieval

Архив завершённых исследований от 2026-10-12. Код экспериментов:
`6adc8e655fa69b5475adf613c8c446dd3a604b98`. Поведение V3 остаётся opt-in.

## Основные результаты

- [Mini / budget после prepared retrieval: 40 вопросов](prepared-retrieval/model-comparison-40-20261012/RESULT_RU.md)
  — два opt-in режима, 40 пар / 80 публичных context calls, 450 реальных Mini forwards;
  strict positive 17→20/24, partial 4→3/8, negative 1→1/8. Независимый смысловой
  review: positive 18→20/24, partial 5→4/8; готовый контекст, без генератора.
  Все вопросы, исходные документы, raw результаты и затраты сохранены.
- [Повторное review, исправление отказа и проверка подстройки](prepared-retrieval/review-20261012/RESULT_RU.md)
  — публичный FAIL до фикса и пять PASS после, доказанный prepared reuse/fallback,
  усиленные negative/checklist assertions и новый нечисловой пример без прироста
  относительно контроля; модели не вызывались.
- [Реализация prepared retrieval и интеграционные проверки до модели](prepared-retrieval/implementation-20261012/RESULT_RU.md)
  — новый opt-in путь, четыре новые и две существующие публичные проверки,
  исправленный по независимому review budget-attribution defect; моделей не запускали.
- [Независимое review реализации](prepared-retrieval/implementation-20261012/INDEPENDENT_REVIEW_RU.md)
  и [полный ledger новых исполнений](prepared-retrieval/implementation-20261012/execution_ledger.json).
- [Разбор фильтра DocAtlas и сравнение с Grounded](FILTER_ROOT_CAUSE_AND_GROUNDED_RU.md)
  — последующий анализ кода и сохранённых данных, без новых прогонов.
- [Подготовленный retrieval: анализ исследований и текущей архитектуры](prepared-retrieval/ANALYSIS_RU.md).
- [План для нескольких агентов](prepared-retrieval/MULTI_AGENT_PLAN_RU.md)
  — роли, ownership, этапы, контракт, эксперимент и критерии решения.

| Этап | Итог | Независимый review | Учёт стоимости |
| --- | --- | --- | --- |
| V2 | [RESULT_V2_RU.md](admission-selection-v2/RESULT_V2_RU.md) | [FINAL_REVIEW_V2_RU.md](admission-selection-v2/review/FINAL_REVIEW_V2_RU.md) | [COSTS_V2.json](admission-selection-v2/COSTS_V2.json) |
| V3 | [RESULT_V3_RU.md](admission-v3/RESULT_V3_RU.md) | [INDEPENDENT_REVIEW_RU.md](admission-v3/INDEPENDENT_REVIEW_RU.md) | [COSTS_V3.json](admission-v3/COSTS_V3.json) |

- [V3: результаты по сценариям](admission-v3/RESULTS_V3.json).
- [V2: checkpoint](admission-selection-v2/COMPACT_CHECKPOINT_RU.md).
- [V3: checkpoint](admission-v3/COMPACT_CHECKPOINT_RU.md).
- [V1: итоговый отчёт](admission-full-20261012/FINAL_REPORT_RU.md).
- [Методический аудит](admission-full-20261012/RESEARCH_METHOD_AUDIT_RU.md).

V2 подтвердил узкую пользу Mini; в самих V2/V3 его необходимость после pool repair
ещё не проверялась. Новый парный прогон после prepared retrieval приведён выше.
V3 повысил полноту новых positive задач с 1/4 до 3/4;
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
