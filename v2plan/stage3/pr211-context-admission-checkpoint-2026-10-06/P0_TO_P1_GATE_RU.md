# Проверка перехода P0 → P1

2026-10-06. Текущий вердикт: **P0 ACTIVE (archival debt) / P1 DONE**.
Владелец явно утвердил [P1 approval/freeze](P1_APPROVAL_RU.md), включая перенос
оставшегося archival prerequisite в отдельный долг. P0/release red не стали green.
Ниже — исторические gate snapshots до parallel closure и owner approval;
latest classification — P0_PARALLEL_RESULT_RU.md, latest P1 — P1_STATUS_RU.md.

## Что дополнительно выполнено

- [p0_transition_manifest.py](p0_transition_manifest.py) прошёл в `.venv` и сохранил
  [manifest](archives/p0-transition-manifest.json): package provenance, 29 corpus files
  с SHA256, 157 top-level frame symbols, 159 test assertions, 7 template hashes.
- Прочитаны все 7 Markdown templates. Их contents не содержат thematic query→answer
  таблиц; `agent_contract.md` содержит NL workflow/scope guidance, которое требует
  отдельной синхронизации с proposed optional-lookups RU/EN capability.
  Это не blanket exemption для будущих prompts/generated host configs.
- Production static AST imports в `tests` не найдены; найден один import из `eval`:
  `_patch_review_service_shared.py:12` → `eval.task_level.artifact_hygiene`.
  Это artifact hygiene dependency, не подтверждённый answer dictionary; сохранить
  в D30/package audit как отдельный portability risk.
- Installed `doc-atlas 1.3.2` — editable distribution из текущего repository,
  Python `.venv` 3.12 (точная версия в manifest). Wheel config включает `docmancer`.
- Isolated `python -I` import patch review прошёл, но namespace `eval` разрешился
  **в repository** через editable environment. [Лог](archives/p0-isolated-package-import.log).
   Это не clean-wheel validation. Последующая реальная wheel-проверка ниже
   воспроизвела ошибку без repository leakage.
- Повторный published original-only diagnostic baseline прошёл runner exit 0:
  **8/15 useful facts**, token/source budget violations 0; reported errors сохраняются.
  [JSON](archives/p0-published-question-only-replay.json), [лог](archives/p0-published-question-only-replay.log).
  Runner восстанавливает published intent source in memory; local trust diff не изменяется.
  Это diagnostic replay, не зелёный release gate. HEAD/source hash зафиксированы в report.

## P0 checklist по исходным критериям

| Требование | Статус | Недостающее доказательство |
|---|---|---|
| HEAD/main-ref/merge-base/local diff hashes | DONE для local snapshot | Server freshness не заявляется, fetch не выполнялся |
| Python/lock/product source hashes | DONE для текущего audit environment | Clean-wheel provenance отдельно |
| Small-inline/regex/import/config candidate scan | DONE как scan | Semantic exhaustive classification не заменена результатом scan |
| Все D-IDs symbols/consumers/default/fallback | PARTIAL | 157 frame symbols получили audit decisions; полная classification остальных candidates и resolved reachability ещё не доказаны |
| Retained exceptions назначены | PROPOSED | TD01–TD06 требуют решения и tests, не утверждены автоматически |
| Runtime package/config/template paths | AUDITED для product-owned generated boundary | Wheel import isolation, пять host styles и восемь tool surfaces проверены; full consumer closure учитывается в общем ledger |
| Frozen corpus и reproducing baseline | PARTIAL | RU original/lookups и EN Direct-15 diagnostic reproduced с source hashes; официальный frozen gate и остальные required controls не заменены |
| Public facts/provenance/budgets/stage costs | RECORDED для четырёх diagnostic lanes | Source/index/config manifests и final integrity verified; baseline red checks сохранены; не SLA и не bilingual model acceptance |
| Existing red gates ledger | Existing checkpoint | Не разрешены dictionary redesign или снятием gate |

**Почему не ставим P0 DONE:** исходный план прямо требует отсутствия
неклассифицированных candidates и baseline reproducibility. Оставить C/OPEN и перейти
к реализации P2 было бы уходом от плана.

## Граница P1

Чтобы не блокировать подготовку следующего этапа, создан
[P1_ACCEPTANCE_DRAFT_RU.md](P1_ACCEPTANCE_DRAFT_RU.md) и 64-case proposed bilingual
corpus **до разработки replacement**. Это preparation, не вход в approved P1.
Owner approvals, independent holdout review и freeze отсутствуют.

Следующие работы в P0: полный поэлементный classification ledger и проверка
default/fallback/bridge consumers. Frame decisions, clean-wheel probe и baseline
manifest уже собраны; не повторять их без конкретной обнаруженной неполноты.
Ни один из этих пунктов не разрешает product/test-contract diff вне плана.

Build availability probe: в `.venv` отсутствуют `hatchling`, `pip`, `build`.
Позже wheel собран через `uv build`; см. build log и проверку ниже.
Hashes новых артефактов: [p0-p1-preparation-hashes.json](archives/p0-p1-preparation-hashes.json).
Проверены 64 уникальных draft IDs, source hashes и неизменность всех 383 product files
относительно P0 source manifest.

## Дополнительный evidence slice

- [Wheel build log](archives/p0-wheel-build.log),
  [изолированный probe](archives/p0-clean-wheel-probe.json),
  [runner](p0_wheel_probe.py): настоящий wheel `1.3.2`, `python -I`,
  repository удалён из `sys.path`, origin проверен, `eval` отсутствует.
  `patch_review_service` воспроизводимо падает с `ModuleNotFoundError: No module named 'eval'`.
  Config, query planning, project service и Docs server импортируются успешно.
  Это wheel-import проверка с dependencies текущей venv, не полная clean-install release validation.
- [157 symbol decisions](archives/p0-frame-symbol-decisions.json),
  [runner](p0_frame_classification.py): technical retain candidates, SPLIT и semantic removal.
  Поимённые AST references приложены, но не выдаются за resolved dynamic call graph.
  Implementation OPEN и exception approval PENDING сохраняются.
- [Stage runner](p0_stage_baseline.py) сохранил четыре same-call diagnostic traces:
  [RU original](archives/p0-stages-ru-original.json.gz),
  [RU lookups](archives/p0-stages-ru-lookups.json.gz),
  [EN Direct-15](archives/p0-stages-en-direct15.json.gz),
  [trust probes](archives/p0-stages-trust.json.gz).
  Useful facts: **8/15, 12/15, 11/15** соответственно; runner completion не означает green gate.
  Report errors сохранены. Trust probes без witness gold не дают acceptance score.
  Recorded socket attempts: 0; provider-free lexical route `with_vectors=False`.
  Nested latency содержит overhead profiler и не является production SLA.
  Returns field-selected; source passages сохранены через SHA256 text blobs,
  final payload/snapshot и tracked source hashes приложены. Полноту нужных
  qualification/crop/config fields ещё нужно проверить, поэтому P0 DONE не ставится.

### Generated-config и trace-integrity follow-up

[Audit](P0_CONFIG_AND_TRACE_AUDIT_RU.md): пять host config styles проверены
на actual generation/idempotence, rendered templates сохранены.
Existing config/contract tests: **18 passed**.
[Integrity](archives/p0-trace-integrity.json) проверяет source digests до
compaction, exact projected rows, passage blob hashes и final line ranges.
`WORKFLOW_POLICY` выделена как SPLIT, а не technical schema blanket exemption.
Generated default/admin/advanced/text-fallback surfaces сохранены и reviewed.
Actual isolated SQLite manifest теперь приложен к каждому trace: 134 sources,
1433 parents, 2779 children, 1441 sections; generation/config/schema identity.
Все 134 indexed source bytes совпадают с файлами; все 98 final rows прошли
source digest, projected-row и declared-line checks.
Остаток: полный scan-candidate ledger и resolved default/fallback/bridge call graph.

### Candidate/bridge closure после status update

[Audit](P0_CANDIDATE_CLOSURE_RU.md),
[ledger](archives/p0-candidate-ledger.json.gz): 9874 nodes с hashes/owners,
1440 classification decisions и **8434 REVIEW-REQUIRED**. Это точная очередь,
а не утверждение, что все 8434 nodes — semantic dictionaries.
Девять actual class bridges/348 wrappers проверены; 1273 nodes привязаны
к facade exports. Восемь parser dynamic entries verified.
D38 source-root/corpus rules classified; existing connector tests **67 passed**.
Полный consumer/default/fallback closure остаётся незакрытым. P0 ACTIVE.

### Сверка по symbols вместо raw nodes

[Grouped runner](p0_grouped_closure.py) и
[units](archives/p0-grouped-review-units.json.gz) сохраняют все 9874 nodes,
группируя их в 2624 function/assignment review units:
244 имеют complete node decisions, для 104 доступны pinned frame owner decisions,
2276 пока не имеют recorded owner classification. Owner decisions не освобождают
вложенные semantic branches от migration и не доказывают caller closure.

Уточнение предыдущей оценки: формулировка «остался только завершающий аудит»
недооценивала незавершённость ledger. Большая часть этих units — вероятные
structural/protocol candidates, но объявлять их technical только по предположению
нельзя. Grouping сделан без потери nodes и без ослабления исходного DONE gate.
По текущим доказательствам **P0 ещё нельзя честно закрыть**.

### Последующее расширение classification

[Structural/mixed audit](P0_STRUCTURAL_CLASSIFICATION_RU.md): текущий ledger
содержит 1856 classified / 8018 unresolved nodes; grouped units — 438 complete,
102 с existing owner decision, 2084 REVIEW-REQUIRED. Числа предыдущих slices выше
исторические. 12 audit controls passed; product source hashes неизменны.
Полная classification и consumer closure всё ещё не завершены.

### Ranking/completeness/source consumers

Последующие source reviews:
[ranking/snippets](P0_RANKING_SNIPPETS_CLASSIFICATION_RU.md),
[completeness/source map](P0_COMPLETENESS_SOURCE_MAP_RU.md).
Текущий ledger: **2313 classified / 7561 unresolved nodes**;
grouped units: **568 complete, 102 prior owner decisions, 1954 review required**.
Выделены default/injection/backfill/presentation пути и legacy-next-actions bridge
к `edit_ready`; это classification evidence, не исправление production.
P0 ACTIVE, полного closure нет.

### Итог user-authorized parallel audit

[P0_PARALLEL_RESULT_RU.md](P0_PARALLEL_RESULT_RU.md): все 1954 remaining units
имеют local classification; 276 REMOVE / 469 SPLIT / 1209 technical candidates.
С прежними решениями покрыты 2624 grouped units. Source-bounded attribution и
selector-family maps завершены; прежние finite gaps superseded этими maps.
**P0 всё ещё ACTIVE только до baseline provenance reconciliation:** exact frozen
command/environment/exit record и same-P0 required-control bundle не привязаны.
Actual frozen failure log найден, red не объявлен green. Классификацию заново
не наращивать вместо закрытия этого конкретного evidence gap.
