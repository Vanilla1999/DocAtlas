# v2plan

Планы и результаты model-free / Grounded-style исследования.

- [Один read decision: контракт до реализации](UNIFIED_READ_CONTRACT_RU.md).
- [Пункт 5: реализация, native-inventory replay и границы результата](UNIFIED_READ_RESULT_RU.md).
- [Обязательные правила против переусложнения](AGENTS.md).
- [Что отбрасывается и где конкурируют read решения](ADMISSION_CONFLICT_AUDIT_RU.md).
- [Exact-window сравнение: измеренные расхождения и граница удаления обязанностей](EXACT_WINDOW_CONFLICT_RESULT_RU.md).
- [Решение: что удалять первым и что сохранять](ADMISSION_REMOVAL_DECISION_RU.md).
- [Первый patch: read без proof qualification, native pipeline проверки](READ_GUARD_PATCH_RESULT_RU.md).

- [Admission: Kotlin, Markdown, исследования и направление упрощения](ADMISSION_DIRECTION_REVIEW_RU.md).

- [Typed compiler: реализация и результат paired owner/1500 replay](TYPED_CONSTRAINT_COMPILER_RESULT_RU.md).

- [Temporal question vs condition: root cause и controls](TEMPORAL_CONDITION_REVIEW_RU.md).

- [Исправленный isolated candidate: результат одного прогона 1500](CORRECTED_OWNER_1500_RESULT_RU.md).

- [Subject / literal / condition / topic: уточнённый разбор](ADMISSION_LAYERS_REVIEW_RU.md).

- [Текущий вывод: причины потерь](GROUNDED_LOSS_ATTRIBUTION_RU.md).
- [Результаты budgets 800 / 1500 / 3000](GROUNDED_BUDGET_RESULT_RU.md).
- [План budget эксперимента](M2_GROUNDED_BUDGET_EXPERIMENT_RU.md).
- [Исходный TDD-план 01–09](M2_MODEL_FREE_RETRIEVAL_TDD_RU.md).
- [Execution status](EXECUTION_RU.md).
- [Сохранённые 01–04](ISOLATED_01_04_VALIDATION_RU.md).

Статус: 01–04 сохранены изолированно, replacement не принят, production не менялся.
Исторические планы не являются разрешением на rollout.

Research scripts: `grounded_budget_probe.py`, `grounded_loss_audit.py`.
Tests остаются в `tests/docs/test_grounded_budget_probe.py`.

Сохранённые JSON-результаты находятся в `artifacts/budget/` и
`artifacts/loss-attribution/`. Они скопированы без изменения из последнего полного
прогона; исходные provenance/hash/path значения сохранены как исторические.
Полные fixture DB, corpus copies и native baseline observer captures остаются
по внешнему пути из отчёта: для повторного read-only audit нужен этот archive.
Для нового исследования можно воспроизвести archive budget probe, не меняя runtime.

Исторический Gate A prototype и прежние comparator scripts остаются в
`roadmap/search-quality-2026-10-01/`; ссылки в документах исправлены.
