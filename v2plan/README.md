# v2plan

Планы и результаты model-free / Grounded-style исследования.

## Рабочий маршрут сейчас

**[07 — Grounded-first: инструкция исполнителю](NEXT_07_READ_PIPELINE_OWNERSHIP_RU.md)**
— единственный активный план. Ветка `next07-feasibility-audit`, не `main`.
Статус нового эксперимента: **PLANNED / NOT_RUN**.

Порядок по решению пользователя от 2026-10-04:

1. Реальный pinned Grounded 3.2.1 на исходном LeaseClient, затем минимальный
   Grounded-подобный source-bound read candidate без LLM, с прежними guards и
   полным DTO budget **800 tokens / 3 sources**.
2. Только после локальной приёмки основы — existing source continuation и
   focused lookup workflow, по одному; NO_CHANGE допустим, новые эвристики нет.

План содержит I.0–I.6, II.1–II.2, allowed files, fixed initial algorithm,
обязательные positives/negatives, protocol policy-delta, actual final packet,
retention исторических 49 claim IDs, DONE / REJECTED / BLOCKED и stop rules.
Не начинать с compiler/event-condition expansion. Не добавлять LLM/reranker.

Read-policy candidate явно отличается от старой: unknown applicability сама
по себе не запрещает исходный context, но не получает applicability/support
credit. Source/security/identity/scope/version/freshness/snapshot/span/exact
guards и сохранение условий обязательны с начала, а не добавляются «потом».
Старые tests/frozen labels не переписывать ради результата. Намеренные policy
различия фиксируются до кода; frozen acceptance и блокеры 06 не исчезают.

Ни один G/C run новым планом не выполнен. Предыдущая реконструкция FTS LeaseClient
в чате не является real Grounded capture. Эксперимент запускает пользователь.
Эта запись не меняет runtime/defaults, не разрешает rollout и не закрывает 06.

## История планов 01–07

1. [01 — existing lookup для недостающей части](NEXT_01_LOOKUP_GAPS_RU.md).
2. [02 — удаление одной конкурирующей admission-обязанности](NEXT_02_ADMISSION_SIMPLIFICATION_RU.md).
3. [03 — инструкция focused lookup и завершение работы](NEXT_03_FOCUSED_LOOKUP_WORKFLOW_RU.md).
4. [04 — приёмка текущей версии для выпуска](NEXT_04_PROD_CANDIDATE_EVALUATION_RU.md).
5. [05 — исправление блокеров и завершение приёмки](NEXT_05_RELEASE_BLOCKERS_RU.md).
6. [06 — тестовые контракты и оставшиеся блокеры](NEXT_06_TEST_CONTRACTS_AND_AGENT_ACCEPTANCE_RU.md).
7. [07 — прежний scope/compiler trial и feasibility BLOCKED](NEXT_07_SCOPE_TRIAL_HISTORY_20261004_RU.md).

01 завершён. 02 законсервирован: простое удаление gate отклонено (49 → 45 claims).
03 завершён. Восстанавливать prod для приёмки не требуется.
04 проверен в доступной части, BLOCKED: 49 claims сохранены, но required checks
красные, tools/list превышает byte budget; реальные ответы агента не проверены.
05 выполнен частично, BLOCKED: footprint 6143 bytes, routing исправлен;
128 offline failures, adversarial/question-surface gates и 0/8 ответов оставались.
06 сохраняет очередь решений по tests, gates и изолированному runner.
Его сохранённый полный offline rerun: 6125 PASS / 93 FAIL / 10 SKIP,
новых failing nodes нет; 35 baseline nodes заменены passing checks без удаления
tests и изменения runtime. Ledger: 81 UNRESOLVED, 4 KEEP_FIX_RUNTIME,
8 ENV_BLOCKED, 35 REWRITE. Это исторические результаты, не свежий run плана 07.

Native delivery прежнего кандидата отклонена (LeaseClient); миграция historical
gates требует выяснения parser/acceptance contract. Namespace isolation была
недоступна; восемь ответов проверены в чате, не isolated model run.
49 → 45 относится к отклонённой ablation, не к принятому runtime patch.

**Предыдущая попытка 07 окончательно BLOCKED на 07.1**: existing grammar/consumer
не поддерживают mandatory event-condition даже при local binding. Diagnostic
2 PASS проверяли blocker report, не recovery; 07.2–07.5 NOT_RUN.
[JSON evidence](artifacts/next07/feasibility-audit-20261004.json) неизменён.
Полный старый план скопирован в history byte-for-byte; прежний verdict сохранён.
Preservation trial native 5/7 → candidate 6/7 остаётся REJECTED: expiration
прикреплён к default. Не возобновлять этот маршрут автоматически.

`AGENTS.md` обязателен. Новые результаты писать в существующий активный 07 и
новый `artifacts/next07/grounded-first/<run-id>/`. Старые captures не перезаписывать.
Не создавать отдельный план на каждый прогон. История не является implementation
очередью и не отменяет нынешнюю границу эксперимента.

## Кандидаты на уборку (пока не удалены)

Неактивные планы, кандидаты на архивирование/удаление из рабочей папки:
`M2_MODEL_FREE_RETRIEVAL_RESEARCH_RU.md`, `M2_MODEL_FREE_RETRIEVAL_TDD_RU.md`,
`M2_HEURISTICS_RESEARCH_ANALYSIS_RU.md`, `M2_SIMPLIFICATION_CONTRACT_RU.md`,
`M2_GROUNDED_BUDGET_EXPERIMENT_RU.md`, `GATE_R_PROPOSAL_RU.md`,
`UNIFIED_READ_CONTRACT_RU.md`. Они не являются текущими implementation instructions.

Gate/experiment result отчёты — исторические свидетельства, не мусор:
хранить в архиве при уборке. `EXECUTION_RU.md` — historical log, не текущий план.
Не удалять `*.py`, `artifacts/`, `AGENTS.md`, history 07 или
`M2_GROUNDED_MECHANISM_CHECK_RU.md` вместе со старыми планами: есть test imports,
provenance и ссылки. Перед удалением проверить references; snapshots сохранить.
`experiments/crosslingual_relevance/` не относится к этой уборке.

## Исторические материалы и опорные отчёты

- [Grounded 3.2.1: проверка механизма на mkdocs-05](M2_GROUNDED_MECHANISM_CHECK_RU.md).
- [Один read decision: прежний isolated контракт](UNIFIED_READ_CONTRACT_RU.md).
- [Его результат и границы](UNIFIED_READ_RESULT_RU.md).
- [Правила против переусложнения](AGENTS.md).
- [Конкурирующие read решения](ADMISSION_CONFLICT_AUDIT_RU.md).
- [Exact-window сравнение](EXACT_WINDOW_CONFLICT_RESULT_RU.md).
- [Прежнее решение по удалению обязанностей](ADMISSION_REMOVAL_DECISION_RU.md).
- [Первый patch: read без proof qualification](READ_GUARD_PATCH_RESULT_RU.md).
- [Admission: исследования и направление упрощения](ADMISSION_DIRECTION_REVIEW_RU.md).
- [Typed compiler и paired owner/1500 replay](TYPED_CONSTRAINT_COMPILER_RESULT_RU.md).
- [Temporal question vs condition](TEMPORAL_CONDITION_REVIEW_RU.md).
- [Corrected isolated candidate 1500](CORRECTED_OWNER_1500_RESULT_RU.md).
- [Subject / literal / condition / topic](ADMISSION_LAYERS_REVIEW_RU.md).
- [Причины потерь](GROUNDED_LOSS_ATTRIBUTION_RU.md).
- [Исторические budgets 800 / 1500 / 3000](GROUNDED_BUDGET_RESULT_RU.md).
- [Прежний budget эксперимент](M2_GROUNDED_BUDGET_EXPERIMENT_RU.md).
- [Исходный TDD-план 01–09](M2_MODEL_FREE_RETRIEVAL_TDD_RU.md).
- [Execution history](EXECUTION_RU.md).
- [Сохранённые 01–04](ISOLATED_01_04_VALIDATION_RU.md).

01–04 сохранены изолированно, replacement не принят. Original-read изменён
в `152a4c7b`; rollout не выполнен. Старые заявления «production не менялся» относятся
к соответствующим историческим исследованиям, не к текущему исходному коду.

Research scripts: `grounded_budget_probe.py`, `grounded_loss_audit.py`.
Tests: `tests/docs/test_grounded_budget_probe.py`.
JSON-результаты находятся в `artifacts/budget/` и `artifacts/loss-attribution/`.
Они сохранены без изменения provenance/hash/path. Полные fixture DB, corpus
copies и native observer captures остаются по внешнему пути из отчёта;
наличие лишь summary не считать наличием полного исполняемого baseline.

Исторический Gate A prototype и comparator scripts остаются в
`roadmap/search-quality-2026-10-01/`. Они не подключаются к candidate автоматически.
