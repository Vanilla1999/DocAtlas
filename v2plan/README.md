# v2plan

Планы и результаты model-free / Grounded-style исследования.

## Рабочий маршрут сейчас

1. [01 — existing lookup для недостающей части](NEXT_01_LOOKUP_GAPS_RU.md).
2. [02 — удаление одной конкурирующей admission-обязанности](NEXT_02_ADMISSION_SIMPLIFICATION_RU.md).
3. [03 — инструкция focused lookup и завершение работы](NEXT_03_FOCUSED_LOOKUP_WORKFLOW_RU.md).
4. [04 — приёмка текущей версии для выпуска](NEXT_04_PROD_CANDIDATE_EVALUATION_RU.md).
5. [05 — исправление блокеров и завершение приёмки](NEXT_05_RELEASE_BLOCKERS_RU.md).
6. [06 — тестовые контракты и оставшиеся блокеры](NEXT_06_TEST_CONTRACTS_AND_AGENT_ACCEPTANCE_RU.md).
7. [07 — причины потери read context и одна проверяемая замена](NEXT_07_READ_PIPELINE_OWNERSHIP_RU.md).

01 завершён. 02 законсервирован: простое удаление gate отклонено (49 → 45 claims).
03 завершён. Восстанавливать prod для приёмки не требуется.
04 проверен в доступной части, BLOCKED: 49 claims сохранены, но required checks
красные, tools/list превышает byte budget; реальные ответы агента не проверены.
05: два локальных исправления и завершение проверок.
05 выполнен частично, BLOCKED: footprint 6143 bytes, routing исправлен;
128 offline failures, adversarial/question-surface gates и 0/8 ответов остаются.
06 сохраняет очередь решений по tests, gates и изолированному runner.
06 не завершён: после test-contract trials 6124 PASS / 94 FAIL / 10 SKIP,
новых failing nodes нет; 34 baseline nodes заменены passing checks без удаления
tests и изменения runtime. Последующий focused trial: ledger 81 UNRESOLVED,
4 KEEP_FIX_RUNTIME, 8 ENV_BLOCKED, 35 REWRITE; full rerun после него не выполнен.
Native delivery кандидата отклонена (LeaseClient); миграция historical gates
требует выяснения действующего parser/acceptance contract. Namespace isolation
недоступна; восемь ответов проверены в чате (не isolated model run), полный
per-node разбор ещё не выполнен. Подробные основания — в плане 06.
49 → 45 относится только к отклонённой ablation, не к принятому runtime patch.
07 — новый ограниченный маршрут по запросу пользователя: сначала подтвердить
причины потери и контракт, затем выбрать одну ответственность либо остановиться.
План 07 пока PLANNED, не закрывает 06 и не разрешает unified replacement/rollout.
Admission/selection research за пределами границ 07 автоматически не продолжать.
Критерии DONE/BLOCKED/REJECTED находятся внутри.
Результаты дописывать в соответствующий план, не создавать новый на каждый прогон.
`AGENTS.md` обязателен. Актуальные опорные отчёты: `READ_GUARD_PATCH_RESULT_RU.md`,
`EXACT_WINDOW_CONFLICT_RESULT_RU.md`, `ADMISSION_REMOVAL_DECISION_RU.md`,
`ADMISSION_DIRECTION_REVIEW_RU.md`. Остальные материалы ниже — история, не очередь задач.

## Кандидаты на уборку (пока не удалены)

Неактивные планы, кандидаты на архивирование/удаление из рабочей папки:
`M2_MODEL_FREE_RETRIEVAL_RESEARCH_RU.md`, `M2_MODEL_FREE_RETRIEVAL_TDD_RU.md`,
`M2_HEURISTICS_RESEARCH_ANALYSIS_RU.md`, `M2_SIMPLIFICATION_CONTRACT_RU.md`,
`M2_GROUNDED_BUDGET_EXPERIMENT_RU.md`, `GATE_R_PROPOSAL_RU.md`,
`UNIFIED_READ_CONTRACT_RU.md`. Они не являются текущими implementation instructions.

Gate/experiment result отчёты — исторические свидетельства, не мусор:
хранить в архиве при уборке. `EXECUTION_RU.md` — historical log, не текущий план.
Не удалять `*.py`, `artifacts/`, `AGENTS.md` или `M2_GROUNDED_MECHANISM_CHECK_RU.md`
вместе со старыми планами: есть test imports, provenance и ссылки на доказательства.
Перед физическим удалением проверить references и поправить ссылки; snapshots
сохранены в git. `experiments/crosslingual_relevance/` не относится к этой уборке.

## Исторические материалы и опорные отчёты

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

Статус: 01–04 сохранены изолированно, replacement не принят. Original-read изменён
в `152a4c7b`; rollout не выполнен. Старые заявления «production не менялся» относятся
к соответствующим историческим исследованиям, не к текущему исходному коду.
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
