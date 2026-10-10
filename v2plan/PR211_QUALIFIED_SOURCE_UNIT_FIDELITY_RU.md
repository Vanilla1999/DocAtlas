# PR #211: сохранность различных квалифицированных source units

## Статус и границы evidence

База — опубликованный HEAD `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07` (slice 136),
tree `7f663bac25aa6e79c48a07301d2e94e5e7352c42`.
Все четыре base blobs повторно прочитаны по этому HEAD и совпали с manifest ниже.

Последний переданный root actual 130 результат V2 request-flow — 2/4 полных факта:
MCP/gateway присутствуют, application/selection отсутствуют. В actual 126 уже
наблюдался текущий source window `docs/modules/project-context-retrieval.md`
[1346:1804], квалифицированный для `query-lookup-2`, в ProjectContext и Unified.
Документ имеет blob `bcb180b3042361e68f07764f5f93fcee1681b74c`.
Эти наблюдения доказывают приобретение и передачу окна до проекции. Они **не
устанавливают первый внутренний отказ** projector для конкретного V2 случая.

Этот slice устраняет конкретную ветвь потери, установленную по source: разные
проверенные части документов могли быть отброшены только потому, что query ID
или слова lookup уже были представлены другим источником. Новый
`V2_SELECTION_OPERANDS` reader в 136 должен отдельно показать действительную
ветвь отбора V2; такой результат здесь не предполагается.

Фактический critical 130 ещё не был здоровым baseline: его единственный failure
на existing native member control — `critical_project_read_request_work_bound`
в старом oversized-original setup. Slice 134 исправил контракт этого setup;
данный slice начинается с его blob `11a71021` и не меняет этот tail.
Ни новый healthy baseline, ни два новых mutation kills здесь не объявлены:
целевой следующий critical прогон — **61 cases / 41 mutants, PENDING**.
Recovery runner и его 43 mutants этим slice не изменяются.

## Правило сохранения

После прежних source/current/scope/qualification проверок projector уже строит
private `DeliveryUnit` и `VariantFootprint` из того же текущего окна. Новый
`has_new_qualified_units` использует только этот заново вычисленный footprint.

Для положительного результата нужны непустые полные unit keys и query IDs.
Новизна — различие body/applicability fingerprints относительно уже выбранных
units **внутри того же OriginKey**. OriginKey включает project/version/snapshot,
document ID, SHA-256 и границы исходного окна, owner ID и digest query plan.
Поэтому сравнение не выдаёт одинаковые слова в разных источниках, окнах или
снимках за взаимозаменяемые доказательства.

Existing unit builder проверяет соответствие raw window, полный body hash,
координаты и зависимые spans; повторно квалифицирует варианты против текущего
plan. `block_work_limited` по-прежнему даёт пустой inventory. Получить разрешение
через заявленный в metadata счётчик, число sources либо повторённые query IDs
нельзя.

В core добавлено ровно три места применения этого признака:

1. Новый самостоятельный текущий unit может пройти `no_new_direction`, даже
   когда его допустимый query ID уже представлен.
2. Такой же unit может пройти `insufficient_new_host_terms`, даже когда он
   сообщает другой факт с теми же словами lookup.
3. При уже занятом evidence ID непересекающийся вариант сохраняется отдельным
   existing deterministic variant ID, когда он добавляет допустимый query lane
   либо такой unit. Разорванный текст не объединяется; прежний фрагмент остаётся.

Нет нового query attribution, inferred role, answer/edit grant или original
coverage. Прежние `authority_duplicate`, path-only и no-visible-qualification
veto остаются. Замена существующего варианта всё ещё проверяет сохранность
query/component/command/mandatory evidence. После отбора обязательна прежняя
валидация публичного snapshot.

Source acquisition и его operational limits не меняются. Существующие bounded
control view и предупреждение об overflow также остаются; эта поправка касается
последующего выбора из уже приобретённых и проверенных окон. Нового SQL,
retrieval либо network вызова она не добавляет. Требование «zero filesystem
calls» не заявляется: прежняя source attribution/continuation path validation
может обращаться к пути.

## Независимый контроль на тех же входах

Усилен helper существующего
`tests/test_mcp_delivery_member_transaction.py::test_real_service_retrieves_committed_fixture_member_bytes[none]`.
Новых pytest functions, module/node identities, вопросов или corpus files нет.

Полностью сохранены 24 исходных finite documents: по 12 revision facts для
`AlphaWindowRecord` и `BetaWindowRecord`, исходный вопрос
`How is the host receipt assembled?` и два явных lookup. Unicode `λ` остаётся
в тех же байтах. Healthy native read по-прежнему один, успешных dispatcher
calls по-прежнему четыре: original дважды и два host lookup. Их current
scope/filter/limit/budget проверки не менялись.

До нового guard остаются все старые доказательства:

- finite preparation, 24 уникальных текущих SQL children, generation/owner;
- exact raw/display hashes, prefix-bearing file hashes, Unicode char/byte spans;
- 24 реально приобретённых qualified результатов, отсутствие original credit;
- bounded view из 20 с предупреждением и 24 окна в ProjectContext и Unified;
- public status, обе lookup directions, отсутствие answer/edit/original authority;
- current source snapshot, полный authored body и binding каждого public source.

Затем `critical_project_read_distinct_lookup_units` требует **все 24** разных
факта. Expected set вычисляется из независимых literal fixture bodies и
прочитанных committed SQL children: path, stable/parent/source IDs,
generation/project identity/class/scope, char/byte/line spans и SHA-256 полной
строки. Output count или production unit helper не используются как oracle.
Утверждение о полноте относится именно к этому конечному fixture.

Добавлен identity-return observer единственного реального projector вызова:
копируется его фактический input до выполнения, original вызывается один раз,
возвращается исходный tuple. На сохранённой копии выполняются **две отдельно
учтённые projection replays**:

| Replay | Входных окон | Независимое требование |
| --- | ---: | --- |
| `repeated_current_units` | 48, каждый current operand повторён дважды | Ровно те же 24 полных source units, без повторной выдачи |
| `reversed_current_units` | 24 в обратном порядке | Ровно тот же set из 24 полных source units |

Все четыре acquisition entry points во время этих replays заменены отказом.
Вызовов retrieval они не добавляют. Проверяются final snapshot, byte/source
binding, прежние false authority flags, неизменность captured input и storage.
Это два дополнительных вызова projector, а не бесплатная проверка и не два
новых native reads.

Все 16 прежних negative operations и их порядок сохранены: project/dependency
consent и stale status, invalid catalog, acquisition error, stale/foreign/corrupt
windows, catalog hash, действительное dependency stage overflow, explicit
delivery veto, host lookup work bound, полный original длиной 4001, interrupted
acquisition без retry и отсутствие обязательного patch retention ACK.
Существующие negative операции могут сами доходить до контролируемой ошибки
acquisition; счётчик «один native read» относится к healthy receipt.

Duplicate/reorder replays доказывают повторение **того же** source/window
binding; semantic dedup между разными origins не заявляется. В исходных 24
документах по одному небольшому paragraph unit. Отдельный native сценарий
нескольких disjoint units одного origin этими входами не создаётся; сохранность
соответствующей existing variant-ID ветви проверена по source, а не выдана за
фактическое дополнительное native доказательство.

## Направленные faults

Сохранены все 39 прежних mutation blocks, target roster/case counts и весь
executor. Добавлены только два faults в тот же native selector; для каждого
ожидается один failure с первым guard
`critical_project_read_distinct_lookup_units`.

| Fault | Изменение | Почему oracle должен сработать |
| --- | --- | --- |
| `project_read_preserves_units_after_query_coverage` | Убирает unit exemption только из `no_new_direction` | После первых lookup representatives другие полные факты теряются; прежние handoff проверки ещё проходят |
| `project_read_preserves_units_without_new_query_terms` | Убирает unit exemption только из `insufficient_new_host_terms` | Unit проходит первый gate, но затем теряется из-за уже представленных слов того же lookup |

Оба exact anchors встречаются по одному разу. Before core SHA-256:
`866d6154c0d59dd4ab76ea946cb408a2cc440e073f2988f41bdf34ef32837de2`.

After SHA-256 соответственно:

- `b489f798efdd16fac472fbb2dfa69de94bf02172935eed6d59bc6f08295dfadc`;
- `d3c18d77d2502641934a590b1d49d11dae91d9d0060a79969b64b4fbe3c11ca0`.

SHA-256 побайтно сохранённого prefix старых 39 blocks, от `MUTANTS = (`
до его прежнего closing delimiter:
`a81f95c91c0ae9dce7e89cbad873a5fab8a0cd37be4c676b38ec9a94e324d78f`.

В existing import-origin inventory добавлены два фактических private owners:
`context_variant_retention` и `qualified_support_units`. Это наблюдение пути
и hash настоящего импортированного исходника; подмены evaluator/producer нет.
Прежние три critical mutation anchors этого core также сохранили count 1.
Зависимые descriptive source-hash recipes должны быть отдельно rebased root
на новый core; frozen inputs и другие mutation runners здесь не редактировались.

## Exact manifest

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `docmancer/docs/application/context_variant_retention.py` | 100644 | `b328b2869324fb2b304e819b02bd3d3b5898d842` | `844653550f0b77e87d7e5eb977e066507573b567` |
| `docmancer/docs/application/_docs_context_projection_core.py` | 100644 | `3dc9c8f19b4431503a073730e1c6f330cd583634` | `0eb803a9105bbb2b4e07e0659eb46b7739725f28` |
| `eval/agent_developer_v1/project_read_presentation_controls.py` | 100644 | `11a71021d2f1bb52aff95f53467d9c70ef77f911` | `f133d9768ab498714bb48b4e3adea8076187e45a` |
| `scripts/run_critical_mutation_gate.py` | 100755 | `e8acf1d3e91cdc37b1eb1b1296f57a9bbf9044c2` | `8b9e6f1e73a6fd855675935ccb6d1da043e3f72e` |
| `v2plan/PR211_QUALIFIED_SOURCE_UNIT_FIDELITY_RU.md` | 100644 | new | this note |

Source sizes: helper 312 lines, core 999, control 441, runner 979.
Core остаётся в существующем 1000-line footprint.
Все code blobs прошли exact GitHub readback. Inverse edits восстанавливают
каждый base побайтно: core 7, control 8, runner 2 узких замены; helper — одна
новая функция. Source-only review не заменяет healthy run и intended kills.
Локальное исполнение, импорты, pytest, subprocess, refs и commits агентом не
выполнялись.
