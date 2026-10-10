# P0 application: финальный локальный review 11 OPEN owners

2026-10-06. **P0 ACTIVE до общей integration/reconciliation.** Изменены только этот
отчёт и `archives/p0-application-final-review.json`; общие/product/test/gold/baseline
файлы не изменены. Прочитаны завершённые application outputs и фактический source.
Новые product imports, network, baseline/test runs и mutations не выполнялись.

## Classification отдельно от consumer closure

Вход: семь `decision=OPEN` из `p0-application-resolved-0.json` и четыре из
`p0-application-resolved-2.json`. Все 11 file hashes совпали с actual source bytes.
JSON сохраняет **те же path/owner/source_sha256 keys**, локальное решение, spans,
смешанные составляющие, consumers, preserve и отдельные closure status/gaps.

**Локальные механизмы всех 11 классифицированы:** восемь `SPLIT`, три
`TECHNICAL-RETAIN-CANDIDATE`. Нет причины оставлять mechanism `OPEN` лишь из-за
отсутствия полного transitive графа. При этом у восьми mixed owners consumer closure
остаётся `OPEN` с конкретными gaps, не с абстрактным «весь Python не доказан».

У ingest/sync/library refresh `CLOSED-SOURCE-BOUNDED` означает только проверенный
default orchestration/root/delegate map в production source. Это **не** runtime
execution, independent approval, полное качество parser/fetch/publication и **не**
TECHNICAL-RETAIN для upstream corpus policy. External injected facade/port overrides
явно исключены, не объявлены рабочими и не превращены в универсальную P0 обязанность.
Итоговые child decisions и D-ID links интегратор всё равно должен сверить.

| Owner | Локальное решение | Конкретное отличие |
|---|---|---|
| `select_evidence:33–465` | SPLIT | Legal/source policy, typed/facet qualification и context-only gates vs identity/caps/source-local assignment accounting |
| `ingest_project_docs:598–770` | TECHNICAL candidate | Exact candidate includes, locks, metadata/verified outcomes; default discovery policy — отдельный producer |
| `inspect_project_docs:403–596` | SPLIT | Overview/name/placeholder inference and create-doc handoff vs invalid-catalog/index/confirmation contracts |
| `sync_project_docs:311–479` | TECHNICAL candidate | Explicit full/incremental path reconciliation; upstream discovered corpus не exempt |
| `qualified_fragments:127–294` | SPLIT | Verbatim slices/union/footprints vs semantic focus, requalification and component witnesses |
| `packet_alternatives:141–202` | SPLIT | Authenticated structural seed hulls/private snapshots vs final semantic query/component checks |
| `LibraryRefreshOps.refresh_docs:621–760` | TECHNICAL candidate | Explicit versions/status/locks/ports; source resolver и crawl policy отдельно |
| Core `project_docs_context:65–794` | SPLIT | Named relation/intent/lifecycle/fallback admission vs source/crop/budget/no-loss retention |
| `get_patch_constraints:17–113` | SPLIT | Alias/normative/owner/symbol inference vs packet caps/source refs/advisory DTO |
| `get_project_context:17–865` | SPLIT | NL requirements/routing/prefit/dependency/relevance/completeness vs consent/rescue provenance |
| Unified `get_docs_context:58–580` | SPLIT | Mutation/task/snippet/legacy handoff consumers vs explicit modes/network/canonical aggregation |

## Дополнительно resolved реальные roots/dependencies

- `service.py:307–359` реально делегирует inspect/ingest/sync/project/patch/unified
  operations в соответствующие classes; пустой `consumers` в прежнем scan не dead code.
- `project_docs_service.py:11,29`, `patch_constraints_service.py:11,29` задают MRO и
  sync-before-call globals bridge. У project operations `__getattr__` part01:81–82
  направляет отсутствующие collaborators в service facade.
- Historical `_project_*_impl` hooks видны в callers, но product definitions не
  найдены. Default source-bounded map не предполагает их существования; external
  embedder replacement не сертификат закрытого runtime.
- Default `ProjectMetadataReader.read` выбирает explicit valid catalog или default
  `discover_docs` (`project.py:98–109`). Corpus role/name/module inference
  `:378–420,439–487,642–656` отличается от contained paths/hash metadata `:552–626`.
  Не передавать ему technical статус ingest/sync.
- Overview `domain/project_state.py:243–255` использует role/stem/path vocabulary;
  preflight `part01:331–344` — category и placeholder text regex. Это реальный
  semantic источник creation/confirmation decisions, не только serialization.
- Refresh ports установлены в `_library_docs_service_part01.py:30–59` с конкретными
  resolver/record/target/agent/publication collaborators. **Final** `_record_from_info`
  `:656–659` — actual method; earlier same-name forwarding definition `:99` не
  выбирается class body. Resolver `:108–342` различает exact registry, explicit URL,
  Dart/curated defaults; fetch `refresh_record:190–204` передаёт allowed domains/path
  prefixes/source manifest. Нельзя считать произвольный ports callback technical.
- Core passes concrete `_requalify_visible_source` into `qualified_fragments`
  `:332–340`. Public facade `docs_context_projection.py:47–82` динамически заменяет
  supported hooks. Crop requalification и inherited audited parent derivation
  существуют; это не доказательство semantic equivalence original/lookup.
- Joint route достижим в public projector `docs_context_projection.py:285`, а не
  просто experimental dead code. `select_joint_context:215–217` исключает caller
  lookups. `_draft_subsets:113–136` requalifies inherited traces; `_finish:42–82`
  финализирует quality на private clones; finalizer `:178–193` вызывает semantic
  component coverage. Seed lineage `joint_context_lineage.py:44–64` доказывает
  occurrences/snapshot containment, не proposition.
- `context_selection.component_witnesses:61–73` вызывает `extract_answer_units` и
  `best_local_proof`, тогда как `visible_assignments:180–224` проверяет occurrence,
  offsets и hash. Не объединять эти два механизма как technical.
- `need_context_projection:108–140` компилирует semantic need contracts и классифицирует
  evidence sets; precedence regex `:169–170` и list focus/count preference `:199–213`
  реально влияют на ordering/partial admission. Полная callee reconciliation pending.
- Project-context `:655–668` сам подставляет известные Docs/Packs command descriptions
  при `mcp_disambiguation`. Это local semantic injection даже без удаления aliases.
- Unified `_select_mode:642–651` — explicit inputs, не NL mode inference. Но
  `_patch_constraints_next_action:657–658` угадывает patch task из vocabulary, а
  `:527–529` копирует readiness из legacy completeness. `edit_ready` DTO не означает
  final mutation permission: MCP передаёт mutation contract и проверяет packet.

## Независимая выборка high-risk retain proposals

Это source sample завершённых application rows, не approval всех остальных partitions.

### Конкретные противоречия — требуется исправить decisions/границы

1. **`_PatchConstraintsServicePart02._symbol_from_line`**, resolved-2 объявляет весь
   owner `TECHNICAL-RETAIN-CANDIDATE` как call/declaration regex с generic exclusions.
   Actual `part02:554–559` отбрасывает `GENERIC_CALL_SYMBOLS` и берёт последний
   non-generic call; shared `:68–71` содержит **read/watch/of/push/pop/map/where/
   firstWhere/maybeWhen/when/setState** — это не reserved language words. `:565`
   также mixes declaration syntax с known `Future`/`Widget` types. Consumer
   `_symbol_candidates:428–438` превращает результат в matched symbol/confidence,
   `_symbol_candidate_constraints:607–618` — в project_convention/source_of_truth
   guidance. Требуется **SPLIT**: literal call/declaration extraction отдельно;
   library blacklist, known type preference и guessed last-call selection отдельно.
   Discovery-only disclaimer не делает словарь technical. Это соответствует уже
   recorded D30 SPLIT в `P0_NEIGHBOR_BRIDGE_AUDIT_RU.md:39–45`.

2. **`requirement_probe_query`**, resolved-2 объявляет whole owner technical bounded
   scheduling. Actual `_evidence_selection_part04.py:34–36` для `result_access`
   добавляет **`result`**, которого нет в extracted entity/detail: это semantic
   relation→search term. `:13–21` также сериализует `subject_aliases/expected_value`
   из typed plan; источник этих значений может быть ручным command/semantic rule,
   и scheduling их не очищает. Требуется **SPLIT**: exact supplied values/JSON
   code fragments/dedupe/bounds отдельно; inserted `result` отдельно, semantic
   producer dependencies named. Это default component rescue consumer
   `get_project_context:420–427`, а не лишённая execution caller test utility.
   Замечание точности: `:26` ограничивает только obligation branch до 320 chars;
   exact/facet/code-group branches не имеют общего 320-char clamp. Claim о
   blanket 320 bound тоже нужно сузить без product исправлений в audit.

### Retain proposals, проверенные без обнаруженной local semantic contradiction

- `_candidate_source_view:454–480` копирует supplied metadata/authority/status;
  `active` fallback — recorded metadata policy assumption, не доказательство
  currentness. Narrow technical projection обоснована; proof consumers отдельно.
- `aggregate_mixed_selection` (`part01:168–293`) namespaced child requirements,
  assignments и AND support. Это accounting supplied child proofs, не NL parser.
  Technical retain не закрывает child proofs.
- `joint_context_candidates._context_row:39–82` создаёт exact source slice/owner,
  перепроверяет reference/policy, очищает supplementary attribution. Локально
  structural; delegated policies и upstream probes не exempt. Whole transitive
  admission нельзя считать technical, но это не противоречие local retain.
- `joint_context_selection._finish:42–82` — clones/line/capability/budget orchestration,
  не local synonym table. `_finalize_quality` semantic dependency должна быть в
  consumer map (не спрятана под technical finalizer); в JSON mixed parent остаётся OPEN.
- `_flutter_targets_for_request:135–156` проверяет explicit library/ecosystem/URL
  host, не question topic; endpoint registry candidate может retained узко.
  Guides/API endpoint и channel не exact version snapshot proof.

Результат sample: **две конкретные whole-owner retain классификации оспорены**.
Они не находятся среди 11 входных OPEN keys, поэтому JSON не добавляет чужие rows
и не изменяет common partitions. Интегратор должен перенести исправления отдельно.

## Pending consumer closure и final reconciliation

JSON gaps оставлены для actual semantic цепочек: family-specific proofability,
need/reference/evidence-set admission, snippet/reselection, documentation-gap
handoff, normative ownership/patch validation и legacy completeness→public
authorization. Отсутствие исполнения каждого branch — limitation, не универсальный
«полный Python graph» blocker; известный semantic helper — classified dependency,
не unknown local owner. `CLOSED-SOURCE-BOUNDED` не означает capabilities green.

Финальный интегратор должен:

1. Проверить union ровно 11 keys против исходных OPEN rows и source hashes; заменить
   **local** classification, сохранив отдельную OPEN closure очередь.
2. Удалить/согласовать stale `mechanism_review:OPEN` текст: он исторический, не
   должен противоречить новым completed local findings. Не обнулять closure gaps.
3. Исправить два sample retain proposals с точными child-component boundaries.
4. Сверить D-ID assignments, default/fallback/SDK/bridge roots и technical exception
   grounds с четырьмя completed partitions и исходным P0 checklist.
5. Не повторять baseline ради количества, не менять gold/tests/production, не
   объявлять P0 DONE до этой reconciliation. P1/P2/merge approval остаются отдельно.

Input SHA256:

- resolved-0: `7ac3ea813e3a99899c6eddc888426b72974241b134b3aa4b48b7a922af755faa`
- resolved-1 (sample): `e087a888a9bcb3a2d16895fe9e1e7b8c255608f3d13bcaf81f5eeed687e3ff4f`
- resolved-2: `a70a5d802c68d91f17a2747a629f403fd3e94055862d9135141ff4e5db0db1bc`

**Вердикт:** local classification завершена в оговорённых 11 owners; transitive
semantic reconciliation частична и явно выделена. P0 пока ACTIVE, не dictionary-free.
