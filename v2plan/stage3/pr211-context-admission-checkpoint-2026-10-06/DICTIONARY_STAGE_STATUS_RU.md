# Выполнение dictionary-exit

2026-10-06: **partial dictionary exit implemented, общий milestone ACTIVE / NOT DONE**.
Latest status и next task: [CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md).
Owner change и execution: [DICTIONARY_EXIT_EXECUTION_RU.md](DICTIONARY_EXIT_EXECUTION_RU.md).
146 новых tests passed, stdio smoke PASS; quality gate FAIL, remaining live rules OPEN.
P0 archival debt отдельный; P1 approval/freeze сохранён. Старый порядок P2→P3–P7
superseded: реализация уже затронула retrieval/admission/read/public consumers.
Исторические slices ниже не являются latest implementation status.

| Stage | D-IDs | Evidence / результат | Checks | Unresolved / следующий шаг |
|---|---|---|---|---|
| P0 | D01/D02/D06/D19/D33/D34 | Source caller map; 383-file hash manifest; small-inline и regex scan; D34 добавлена | Runner exit 0, 0 parse errors; compressed archive hashes проверяются отдельно | Все остальные candidates, dynamic/package paths, corpus/model hashes; далее D20/D25/D28 и D15/D34 inputs |
| P0 slice 2 | D20/D25/D28/D34 | Symbol decisions, policy producer→consumer map, diagnostic observations на неизменённом code | Probes exit 0; existing subset 81 passed (3.30s) | D25 оставшиеся frames/bridges, D30–D32, technical exceptions approval |
| P0 slice 3 | D25/D29/D30/D31/D32 | Inline patch-review dictionary, surface subject injection, exact registries, public→shard bridges | Public facade probes exit 0; existing subset 76 passed (1.03s) | Remaining frames/config/package audit; P1 decision ledger |
| P0 transition check | D25/D30/D33 | 157 frame symbols, 159 assertion inventory; 29 corpus hashes; editable provenance; templates reviewed | Published RU question-only reproduced 8/15 useful facts; isolated editable import exit 0 | Full classification, clean-wheel, per-stage/source baseline: P0 not DONE |
| P1 preparation only | TD01–TD06 / TM01–TM06 | Proposed acceptance, ledger и 64 bilingual cases до replacement | Draft generation exit 0; не release gate | P0 completion, independent holdout review и owner approvals: entry NOT READY |
| P0 wheel/frame baseline | D25/D30/D35–D37 | 157 frame audit decisions; real wheel imports; four same-call stage traces | Wheel patch-review import fails without eval; useful facts 8/15, 12/15, 11/15 | Audit classification не равна implementation; полный candidate ledger/call graph остаётся |
| P0 config/trace integrity | D33 | Five host styles; eight tool surfaces; static/generated resources; actual isolated SQLite generation/config/rows | 18 existing tests passed; 134 indexed source bytes per lane matched; 98 final citation checks passed | Full remaining candidate classification и default/fallback/bridge reachability; P0 ACTIVE |
| P0 candidate closure | D01–D38 / TECH-EXPORT / TECH-CASE | Unified 9874-node queue; 1440 classification decisions; actual nine class bridges/348 wrappers, eight parser entries | Product hashes pinned; bridge sync/restoration probes pass; connector subset 67 passed | 8434 REVIEW-REQUIRED; complete caller closure не доказан; P0 ACTIVE |

Отчёт: [P0_READ_PATH_AUDIT_RU.md](P0_READ_PATH_AUDIT_RU.md).
Slice 2: [P0_SYMBOL_POLICY_AUDIT_RU.md](P0_SYMBOL_POLICY_AUDIT_RU.md).
Slice 3: [P0_NEIGHBOR_BRIDGE_AUDIT_RU.md](P0_NEIGHBOR_BRIDGE_AUDIT_RU.md).
Переход: [P0_TO_P1_GATE_RU.md](P0_TO_P1_GATE_RU.md).
Подготовка P1: [P1_ACCEPTANCE_DRAFT_RU.md](P1_ACCEPTANCE_DRAFT_RU.md).
Config/index/citation audit: [P0_CONFIG_AND_TRACE_AUDIT_RU.md](P0_CONFIG_AND_TRACE_AUDIT_RU.md).
Candidate/bridge closure: [P0_CANDIDATE_CLOSURE_RU.md](P0_CANDIDATE_CLOSURE_RU.md).
Latest classification: [P0_STRUCTURAL_CLASSIFICATION_RU.md](P0_STRUCTURAL_CLASSIFICATION_RU.md)
— 1856 nodes classified; 2084 grouped units require review; P0 ACTIVE.
Последующий slice: [P0_COMPLETENESS_SOURCE_MAP_RU.md](P0_COMPLETENESS_SOURCE_MAP_RU.md),
[P0_RANKING_SNIPPETS_CLASSIFICATION_RU.md](P0_RANKING_SNIPPETS_CLASSIFICATION_RU.md)
— текущие 2313 classified nodes / 1954 grouped units REVIEW-REQUIRED; P0 ACTIVE.
**Superseding parallel result:** [P0_PARALLEL_RESULT_RU.md](P0_PARALLEL_RESULT_RU.md).
Remaining 1954/1954 units classified, local OPEN=0; attribution/selector maps
completed as source audit. P0 ACTIVE pending exact baseline execution provenance
and same-P0 required-control bundle linkage, not further raw-node classification.
В этом slice новый product/test diff отсутствует. Ранее существовавшее локальное
удаление trust trigger сохранено, не принято как готовое исправление.
Commit/push/merge не выполнялись. P1 контрактные изменения требуют отдельного согласования.
