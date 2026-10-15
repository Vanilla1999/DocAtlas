# Независимое reviewer assessment: граница закрытия P0

2026-10-06. **На момент review: P0 closure НЕ подтверждён.** Это не verdict по ещё
не завершённым результатам четырёх classification agents. Их outputs не читались.
Единственная запись этого reviewer — настоящий файл; production, baseline, gold,
tests и общий registry не изменялись, runners повторно не запускались.

`AGENTS.md` отсутствует в workspace и проверенных ancestor directories
(`/tmp/opencode`, `/tmp`, `/`); вложенный scan `/tmp/opencode/**/AGENTS.md` нашёл
только файл в другом repository, не применимый к этой задаче.

## 1. Точный gate: P0 DONE не равен dictionary exit DONE

Source: `DICTIONARY_EXIT_PLAN_RU.md:100–182`, `P0_TO_P1_GATE_RU.md:31–59`,
`DICTIONARY_INVENTORY_RU.md:149–158`.

P0 требует одновременно:

1. Полной классификации кандидатов **в объявленном scope**, включая small inline,
   chained substring/regex, config/generated prompt и production eval imports.
   Каждый candidate связан с pinned source/AST identity и enclosing symbol;
   structural данные не освобождаются blanket module/owner exemption.
2. Symbol inventory и concrete consumer/default/fallback map для D01–D38 и вновь
   обнаруженных semantic механизмов. Shard globals, wildcard exports, facade
   overrides, parser dynamic imports и installed entry points учитываются явно.
3. Названных retained exceptions с ограниченным техническим основанием; mixed
   symbol должен разнести semantic branches и сохраняемые guards/parse contracts.
4. Воспроизводимого pinned baseline/environment/corpus/index/config manifest,
   public facts/citations/omissions/coverage/authority, budgets и stage costs;
   существующие red checks остаются red и отражены в ledger.

P0 **не требует** уже удалить D01–D38, доказать replacement RU/EN, получить green
P2/P7, изменить tests или получить merge approval. `REMOVE` — audit/migration
decision, не implementation `REMOVED`. `SPLIT` допустим как завершённое audit
решение только с явными решениями по составляющим, не как новое имя неизвестности.
Implementation `OPEN` semantic entries после P0 нормальны; общий dictionary exit
при них НЕ DONE (`DICTIONARY_EXIT_PLAN_RU.md:19–30`). P1 approvals/freeze также
отдельны от P0 classification; proposed exception нельзя выдавать за owner approval.

### Что могут закрыть parallel classification outputs

| Критерий | Могут закрыть | Не закрывают автоматически |
|---|---|---|
| Candidate classification | Поэлементные decisions + причины + hashes; новые D-IDs | Scan completeness вне входных partitions; скрытые assets/dynamic edges |
| Technical exceptions | Названные narrow contracts и test/evidence anchors | Полный module exemption; semantic rule, переименованный в grammar/policy |
| Semantic consumer map | Concrete caller chains, default/fallback/SDK roots | AST reference count, importable modules, ноль unresolved по счётчику |
| Baseline | Сверку с уже pinned evidence без rerun | Новый backend acceptance, green release, изменение gold/hash sidecar |
| Итоговый registry | Материал для единой reconciliation | Consistency общего registry без интеграционного validation |

## 2. Реальные high-risk цепочки, проверенные по source

Пути ниже относительно repository root. Это source-grounded named consumer map,
не утверждение, что каждый branch был исполнен на четырёх diagnostic lanes.

### A. Original vs caller lookup attribution — D01/D02/D05/D21/D25

`documentation_query_plan.py:_host_lookup_can_derive_original:209–248` сначала
вызывает `admission_meaning.questions_have_same_supported_meaning`, затем сравнивает
ручные intents/aliases и canonical texts. `_can_derive_original_from_intent:174–187`
использует whitelist intents и qualifier/negation/anchor exclusions. Это semantic
эквивалентность, не техническая parent-ID bookkeeping.

`build_documentation_query_plan:518–567` назначает `relation="audited_rewrite"`
и parent `query-original` либо caller lookup. Затем
`application/reference_query_tagging.py:45–83` переносит relation/policies в trace,
квалифицирует найденное body и вызывает
`evidence_qualification.py:derived_parent_trace:520–539`. Последний проверяет
`qualified`, `audited_rewrite`, непустой parent и отсутствие missing parent exact
terms; он **не доказывает заново смысловую эквивалентность** вопроса и lookup.

В final projection `_docs_context_projection_core.py:875–929` действительно
пересобирает qualification по видимому snippet и снова вызывает parent derivation.
Это необходимый crop guard, но semantic предпосылка relation остаётся upstream.
Нельзя объявить такой путь dictionary-free потому, что после crop quotes валидны.
В P0 retained: IDs/lineage/exact binding/source checks. Semantic migration:
whitelists/equivalence/policy inheritance. Final reconciliation должна отдельно
проверить parent claim и delivered quote; успешный lookup не равен covered original.

### B. Partial context и fallback — D01/D04/D06/D19/D25/D34/D35

Default preparation в `_project_context_service_part01.py` строит intent,
requirements и scheduled plan до retrieval; concrete anchors сохранены в
`P0_READ_PATH_AUDIT_RU.md:38–55`. `_project_docs_service_part03.py` имеет отдельные
`fail_closed_workflow` adjacent-expansion/budget branches и origin grouping.
Это не покрывается выключением одного alias builder.

`context_hint_policy.py:5,19–31` импортирует `_specific_contract_request/_tokens`
из D01 и отключает hint fallback для распознанного normative request; отдельно
проверяет hard stop, component contract и explicit paths. `:63–74` сохраняет
unresolved candidate только после independent evidence-policy guard и body
support. Body floor `:41–50` не добавляет original coverage.

Projection `_docs_context_projection_core.py:113–188` выводит broad context из
relation names/unresolved parts/`intent-context:*`, добавляет canonical/need/hint
IDs и fallback lifecycle inference. `:238–283` requalifies и может отбросить
candidate из-за strict attribute, no visible qualification, path-only либо
contract-fact criteria. Partial context сохраняется не безусловно: typed parser и
semantic admission продолжают влиять на достижимость final quote.

Retain: hard stop, explicit path/source identity, body/crop verification, budgets.
Не retain автоматически: topic-dependent eligibility и `_specific_contract_request`.
P0 map должен включить primary → prefit retention → final fallback, а не только
retrieval builder. Будущий no-alias-call test доказывает отсутствие вызова, не recall.

### C. Legacy completeness → edit_ready — D27/D31/D09

`answer_completeness.py:282–302` создаёт recommended local source action из legacy
story/missing terms и вычисляет readiness из exact status либо handoff.
`derive_project_answer_completeness:323–358` заменяет status/coverage canonical
support, **но сохраняет legacy recommended_next_actions** и использует их в
`edit_ready = supported or has_safe_local_source_handoff(...)`.

`recovery_handoff.py:13–25` — точный структурный контракт: `code_search`,
`search_local_source`, `coding_agent`, false confirmation/repeat/auto_execute.
Он не исполняет mutation и не доказывает documentary answer. Сохранять его можно
отдельно от NL story rules. Однако D27 не только diagnostic: legacy semantics
выбирают, появляется ли такой handoff.

Consumers: project-context canonical derive (`_project_context_service_part01.py:738`),
unified projection (`_unified_context_service_part01.py:527–528`). Public MCP
`interfaces/mcp/context_tools.py:303–334` строит mutation intent, а позднее packet
projection передаёт его contract (`:503–505`). Final authority имеет дополнительные
guards: `model_visible_projection.py:588` использует packet validity, mutation
readiness и survived mandatory assignments; Docs-only payload/projector выставляет
`edit_ready=False` (`_docs_context_payload.py:137`, core `:707`).

Следовательно, нельзя утверждать ни «legacy всегда разрешает edit», ни «legacy
только диагностика и не влияет». Map должен различить внутренний handoff flag,
unified result и model-visible authorization; потеря proof не разрешает mutation.

### D. Lifecycle, security, source scope — D13/D14/D18/D33/D38

`lifecycle_policy.py:9–35` — status enums и exact metadata filtering; `:38–39`
вызывает NL `lifecycle_intent_for_question` из answer-contract facade. Projection
core `:186–188` применяет inference как fallback, если requirement intent отсутствует.
Retain statuses/current-source guards; semantic historical/current triggers не
становятся technical от соседства с enums.

`evidence_qualification.py:211–225` проверяет project identity, freshness,
synchronization и lifecycle. `:227–238` отдельно применяет forbidden terms/roles,
пришедшие из proposal policies. Эти две группы нельзя удалить или сохранить одним
blanket решением. `project_context_service_shared.py:369–374` снимает low-trust
artifact ban по `LOW_TRUST_QUERY_TERMS` — NL source policy D14, не authorization.
Lexical hostile-content guards (`content_trust`, action packet) требуют отдельной
warning/telemetry/permission классификации, а не удаления как query synonyms.

D33 runtime router `_dispatch_part01.py:_apply_router` использует первый regex
match и `setdefault`: explicit filters не перезаписываются, отсутствующие могут
выводиться из query. Default routers пусты; configured path остаётся capability.
Generated instructions — тоже consumer surface: `WORKFLOW_POLICY` и rendered
resources/14 descriptions reviewed в `P0_CONFIG_AND_TRACE_AUDIT_RU.md:30–77`.
NL category→scope guidance не technical DTO; exact host/tool registry может быть.

D38 ограничивает corpus ещё до поиска: filtering root/locale/blocklist/strip-param
helpers и GitHub default exclusions (`P0_CANDIDATE_CLOSURE_RU.md:81–102`).
Default factory возвращает WebFetcher; direct GitHubFetcher остаётся SDK root,
не dead code. Root RU mirror suppression не blanket RU ban: RU seed и nested
`docs/i18n/ru` имеют иное поведение. Same-host/root/network/version identity guards
сохраняются независимо от semantic corpus exclusions.

### E. Production import eval — D30/package boundary

`_patch_review_service_shared.py:12` напрямую импортирует
`eval.task_level.artifact_hygiene` (три hygiene helpers). Public
`patch_review_service.py` импортирует shard через facade/class bridge.
Это concrete production dependency, **не доказанный query→answer dictionary**.
Editable `python -I` import недостаточен: eval разрешался из repository.
`archives/p0-clean-wheel-probe.json` и `P0_TO_P1_GATE_RU.md:69–75` фиксируют
настоящий wheel без repository leakage и `ModuleNotFoundError: eval`.

Классификация может закрыть обнаружение/consumer/portability risk в P0, не исправляя
package. Defect остаётся отдельным production/release blocker. Исправление не
обязательный новый product diff в audit P0; объявлять installed patch lane рабочим
при этом запрещено. Probe использовал dependencies текущей venv, не clean install.

## 3. D01–D38: обязательная reconciliation, не новый implementation registry

| IDs | Semantic consumers, которые нельзя потерять | Technical boundary |
|---|---|---|
| D01–D06 | Alias/disposition, parent attribution, answer concept injection, surface rewrite, schedule allowance/order | Original/literals, lineage, caps, explicit lookups |
| D07–D10 | Initial stages, tool inference, read/change narrative triggers, Packs synonym search | Explicit action/tool schema, masking, authorization |
| D11–D17 | SQLite/dispatcher ranking, source lanes/trust, evidence legal/qualifier gates, snippet/command relevance | General lexical scores, source checks, code/fence syntax |
| D18–D20 | Lifecycle inference, intent-context/fallback, stopword/exact-anchor exceptions | Status enums, exact path/source/crop/budget |
| D21–D26 | Admission equivalence, injected command values, proof synonyms, semantic frames, reference/technical-kind inference | Source/subject/value/polarity binding, literal spans |
| D27–D28 | Completeness/recovery handoff, number/negation interpretation | Structural handoff, numeric bytes/bounds; NL numbers need named decision |
| D29–D31 | Patch aliases **и inline duplicates**, review filters, generated source inference/navigation | Current-source extraction, ownership constraints, bounded traversal |
| D32–D33 | Exact library lookup vs guessed topic; config routers and generated host guidance | Identity→URL registry with version/fetch guards, serialization/schema |
| D34–D38 | Relation qualification, request preferences/stopping, semantic density, frozen-question arbitration, source corpus policy | Segmentation/budgets, source syntax/metadata, explicit source/locale boundaries |

D37 особенно важна: illustrative `PUBLIC_EXAMPLES` не runtime arbitration, но
`FROZEN_OWNERSHIP_CASES → FROZEN_LEGACY_QUESTIONS → evidence_requirements.py`
достижим в production. Нельзя закрыть оба как test data. D36 patch scoring также
не вычёркивается из общего P0 только потому, что Docs read является первым milestone.

## 4. Facade/dynamic roots и границы достижимости

Прочитан `_internal/shard_compat.py:50–55,71–83,122–140`: wrapper синхронизирует
public globals перед вызовом shard; function bridge имеет аналогичный механизм.
Private monkeypatch может быть перезаписан. Existing bridge probe проверил девять
class bridges и 348 wrappers, но это closure **конкретных edges**, не execution
всех business branches. Function facades и wildcard imports проверяются отдельно.

`project_answer_contract.py:15–25` импортирует три shards, сохраняет legacy builder
и поверх подключает question-plan/coverage/technical-term collaborators.
`docs_context_projection.py:47–82` использует dynamic public facade hooks: observers
должны соответствовать actual final crop/requalification path, не старому bound import.
Parser registry/factory edges verified в existing connector probe; direct SDK
classes и package exports не объявляются unreachable из-за отсутствия MCP caller.

**Не требуется универсальный полный Python call graph.** Исходная обязанность —
named semantic consumer map + технические/default/fallback roots в согласованном
scope. Граф каждого DTO serializer или third-party internals не новая P0 задача.
Но неизвестный edge, который может менять proposal, source policy, admission,
public attribution или authority, должен остаться pending. Если доказана лишь
часть именно этого semantic consumer scope, план `:180–182` запрещает P0 DONE.
Static imports/references не заменяют resolved facade/dispatch edge; источник
доказательства помечается `SOURCE`, `PROBE`, `BASELINE`, а не смешивается.

## 5. Pending blockers и финальный validation

До получения завершённых outputs остаются **pending**:

1. Полнота/reconciliation всех candidate decisions: новые partitions пока не
   reviewed; исторические counts в gate не финальные. Этот reviewer не делает
   вывод по ним и не читает concurrent unfinished files.
2. Единый D01–D38 consumer/default/fallback/root ledger, включая named mixed
   branches выше. Owner-level decision не закрывает вложенную неизвестность.
3. Named retained exceptions и test/evidence anchors; distinction audit decision
   / implementation status / owner approval в final registry.
4. Baseline gate reconciliation: текущий gate всё ещё пишет `PARTIAL` для frozen
   reproduction. Existing four lanes/index/citation integrity дают сильное
   evidence, но diagnostic runner exit 0 не green Direct-15/frozen gate. Финальный
   интегратор должен явно указать, какой pinned baseline воспроизведён, какие red
   checks и limitations сохранены и есть ли реально отсутствующее обязательное
   evidence. Red baseline сам по себе не причина бесконечно повторять runs.

Отдельно **не устранены** packaging eval defect, instruction compatibility defects,
baseline red required checks, P1 approvals/holdout freeze и P2 replacement. Это не
одинаковые blockers: первые должны быть честно зафиксированы для P0; P1/P2/P7
не объявляются выполненными вслед за classification.

Предлагаемый final reconciliation validation без нового baseline/product diff:

- Сначала дождаться завершения всех четырёх partitions; проверить source/file-set
  hashes против одного pinned manifest, partition disjointness, ID uniqueness,
  union equality и отсутствие dropped nodes. Сохранить final artifact hashes.
- Проверить decisions по source, особенно mixed owners: semantic child не может
  получить `TECHNICAL` только от casefold/export/DTO родителя. Любой new mechanism
  получает D-ID либо явную связь с существующим, не теряется в technical bucket.
- Для каждого D-ID проверить symbol → immediate consumers → public/default root
  и альтернативный fallback/config/SDK root; записать конкретный guard/edge и
  bounded limitation. Сверить facade synchronization, wildcard override,
  projection hooks, dynamic parser/factory и eval import с existing probes.
- Отдельная ручная проверка четырёх опасных claims: lookup→original, final partial
  retention, completeness→handoff→model-visible edit flag, NL→source/lifecycle
  policy. Проверять source quotes, не aggregate count.
- Сверить final registry с original P0 checklist и existing manifests/logs;
  устранить stale исторические статусы без ретроактивной подмены evidence. Не
  обновлять corpus/gold/README sidecar и не отключать red gates.
- Если criteria 1–4 раздела 1 закрыты, можно отдельно признать **P0 audit DONE**
  с limitations/remaining implementation OPEN. Если semantic edge или candidate
  unresolved — **P0 ACTIVE**, конкретный blocker и next action. Ни число решений,
  ни полный registry rows count не заменяют reviewer verdict.

**Итог:** новые classification outputs потенциально закрывают основную audit queue,
но финальное P0 решение требует source-grounded consumer reconciliation и pinned
baseline checklist. Этот отчёт не разрешает P2 integration, test migration или merge.
