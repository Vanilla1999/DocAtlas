# PR #211: ownership завершающей волны

База: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Рабочая ветка: `implementation/pr211-merge-readiness`.

| Writer | Область |
| --- | --- |
| Координатор | Registration/unified вызов, scope test successors, docs-output fidelity test; интеграция и итоговый checkpoint |
| Trust reviewer/implementer | Trust-resource test в `tests/test_dictionary_exit_delivered_surfaces.py`, companion `tests/docs/test_trust_contract.py`, обоснование trust migration |
| Schema implementer | После review первого slice: compact advertised schema и её equivalence controls; без повышения byte ceilings |
| Acceptance reviewer | Сначала read-only CI/runtime audit; дополнительные harness paths назначаются отдельно |

Общий diagnostic manifest меняет только координатор. Существующие concrete node
names сохраняются. Upstream retrieval, gold, thresholds и required gates не меняются.
Новые dependency/model downloads, provider calls и реальные пользовательские
индексы не входят в локальные проверки. Разрешённый runtime — fixture-only
Git/server descendants, без изменения permissions или обходов guard controls.

Изменения рассматриваются узкими slices. Обычный push в существующий PR разрешён
решениями текущей волны; force-push, merge и release не выполняются.

## Critical slice от 2026-10-09

База: `7a78c516a62304fc258bda5d5eb2b11544c829b5`.
Изолированная рабочая ветка: `implementation/pr211-critical-contract-20261009`.
Продолжение реализует `PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md` после указания
владельца продолжить; уточнение текущего literal-coverage контракта записано в
`CURRENT_WAVE_DECISIONS_RU.md`.

| Writer | Единственная область записи |
| --- | --- |
| normative_tests | `tests/docs/test_normative_language.py`, `PR211_CRITICAL_TEST_MIGRATION_REVIEW_RU.md` |
| critical_mutants | `scripts/run_critical_mutation_gate.py`, `PR211_CRITICAL_MUTATION_MIGRATION_REVIEW_RU.md` |
| critical_review | Только `PR211_CRITICAL_MIGRATION_INDEPENDENT_REVIEW_RU.md`; исходники авторов читает |
| Координатор | Current decisions, этот ledger, checkpoint, совместный source/artifact audit и публикация |

Новые concrete test nodes не планируются: исходные 26 tuples и остальные tests
normative module сохраняются. Локальная работа ограничена source/AST и чтением
GitHub artifacts; actual project execution выполняет существующий PR CI.
Production, deferred retrieval, остальные gold/gates и пользовательский checkout
не входят в изменяемые пути slice.
