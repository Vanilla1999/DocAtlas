# Первый slice M1: metadata boundary

Checkpoint плана: `d521b358`. **M1 закрыт как совместимый extraction**;
окончательная приёмка: [M01_ACCEPTANCE_RU.md](M01_ACCEPTANCE_RU.md).
Ниже сохранена последовательность частичных проверок; M2–M6 не завершены.

## Изменение

В `evidence_qualification.py` выделена `source_metadata_rejection_reason`:
существующие identity/freshness/index/risk/lifecycle проверки без query prose.
`evidence_policy_rejection_reason` вызывает её первой, затем выполняет прежние
text/catalog exclusions. Причины, порядок и optional candidate semantics сохранены.
Version/scope/snapshot проверки других слоёв не перенесены и не заменены.

Ни один admission gate не отключён. Defaults, packets, providers и budgets
не менялись. Это подготовка границы, не исправленный multilingual поиск.

## Подтверждённые application callers

`qualify_evidence` вызывается из:
- `need_context_disposition.py`;
- `context_candidate_ranking.py`;
- `reference_query_tagging.py`;
- `context_query_probes.py`;
- `_docs_context_projection_core.py` (повторная visible qualification).

`evidence_policy_rejection_reason` также используется в:
- `joint_context_selection.py`;
- `joint_context_candidates.py`;
- `context_query_probes.py`.

Это список прямых application callers, не полная карта transitive read-path.
До изменения delivery нужны tracing остальных guards и классификация callers
по read/certification/mutation lanes.

Дополнительные domain callers: `context_hint_policy.has_context_hint_support`
и compatibility wrapper `qualify_visible_trace` в `evidence_qualification.py`.
Поэтому замены только application callers недостаточно.

Повторная qualification подключается не только в основной projection:
`query_block_bridge`, `joint_context_selection`, `inspection_recovery_seeds`
используют `_requalify_visible_source`; `context_variant_retention` и
`qualified_support_units` принимают её callback. Их нельзя пропустить при M4.

Read-path query planning строится в `_project_context_service_part01.py` и
`_project_docs_service_part03.py`, затем projection использует independent query
probes, visible requalification, hint support и variant retention. Этот перечень
ещё не является полной классификацией library/certification/mutation paths.

## Проверка

Команда: `python -m pytest tests/test_source_metadata_eligibility.py
tests/docs/test_evidence_qualification.py
tests/docs/test_discovery_independent_qualification.py
tests/docs/test_bound_table_qualification.py -q`.

Результат: **108 passed**. Из них 42 новых cases проверяют пять языков visible
text, metadata rejection mutations, precedence, text/catalog exclusions и
explicit historical intent. Это не проверка natural-language lifecycle inference
и не end-to-end гарантия равенства packets.

Использован Python из `.venv` соседнего checkout; production modules взяты из
текущего worktree. Installed-wheel и host-model проверки не выполнялись.
Первоначально collection блокировался diagnostic inventory; модуль и hash трёх
base test node IDs зарегистрированы без отключения inventory validation.
Тесты написаны после extraction; TDD Red/Green для этой правки не заявляется.

### Дополнительная проверка совместимости

`PYTHONPATH=. python roadmap/search-quality-2026-10-01/check_metadata_boundary.py`
сравнивает actual baseline функцию из Git `d521b358` с текущей policy.
**7 686 сравнений совпали**: комбинации identity, stale/freshness, index,
risk/lifecycle, intent, пяти языков текста и forbidden terms/roles, включая
optional metadata. Используется общая неизменённая `lifecycle_allows`;
это проверка extraction, не независимый аудит lifecycle policy.

Расширенный pytest набор (предыдущие четыре модуля плюс
`test_admission_guard_composition`, `test_admission_pipeline_invariants`,
`test_context_projection_boundaries`, `test_context_trust_gates`,
`test_patch_context_public`, `test_joint_context_invariants`,
`test_reference_projection_retention`): **227 passed, 1 failed**.

Сбой: `test_frozen_request_flow_prefers_project_context_module_witnesses` —
нет visible `flow_mcp` witness. Отдельный detached baseline worktree
`/tmp/opencode/docatlas-m1-baseline` на `d521b358` воспроизводит тот же сбой:
**1 failed**, тот же missing obligation. Он не исправлен и не списан в PASS.
Полная эквивалентность публичных packets этим не доказана.

## Осталось

Дополнена isolation проверка M1: baseline policy из `d521b358` подставляется
в текущую projection при fixed M2 terms. На трёх non-empty fixtures
original/host-lookup/exact-path итоговые payload **и snapshots совпали**.
Это DTO fixtures, не installed MCP и не сравнение всего baseline runtime.
Первый original fixture был пустым из-за неполного query plan; fixture исправлен,
non-empty assertion сохранён — пустые packets не засчитаны как успех.

Controlled публичный branch regression с facade spy подтверждает:
project read → docs_context, explicit library → docs_answer, patch → patch_context;
prepare/network остаются false, edit permission отсутствует. Реальный backend
в этом trace не используется. Новый/compound/patch набор: **82 passed**.

Полная M0 карта и baseline-equivalence проверка публичных packets; затем
query/intent и multilingual relevance эксперименты. Шаг 07 остаётся открытым,
шаг 08 не начат. Реализация этого slice пока не закоммичена.
