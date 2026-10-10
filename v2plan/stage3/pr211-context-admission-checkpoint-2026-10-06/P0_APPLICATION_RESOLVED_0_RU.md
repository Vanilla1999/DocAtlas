# P0 application OPEN-0: индивидуальный разбор 83 строк

Дата: 2026-10-06. Только P0; production-код не изменён.

**Все 83 входные строки обработаны; 76 получили локальную классификацию,
7 честно остаются `OPEN`. Это не закрытие всего P0 и не разрешение реализации.**

Результат: `archives/p0-application-resolved-0.json`.
В каждой строке сохранены все исходные поля, кроме заменённых `decision` и
`reason`; добавлен `evidence`. Исходные `limitations` сохранены как исторический
mapping, а не выданы за результаты нового механистического разбора.

## Проверки

| Проверка | Результат |
|---|---:|
| Вход / выход / уникальные `(path, owner)` | 83 / 83 / 83 |
| Упорядоченные `(path, owner, source_sha256)` | точное равенство |
| SHA-256 source files | 53 / 53 совпали |
| SHA-256 полного текста owner | 83 / 83 совпали |
| Все исходные expressions сопоставлены с реальным AST | 496 / 496 |
| REMOVE | 16 |
| SPLIT | 23 |
| TECHNICAL-RETAIN-CANDIDATE | 37 |
| OPEN | 7 |

SHA-256 входа `archives/p0-application-open-0.json`:
`770d2b95f6582ee199a26dd7d124a5c15179ea53c5422a10f374ecb1ccbf57da`.

SHA-256 результата `archives/p0-application-resolved-0.json`:
`7ac3ea813e3a99899c6eddc888426b72974241b134b3aa4b48b7a922af755faa`.

Owner pin считается от полного диапазона source lines, соединённых `\n`,
с удалённым начальным whitespace (`lstrip`), как в исходном архиве. Все source
hashes повторно проверены перед записью. Production modules не импортировались;
тесты не запускались: это source audit, не regression acceptance.

Применимых `AGENTS.md` в репозитории и родительских `/`, `/tmp`, `/tmp/opencode`
не обнаружено. Найденный в другом соседнем worktree файл сюда не применим.

## Что именно доказано

`evidence.owner_source` содержит полный, неусечённый owner, диапазон и pins.
`evidence.input_expressions` сохраняет все 496 исходных выражений, проверку
точного текста по AST и excerpt реальных входных строк. `consumer_sites`
содержит source/hash/контекст исходных consumer references. Дополнительно
закреплены определения статически разрешённых dependencies и отдельные
показательные границы: normative regexes, component proofs, generated-asset
consumer, inspection URL grammar и rephrase templates.

Наличие pinned dependency **не означает** полного transitive semantic review.
Сохранены исходные `consumers`, `preserve`, `reachability` и limitations;
wildcard/facade/MRO/callback edges не повышены до доказанного runtime dispatch.
Пустой consumer array не объявлен доказательством dead code. Конкретные
дополнительные guards и остаточные ограничения сформулированы в каждом `reason`.

`REMOVE` означает замену ручного inference, не удаление защитных проверок.
`SPLIT` указывает две конкретные части owner: semantic inference/delegate
authority против identity/schema/citation/budget/transport guards.
`TECHNICAL-RETAIN-CANDIDATE` — локальное направление, не approval вызываемых
semantic producers, не право отвечать/редактировать.

## Выявленные REMOVE-механизмы

- `_extract_facts`: фиксированная normative/command классификация;
  `_validation_bucket`: перечни compiler/lint и default `tests`.
- `_owner_is_repo_grounded`, `_source_authority`: spelling occurrence и
  имя/путь как ownership/source-authority proof.
- `_fallback_constraints`: несourced verification prescriptions.
- `_is_generated_asset_path`, `ASSET_REGISTRY_FILENAMES`: filename-derived
  generated-asset inference; `_symbol_candidates`: task-to-symbol advice.
- `_coverage_categories_for_constraint`, `_has_manual_unknown_signal`:
  free-text coverage/manual triage dictionaries.
- `_task_symbol_tokens`: project-specific intent aliases;
  `PLACEHOLDER_CONTEXT_DOC_RE`: lexical document-quality exclusion.
- `dart_refresh_diagnostics`: отсутствие substring `pub.dev` как official flag;
  `_python_candidates`: metadata-label-derived confidence.
- `diagnose_proofability`: heuristic author-blame/remediation из missing/counts;
  `_need_obligations`: fixed requirement/exception/state obligation inference.

## Важные различения

- У `_compact_failure_packet`, `_compact_insufficient_support` и
  `_minimal_recovery_action` сохранены terminal insufficient/no-auto-execute
  guards. Error/template/status literals не объявлены semantic dictionaries.
- `GENERATED_ARTIFACT_SOURCE_PATTERNS` и `PATCH_REVIEW_ARTIFACT_NAMES` оставлены
  техническими кандидатами как конкретные producer-output contamination
  boundaries. Это не exemption всех path-based classifiers:
  `_excluded_source_reason` получил SPLIT за broad `oracle`/`hidden` inference.
- `flutter_docs_version_for` — locator channel protocol, не exact-version proof.
- `_selected_feature_trace` — post-selection advisory metrics, не selector proof.
- `ranked_blocks` — стандартный локальный BM25/структурные source offsets,
  не hand intent vocabulary и не entailment.
- `_already_rephrased` — recognizer собственного recovery output template,
  не semantic interpretation вопроса.
- У `component_coverage_decision`, `_annotate_budget_omissions`,
  `validate_model_visible_projection` semantic/unit-proof delegates отделены
  от coverage/schema/hash math, а не спрятаны техническим DTO exemption.
- Capability issuance, staging storage, SQLite job persistence и queue/deadline
  orchestration классифицированы по реально выполняемым техническим операциям;
  upstream source policy не считается автоматически закрытой.

## Семь конкретных OPEN-границ

Все пути ниже относительны к `docmancer/docs/application/`.

| Owner / файл | Что ещё не закрыто |
|---|---|
| `select_evidence`, `_evidence_selection_part03.py` | Eligibility/policy/optimizer/legacy witness closure до projected assignments и answer authorization. |
| `ingest_project_docs`, `_project_docs_service_part01.py` | Facade override, candidate authority/lifecycle metadata producer и `agent.ingest` publication. |
| `inspect_project_docs`, `_project_docs_service_part01.py` | Discovery/overview/preflight/structured-next-action authority до auto-sync/create proposals. |
| `sync_project_docs`, `_project_docs_service_part02.py` | Discovery/state/facade/incremental authority до удаления duplicate/orphan sources. |
| `qualified_fragments`, `context_variant_retention.py` | Requalify callback, required-block pruning, union/rank preservation всех witnesses. |
| `packet_alternatives`, `joint_context_selection.py` | Seed/finalizer/subset/finish chain и восстановленная quality/assignment binding. |
| `LibraryRefreshOps.refresh_docs`, `library_refresh_ops.py` | Runtime resolve/record ports и `refresh_record` publication/partial-generation authority. |

Следующий P0 проход должен закрыть именно эти transitive boundaries, не
заменять их blanket SPLIT/TECHNICAL и не переносить очередь в P1 под видом
полного семантического завершения.
