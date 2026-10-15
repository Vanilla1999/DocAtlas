# PR211: фактический final source carrier и private projection decisions

Статус: report-only source patch подготовлен; новые V2 operands и совместный
runtime на конечном tree ещё PENDING. Отбор, qualification, authority, corpus,
scorer, mutation controls и публичный DTO не меняются.

## Что действительно наблюдено на 136

Проверен reader job [114141422568](https://github.com/Vanilla1999/DocAtlas/actions/runs/38026891736/job/114141422568)
для HEAD `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07`, merge
`32765e44d2e85d3f638ac9d22a2fa6f4f46f6aee`, same tree
`7f663bac25aa6e79c48a07301d2e94e5e7352c42`.
Полученный log: 674211 UTF-8 bytes, SHA-256
`fdf815da3d3a2f0c301b4b36740aac2c29c3de79f0c50fe536281d7aac8bd7f0`.

`v2-natural-request-flow` имеет actual payload.source_count=18 и все 18 source
rows без transport omissions, но прежний diagnostic final_visible_evidence_ids
содержит только три ID. Они совпадают с первыми тремя public rows.
В том же сохранённом record: pre_projection_qualified_ids=5,
selected_candidate_ids=15, considered_variants=29, projection_rejections=0.
Artifact `project-context-quality-v2-live.json`: 13377004 bytes, SHA-256
`988b3c0e9fdc4f6c04ca0b8ae886c4ebbe56894ca73ecbdcf99ab77d33b81c79`.
Observed retrieval_calls=1 и validation_calls=1 относятся к прежнему capture;
этот slice не объявляет новых вызовов либо новых PASS.

Это не доказательство потери 15 sources. Исходный core записывает final IDs
через `payload["sources"][:3]`, а MCP observer снова берёт `[:3]`.
pre_projection_qualified_ids получены только из первых 32 qualification rows.
Имя selected_candidate_ids исторически обозначает dedup prepared preview:
источник — considered_variants, не фактические accepted selection events.
Пустой projection_rejections описывает только узкую visible_qualification ветвь.

Core payload также предшествует facade finalizers в
`docs_context_projection.py` (`c7aef87448fbd4508634c16d86ec589dc22ab159`).
Joint/query-block finalization может менять final source carrier. Поэтому даже
полный core count не подменяет наблюдение после конечной model-visible validation.
Неизвестный first-veto целевого V2 окна не объявляется установленным.

## Что меняет диагностика

В существующий private callback добавлен projection_observation.schema_version=1.
Он вызывается только в прежнем `_observe_same_call_diagnostics`; нового observer
или нового вызова handler, acquisition, projector, qualification либо validator нет.

| Carrier | Источник и граница |
| --- | --- |
| final_callback.sources | Реальный projection после существующей validate_model_visible_projection; полный source count и preview ID |
| returned_core_diagnostics | Diagnostics текущего core attempt, отдельно от итогового payload |
| primary_attempt / hint_attempt | Уже сохранённые отдельные snapshots; attempt_kind берётся из действительного _allow_context_hints |
| ranked_candidates | Размер реально материализованного ranked list после текущих filters и preview IDs |
| prepared_qualified_variants | Полный существующий qualified_variants counter и prepared preview; не selection proof |
| decision_trace | Копия существующих executed branch events/counts; события не добавляются и не повторяются |
| selection_events | Фильтр уже записанных selection events с отдельными producer/preview omissions |
| upstream_received | Размер полученных retrieval/qualification carriers; полнота до их producer неизвестна |

Каждая доступная серия содержит recorded_count, producer_count/producer_omitted
при известном полном числе, preview_count/preview_omitted и не более 32 items.
Неизвестное producer_count остаётся null. Missing, explicit null и malformed
carriers различаются. Отсутствие строки в preview не превращается в доказанное
отсутствие acquisition или первого veto.

Источники новых полей ограничены IDs, целочисленными counts, status/flags и
существующими branch reason/hash keys. Body, snippet, raw_document и новые
вопросы не копируются. Scalar strings ограничены 512 characters; diagnostic
превью не является продуктовым output cap. Прежний trace сохраняет собственный
предел 128 recorded events и исходные omitted counters без изменений.

Для actual final callback все прежние validation call sites остаются раньше
наблюдения, включая уже проверенный blocked payload. `delivery_blocked`
передаётся отдельно; пустой безопасный packet не объявляется успешной retrieval.
Core source observation относится к positive `_payload` boundary: ранний return
без этой записи остаётся missing, а не выдуманным observed zero.

## Сохранённые контракты и выполнение

Старые поля callback, включая прежние bounded final IDs и selected_candidate_ids,
сохранены для совместимости. V2 evaluator использует часть этих полей в
root_cause classification; этот report-only slice не меняет такую классификацию.
Новые точные carriers расположены отдельно и подписаны по их настоящему смыслу.

В core меняются только import, attempt_kind и diagnostics assignments: ranked
assignment перенесён в pure formatter, новый core source record добавлен после
полностью сохранённого legacy final assignment. Именно этот прежний текст
нужен live relation mutation anchor; anchor и fault text остались неизменны.
Никакие selection branches, source bytes, scopes, state, eligibility либо
answer/edit/query credit не изменяются. Core остаётся 998 physical lines.

В projection_decision_trace прежние 55 строк, class и event recorder сохранены
побайтно. Добавленные helpers только форматируют уже полученные Python values.
Они не импортируют service, storage, network или projection owners. Ошибка
private callback по-прежнему не изменяет валидированный public result.

Reader добавляет projection_observation ровно в два existing whitelists.
`run_project_context_quality_v2_gate.py` (`c261ce9c9bc07f427a005b4d2222d346e491a92d`)
уже импортирует этот shared formatter; отдельный V2 gate не редактируется.
Existing depth12, 768000-byte diagnostic console budget, priority order,
artifact completeness/omission receipts и exit/verdict semantics не меняются.

## Hash recipes и proof

Owning core hash меняется из-за diagnostics. Structured relation crosswalk
обновляет только base_blob, expected_before_sha256, expected_after_sha256
для прежнего callable fault и добавляет pending-only rebase record.
Raw и unit-fidelity notes получают только append-only current recipe sections.
Текущий literal owner 42a7 после pair slice149 также учтён в трёх raw faults.
Исторические sections и receipts остаются историческими.

Пять existing critical core anchors и четыре existing raw recovery anchors
заново проверены: по одному в соответствующем current owner, прежние before/
after texts и intended guards сохранены. Новые before/after hashes перечислены
в связанных notes/crosswalk. Critical и recovery runner этим slice не меняются.
Никакой старый baseline/kill не приписывается новому source hash.

## Exact manifest

| Path | Mode | Base blob | Proposed blob | Lines |
| --- | --- | --- | --- | ---: |
| docmancer/docs/application/projection_decision_trace.py | 100644 | 87ef89d1cafcf3e15deada1d0431fbea9d7b90af | 0b98a1d278d8f7d9f1a93524e65a203b81d42e5e | 192 |
| docmancer/docs/application/_docs_context_projection_core.py | 100644 | 0eb803a9105bbb2b4e07e0659eb46b7739725f28 | e78efba8d381104b9d5d4ac32d25dad6ad1433d4 | 998 |
| docmancer/docs/interfaces/mcp/context_tools.py | 100644 | 28fd767567e5c32124d84496a5937a87ee62164c | c22eaae8579ad230b7aeaaff619974c86424beee | 958 |
| scripts/summarize_acceptance_artifacts.py | 100644 | 2ddc2fc70476ef522bb8225c504e2b7fb64ef9bc | 64552e89ce073b5f62317c87efa059bb156add2c | 847 |
| eval/task_level/contract_history/admission_relation_live_source_inputs.json | 100644 | 2e742877e97ecd476b2ffe30965de5f143a9366e | 044d87fc5e5499f7a95d467c9363ec94daee3036 | 253 |
| v2plan/PR211_LITERAL_RAW_WINDOW_BINDING_RU.md | 100644 | 856a8de92502a40349d40d0bd811d3ab295dc25a | bd82552e60326ffa5794f0dbdbee90e8823d8a9e | 248 |
| v2plan/PR211_QUALIFIED_SOURCE_UNIT_FIDELITY_RU.md | 100644 | 2208d4d835fb69ebf4b8536dd1c91c72bfe9126f | 4c7884fc7bbb9318c69830d13bc410ee49608d80 | 209 |

Новая note: `v2plan/PR211_FINAL_PROJECTION_OBSERVATION_RU.md`, mode100644.

| Source | SHA-256 |
| --- | --- |
| docmancer/docs/application/projection_decision_trace.py | 4ecfb6c5870ec46c254f8bdde9d45f850e20c1c921e5fc1881e782870b49f3e6 |
| docmancer/docs/application/_docs_context_projection_core.py | 97f0876ecd70548773b5ab1f6356251bb870ff5f99da77c92ba4a0eab1bddb90 |
| docmancer/docs/interfaces/mcp/context_tools.py | cd66b49c1733736af9e6ceef2a421564104845dc434115c76fd6dd31a8a6742a |
| scripts/summarize_acceptance_artifacts.py | 1ba0a97ca20bc513b89bf0ce1bbf2369d4a4ff81f8574f001588759f8189a2bd |
| eval/task_level/contract_history/admission_relation_live_source_inputs.json | d78cd0def2a9d19233a952e82dfe705bc7ffe5a5d8c06f533554c8ab0de68470 |
| v2plan/PR211_LITERAL_RAW_WINDOW_BINDING_RU.md | cd08949fcd5a3f4ee7e986fb7800d7f6b8fa974a0c75a9dac59ef65acb1c7e04 |
| v2plan/PR211_QUALIFIED_SOURCE_UNIT_FIDELITY_RU.md | a0b98db916480267b5fa5b368366da9371a20e5e10d046133c141ff870a5bd62 |

Exact source readback и inverse выполнены без local Python/AST/import/runtime:
core — четыре узких обратных замены; callback — две; trace — удаление
append-only helpers; reader — удаление двух whitelist строк; crosswalk — три
scalar fields плюс новый record; прежние notes — удаление только appended section.

Следующий обычный совместный CI должен показать все три V2 diagnostic carriers
на новом tree вместе с healthy critical/recovery и intended mutation receipts.
До него нет нового source-window fidelity, AgentDeveloper/V2 success или
merge-ready утверждения. Дополнительные runtime/jobs/actions не запускались.

## Дополнение: original-input и прежний literal-credit faults

При окончательном review учтён также changed owner context_tools.py.
Его прежний current 4001-character forwarding control и fault text сохранены:
только `question` срезается до 4000 в направленной mutation. Эта recipe не
возвращает product input cap и не переписывает историческую input note.

| Existing fault | Current owner blob | Anchor count | Before SHA-256 | After SHA-256 | Intended guard |
| --- | --- | ---: | --- | --- | --- |
| project_read_original_is_not_truncated | c22eaae8579ad230b7aeaaff619974c86424beee | 1 | cd66b49c1733736af9e6ceef2a421564104845dc434115c76fd6dd31a8a6742a | 2678279375b1086328af50bfb1368b4149540ff92a0ff61d46c09a8f97dc3255 | critical_project_read_original_input_fidelity |
| literal-context-mints-original-credit | e78efba8d381104b9d5d4ac32d25dad6ad1433d4 | 1 | 97f0876ecd70548773b5ab1f6356251bb870ff5f99da77c92ba4a0eab1bddb90 | 74ea5d71f27786d7ba31caeea7e6841d5de5864907c05e89740b0d0129a5b64c | recovery_partial_no_query_credit |

Оба expected outcome: ровно 1 failure, 0 errors; для recovery credit fault
case `literal_anchor_context`. Это pending-only source recipes, не новые kills.
Guard, input, selector и runtime verifier не менялись.

Focused owner audit выполнен по current critical43 tuple
`15413c51f495d09ce11ebd1f48f2b1ea65603fa2`, recovery46 tuple
`b1673f6eb2b6623fc9358a90fa307634b380568c` и literal51 manifest
`8f92ea6d9c0045bd32d407f407a80f8d7198673a`.
В первых двух owning runners изменённые production paths встречаются как
targets только у пяти перечисленных core critical faults, одного context_tools
original-input fault и двух recovery core faults (raw-wire и literal-credit).
Trace helper не является target, literal51 не содержит ни одного из трёх
изменённых production owners. Current AgentDeveloper adversarial execution
inventory также не включает эти owners. Этот scope не заявляет глобальный
поиск всех возможных будущих recipes либо исполнение runtime.

Все найденные exact anchors встречаются один раз; hashes вычислены текстовой
подстановкой на текущих blobs. Исторические receipts остаются историческими.
