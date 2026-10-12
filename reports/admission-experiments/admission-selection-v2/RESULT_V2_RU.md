# DocAtlas selection V2 — результат сквозного эксперимента

## Решение после независимого review

**Mini полезен как ограниченный selector, но не устраняет основной upstream admission blocker. Default не менять. Внедрение текущей XProvence pruning адаптации не обосновано.** Независимый review завершён: проверены 39 сохранённых ответов, источники, common pools, bindings и состояния. Один прерванный host-запрос остаётся UNKNOWN, без повторения.

Итоговые независимые таблицы: `review/REVIEW_RESULTS.json`, `review/X_REVIEW_RESULTS.json`; разборы: `review/FINAL_REVIEW_V2_RU.md`, `review/X_FINAL_REVIEW_RU.md`.

| Проверка | B1 | Budget k=2 | Mini k=2 |
|---|---:|---:|---:|
| Полная exact-witness доставка positive holdout | 2/6 | 1/6 | 2/6 |
| Полные семантические positive ответы | 3/6 | 1/5 завершённых + 1 UNKNOWN | 3/6 |
| Честный отказ на all-irrelevant holdout | 2/2 | 2/2 | 2/2 |

Mini сохранил 14/14 witnesses, доставленных B1; сам B1 доставил только 14/25. Сохранение baseline не доказывает полноту задач. Проверенных ошибок project/hash/span/generation operands нет; это не assurance всех access/consent/version состояний.

Strict citations primary: 30 PASS, 5 FAIL, 1 UNKNOWN; 14 PASS — ответы без цитат, не доказательство полноты. Помимо Q16 whitespace FAIL, Budget/Mini Q46 удалили Markdown `**` из цитаты. Эти FAIL не исправлялись. По шести negative сценариям, включая calibration, каждый arm имеет 1/6 empty-source PASS и 5/6 FAIL независимо от правильного отказа хоста.

У X-prune факты/семантика обоих diagnostics сохранены, но сумма submitted prompt proxies **2794 → 2985 (+6,8%)**. Q16 citation FAIL остался; Q46 prune citation PASS — одно наблюдение выбора более короткой цитаты, не гарантированное исправление.

Уточнения независимого review: unrelated source bytes/hash сохранены, но путь изменён с `docs/store.md` на `docs/fixture.md`; это не exact replay старой fixture. Для HOLD07 universal sailing rule достаточен семантически, хотя frozen two-document/exact-witness metric остаётся FAIL. Oracle не переписывался, оси разделены. Реальная положительная calibration ограничена двумя задачами одного семейства, а не всеми четырьмя positive cases.

### Реально выполнено

- Три arms B1/Budget/Mini: один полный upstream universe и selectable pool, top-k budget одинаковый, checked source/projection/validation path настоящий public in-process MCP/SQLite.
- Independent corpus6calibration+8holdout на четырёх непересекающихся семействах; originalQ16/Q46 и2negatives отдельноdiagnostic. k=2 выбран и подтверждён на finalpublic calibration, до holdout.
- 7 preparations, **58 публичных context-вызовов** (54 primary + 2 X-rank + 2 default-off), 56 model forwards (40 Mini + 16 X), 40 host requests; 39 ответов сохранены, один HOLD07/Budget имеет UNKNOWN completion после shell deadline 120s. Его не повторяли. Recovery использовал прежние private stores/projects/generations без prepare/re-score; только оставшиеся calls.
- X-rank/X-prune: paired2known diagnostics, одинаковые native selectedIDs; ranking через настоящий publicpath, pruning — отдельно маркированная exactsource clientadaptation, не nativeprunedDTO.
- Unit/private-helper tests, CI, model downloads/installs, commits/push/deployment не выполнялись. Старые frozen данные и четыре прежних изменения сохранены. Новый product delta: экспериментальный host-only selector module + 2-line hook; callback NONE / default-off сохраняет прежний путь. Два настоящих default-off Q16/Q46 запроса после нового hook совпали с прежним empty-source результатом, состояние источников не изменилось. Полная default regression/parity НЕ запускалась.

### Что удалось установить

1. **Собственная польза Mini сверх просто top2 есть хотя бы в одном независимом положительном вопросе.** HOLD01 требует правил готовности сосуда и правил охлаждения; Budget выбрал охлаждение/неисправность и получил partialanswer. Mini выбрал готовность/охлаждение, получен completeanswer с реальными sources. Это эффект выбранных документов, не только случайное изменение ответа при одинаковом input.
2. **B1 всё ещё отбрасывает найденную информацию до ранжирования.** HOLD03/HOLD05 пусты при nonempty fullupstreampool, HOLD06 теряет cargo facet. Source-reconstructed sufficient numericguard требует всехquerynumbers в одномbodyblock. Это несовместимо с некоторыми вопросами о thresholdcomparison и multifragment условиях. Конкретная внутренняя branchне наблюдалась; границу/bytes/nulladmission rawподтверждает. См.UPSTREAM_BLOCKER_RU.md.
3. **Экономию нельзя приписать целиком Mini.** На8holdout submittedprompt proxies: B15860, Budget5212, Mini5180. Большую часть сокращения даёт самbudget; разницаMiniBudget32proxy tokens. ЦенностьMini здесь — сохранить нужныйfacet, а не гарантированно дополнительно уменьшить размер.
4. **Безопасный отказ хоста не исправляет empty-source контракт.** OtherAPI и unrelated выдают нерелевантныйcontext во всехprimaryarms. Currentcontract failures сохраняются отдельно от refusal.

### XProvence paired diagnostic

Native top2 memberships Xrank совпали с Mini в Q16/Q46. Дополнительной пользыranking на этих2knowncases не обнаружено.

| Case | X-rank submittedprompt proxy | X-prune proxy | Изменение |
|---|---:|---:|---:|
| Q16 |1653|1479|−10.53%|
| Q46 |1141|1506|+31.99%|

Rawspan content уменьшается в обоих случаях, но Q46 framing/provenance6excerpts увеличивает общийhostinput вместо2parentsources. Q16 nonverbatim quote вXprune сохраняет прежнюю whitespace-проблему. Не ремонтировалось. Окончательный semantic/grounding/citation verdict принадлежит independentreview. Это2diagnostics, не newholdout и не paperreproduction.

### Полная стоимость и ограничения

`COSTS_V2.json` включает настоящую orchestration: Budget/Mini исходныйB1capture +реальныйselectedpublicread +Miniresidentscoring +host. Нельзя выдавать предполагаемый будущий inlineonecallpath за измереннуюlatency. Coldloads отдельно; CPU-only; wallobservationssinglepass, неp95. Providerbackendrevision/sampling/billing UNKNOWN. Interruptedrequest promptcount есть, completedwall/billing unknown.

Суммы per-case времени — **нижние границы**, не полная latency: tokenization, model process startup/import, alignment и JSON/storage overhead отдельно не распределены. Полные scorer-stage wall и cold load сохранены отдельно. Неизмеренные расходы не считаются нулевыми; доказанного ускорения полного хода нет. Полные реально отправленные prompt proxies и число всех операций учитываются.

Calibration guarantee — сохранение **B1-delivered** witnessостатка, не достаточность всехисходныхзадач; дваnumericcalibrationpositives уже пустыдоselection. Это существенно ограничивает перенос выбранногок2. Sourcefamilycatalog/hash/generation/pool/finalbindings проверяются; version2026.1 — syntheticannotation. Actualtransport unversioned; requested-versionfiltering NOT_TESTED/literal2026.1transport expectation UNSATISFIED. Scopeisolation физическипоотдельнымprojects, не произвольныйnewMCPscope.

### Практический следующий приоритет

1. Отдельно согласовать границу sourcepolicy и numeric/owner/query-condition semantics; проверить полноценный multi-document positive и прежние hardnegatives черезpublicAPI. Не просто снятьguard и не крутитьscorethreshold.
2. Mini оставить первымranker-кандидатом: boundedselection с сохранениемусловий/владельца, без глобальногоprobabilityveto. После восстановленияnativepool он требует новой независимойcalibration, не retuneэтогоholdout.
3. Точноеcitations extraction — отдельнаяadaptation с rawanswer и claim-support проверкой, не исправлениерезультатовзаднимчислом.
4. Xpruning отложить: сначала экономичныйsource-span/provenanceframing и полноценныйqualitycontrol. НовыеQwen/CRAG/LLML/SWE matrixruns этимэтапом не оправданы.

### Evidence

`PROTOCOL_V2_RU.md`, `TRANSPORT_BINDING_RU.md`, `FROZEN_SELECTION.json`, `CALIBRATION_FINAL.json`, `public/`, `host/`, `scores/`, `X/`, `COSTS_V2.json`, `UPSTREAM_BLOCKER_RU.md`, `RECOVERY_RECEIPT.json`, `SOURCE_IDENTITY.json`, `SELECTION_V2.patch`. Не применятьpatchповторно поверхрабочейкопии. Independentreview files находятсяв`review/` и после завершения должны уточнить acceptancecounts/ограничения этогоотчёта.
