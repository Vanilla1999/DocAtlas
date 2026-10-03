# M2 model-free: execution manifest

## Пункт 5 — isolated unified read 2026-10-03

Один research read decision без вызова proof qualification и без новой grammar/
fallback. Existing locality и applicability сохранены. На native captured inventory:
80 cases, 429 candidates, native-read → unified-read: 18 → 18 packets,
11 → 11 supported, 80/80 identical payloads. Никакого claim recovery.
115 focused tests passed. Это parity isolated read boundary, **не** parity полного
native pipeline (historical 49 supported). Runtime consumers не мигрировали.
[Контракт](UNIFIED_READ_CONTRACT_RU.md), [результат](UNIFIED_READ_RESULT_RU.md).
Правило против переусложнения закреплено в `v2plan/AGENTS.md`. Replacement остаётся
закрытым; новые exceptions по итогам trial не добавляются.

## Admission direction review 2026-10-03 — анализ

Сверены Kotlin historical library smoke, project candidate losses и первичные
retrieval/RAG исследования. Candidate сохраняет 13/49 baseline claims; остальные
2 из его 15 supported — дополнительные. Восемь unanswerable cases используют
один шаблон. Рекомендовано упрощать владение read decision, а не расширять grammar;
готовый общий relevance predicate пока не установлен.
[ADMISSION_DIRECTION_REVIEW_RU.md](ADMISSION_DIRECTION_REVIEW_RU.md).
Runtime, tests, frozen annotations и production route не изменены; новый replay
в этом анализе не выполнялся.

## Typed constraint research compiler 2026-10-03

Single-frame constraints теперь проверены отдельным research compiler из typed
condition slots. Compositional/unknown contracts сохранены. Один paired owner/1500
replay: 80 cases, packets 18 → 19, supported required claims 15 → 15,
baseline losses 36 без восстановления. 87 selected tests passed.
[TYPED_CONSTRAINT_COMPILER_RESULT_RU.md](TYPED_CONSTRAINT_COMPILER_RESULT_RU.md).
Runtime не изменён; compiler сохранён как isolated result, не production approval.

## Temporal/condition diagnostic 2026-10-03

17 synthetic question/body pairs и 13 frozen constraint-bearing cases проверены.
Fully parsed temporal frame имеет empty condition slots, но keyword fallback
compiler добавляет whole-query constraint. Root cause описан в
[TEMPORAL_CONDITION_REVIEW_RU.md](TEMPORAL_CONDITION_REVIEW_RU.md).
32 selected tests passed. Runtime/veto не изменены; recovery claims не заявлен.

## Corrected adapter replay 2026-10-03

Один isolated owner replay при 1500 после исправления case handling и разделения
literal/verified-subject checks: 80 cases, 18 packets, 15 supported required claims.
Ни одна из 36 historical baseline потерь не восстановлена: 32 admission, 4 discovery
pool. Conditions/topic native veto не сняты, 01–04/runtime не изменены.
Отчёт: [CORRECTED_OWNER_1500_RESULT_RU.md](CORRECTED_OWNER_1500_RESULT_RU.md).

## Решение 2026-10-03 — replacement остановлен, 01–04 сохранены

По решению пользователя текущая Gate A/replacement-связка не продолжается как
production design. API 01–04 остаются изолированными; public route не переключён.
Budget probe и read-only loss attribution сохранены в
`GROUNDED_BUDGET_RESULT_RU.md` и `GROUNDED_LOSS_ATTRIBUTION_RU.md`.
При strict owner 1500/3000: 36 потерь baseline claims, из них 32 admission и
4 per-source hydration cap; final DTO budget не объясняет эти 36 потерь.
Повторные controls 01–04: 29 passed; вместе с 9 research tests: 38 passed.
Это не общий safety/semantic Green и не разрешение на шаги 05–09/rollout.

## Шаг 00 — baseline и active callers

Статус: **baseline зафиксирован; controls RED; gates R/A открыты**.
Это не acceptance реализации и не разрешение на rollout.

### Baseline / ownership

- Согласованный snapshot текущего состояния: `30056be881cf99f085e6ff9a839c4e12f0c4ae28`.
- Пользователь явно разрешил коммит текущего состояния. Четыре production drafts
  сохранены без исправлений; их наличие в коммите не подтверждает корректность.
- До выполнения controls working tree чистый. Diff SHA256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- SHA256 manifest всех tracked file bytes:
  `c5c59ab88af7dbde13dfa39cde169f5adf004284bf77fb15bbee7dc35e53cd65`.
  Это snapshot checkout, **не** frozen evaluation corpus и не hash generated index.
- Артефакты: `/tmp/opencode/m2-model-free-execution-30056be8/`:
  `baseline.json`, `tracked-source-manifest.json`, `controls.log`, `inventory.log`.
- Interpreter: `/usr/bin/python3.12`, Python 3.12.3, pytest 9.1.1.
  Import: `/tmp/opencode/docatlas-multilingual/docmancer/__init__.py`.
  Системный `python3` — 3.14.3, вне project range; для проверок не используется.

### Проверки

```bash
/usr/bin/python3.12 -m pytest -q tests/test_structured_chunking.py tests/test_parent_child_index.py tests/test_pre_hydration_source_policy.py tests/docs/test_evidence_qualification.py tests/docs/test_context_constraint_roles.py tests/docs/test_read_context_admission_boundary.py tests/docs/test_shared_context_proposals.py tests/docs/test_source_bound_subject_context.py
```

Результат: **141 passed, 1 failed**, exit 1. Collect-only того же inventory: exit 0.
Environment warning: неизвестная настройка `asyncio_mode` (plugin в этом
interpreter отсутствует); выбранные tests выполнились, это не причина failure.
Полный regression и installed-wheel проверки не запускались.

Failing node:

```text
tests/docs/test_shared_context_proposals.py::test_precedence_proposals_do_not_rescue_echo_or_heading[page title wins when navigation configuration and Markdown content define different titles.]
```

Assertion требует отсутствия `preferred_context_variants`; текущий draft
создаёт proposal. Этот тест проверяет proposal boundary, поэтому **из него
нельзя отдельно заключить**, что public packet или permission уже нарушены.
Draft `need_context_projection.py:177` вызывает locality с `require_pair=False`
и `sentence_pattern=relation`; `read_context_admission.py:94–124` реализует эту
shape-dependent ветку. Тест/ожидание не изменялись. Исправление draft не смешано
с source-guard extraction. До Gate A нужна проверка единого public negative
контракта без такого исключения.

### Active-callers migration map (текущий project read маршрут)

| Граница | Текущие обязанности | При миграции |
|---|---|---|
| `docs/interfaces/mcp/context_tools.py` | Request dispatch, projector, final `validate_model_visible_projection` (стр. 467), diagnostics, public return | Сохранить schema, budgets, final binding validation и permission separation |
| `_project_context_service_part01.py:80–143` | Plan/schedule, project retrieval, explicit path filter, `iter_prefit_context_variants`, `rerank_project_doc_chunks`, routing budget | Заменить read prefit/rerank; сохранить request/scope/path/lifecycle/budget duties |
| `_project_docs_service_part03.py` | Project preflight/query, lookup qualification, candidate admission diagnostics | Source readiness/version/scope и confirmation сохраняются; qualification не использовать как общий read veto |
| `retrieval/_dispatch_part01.py` и `_dispatch_part02.py` | Store retrieval, intent/body order, supplement, diversity/caps, hydration | Один targeted lexical BM25 order; сохранить pre-hydration filtering и resource bounds, не менять other modes |
| `core/_sqlite_store_part03.py` | FTS query/order и выдача source chunks | Passage API с native BM25; exact snapshots/generation/filtering остаются обязательными |
| `domain/project_doc_ranking.py:624` | Project rerank, qualification, novelty/selection | Retire targeted competing relevance order/veto, не удалять shared source taxonomy |
| `read_context_admission.py:26–91` | Snapshot digest/span/root binding, qualification reason checks, exact/subject/conditions, locality | Source eligibility отделить от read policy; hard applicability и rechecks сохранить |
| `need_context_projection.py` | Typed/precedence proposals, dispositions, DTO prefit | Перенести structural/applicability обязанности; shape-dependent approval не сохранять как отдельный relevance путь |
| `_docs_context_projection_core.py` | Candidate packing, proof/coverage bookkeeping, fallback (стр. 665), recursive projection | Один approved window inventory/selector; proof не выводить из read context |
| `docs_context_projection.py:210–289` | Core, quality finalization, read-next preparation, continuation locators; затем три selectors | Сохранить recovery/URI duties, заменить competing final read selection |
| `joint_context_selection.py` | Structural alternatives, budget и validation | Перенести intact structure/revalidation, retire самостоятельный read order |
| `query_block_context.py` | Дополнительный window selection и validation | Перенести нужные window checks, retire самостоятельный selector |
| `query_block_recovery.py` | Recovery через уже registered resource, сохранение query/citations/proof | Не потерять registered-resource duty при retirement read selection |

Карта получена по статическим callers. Это не runtime invocation trace всех
`project/module/all` и change/library routes; такой trace обязателен до шага 07.
Source reads/publication запрещено переносить в pure alternatives enumeration.

### Ранний Gate A: установленные ограничения, не готовый predicate

1. Current negative уже конфликтует с shape-dependent relation preference.
2. BM25 order не решает echo/heading/subject/condition abstention сам по себе.
3. Source safety, applicability, read relevance и proof нужны как разные решения.
4. Ни отказ qualification по lexical ratio, ни высокий retrieval score не должны
   автоматически давать/запрещать read window.
5. Gate A остаётся открытым: нет принятого общего predicate и packing objective.
   Не добавлены regex, aliases, score thresholds или новые модели.

### Сдача шага

- Runtime changes: **нет**; changed file — этот manifest.
- Red: указан failing node и полный log. Green: не заявлен; baseline не исправлялся.
- Guards/queries/budgets: runtime bytes неизменны относительно snapshot.
- Следующий этап: шаг 01 source eligibility extraction; Gate R до шага 02,
  Gate A до шага 05. Шаг 01 пока **не начат**.
- M2, independent held-out/reader evaluation и rollout остаются открытыми.

## Шаг 01 — source eligibility extraction

Статус: **focused Green; baseline control остаётся RED**. Новый маршрут поиска
не подключён; qualification/applicability/read relevance не ослаблены.

- Новый `domain/source_window_eligibility.py`: `EligibilityDecision` содержит
  eligibility/reason/exact span, без qualified IDs, coverage или permissions.
- `prepare_source_probe` переиспользует существующие metadata/catalog policy и
  `prepare_reference_probe`. Qualification вызывает тот же helper в прежнем
  порядке; её lexical, exact, subject, condition и proof logic не менялась.
- Строгий window API дополнительно проверяет original request, raw digest и
  буквальные source offsets. `char_span` — контракт proposed window; legacy
  `char_start/end` нормализуются только в локальной копии для reference checker.
  Prepared evidence envelope по-прежнему ограничивает окно. Поиск первого
  совпадения во всём документе не используется.
- Новый behavioral inventory зарегистрирован отдельным hash-bound shard.

### Red → Green

Команда нового модуля:

```bash
/usr/bin/python3.12 -m pytest -q tests/docs/test_source_window_eligibility.py
```

`step01-red.log`: stub отверг safe window; 2 behavioral failures, 11 passed.
После implementation добавлены negative mutations и повторяющийся source text;
`step01-green.log`: **15 passed**, exit 0.

Проверяются: lexical refusal при safe source, forged approval, project/repository,
freshness/index/lifecycle/risk, version/generation/path, source/request mutation,
Unicode char-vs-byte mismatch и второй occurrence повторяющегося paragraph.

Повтор исходных восьми control modules + нового модуля:
`step01-final-controls.log`: **156 passed, 1 failed**, exit 1.
Единственный failure — ровно baseline precedence negative, указанный в шаге 00.
Изменения tests/expected negative или drafts отсутствуют. Это focused non-regression,
не доказательство полного output parity или завершённого source security review.

### Ограничения / следующий gate

Scope/version checks здесь наследуют prepared reference scope; pure API не
читает filesystem и не устанавливает актуальность snapshot независимо от caller.
Hard subject/condition checks остаются в существующем qualification/admission.
Не считать `eligible=True` разрешением read или support.

Changed files: `evidence_qualification.py`, новый source helper, новый test module,
diagnostic shard и этот manifest. Queries, DTO budgets, index defaults и permissions
не менялись. Шаг 02 не начат: прежде требуется approved Gate R с численными
resource limits. Gate A также остаётся открытым.

## Подготовка Gate R

Проверены текущие chunk/candidate/store/window resource параметры.
Составлен [численный профиль](GATE_R_PROPOSAL_RU.md) с происхождением единиц,
strict byte accounting и unresolved raw-snapshot costs. Статус PROPOSED;
согласование не выведено из просьбы «продолжи».

Важные находки: старый store budget допускает oversized first hit; passage text
budget нельзя выдавать за total hydration budget. Модули context windows/blocks
находятся в domain, не application. Runtime/test expectations не менялись.
Шаг 02 не начат до решения Gate R. Не запускались новые benchmarks.

## Шаг 02 — contextual passage builder

Gate R принят пользователем для isolated implementation. Новый pure builder:
`docmancer/core/retrieval_passages.py`. Это не изменение defaults/index schema.

- Default target/hard 512 byte-estimate units, 2048 UTF-8 bytes, zero overlap.
- Grouping contiguous intact atoms внутри existing heading-scoped parent.
  Не пересекает source/snapshot/owner; caller обязан передать scoped source identity.
- Full stable identity связывает profile/source/snapshot/content hash/exact offsets.
  Все text/char/byte/line spans — исходные slices, без annotations или summaries.
- Oversized atom deferred целиком; passages не склеиваются через deferred hole.
  Introduced list, pipe table и fenced code используют existing atom boundaries.
- Atom overflow возвращается явно. Existing parser сначала materializes atoms:
  max_atoms здесь ограничивает дальнейшую обработку, **не** доказывает bounded
  parser allocation. Total file/parser resource guards остаются обязанностью ingest.
- Ни display children, ни vector inputs, ни их config/IDs не изменены.

Tests: `tests/test_retrieval_passages.py`, behavioral hash-bound inventory shard.
Stub Red записан в `step02-red.log`; Green/controls:

```bash
/usr/bin/python3.12 -m pytest -q tests/test_retrieval_passages.py tests/test_structured_chunking.py tests/test_contextual_indexing.py tests/test_parent_child_vectors.py
```

`step02-green-controls.log`: **29 passed**, exit 0 (existing asyncio_mode warning).
Проверены adjacent topic/rule, owner separation, source/snapshot/profile identity,
Unicode/repeated offsets, children parity, oversized/deferred и work cap.
Small repeat test использует 6 estimate units: atom занимает 21 UTF-8 bytes;
первоначальные 5 не позволяли intact atom и исправлены до Green, не по benchmark.

Passage не объявляется semantic-complete, relevant или supported. Heading-only
passage допустим как search representation, не как admitted read window.
Setext/нестандартные Markdown structures наследуют ограничения existing parser;
нужен downstream structural validation, не расширение source authority.

Шаг 03 не начат: далее atomic passage generation/index lifecycle tests.
Gate A и полный regression/held-out/rollout остаются открытыми.

## Шаг 03 — opt-in atomic passage index

Статус: **focused Green**, не production activation и не новый search route.

- `SQLiteStore(..., passage_profile=PassageProfile())` явно включает representation.
  Без profile обычный storage/retrieval не строит passage records.
- Новый `_sqlite_store_passages.py`: generation-owned records, external-content
  FTS5, profile/count/deferred manifest и диагностический inventory API.
  DDL выполняется при explicit store initialization, **не** через executescript
  внутри generation transaction (что могло бы неявно commit).
- Generation build вставляет passage records/FTS после generation sources и
  до existing validation/activation. Metadata берётся из этой же generation.
  Unchanged copied sources переиндексируются в новый snapshot; child/vector IDs
  и retrieval_config_hash не изменяются. Passage IDs меняются со snapshot,
  source_content_hash при metadata-only change остаётся прежним.
- SQL row-count parity и FTS5 external-content integrity-check выполнены до
  passage manifest; исключение откатывает весь candidate transaction.
- Source prune clone также строит representation перед activation. Старые rows
  могут оставаться в superseded generations по existing history policy, но
  active inventory/FTS join их не возвращает.
- `passage_index_status` проверяет active status и exact profile identity.
  Missing/incompatible profile → `preparation_required`; чтение ничего не
  rebuild-ит, legacy fallback отсутствует. Index preparation readiness здесь
  отдельная от child/vector config, ещё не подключена к public project preflight.

### TDD и controls

Новый `tests/test_retrieval_passage_index.py` зарегистрирован behavioral shard.
Stub Red: `step03-red.log`. Дополнительный prune Red:
`step03-prune-red.log` — source deletion сначала теряла passage readiness;
hook clone generation исправлен, ожидание не ослаблено.

```bash
/usr/bin/python3.12 -m pytest -q tests/test_retrieval_passage_index.py tests/test_retrieval_passages.py tests/test_parent_child_index.py tests/test_clear_rebuild_lifecycle.py tests/test_pre_hydration_source_policy.py tests/test_index_storage_cleanup.py tests/test_contextual_indexing.py tests/test_parent_child_vectors.py
```

`step03-green-controls.log`: **60 passed**, exit 0, existing asyncio_mode warning.
Проверены inactive build/activation и active FTS join, rollback **после** passage
insertion с сохранением extracted artifacts, metadata-only promotion, edit,
recreate/prune, profile mismatch и идентичный text разных project sources.

### Ограничения

`list_active_passages` — полный diagnostic inventory, не bounded query API;
его нельзя использовать как production retrieval или считать соблюдением
9600-byte request cap. Полный snapshot build является ingest work, не request
hydration. Existing source identity и scope metadata сохраняются; ещё требуется
pre-hydration filtering в шаге 04 и public binding checks в последующих шагах.
Atomic lifecycle tests не заменяют independently reviewed guard/security gate.

Changed runtime files: `sqlite_store.py`, `_sqlite_store_part01.py`,
`_sqlite_store_part02.py`, `_sqlite_store_part03.py`, новый passage shard.
Пользовательские индексы, defaults, budgets и permissions не изменялись.
Шаг 04 не начат: далее bounded passage query API с одним native BM25 order.
Gate A, baseline precedence failure, полный regression и rollout остаются открытыми.

## Шаг 04 — bounded native BM25 API

Статус: **новый API focused Green; 2 baseline vector controls RED**.
Public project-read pipeline не переключён. Это candidate retrieval, не proof
или финальное delivery. Route — current project docs, не historical/library.

### Реализация

- `_sqlite_store_passages.py::query_passages`: literal quoted FTS tokens исходного
  question, один OR MATCH expression, без aliases/rewrites/translation. Original
  question сохранён; explicit lookup может вызывать этот API отдельно, но его
  score нельзя суммировать с другими queries. Multi-query orchestration здесь
  не реализована и не заявлена принятой.
- Только active generation с exact accepted profile. Обязателен concrete project
  identity. Existing metadata filter compiler принимает scope/version/module/path
  constraints caller; source/source_identity берутся из generation source,
  не подделываемых alias fields. Глобальный/unscoped search не допускается.
- SQL pre-LIMIT predicate вызывает существующий source metadata rejection helper
  через pure SQLite UDF. Current lifecycle/freshness/index/risk/project guards
  сохраняются; instruction risk и source_class также проверяются. Не копируется
  новый ослабленный набор source policy. Invalid JSON fail closed с ошибкой.
- Порядок: native `bm25(retrieval_passages_fts)` ascending, затем full stable ID.
  Никаких synthetic scores, intent/body/parent boosts или legacy fallback.
- SQL сначала возвращает ID/cost/text-byte-size, без passage text в Python.
  Oversized individual passage исключается до top-k; payload hydration только
  после aggregate budget и per-source caps. Aggregate ≤2400 byte-estimate units
  и ≤9600 text bytes; smaller caller budget не повышается, first-hit exception нет.
- Candidate cap ≤20/default 12, per-source cap ≤2. Cap exclusions сохраняются
  в trace; они не semantic abstention. Вторая hydration не меняет BM25 порядок.
- Trace отдельно содержит hydrated passage bytes и serialized payload bytes.
  Metadata/payload overhead не назван бесплатно покрытым text budget. SQL/FTS
  внутренне читает индекс/строки; отсутствие Python hydration не означает нулевого
  SQLite I/O или bounded RSS. Raw source documents query API не загружает.
- `_dispatch_part01.py::run_project_passages`: отдельный opt-in entry point,
  учитывает меньшие configured limit/budget. Public route и other modes прежние.

### Red → Green / non-regression

`step04-red.log`: stub даёт behavioral failures, не import/collection failure.
`step04-green.log`: новый модуль **4 passed**, exit 0.
Tests зарегистрированы behavioral shard. Независимый SQL BM25 oracle, reversed
FTS insertion order в том же snapshot, no proof/score fields, pre-top-k project/risk/
freshness/scope/version/module/path filtering, invalid metadata, Unicode/quotes,
empty query, tiny budget, candidate/per-source caps и forbidden legacy calls.

Frozen `mkdocs-05`: original case/source manifest загружены с existing hash
validation; полный MkDocs corpus индексируется native passage builder. Witness
использован только в assertion после retrieval; rule присутствует в bounded
pool при обычном API budget. Это **не** public DTO delivery и не general gain.

Controls command:

```bash
/usr/bin/python3.12 -m pytest -q tests/test_lexical_passage_retrieval.py tests/test_retrieval_passage_index.py tests/test_pre_hydration_source_policy.py tests/test_sqlite_ranking_truth.py tests/test_retrieval_diversity_policy.py tests/test_public_vector_retrieval.py tests/test_vector_fallback.py
```

`step04-green-controls.log`: **37 passed, 2 failed**, exit 1.
Отдельный detached baseline worktree `/tmp/opencode/m2-step04-baseline`, snapshot
`30056be8`: те же пять legacy control modules без новых API tests — **29 passed,
2 failed** (`step04-baseline-controls.log`). Новых failing node IDs нет:

```text
tests/test_public_vector_retrieval.py::test_public_project_docs_query_consumes_dense_vector_index
tests/test_public_vector_retrieval.py::test_public_library_query_consumes_dense_vector_index
```

Оба baseline/candidate failures: `vector_store_unavailable`, при required dense
mode. Зависимости не добавлялись, tests/expectations не ослаблены. Это limitation
этого environment, не разрешение считать vector controls PASS.

Changed: passage shard, dispatcher entry point, new tests/inventory и manifest.
Index/user defaults, question/source gold, DTO budget и permissions неизменны.
Шаг 05 **BLOCKED до Gate A**: нужен общий relevance/abstention decision table
и packing objective; source eligibility + BM25 не достаточно для read admission.
Baseline precedence failure, full regression, independent review и rollout открыты.

## Gate A review перед шагом 05

Составлены [единая decision table и window interface](GATE_A_REVIEW_RU.md).
Existing predicate диагностирован на MkDocs rule, precedence echo, reordered
negative и known partial positive; результаты сохранены вне checkout.

Pair required отвергает MkDocs rule; без pair проходят reordered negative и
precedence echo. Ни одна из этих двух настроек не является готовым общим contract.
Обнаружена precedence-specific condition ветка existing `_applicable_context`;
она требует отдельного guard/applicability review, не silent removal.

Runtime/test expectations/budgets не менялись. Шаг 05 не начат: discriminator
и packing objective не определены, Gate A **BLOCKED**, не approved. Документация
честно отделяет решённые source/index/retrieval обязанности от нерешённой read
semantics. Это не benchmark gain и не финальная приёмка.

## Разработка кандидата Gate A

По запросу пользователя разработаны [predicate и packing objective](GATE_A_CANDIDATE_RU.md),
review-only `gate_a_candidate.py` и behavioral tests. Production не импортирует
prototype; правила read admission пока не менялись.

Общий механизм: prose soft-wrap normalization + прежний local topic floor/pair
+ общий content-term echo refusal. Shape-specific sentence_pattern/require_pair
не используются. Native MkDocs passage имеет topic witness без relation exception,
но isolated paraphrase rule остаётся unknown — нельзя наследовать approval после
clipping. Это conservative topical witness, не universal semantic discriminator.

Packing: native rank representation vector, затем exact source coverage vector,
затем whole-DTO cost и stable ties. Никаких BM25 sums или нового lexical utility.
Prototype реализует comparison objective, **не** bounded production selector.

Prototype tests: 11 passed. Вместе с unchanged native read controls: 67 passed,
1 baseline precedence failure. Логи: `gate-a-candidate-tests.log`,
`gate-a-candidate-controls.log`. Полный regression/paired/held-out не выполнялся.

Gate A PROPOSED, не approved: ещё нужны independently checked fact-witness
adapter, code/table/list controls, opposite-relation semantics и solver work bound.
Новое отдельное semantic-model/regex/lexical-exception решение не добавлено.

## Финальный локальный review Gate A — 2026-10-02

Статус: **BLOCKED с двумя воспроизводимыми research counterexamples**.
Предыдущие разделы описывают исторические этапы; актуальный status здесь и в
[Gate A candidate, раздел 6](GATE_A_CANDIDATE_RU.md#6-финальный-локальный-review-2026-10-02--blocked).

После начального prototype добавлены existing typed/default fact adapter,
intact-atom structural check и exhaustive solver с предложенным cap 4096 visits.
Known partial facts проверены на native candidate retrieval; HTTPX initial Red
исправлен общим default witness без query rewrite/grammar changes. Public route
не переключён; candidate retention не приравнивается к public delivery.

В шаге 05 уже есть `ReadWindowDecision` / `decide_read_window` stub и
`tests/docs/test_passage_read_decision.py`: последний сохранённый Red 6 failed /
12 passed (`step05-red.log`). Stub всегда unknown; negative passes с ним не
доказывают guards. Green не выполняется до принятия Gate A.

### Проверка текущего кандидата

```bash
/usr/bin/python3.12 -m pytest -q tests/docs/test_gate_a_review_blockers.py tests/docs/test_gate_a_remaining_contract.py tests/docs/test_gate_a_contract_candidate.py tests/docs/test_admission_relation_witnesses.py tests/docs/test_admission_local_binding.py tests/docs/test_read_context_admission_boundary.py tests/docs/test_shared_context_proposals.py
```

Лог `/tmp/opencode/m2-model-free-execution-30056be8/gate-a-final-review.log`:
**183 passed, 3 failed**, existing asyncio_mode warning, exit 1.

- B1: `test_code_window_cannot_drop_following_applicability_restriction` —
  clipped window intro + intact code допускается без последующего restriction.
- B2: `test_legal_inventory_does_not_lose_all_feasible_context_to_solver_limit` —
  30 alternatives / 15 candidates exhaust 4096 visits; пустой packet при feasible
  arithmetic-cost packets. Не public DTO benchmark, но solver retention blocker.
- Прежний baseline failure: precedence echo в `test_shared_context_proposals`.

Новый blocker module зарегистрирован behavioral inventory shard с node hash;
ожидания не ослаблены, xfail/skip нет. Research Reds оставлены открытыми намеренно,
они не production regression действующего route. Runtime в этом review не менялся.

### Следующий этап

Пересмотреть общий structural dependency contract и bounded solver под B1/B2;
не добавлять lexical rescues, не увеличивать limits, не выдавать safe hit за
relevance и не возвращать unchecked best-so-far. Затем повторить controls и
получить Gate A signoff для isolated шага 05. Если общий контракт не найден —
сохранить M2 blocked, действующий route и изолированные результаты 01–04.
Смена relevance semantics или resource limits требует отдельного approval.
Независимая review/held-out оценка и полный regression не выполнены; rollout нет.

## Одна ограниченная попытка Gate A — завершена STOP на B1

2026-10-02. Пользователь согласовал ограниченный read-контракт, explicit
opposite-answer semantics и остановку при необходимости нового semantic механизма,
lexical exceptions или несогласованных ресурсов. Контракт зафиксирован в
`GATE_A_CANDIDATE_RU.md`, раздел 1; implementation approval не получен.

Переиспользование existing `_atom_spans`/`source_graph`/dependency closure/block
alternatives проверено на исходном B1 snapshot. Code closure содержит только fence,
edges отсутствуют, restriction — самостоятельный prose atom. Graph validator не
способен обнаружить неизвестную graph dependency. Blanket owner проверен как
контрпредложение: 4176 whole-DTO units против 339 для complete local example,
а также выход за bounded authorized extent. Cost diagnostic не назван valid public
projection или frozen regression. Артефакт: `gate-a-bounded-attempt-b1.json` в
`/tmp/opencode/m2-model-free-execution-30056be8/`.

Общий способ на existing helpers не найден; эвристика одного следующего paragraph
не выдана за completeness. Попытка остановлена на B1 согласно user stop-rule.
Research prototype, runtime, tests/inventory, budgets, storage и gold не менялись
в этой попытке. B2 не исправлялся; новые rescues не добавлены.

Повторён прежний focused command: `gate-a-bounded-attempt-controls.log`,
**183 passed, 3 failed** (B1/B2/известный precedence). Отдельный step05 stub command:
`gate-a-bounded-attempt-step05-red.log`, **12 passed, 6 failed**. Existing
asyncio_mode warning; оба exit 1. Это controls, не completed regression review.

Итог: **Gate A BLOCKED, эта ограниченная попытка закончена; Green шага 05 и
шаги 06–09 не продолжаются.** Действующий public route и isolated 01–04 сохранены.
Новый research этап автоматически не назначается. Возобновление требует отдельного
запроса/согласованного контракта. Это не математическое доказательство невозможности
model-free design и не закрытие M2. Независимая приёмка/rollout не выполнялись.

## Закрепление 01–04 после checkpoint

По запросу пользователя выполнена [изолированная проверка 01–04](ISOLATED_01_04_VALIDATION_RU.md).
Candidate `3dc6a17b`; baseline `30056be8`. Новые четыре API test modules:
**29 passed**. Одинаковые 16 legacy modules в обоих checkout: **195 passed,
3 failed**, идентичные failing node IDs (прежний precedence и два vector failures).
Новых failing nodes нет; full output parity/full regression не заявлены.
Артефакты `isolated-01-04-*.log` и `isolated-01-04-comparison.json` в прежнем
external log directory. Runtime/storage/defaults не менялись.

Gate A остаётся blocked. Запрошенный пользователем Gate B отсутствует в roadmap:
следующий переход ожидает определения/ссылки, не обхода Gate A.
