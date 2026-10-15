# Checkpoint перед compaction: DocAtlas admission selection V2

Дата исследования: 2026-10-12. **Этап завершён, включая независимый review. Новые исполнения не запланированы.** Последний запрос владельца — сохранить релевантный контекст перед compaction, не разрешение исправлять admission или запускать следующий эксперимент.

## Цель и решения

Владелец поручил исполнить `/tmp/opencode/docatlas-review-evidence/CONTINUE_ADMISSION_RESEARCH_V2_RU.md`: сопоставить B1, простой бюджетный отбор и mMiniLM до конечного ответа; условно проверить XProvence ranking-only против pruning. Не повторять старую матрицу моделей, не менять вопросы/корпус/эталоны, не включать default.

**Результат:** Mini имеет один подтверждённый membership gain на независимом HOLD01; production/default решение не готово. Главный следующий приоритет — upstream numeric/query-condition admission, затем точные цитаты и relevance/empty-source контракт. X-prune в текущей адаптации не рекомендован: summed submitted proxy +6.8%. Непроверенные методы не объявлены бесполезными. Новые работы только по новому запросу.

## Git и незакоммиченные изменения

Repo `/tmp/opencode/docatlas-compact-review`, branch `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`.
Четыре прежних изменения сохранены:
- `docmancer/docs/domain/original_body_discovery.py`
- `docmancer/docs/domain/ordinary_body_context.py`
- `docmancer/docs/domain/literal_context_admission.py`
- `eval/main_flow_comparison/run_extra40.py`

V2 добавил:
- modified `docmancer/docs/application/_project_docs_service_part03.py` — 2-line hook после qualification/admission-priority sort, до selected/retained packing;
- untracked `docmancer/docs/application/experimental_candidate_selection.py` — host-only ContextVar callback, выбирающий индексы существующих объектов. Callback отсутствует / B1 inactive => прежний путь. Callback не подключается wire аргументом и не является sandbox против произвольного Python-кода.

Не откатывать/не удалять эти файлы, не применять сохранённые patches повторно. Commit/push/merge/release/нового CI не было. `SOURCE_IDENTITY.json` и `SELECTION_V2.patch` сохраняют V2-only delta; patch SHA256 `9819bf978e8978d9bb3ddfaee8a385b445e8aa6614391bb8a70b8507b39f9755`.
Experimental admission `DOCATLAS_EXPERIMENT_ADMISSION=policy_candidates_v1` остаётся opt-in, default OFF.

## Где доказательства

Новый каталог: `/tmp/opencode/docatlas-review-evidence/admission-selection-v2/`.
Сначала читать:
1. `RESULT_V2_RU.md` — итог координатора; ранние формулировки pending внутри подробных разделов исторические.
2. `review/FINAL_REVIEW_V2_RU.md`, `review/REVIEW_RESULTS.json` — независимый primary verdict.
3. `review/X_FINAL_REVIEW_RU.md`, `review/X_REVIEW_RESULTS.json` — X paired verdict.
4. `UPSTREAM_BLOCKER_RU.md` — новая source-level реконструкция numeric ограничения.
5. `PROTOCOL_V2_RU.md`, `TRANSPORT_BINDING_RU.md`, `X_PROTOCOL_RU.md`, `FROZEN_SELECTION.json`.
6. `COSTS_V2.json`, `X/COSTS.json`, `LEDGER.json`, `STATE.md`, `RECOVERY_RECEIPT.json`, `DEFAULT_OFF_SMOKE.json`.

Raw: `public/`, `host/`, `scores/`, `prepares/`, `bindings/`, `X/`; independent audits/hashes/scripts и frozen corpus/cases/oracle в `review/`. Drivers: `run_public.py`, `score_mini.py`, `resume_remaining.py`, `run_x_pair.py`, `default_off_smoke.py`; saved-data counters `measure_costs.py`, `measure_x_costs.py`. Не запускать их заново автоматически.

Предыдущий этап: `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/`, особенно `RESEARCH_METHOD_AUDIT_RU.md`, `COMPACT_CHECKPOINT_RU.md`, `G_FINAL_REVIEW.md`. Старые outputs не перезаписывались.

## Исполнение и границы

Финальный ledger: **7 preparations,58 public context calls,56 neural forwards,40 host endpoint attempts:39 finished answers +1 UNKNOWN**.
- Primary:54 context /40 Mini forwards /36 host attempts /35 finished.
- Conditional X:2 дополнительных context /16 joint forwards /4 host /4 finished.
- Ancillary default-off:2 context /0 prepare /0 model /0 host.

Настоящий in-process public MCP dispatcher/SQLite; не installed stdio, не real client или production smoke. Все models CPU FP32, <=8 threads, без quantization/training/downloads/new installs. Host existing alias `openai/gpt-5.6-luna#medium` через `opencode api post /api/experimental/generate`, одна попытка, старый frozen `HOST_PROMPT_RU.txt` и прозрачная conversation-JSON wrapper adaptation. Backend revision/sampling/billing/provider HTTP retry counts UNKNOWN. Ни source-policy grant, ни answer/edit authority модельным score не создавались.

Upstream native acquired windows могут уже содержать SQLite page expansion второго authoritative read. Новая граница до downstream snippet packing/expansion, не до всей upstream expansion. Acquisition не переписано. Selectable pool требует существующие original qualified/literal traces и live same-call discovery binding. Complete original universe, selectable pool, exclusions, IDs/order/text/source bindings сравнивались across arms; Budget↔Mini равный k/packing. B1 original-delivery comparator сохраняет extra original candidates/merge/veto, не буквально тот же deduplicated selectable universe.

Mini scoring один раз на case, потом индексы подаются реальному public selector только при совпадении полного pool/universe. Actual orchestration Budget/Mini требует B1 capture +новый public selected read; это не измеренный inline single-call production ranker.

## Frozen данные и calibration

Независимый corpus:12 русских документов,6 calibration +8 holdout. Calibration seed_bank/stage_rigging; holdout ceramic_firing/tidal_ferry. Четыре семейства, не14 независимых доменов. Четыре isolated family projects +3 diagnostic fixtures =7 prepares.

Reviewer создал docs/cases/oracle до inference; executor использовал только calibration_labels, не holdout oracle для параметров. Рассматривали k∈{1,2,4}; **k=2** выбран по native provisional retention и подтверждён final public calibration до holdout. Никакой глобальный score threshold/abstention judge не добавлен.

Эффективная положительная calibration — только CAL04/CAL05 одного stage_rigging семейства:11 B1-delivered witnesses. CAL01/CAL02 уже пусты до selection. Поэтому guarantee — retention остатка, не полная достаточность6calibration. Calibration host не вызывался. Параметры после holdout не менялись.

## Результаты primary

| Ось | B1 | Budget k2 | Mini k2 |
|---|---:|---:|---:|
| Full exact-witness positive holdout delivery |2/6|1/6|2/6|
| Exact-supported frozen fact groups |11/22|9/22|11/22|
| Delivered required witnesses |14/25|10/25|14/25|
| Complete semantic positive answers |3/6|1/5 finished +1UNKNOWN|3/6|
| Honest all-irrelevant holdout refusals |2/2|2/2|2/2|
| Holdout empty-source negatives |1/2|1/2|1/2|

Mini retains14/14 B1 witnesses, не25/25 оригинальных требований. HOLD01: Budget cooling+incident теряет loading обязанности, Mini loading+cooling полный grounded ответ. HOLD02 все arms полны. HOLD03/HOLD05 пустые positives. HOLD06 sailing только, cargo facet отсутствует. HOLD07 B1/Mini семантически полны через universal sailing rule; frozen explicit cargo witness/two-document metric FAIL. Reviewer признал two-document ограничение oracle избыточным для semantic entailment; oracle не переписан, оси разделены. Budget HOLD07 answer UNKNOWN.

12 finished primary negative host answers правильно отказываются, unsupported affirmative0. Но CAL03/CAL06/HOLD04/OtherAPI/unrelated nonempty =>CURRENT_CONTRACT FAIL во всех arms; HOLD08 empty PASS. Итого1/6PASS,5/6FAIL на arm по этим negative scenarios. Compound/Setext/numeric старые controls здесь не переисполнялись.

Primary strict citation30PASS/5FAIL/1UNKNOWN;14PASS относятся к ответам без citations, не доказательство полноты. Q16 B1/Budget/Mini newline→space FAIL. Q46 Budget/Mini убрали Markdown `**`, тоже FAIL. Semantics этих diagnostic ответов правильная. Никаких quote repairs/retries.

Ошибок проверенных source/hash/span/generation/catalog/state/common pool/host input operands reviewer не нашёл. Не доказаны все ACL/access/consent/version denial состояния. Family scope выражен отдельными project identities; synthetic version2026.1 не подставляли в DTO: actual versionunversioned. Requested-version filtering NOT_TESTED; literal transport2026.1 UNSATISFIED.

## Upstream blocker

`ordinary_body_context.py:232–237` требует ВСЕ numeric literal terms question в одном body block; используется ordinary и B1 lanes. Source-reconstructed sufficient cause:
- CAL01/CAL02 query11/8 против source threshold9 =>empty;
- HOLD03 query12 и100 против source12/80/120/40 =>empty;
- HOLD05 query1,3 против source1,4 =>empty;
- HOLD06 cargo source не повторяет1,4 из question =>cargo discarded, sailing остаётся.

Raw наблюдает найденные windows/null admission/пустую или частичную выдачу; конкретная return branch реконструирована статически, не exact internal trace. Missing hard-exact=[]; это не canonical missing-exact failure. Более ранние причины возможны. Guard также защищает прежние priority7/7-9 negatives — нельзя просто снять его. Нужны отдельное contract решение и public positive/negative проверка numerical reasoning/multi-document contribution при неизменном source policy.

## X pair и стоимость

Только Q16/Q46 known diagnostics, pool10+6, тот же k2. X top2 memberships и final public source bytes совпали с Mini. X-prune — client exact-span view после validated X-rank parent, **не native pruned DTO**. Same joint forward masks; outside selected-native windows expanded content сохраняется, headings защищены, contiguous runs only, no decoded fake quotes/oracle rescue. Parent line ranges наследуются, exact child coords в sidecar — presentation limitation.

Оба facts/semantic answers сохранены. Q16 Xrank/Xprune strict citation FAIL; Q46 Xrank FAIL, Xprune PASS. Это не гарантированное citation исправление.
Submitted proxies Q16 1653→1479(−10.5%),Q46 1141→1506(+32%), сумма2794→2985(**+6.8%**). Source text −20.9%, но excerpt framing вырос. X16 forwards resident2.699s, cold2.904s, peak2.231GB. Mini40 forwards resident0.740s, two cold loads0.648+0.631s, peak≈844MB.

Holdout submitted proxies B15860,Budget5212,Mini5180: большую часть экономии даёт budget, Mini−32tokens сверх Budget; quality gain важнее token difference. Proxy неbilling. Actual per-case sums включают B1capture +selectedread +residentforward +host, cold separately; это lower bounds: tokenizer/process/import/alignment/serialization не распределены. Complete speedup/p95/provider price advantage не доказаны. Не складывать shared X parent/model costs как новые вызовы каждой paired строки.

## Recovery и default

Shell foreground deadline120s убил primary после44context/20host attempts. HOLD07Budget receipt STARTED backendcompletionUNKNOWN. Его не повторяли. Сохранились private /tmp projects/memberstores; recovery reattached same paths/generations, выполнил только10missingcontext+16unconsumedhost,0prepare/0score. Это interrupted/recovered run, не continuous benchmark. Private stores под sticky `/tmp` из-за guard на group-writable ancestors; artifacts/venvs под `/tmp/opencode`.

Два свежих default-off Q16/Q46 public запросa после нового hook снова пусты/insufficient_evidence/falseauthority, readstate unchanged. Это НЕ full40/50parity. Unrelated semantic negative bytes/hash сохранены, но path изменён `docs/store.md`→`docs/fixture.md`: не exact replay старой fixture.

## История V1, не смешивать с V2

V1 B0 delivery28/40, opt-in B1 delivery39/40, прежние28 сохранены,4relevance negatives нарушены, defaultoff parity подтверждена тогда. Это доставка фактов, не39generated correct answers. Q31 остаётся unresolved HumanEval vs HumanEval/LeetCode literal owner boundary. V1 experimental full diff уже в рабочей копии. Предыдущие109neuralforwards/21hostrequests НЕ включены в V2ledger. Сначала V1 назвали завершённым сравнением, затем RESEARCH_METHOD_AUDIT_RU.md исправил: закончена диагностика, но apples-to-apples end-to-end comparisons отсутствовали. V2 закрывает узкое selection сравнение, не production assurance.

## Дальнейшее действие

Ждать нового запроса. Если владелец поручит разработку: сначала отдельное numeric/query-condition contract решение и минимальный публичный сценарий с положительным numerical/multifragment вопросом +защитными negatives; затем honest exact citation extraction и relevance/empty-source contract; затем новая independent calibration/holdout и нужная regression. Не retune V2holdout, не повторять UNKNOWN ради красивого denominator, не добавлять X автоматически, не запускать старую model matrix.

AGENTS.md обязателен: новые проверки integration+; unit/privatehelper/AST/compile checks запрещены текущим заданием. Общие tests/fixtures не удалять в рамках этой работы. Не infer authorization for commit/push/default/deployment/новые provider/models. Подробные traces не дают PASS — его определяет independent final evidence.

Единственная independent reviewer session: `ses_ecfeee2dbffeq5JcGfOvA1CCU4`; завершена, может быть продолжена только при необходимости и новом задании. Context7 quota exceeded; Docs MCP source context unavailable, fallback code search использован. Это не blockers завершённого этапа.
