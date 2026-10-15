# P1: контракт replacement для согласования

**P1 ACTIVE / OWNER APPROVAL PENDING. P2 NOT STARTED.**
Начало P1 разрешено владельцем; P0 формально ACTIVE из-за archival provenance.
Это разрешение готовить контракт, не автоматическое утверждение TD/TM решений.
Product, existing tests/gold и release thresholds не меняются.

## 1. Что replacement обязан сохранить

Для RU→RU, RU→EN, EN→RU, EN→EN отдельно, без/с explicit caller lookups:

- Доставлять каждый заранее назначенный source-backed witness в final visible
  output; query/source identifiers могут быть неизвестными продукту.
- Сохранять subject, значения, условия, отрицания и обе стороны сравнения.
  Полезный partial context не удалять из-за отсутствия полного answer proof.
- Unknown facet остаётся unresolved; чужие значения не присваивать своему subject.
- Original question сохраняется неизменной; успех lookup не даёт original proof.
- Name-only/quantum unrelated match не даёт topical coverage или answer authority.
- Только разрешённые project/module/version/generation, verified bytes/ranges.
  Reject stale/unsynced/hash mismatch независимо от релевантности body.
- Документ не разрешает actions/network/scope. Optional backend failure не
  обнуляет допустимый local context и не запускает скрытый network fallback.
- Final serialized DTO соблюдает существующие configured ceilings. Budget
  pressure проверяется с distractors, а не только коротким одиночным текстом.

На fixed controls: **0 integrity violations, 0 missing required witnesses**.
Baseline red не снижает это требование. Агрегат не компенсирует потерю case/lane.
Альтернативный witness допустим только после отдельного source-bound review.
Все synthetic retrieval cases требуют `answer_supported=false/edit_ready=false`.
Existing typed-proof positive tests остаются обязательными: global false workaround
не проходит контракт. Pydantic/Pebble/trust/adversarial real controls дополняются,
а не заменяются короткими synthetic fixtures.

## 2. Технические исключения — proposal, не blanket exemption

| TD | Предлагаемое решение | Ограничение |
|---|---|---|
| TD01 | Retain exact schema enums/action maps | Explicit typed input only; не NL intent inference |
| TD02 | Retain identity→URL registries | Exact identity/version/source binding; не confidence→proof |
| TD03 | Не разрешать новые RU/EN number tables; существующую normalization изолировать до отдельного решения | Literal span→subject/facet; multi-count negatives; removal только после replacement |
| TD04 | Retain language syntax tokens | Code parsing only; не ranking/admission; unknown identifiers |
| TD05 | Retain JSON/fences/paths/numeric syntax и guards | Exact bytes/ranges/hash/scope/freshness/budgets независимо от relevance |
| TD06 | Исторический/source-class scope задавать explicit request contract | Не добавлять query triggers; изменение public DTO отдельно согласовать |

Все TD: **OWNER PENDING**. 1209 audit technical candidates не равны 1209
утверждённым исключениям. `_symbol_from_line` и `requirement_probe_query` — SPLIT.
Никаких topic aliases, keyword routers, тематических regex или скрытого переноса
таблиц в parser/prompt/model adapter. P2 model/backend selection здесь не сделан.

## 3. Миграция tests

Сохраняются 159 assertion records исходного manifest и TM01–TM06 из
[draft](P1_ACCEPTANCE_DRAFT_RU.md). **Ни один assertion пока не меняется.**
Для каждого будущего diff обязательны old guarantee, incompatible implementation
detail, replacement test ID, positive+negative evidence baseline/candidate,
owner approval, independent reviewer и SHA. Scope/budget/proof guards не удалять.
Alias-existence assertions заменить только после demonstrated fact delivery.
Original-derived coverage и README blob sidecar требуют отдельного решения;
fake derived coverage, floor lowering и opportunistic hash update запрещены.

## 4. Корпус и freeze

Builder: `p1_contract_corpus.py`. 28 families × 8 lanes = **224 cases**;
88 development / 136 holdout-candidate. Есть exact source hashes, code-point
spans, requested/actual scope metadata и concrete injected integrity faults.
Version decoy имеет отдельную identity; offline имеет named fault timing/counters.
Budget workload фиксирует 12 distractor bodies/hashes, 3 ordering permutations,
Pydantic companion witness, zero additional calls/hidden retries. Actual
config/serializer/tokenizer binding — до исполнения; ceilings не увеличиваются.
Есть rename peers, foreign/owned project pair, quantum unrelated, lookup-only,
divergent negation, reversed comparison и explicit forbidden subject relations.
Корпус — evaluation data; product импортировать его не должен.

Holdout **не blind**: авторы/агенты видели fixtures. Family-disjoint fixed
evaluation полезен, но не измерение полностью unseen generalization.
Independent review до freeze проверяет все spans/facts, metadata, positive/negative
семантику, family leakage и missing controls. Reviewed snapshot хешируется;
approved freeze только после owner TD/TM/behavior/resource decisions.
После freeze нельзя редактировать cases по candidate output. Исправления — новая
версия с сохранением старого отчёта и отдельным approval.

## 5. P2 entry

Нужны owner acceptance и independent corpus review; P0 archival limitation
записана отдельно, не превращена в green. Before candidate run pin actual HEAD,
local diff, config/index/corpus/model/prompt/environment и baseline/candidate logs.
Действующие budget ceilings не увеличиваются. Numeric latency/cost/storage
ceilings для выбранного backend: **PENDING**, определить до model choice/download/run;
нет разрешения автоматически выбрать произвольные лимиты.
Model-dependent route: 3 final repetitions, worst run/range, no best-of.
Existing core/advanced/adversarial/required CI/release gates не отменяются.

**P1 DONE нельзя заявить до owner решений и approved freeze.**
