# Критическое ревью: Natural-language library retrieval

**Дата:** 2026-07-21
**Ветка:** `feat/natural-language-library-retrieval`
**План:** `.hermes/plans/2026-07-20-natural-language-library-retrieval.md`
**Вердикт:** **НЕ ГОТОВО К MERGE**

## 1. Краткий вывод

В worktree реализована значительная часть Phases 1–3.1: manifest-first GitHub ingestion, generation-aware publication/inspection, evidence requirements, support projection, raw-topic lexical dispatch, record filters и retrieval telemetry. Однако статус «Phase 2 done» в плане завышен, Phase 3.1 закрыта не по всем acceptance criteria, а Phase 3.2 пока не существует как воспроизводимый A/B harness.

Главные блокеры текущего worktree:

1. **RESOLVED in Task 2.2:** `UnifiedContextService` consumes the canonical immutable `SupportDecision` produced by `select_evidence`; nonempty context can no longer manufacture answer support;
2. failed/empty candidate refresh способен логически выключить либо опубликовать поверх предыдущего active корпуса, что нарушает rollback invariant;
3. publication и coverage проверяют агрегатные counts, а не точный manifest source set/provenance;
4. code-group policy жёстко кодирует Kotlin `async {` / `.await()`, нарушая non-Kotlin/generalization требования плана;
5. Phase 3.2 baseline оценивает frozen pre-ranked candidates, а не lexical/hybrid dispatcher lanes;
6. Phase 3.1 не реализует bounded index-witness probe, необходимый для честного `retrieval_miss`.

После первичного ревью stale diagnostic manifest и потеря support envelope **в projection path** исправлены минимальным TDD-циклом. Свежая проверка: `40 passed` для projection module и `152 passed` для затронутого набора. Это не закрывает production wiring/rollback/source-set blockers.

Первоначальный hybrid probe с `dense=0`, `sparse=0` не доказал поломку Qdrant или dispatcher. Probe обошёл production parent-child ingest и generation/collection lifecycle. После приведения probe к production contract filtered dense/sparse retrieval и hybrid dispatcher заработали.

## 2. Объём и состояние patch

На момент ревью:

- 26 tracked-файлов изменены;
- 7 путей/групп файлов были untracked до создания этого review-файла;
- изменения Phases 0–3.1 смешаны в одном незакоммиченном worktree;
- `git diff --check` проходит;
- исходный целевой pytest gate не проходил collection preflight; после review/fix diagnostic manifest синхронизирован, а целевой набор проходит (см. §9).

Это противоречит рекомендуемой в плане последовательности маленьких phase-scoped patches и сильно затрудняет review/rollback/bisect.

## 3. Сопоставление фаз с реализацией

| Фаза | Фактический вердикт | Комментарий |
|---|---|---|
| Phase 0 | Выполнена как characterization | Fixtures, RED/compatibility contracts и thin frozen adapter соответствуют цели этой фазы; они намеренно не доказывают качество реального dispatcher. |
| Phase 1.1 | В основном выполнена | Есть schema-v2 manifest, immutable commit resolution, exact blob set, content/blob verification, cancellation/deadline handling и fail-closed fetch. |
| Phase 1.2 | Не принята | Candidate generation есть, но rollback старого active корпуса и exact source-set validation нарушены. |
| Phase 1.3 | Не принята | Coverage рассчитывается по counts, а не identity path/blob set; inspection contract неполон. |
| Phase 2.1 | Выполнена для shared-requirements scope | Один immutable `EvidenceRequirementSet` владеет entities/facets, provenance, deterministic query spans, явными source/version/snapshot/project/module scope requirements и complete-contract hash. Comparison spans вычисляются из capture-group coordinates фактического raw-query regex match: canonical values удаляют optional backtick wrappers, но exact span сохраняет raw wrappers. Exhaustive regression требует один точный query slice у каждого query-derived requirement и покрывает повторённый ранее RHS и bare/backticked варианты всех трёх поддерживаемых comparison patterns. Query planner, dispatcher и library gateway сохраняют тот же instance; selector больше не пересобирает его без фактического policy enrichment. Fresh focused gate: `pytest -q tests/docs/test_evidence_selection.py tests/docs/test_agent_index_gateway.py tests/test_query_planning.py --tb=short` → `51 passed` (2026-07-22), including ordered-input determinism and non-Kotlin `create_task`/`gather` coverage. |
| Phase 2.2 | Принята для single-owner support scope | `select_evidence()` alone produces immutable `SupportDecision`; public unified/model-visible/MCP modes preserve its verdict, provenance, mandatory coverage, selected evidence IDs, reason and hash. Missing decisions and snippet-only fallbacks fail closed; `answer_available` aliases `answer_supported`. |
| Phase 2.3 | Не принята | Code-group policy остаётся hardcoded под Kotlin; presentation-only snippet constraints и их отдельная acceptance-проверка ещё не закрыты. |
| Phase 3.1 | Частично выполнена | Raw topic, lexical dispatcher, typed record filters и telemetry есть. Нет bounded index-witness probe и полного shared-requirements contract с query planning. |
| Phase 3.2 | Не выполнена | Нет checked-in variant runner, реального holdout A/B и multilingual lane. Default lexical корректно не изменён. |
| Phase 5 | Не начата | Canary/readiness contract не оценивался. |

## 4. Findings

### RESOLVED AFTER REVIEW — stale diagnostic manifest и projection envelope

Первичный targeted pytest был остановлен stale module-node hash для `tests/docs/test_model_visible_projection.py`. После детерминированной синхронизации hash новый test дал ожидаемый RED: `KeyError: 'decision_hash'`.

`_docs_support_decision()` теперь:

- сохраняет immutable support fields, если они уже пришли из upstream retrieval;
- иначе публикует `decision_hash = SelectionDecision.selection_hash`.

Exact-key public projection test обновлён на canonical envelope, не ослаблен до subset. Проверка после fix: projection module — `40 passed`; затронутый набор — `152 passed`.

### RESOLVED — BLOCKER-1: обычный публичный path потребляет canonical support decision

`LibraryDocsApplicationService` now calls `select_evidence()` once after guarded retrieval and stores the resulting frozen `SupportDecision` with the unchanged canonical `EvidenceRequirementSet`. `UnifiedContextService`, model-visible projection, MCP bounded/answer/compact output, and unsupported/error paths consume that decision instead of recomputing eligibility or coverage. `answer_available` is a compatibility alias of `answer_supported`; absent canonical decisions fail closed, and snippets cannot manufacture support. `DocsResult.schema_version` is `2.1-mvp`.

Verification (2026-07-22): focused plus directly affected selector/model/MCP/gateway/planner/diagnostic/baseline/unified/service/snippet/isolation/action-packet gate → `271 passed`; full offline suite with the known unrelated Phase 3.1 Riverpod retrieval node deselected → `2526 passed, 1 skipped, 1 deselected`. Novel comparison-only evidence produced `answer_supported=false`, `answer_available=false`, mandatory coverage `0.8`, and missing `result_access`.

### BLOCKER-2 — failed/empty candidate нарушает rollback старого active корпуса

При non-retryable indexing exception refresh перезаписывает registry status как `failed` (`library_refresh_ops.py:313-337`). `status_for()` немедленно возвращает `failed`, независимо от физически сохранённого старого индекса (`library_registry_ops.py:70-73`).

Для empty candidate `_commit_registry()` всё равно вызывает staging publication (`library_refresh_ops.py:404-429`), хотя инвариант плана требует сохранить предыдущий active generation при zero chunks/extraction/index/vector failure.

**Что требуется:** разделить candidate-attempt diagnostics от active registry state; publication разрешать только после exact corpus validation, не при aggregate non-zero/empty checks.

### BLOCKER-3 — publication и coverage не валидируют exact source set

Перед публикацией проверяются только `sections_indexed`, pages и chunks (`library_refresh_ops.py:372-414`), без exact equality approved manifest paths, per-document chunk existence, blob/content identity и orphan absence.

`manifest_coverage()` вычисляет coverage только по количеству pages: `min(pages, expected)`, `expected-pages`, `pages-expected` (`library_registry_ops.py:107-113`). Равные по размеру, но разные source sets ошибочно выглядят healthy.

**Что требуется:** сравнивать canonical manifest document identity (path + commit/blob/content hash) с indexed source identity до publication и в inspect health check.

### BLOCKER-4 — code-group policy hardcoded под Kotlin

**Код**

`docmancer/docs/application/model_visible_projection.py:206-224` всегда использует:

```text
witnesses = ["async {", ".await()"]
```

**Риск**

- Python case `create_task(...); value = await task` не может быть доказан этим механизмом;
- любые другие библиотеки требуют редактирования core projection;
- это прямо нарушает Non-goal плана: не hardcode Kotlin API names как universal fix;
- единственный test code-group находится в Kotlin fixture (`tests/test_library_natural_language_retrieval.py:210-215`), поэтому generalization не проверяется.

**Подтверждённая граница быстрого fix:** Python fixture содержит code block с `asyncio.create_task(...)` и `await task`, но текущий selector выбирает `task-cancellation.md`; projection-only contract-derived implementation поэтому честно вернула бы `satisfied=false`. Значит, code group должен быть частью eligibility/sufficiency `EvidenceRequirementSet`, а не только презентационным полем после selection.

**Что требуется**

Перенести code groups в canonical `EvidenceRequirementSet`/public requirement contract. Projection должна сериализовать решение selector, а не изобретать библиотечную policy.

### HIGH-1 — Phase 3.2 baseline не измеряет retrieval variants

`eval/library_retrieval_quality_baseline.py` загружает candidates с уже заданным `retrieval_rank` и вызывает projection/selection. Он не:

- строит record-specific SQLite/Qdrant index;
- вызывает `RetrievalDispatcher` в lexical/hybrid variants;
- сохраняет `mode_requested`/`mode_used` и lane failures;
- сравнивает реальные candidate sets/ranks;
- измеряет multilingual lane.

Поэтому текущие baseline-метрики нельзя использовать для решения «включать hybrid или нет».

Dataset содержит только 3 cases (development/holdout/adversarial по одному). Это недостаточно для заявленного Phase 3.2 grid: English explicit, conceptual paraphrase, launch-only control, unrelated API overlap, non-Kotlin case, Russian cross-language case и incomplete-corpus cases.

**Что требуется**

Checked-in provider-free runner с immutable dataset digests, отдельными record scopes, реальным dispatcher и variant identity. Multilingual variant должен быть отдельно промаркирован и запускаться только с задокументированной multilingual model.

### HIGH-2 — отсутствует bounded index-witness probe

План различает:

- `retrieval_miss`: witness существует в полном индексе, но retrieval его не выбрал;
- `required_evidence_missing`: witness в corpus/candidate bundle не доказан.

В текущем library path нет bounded exact-term/code-pattern probe и нет `index_witness` diagnostics. Поэтому причины недостаточности всё ещё нельзя классифицировать по заявленному контракту.

**Что требуется**

После miss запускать bounded deterministic probe только по mandatory requirements, с теми же library/version/snapshot filters. Публиковать bounded witness metadata без raw corpus leakage.

### HIGH-3 — Phase 1.3 inspection contract неполон относительно плана

`DocsInspectResult` (`docmancer/docs/models.py:269-299`) содержит:

- `manifest_expected/indexed/missing/stale_orphans`;
- active/attempt/complete manifest digests.

Но не содержит заявленные в плане:

- `manifest_fetched`;
- active generation identity;
- явные `requested_ref`, `resolved_commit_sha`, `complete`, `truncated` в inspection result.

Часть данных может жить в registry `target_spec`, но acceptance contract требует их на inspection/telemetry surface.

**Закрыто для текущего Phase 1.3 scope (2026-07-22).** `DocsInspectResult` теперь публикует `manifest_fetched`, active generation ID, `requested_ref`, `resolved_commit_sha`, `manifest_complete`, `manifest_truncated`, ingestion-policy version, active `docs_url_template` и bounded last-attempt diagnostics вместе с ранее добавленными digest/count fields. Parameterized rollback test проверяет no-chunk, source-set-mismatch и vector failure без изменения active identity; `pytest -q tests/test_docs_service.py -k 'manifest or inspect or status or generation' --tb=short` → `40 passed, 183 deselected`; shared manifest/fetch contracts → `66 passed`.

### RESOLVED AFTER REVIEW — shared `EvidenceRequirementSet` propagated to query planning

`EvidenceRequirementSet` is now the canonical immutable contract from `build_requirements()`. `retrieval/query_planning.py` accepts the same instance and projects its exact-term/entity requirements into bounded retrieval hints without reconstructing it; `RetrievalDispatcher`, `AgentIndexGateway`, and `select_evidence()` preserve identity and complete hash unless explicit policy enrichment is required. Comparison spans are bound to the actual raw-query regex capture groups, including repeated earlier terms and optional backtick wrappers, while canonical values stay normalized. The focused gate above covers deterministic ordering, non-Kotlin extraction, exhaustive exact query spans, scope requirements, planner identity/hash propagation, gateway identity propagation, and selector identity propagation.

### MEDIUM-1 — status table плана устарела и противоречива

План одновременно утверждает:

- Phase 2 `done` и сохранение immutable envelope;
- Phases 3,5 `not started` (`plan:20-27`).

Фактически Phase 2 имеет blockers, а Phase 3.1 уже реализована. Статусная таблица не является надёжным источником текущего состояния.

### MEDIUM-2 — Qdrant client/server version drift

Локально:

- Qdrant server: `1.14.1`;
- Python client: `1.18.0`.

Client предупреждает о несовместимости minor versions. Это нужно устранить или зафиксировать в reproducible environment до формального benchmark. Однако это **не причина** исходных нулевых vector lanes: прямой filtered search и hybrid retrieval работают после исправления probe lifecycle.

### MEDIUM-3 — тесты чрезмерно fixture-driven

`RecordScopedGateway` в `tests/test_library_natural_language_retrieval.py:49-79` возвращает corpus documents в fixture order и не выполняет lexical ranking. Поэтому тесты хорошо проверяют support semantics на заранее заданном candidate bundle, но не доказывают natural-language retrieval quality. Название suite создаёт более сильное впечатление, чем реально проверяемый контракт.

## 5. Почему первоначальный hybrid test «не работал»

### Наблюдение

Первый probe показывал:

```text
collection_count=4
sync upserted=4
dense=0
sparse=0
failures={}
```

Это выглядело как проблема Qdrant/dispatcher, но прямой probe уточнил картину:

```text
dense_unfiltered=5
dense_filtered=0
sparse_unfiltered=4
sparse_filtered=0
Qdrant payload library_id отсутствует
```

### Корневая причина

Probe напрямую вызвал `SQLiteStore.add_documents()` и создал legacy sections. Он не прошёл production `DocmancerAgent.ingest_documents()` lifecycle, который для Markdown включает:

```text
format=markdown
chunking_schema=parent-child-v1
```

(`docmancer/agent.py:86-103`).

Typed fields (`library_id`, `resolved_version`, `docs_snapshot_exact`) сохраняются в parent-child retrieval generation и попадают в payload через `SQLiteStore.list_sections_for_embedding()` (`sqlite_store.py:3066-3148`). Legacy embedding rows не несут этот typed payload. Поэтому dispatcher filter:

```text
{"library_id": "phase32-fixture"}
```

правильно отбрасывал все vector hits.

Вторая ошибка probe: произвольная Qdrant collection не была связана с candidate SQLite generation. Readiness guard корректно отклонил её сообщением `collection identity does not match the active SQLite generation`.

### Контрольный повтор

После приведения probe к production lifecycle:

1. `format=markdown`, `chunking_schema=parent-child-v1`;
2. `activate_generation=False`;
3. `set_generation_vector_collection(generation_id, collection)`;
4. vector sync для того же `generation_id`;
5. activation generation после sync;

получено:

```text
collection_count=4
dense_filtered=4
sparse_filtered=4
payload library_id=phase32-fixture
hybrid candidate_counts:
  dense=4
  sparse=4
  lexical=2 или 4
failures={}
```

Итого: hybrid engine в этом probe работает. Не работал **тестовый setup**, потому что он обошёл обязательные ingest и generation identity contracts. Warning Qdrant client/server не был root cause.

## 6. Что сделано хорошо

1. Raw user topic доходит до record-scoped dispatcher без library-name prefix.
2. Default library retrieval остаётся lexical; hybrid не включён молча.
3. Typed filters ограничивают `library_id`, non-empty `resolved_version` и exact snapshot; post-guard сохранён как defense in depth.
4. Retrieval diagnostics включают requested/used mode, query hash, candidate counts, failures, component ranks и post-guard counts без публикации raw topic.
5. Manifest-first path fail-closed проверяет immutable commit/blob/content identity.
6. Candidate generation/collection readiness guard поймал некорректный probe вместо silent cross-generation retrieval.
7. Frozen dataset digests и source/version contamination checks — правильная основа, хотя runner пока не измеряет retrieval variants.

## 7. Рекомендуемый порядок исправлений

1. Встроить canonical support-decision producer в `UnifiedContextService`; projection fix уже зелёный, но один producer отсутствует.
2. Защитить active registry/index от failed и empty candidate; добавлять candidate-attempt diagnostics без publication/status downgrade текущего корпуса.
3. Ввести exact manifest source-set validation перед publication и identity-based coverage health.
4. Перенести code groups в canonical `EvidenceRequirementSet`, чтобы selector требовал один source/version/code block до projection.
5. Добавить bounded index-witness probe и `retrieval_miss` diagnostics.
6. Довести inspection contract Phase 1.3 до полей плана либо явно скорректировать plan/acceptance.
7. Создать checked-in Phase 3.2 dispatcher A/B runner с record-separated corpora; затем расширить dataset всеми объявленными cells и отдельно измерить multilingual model.
8. Зафиксировать совместимые Qdrant server/client версии, разделить worktree на phase-scoped commits и обновить status table плана по факту.

## 8. Итоговый verdict

- **Phase 1:** не принята: rollback и exact source-set publication должны быть исправлены до acceptance.
- **Phase 2:** projection envelope fix зелёный, но Phase 2 не принята без production producer и requirement-derived code groups.
- **Phase 3.1:** полезная интеграция выполнена, но acceptance неполон без shared requirements/index witness.
- **Phase 3.2:** не реализована как benchmark; exploratory probe доказал работоспособность hybrid engine, но не quality uplift.
- **Merge:** **BLOCKED** до устранения production BLOCKER-1..4 и повторной верификации.

## 9. Verification after review/fix

Phase 2.2 correction повторно проверен обязательным affected gate:

```text
pytest -q tests/docs/test_evidence_selection.py tests/docs/test_docs_service_characterization.py tests/docs/test_model_visible_projection.py tests/test_docs_service.py tests/test_snippet_presentation.py tests/test_source_isolation_regression.py tests/test_unified_docs_context.py tests/test_unified_docs_context_mcp.py tests/test_diagnostic_labels.py --tb=short
```

Результат: `459 passed in 57.36s`; `git diff --check` завершился без ошибок. Отдельные provider-free probes подтвердили: canonical scoped IDs без collisions, единый selector/source/answer evidence-ID namespace, byte-identical `SupportDecision` envelope при normal/tiny budgets и невозможность snippet/presentation слоя повысить canonical abstention до supported.

Полный диагностический `pytest -q --tb=short` не объявляется зелёным: `2521 passed, 1 skipped, 9 failed`. Из них пять относятся к untracked Phase 3.1 тестам со старым ожиданием коротких alias IDs или model-visible `rejected_candidates`, три — к frozen evaluation/baseline gates вне Phase 2.2, один — к ранее известному isolated Riverpod retrieval miss. Это явно сохранённый residual rollout scope; closure `BLOCKER-1` основан на обязательном Phase 2.2 gate и semantic probes, а не на ложном утверждении о полном suite pass.
