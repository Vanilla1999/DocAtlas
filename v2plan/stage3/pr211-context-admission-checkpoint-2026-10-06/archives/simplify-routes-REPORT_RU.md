# #211: аудит повторной интерпретации и маршрутов projection

Дата: 2026-10-06. Worktree: `/tmp/opencode/pr211-simplify-routes`.
Ветка: `diagnostic/pr211-simplify-routes-20261006`.
Baseline: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

## Решение

**Одна допустимая механическая чистка:** получить `query_constraint_roles(text)`
один раз при построении нового independent probe вместо трёх обращений.
Это низкоприоритетное упрощение выражений, **не исправление #211**.
Полезного доказанно безопасного сокращения самих main/late маршрутов не найдено.

Существенное ограничение выгоды: функция уже имеет `@lru_cache(maxsize=512)`.
Убираются два повторных cache lookup, а не два полноценных разбора запроса.
Нет основания обещать заметное ускорение pipeline. Если цель — устранить красный
adversarial или значительно уменьшить количество квалификаций, этот cleanup
не достигает цели и не должен становиться отдельным этапом ремонта #211.

Прочитаны primary `PR211_RED_ANALYSIS_REVIEW_RU.md`,
`PR211_POST_PARALLEL_REASSESSMENT_RU.md` и независимый
`/tmp/opencode/pr211-parallel-review/REPORT_RU.md`. Поздняя переоценка имеет приоритет:
отсутствие witness не доказывает отсутствия полезного факта. A/B не предлагаются.

Ни product, ни существующие tests/manifest не изменены. Созданы только этот отчёт,
`routes_diagnostic.py`, `routes_evidence.json` в собственном worktree.
Commits/push/merge отсутствуют. AGENTS.md в дереве и проверенных родительских
каталогах не найден; прочитаны локальные CONTRIBUTING.md, SKILL.md и
`.hermes/engineering.toml`. Внешний docs/network/indexing не использовался.

## 1. Caller → contract → candidate → decision: факты исходников

Все относительные пути ниже относятся к baseline в этом worktree.
`A/` = `docmancer/docs/application/`, `D/` = `docmancer/docs/domain/`.

| Caller / строки | Контракт и кандидат | Решение / следующий узел |
|---|---|---|
| `A/_project_context_service_part01.py:46,56–74,79–89,117–125` | `classify_project_query_intent(question)` для reranking; отдельно canonical requirements и DocumentationQueryPlan | Intent направляет ranking; это не local proof и не решение позднего fallback. |
| `A/evidence_requirements.py:452–464`; `D/documentation_query_plan.py:673–703` | ProjectAnswerContract → proof obligations → `_component_contract`; сохраняются subject, kind, attribute, value_kind, response_mode, scope completeness | Main получает обязательства из этого payload, а не из NeedContract. |
| `A/_project_docs_service_part03.py:178–186,249–263,106–134` | Полученный/построенный query plan, SourceReferenceContext, retrieved chunks; independent lookup, которого нет в matches | `_qualify_candidate_lookups` дополняет discovery traces; для original ставит `admission_only`, `qualification_route=cross_lane_body`. |
| `A/source_reference_evidence.py:60–66,99–110,139–179` | Root ReferencePlan, проверенные current source/window bytes, NeedContracts для structural proposals | `_reference_root_plan`, `_reference_evidence`, `_evidence_sets` идут с кандидатом. Это предложения provenance, не окончательная авторизация. |
| `docs/interfaces/mcp/context_tools.py:394–403`; `A/docs_context_projection.py:198–222` | Raw retrieval с context_pack и query plan, budget ≤800 | Public facade вызывает core, затем очищает locators и пересчитывает quality. |
| `A/_docs_context_projection_core.py:86–94,173–203,212–250` | Decode component obligations; strict single attribute = complete scope + один attribute + truthy value_kind; ranked candidate | Source class/path guards, `_requalify_visible_source`, затем component witnesses; отсутствие последних при strict даёт `missing_attribute`. |
| `A/_docs_context_projection_core.py:868–919`; `A/context_query_probes.py:13–50` | Существующие traces + отсутствующие независимые original/host/retrieval_need probes; фактически видимый snippet | Body qualification, source policies, independent host distinctiveness; original admission-only не получает публичное coverage. Затем core квалифицирует актуальный trace ещё раз. |
| `A/context_selection.py:15–30,33–74` | Mandatory component contract → ProofObligation; current visible source → answer units | `best_local_proof` строит component witnesses. Это другой контракт, чем query matches или NeedContract disposition. |
| `A/_docs_context_projection_core.py:305–341,489–515,711–743`; `A/context_variant_retention.py:143–160,175–190` | Нормализованный источник → разные окна/blocks, merge attribution, expansion | Каждое новое окно requalify; сохраняются query/component/assignment witnesses; финальные coverage и snapshot привязаны к видимым bytes. |
| `A/_docs_context_projection_core.py:364–378,438–463` | Два ранних proposer: precedence, затем set, над `context_candidates`, отфильтрованными по explicit path | Их проверенные context variants входят в тот же finite selection pool; отдельная ветка учитывает novelty need IDs и budget. |
| `A/_docs_context_projection_core.py:665–673` | Только пустая выдача и `(_allow_context_hints or not fallback_ids)`; вход = **initially_ranked**, не список main survivors | `project_need_context_fallback` может вернуть контекст после main rejection. В условии нет strict-attribute veto. |
| `A/need_context_projection.py:70–108,109–155` | В каждом iterator candidate: ReferencePlan из root, identity/current raw window, decoded bundles → `compile_need_contracts(question, plan)` → ≤16 окон | На каждый contract из первых 12 вызывается classifier; не-blocked disposition и DTO budget разрешают yield. Query matches/IDs намеренно пусты. |
| `A/need_context_disposition.py:95–155,160–182` | NeedContract + тот же root plan + конкретные source/span/bundles | Повторная compile проверяет membership; затем root equality, identity/digest, qualification, exact/subject/condition, bundles; scalar typed witness → supported, иначе ≥2 body terms → retrieval_only. |
| `A/need_context_projection.py:158–184,188–215` | Три consumer одного iterator, но разные selection conditions | Precedence требует relation+verb; set требует focus/list completeness; late берёт первый yielded variant, формирует packet/snapshot. |

Дополнительные повторные попытки сохраняются: core hint retry при пустой выдаче
(`:674–689`) и при неполном primary packet (`:744–791`); facade recovery-budget trial
(`A/docs_context_projection.py:234–268`). После core есть finalization и joint/query-block
маршруты (`:282–289`); этот аудит не объявляет их взаимозаменяемыми или полностью проверенными.

### Почему похожие requalification не являются доказанной дубликацией

1. Retrieval chunk и cropped/expanded visible source — разные bytes. Нельзя переносить
   квалификацию full window на fragment по одному evidence ID.
2. Даже внутри `_requalify_visible_source` independent probe проверяется первоначально
   на snippet (`context_query_probes.py:34–38`), а core добавляет original exact terms,
   очищает aggregated lineage, передаёт path/section/snippet и затем применяет need
   witness/parent attribution (`_docs_context_projection_core.py:871–918,920–929`).
   Удаление второго qualifier — не простое common-subexpression elimination.
3. `qualified_query_ids` и `attributable_query_ids` различаются admission-only
   (`context_selection.py:255–277`). Component coverage тоже не заменяет эти множества.
4. `classify_need_context` заново компилирует **свой** NeedContract, проверяя, что
   supplied contract соответствует request (`:110–114`), и передаёт весь current
   contract set в bundle validation (`:153`). Удаление проверки с доверием входному
   DTO изменяет boundary; existing forged-contract control есть в
   `tests/docs/test_evidence_set_disposition.py:91–95`.

## 2. Измеренная повторная работа в need-маршрутах

**Факт исходников:** обе ранние функции вызывают `iter_need_context_variants`
с самого начала (`need_context_projection.py:165,191`). При позднем fallback iterator
вызывается снова (`:176`), но прекращается на первом yield. Между ними выполняются
ranking/selection и другие проверки. Early pool фильтруется по explicit paths, late
получает initially_ranked. Простая замена на один список может поменять порядок,
объём вычисления, diagnostics и provenance/mutation assumptions.

Для одного вызова iterator число полных компиляций равно
`C + Σ(V_i × min(K_i, 12))`: C кандидатов дошли до `:108`, K_i — contracts у кандидата,
V_i — реально классифицированные окна (не более 16). Первая часть — compiler в
iterator, вторая — compiler внутри classifier. Ранние потребители исчерпывают
iterator, late обычно читает только префикс. Ограничение candidate pool — первые 24.
Это локальная формула, не оценка всех компиляций public pipeline.

**Собственный read-only projection-seam контроль:** native core над synthetic
prepared source, построенным существующим `context_case`, без I/O/retrieval dispatcher.
Query неизменен: `How many retry attempts does ProjectRetryPolicy allow?`.
Во всех трёх случаях main contract: complete=true, один attribute `retry attempts`,
number/count. Need contract: mechanism / unknown / unresolved.

| Body под `# ProjectRetryPolicy` | Iterator / classifier compile | Classify | Late calls | Final |
|---|---:|---:|---:|---|
| `ProjectRetryPolicy allows at most two retry attempts.` | 2 / 4 | 4 | 0 | ok, literal сохранён |
| `The retry policy allows at most two attempts.` | 3 / 5 | 5 | 1 | main missing_attribute, ok через late, число сохранено |
| `ProjectRetryPolicy delegates retry scheduling decisions to OtherWorker.` | 3 / 5 | 5 | 1 | main missing_attribute, ok через late, числа нет |

Оба authority flags false; полный snippet и diagnostics сохранены в
`routes_evidence.json` → `numeric_route_observations`. Итоги одинаковы у baseline и
механического prototype. Это собственное подтверждение dataflow, **не новый native
public-ingestion replay frozen adversarial/module fixture**. Потеря relevant context
от отвергнутого A доказана прежним независимым reviewer; A здесь не исполнялся.

**Вывод:** наблюдается дорогое повторение внутри need-пути, но предложенное ниже
малое изменение его не уменьшает. Унификация component contract и NeedContract,
протаскивание `missing_attribute` как veto или удаление late — семантические изменения,
не допустимая чистка. Общая причина всех красных проверок из этого не следует.

## 3. Единственный эскиз: local roles reuse

Файл `A/context_query_probes.py:21–27`:

```diff
         text = str(query.get('text') or '')
+        roles = query_constraint_roles(text)
         probe = {
             'query_text': text, 'query_origin': query['origin'],
             'relation': query.get('relation'),
-            'exact_terms': list(query_constraint_roles(text).hard_exact),
-            'bound_subjects': list(query_constraint_roles(text).bound_subjects),
-            'retrieval_anchors': list(query_constraint_roles(text).retrieval_anchors),
+            'exact_terms': list(roles.hard_exact),
+            'bound_subjects': list(roles.bound_subjects),
+            'retrieval_anchors': list(roles.retrieval_anchors),
```

Diff **не применён** к продукту. Функция возвращает frozen dataclass с tuple fields,
не читает candidate, source bytes, budget или mutable plan
(`D/query_terms.py:159–182`). Один и тот же `text` между обращениями не меняется.
Все три `list(...)` остаются отдельными новыми списками. Получение roles остаётся
после skip existing/empty query ID и origin filtering, новых запросов не возникает.
Это переиспользование одного результата одного контракта, не слияние parser contracts.

Оговорка о точной эквивалентности: меняются cache hit statistics и число обращений
observer к helper; semantics распространяется на обычные dict/string production
inputs и native deterministic helper. Искусственный stateful monkeypatch helper,
exotic Mapping с побочными эффектами или Python exception-trace line numbers не
являются доказанной частью эквивалентности. Cache-info не используется в найденных
decision paths; быстродействие не измерялось.

**Что исчезает:** две записи одного вызова из source выражений; на каждый новый
eligible probe — 3→1 обращения к cached classifier, то есть −2 cache lookup.
**Что остаётся:** все ветки admission/selection, три need consumers, все current-byte
qualifications, membership/source/bundle checks, budgets, hint/recovery retries и
финальные coverage decisions. Новых DTO/parser vocabulary/cache не появляется.
Diff имеет 4 добавленных / 3 удалённых строки: это упрощение повторяющегося выражения,
а не сокращение количества строк или алгоритмических маршрутов.

## 4. Проверка эквивалентности и точные результаты

`routes_diagnostic.py` читает baseline function source, создаёт только описанный
prototype в памяти через `compile` + `FunctionType` с **исходным globals dict**.
`patch.object` временно подключает его к core и добавляет счётчики-врапперы; каждый
wrapper вызывает native function, контекст затем восстанавливает binding.
Сохранённые source hash/Python path находятся в JSON. Product bytes не переписываются.

- 38 входов × direct helper и visible-source seam = **76 пар**: original/host/need,
  exact и missing exact, subject/default/condition, RU, path, пустой text, weak lexical,
  foreign/stale/unsafe, existing trace, derived parent, alias, missing ID, два host lookup.
- **3 пары facade projection** на существующей compound fixture: existing traces,
  absent traces, foreign identity. Сравниваются целиком packet, snapshot и мутированный
  retrieval, включая diagnostics.
- **3 пары native core** для numeric route-таблицы выше.
- Итого **82/82 полных сравнений равны**, вызовы roles **285→95 (−190)**.
- Остальные счётчики равны: iterator starts **16→16**, iterator compiler **8→8**,
  classifier **14→14**, classifier compiler **14→14**, late calls **4→4**.
- Existing focused baseline tests: **26 PASS, 0.23 s**. Это не запуск tests на
  настоящем product patch; в pytest prototype не устанавливался.

Команды из собственного worktree:

```sh
DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/opencode/pr211-simplify-routes /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python routes_diagnostic.py

DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/opencode/pr211-simplify-routes /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest -p no:cacheprovider tests/docs/test_independent_query_probes.py tests/docs/test_evidence_set_disposition.py -q

git diff --check
git diff --exit-code
git status --short
```

Full CI, performance benchmarks, adversarial gate и A/B replay не запускались:
продуктового изменения нет. Диагностические входы синтетические, не holdout; 82 равных
результата не доказывают эквивалентность для всех возможных запросов. Обоснование
local-expression reuse опирается прежде всего на pure immutable return и одинаковый
аргумент; пробы проверяют поведение seams и отсутствие случайного изменения pipeline.

## 5. Инварианты, критерий принятия, необходимая проверка

Сохраняются: hard exact/subject/anchor роли, независимость host lookups, original
admission-only, policies identity/scope/freshness/risk, qualifiers каждого видимого
окна, component witnesses, source-bound snapshots, ordering/diagnostics, ≤800-token
budget и source cap, false answer/edit authority. Полезный heading/prose fallback
сохраняется вместе с прежним delegation-only допуском: улучшение качества не заявлено.

**Измеримый критерий** для этого единственного cleanup: для P реально создаваемых
independent probes число локальных вызовов roles равно P вместо 3P; payload, snapshot,
traces/diagnostics, rejection reasons и количество всех квалификаций/fallback должны
полностью совпадать. Бюджеты и coverage не меняются. Ожидаемое число исправленных
semantic failure IDs от такой чистки — **0**.

Если owner решит реализовать cleanup, необходимы повторение paired diagnostics на
реальном diff с baseline сохранённым отдельно, запуск существующих
`test_independent_query_probes.py`, `test_context_loss_boundaries.py`,
`test_discovery_independent_qualification.py`, `test_evidence_set_disposition.py` и
выбранных projection-seam cases; проверить source diff/line guards. Не добавлять
зеркальные tests на наличие local variable и не мигрировать frozen expectations.
Обязательные PR gates относятся к будущему SHA, этот отчёт их не заменяет.

Для значимого ремонта #211 вывод отрицательный: **без дополнительного доказательства
source/value qualification безопасно удалить один из смысловых маршрутов нельзя**.
Наблюдаемая повторная compile сама по себе не означает эквивалентность контрактов и
не даёт права распространять старый false-negative verdict на оставшийся context path.
