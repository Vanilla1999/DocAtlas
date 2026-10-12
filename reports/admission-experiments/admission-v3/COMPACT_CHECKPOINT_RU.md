# V3 checkpoint

## Обновление после отдельного разрешения на commit

Владелец после завершения V3 поручил сделать commit в текущую ветку. Создан `6adc8e655fa69b5475adf613c8c446dd3a604b98` (`feat(docs): add opt-in admission and candidate selection experiments`) в `fix/main-flow-compact-evidence`: все6 сохранённых V1–V3 файлов, совпадающих с reviewed source identities. Рабочее дерево чистое. Push не выполнялся, default OFF, новых запусков не было. HEAD и отсутствие commit в разделах исследования ниже относятся к историческому pre-commit run; его source/code bytes не изменились. Citation adapter и evidence остаются вне git в admission-v3/.

2026-10-12. Новый запрос владельца: исполнить координатор + A admission/B citation/C independent review по переданному промпту, не только составить план.

## Текущее состояние

**Этап завершён, включая независимый final review C.** Никаких дополнительных запусков не планируется. Default/deployment не готовы и не изменены.

### Подтверждённые результаты

- Новые4 positive public/host complete: B11/4→V33/4; required witnesses6/19→17/19, fact groups4/10→8/10.
- Новые полные gains: CAL01 расчёт38 рублей за14страниц; независимый H02 сравнение routes10≤12 против15>12 + dispatcher/checks. H01 уже решался B1, не V3gain.
- Known DIAG_HOLD03 restored complete; DIAG_HOLD05 threshold часть restored, refunds missing; DIAG_HOLD06 cargo missing. Known complete0/3→1/3, не independent holdout.
- CAL02 tariff restored, dispute accountant/исходный заказ+счёт missing: full FAIL. Ненумерическое contribution общее решение не достигнуто.
- Все9 empty-source negatives: Default9/9PASS; B1/V33PASS/6FAIL каждый. Priority7/7–9 сохранены2/2. H04V3 добавил irrelevant routes к roles; binaryFAIL уже был уB1, это не улучшениеnegativeprecision.
- Все8 реальные negative host answers корректно отказали в unsupported relation; это не превращает непустой packet вPASS. H04V3 reporting inconsistency warning сохранён.
- Coordinate4/4 exact+semantic completePASS; base-parent literal2/4. Новый generator/schema/extraction contract, неrepair прежних raw. Все24base literal15PASS/3FAIL/6N/A; N/A неcompletenessPASS.
- Source-policy defects по проверенным operands0; all57packets/28answers independently reviewed,65source rows; complete B1/V3 universe19/19same. Default observer inactive — all-three universe equality НЕ доказана. Version filtering/ACL/consent deniedstates/installedstdio/client/production NOT_TESTED.

- Repo `/tmp/opencode/docatlas-compact-review`, branch `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`.
- Все V1/V2 незакоммиченные изменения сохранены. V3 изменил дополнительно только `docmancer/docs/domain/original_body_discovery.py` и `docmancer/docs/domain/ordinary_body_context.py`; исходные копии и hashes в baseline/BASELINE_IDENTITY.json. V3_PRODUCT.patch — delta относительно них, НЕ применять повторно.
- Новый host-only opt-in `DOCATLAS_EXPERIMENT_ADMISSION=scalar_label_candidates_v3`. Default OFF и прежний `policy_candidates_v1` сохраняются.
- Scalar+буквальный label допускает отличающееся source значение, source/owner/hard-exact/native guards не снимает. Numeric condition/relevance unassessed, coverage/answer/edit authority не даёт. Безчисловые contributing facets не решены. Strict empty-source ожидания не менялись.
- Полный original raw syntax context проверяется против sign/operator за краями окна; delivery остаётся внутри исходного разрешённого window. Static preflight исправления выполнены ДО runtime, не являются patch→integration циклами.

## Исполнение

- Один непрерывный настоящий in-process public MCP/SQLite run: **7 prepares, 57 contexts, 28 host attempts, 0 neural forwards**, 136.946345699s; errors 0, все 28 raw answers сохранены. Не installed stdio/client/production smoke.
- Отдельно 1 предварительный Docs MCP documentation lookup со статусом insufficient_evidence/source_unavailable: весь stage58context requests, не 58evaluation scenarios. Setup python alias error127 сохранён; product/model/host budget не потребил.
- 19 questions ×DefaultOff/B1/V3. Новые независимые 3 calibration/4 holdout на print_billing и directed_routes; 2 priority controls + дополнительные прежние controls/known diagnostics.
- DIAG_HOLD03/05/06 — прежние V2 вопросы/документы, известные diagnostics, не независимый holdout. Q16/Q46 — citation diagnostics.
- Host прежний `openai/gpt-5.6-luna#medium`, существующий single-attempt endpoint wrapper. Никаких retries/repair/new providers/downloads/installs.
- Mini/X не исполнялись. Новые families имеют по 2 документа, полнота multifacet pool не гарантируется; calibrated bounded-selection gain после patch не установлен. Старое V2 HOLD01 gain не отменён и не превращён в новое доказательство.
- 4 coordinate citation outputs EXTRACTED (V3CAL01/V3H01 parentV3, Q16/Q46 parentB1). Raw claims сохранены без исправлений, exact source slices отдельны. Semantic entailment/completeness — отдельный C review, EXTRACTED не quality PASS.
- Все 40 execution identities совпали после runtime. C исходный freeze 17 hashes неизменен. Никаких unit/private-helper/AST/compile checks, CI/commit/push/merge/release/test deletions.

## Стоимость

COSTS_V3.json: фактические acquisition/preparation/host/reconstruction, submitted chars/UTF8 bytes, parent reuse. На 10 сопоставимых base cases B120866 →V325952 prompt chars (восстановление контекста, не equal-quality cheapness). На 4 citation pairs base33660 →coordinate67217 chars: +99.7% framing overhead, не оправдание дешёвого deployment. Token proxy NOT_MEASURED; actual billing/provider tokens/backend/sampling UNKNOWN. Timing sums lower bounds; runner total136.946s — observed run, не p95/standalone speedup.

## Читать после compact

1. Этот checkpoint и STATE.md.
2. INDEPENDENT_REVIEW_RU.md / RESULTS_V3.json.
3. RESULT_V3_RU.md — итог координатора.
4. CONTRACT_DECISION_RU.md / PROTOCOL_V3_RU.md / EXECUTION_CONFIG.json.
5. review/EXECUTION_GATE_RU.md и предыдущие preflight reviews.
6. A_IMPLEMENTATION_RU.md / B_CITATION_CONTRACT_RU.md / citation_adaptation.py.
7. COSTS_V3.json / LEDGER.json / SOURCE_IDENTITY.json / POST_RUN_IDENTITY.json / V3_PRODUCT.patch.

Raw: public/, host/, citation/, prepares/, bindings/, RAW_HASHES.json. Runners: run_v3.py (НЕ запускать повторно), measure_saved_costs.py (saved-data only). Runtime assets из admission-full-20261012 переиспользованы, V1/V2 evidence не перезаписывались.

## Агентные сессии

- A `ses_ecfb247b9ffevfU5OlKmlSK4di` — implementation завершена.
- B `ses_ecfb212b8ffe9CLKjYS7mvPGYH` — adapter завершён и принят static review.
- C `ses_ecfb1de1affe82S4qB6lfS6Ciq` — final saved-data independent review завершён; audit errors0. Все3агента завершили назначенный этап.

Существующее permission на этот ограниченный workload исчерпано его выполнением; дополнительные experiments не запускаются автоматически. При CURRENT_CONTRACT FAIL default не объявлять готовым. Следующее действие — ждать нового запроса владельца. Приоритеты: nonnumeric contribution/relevance boundary, экономное coordinate framing; Mini только для самостоятельной calibrated selection задачи. Ни unit/private helper checks, ни repeated V2 matrix, ни UNKNOWNHOLD07 replay, ни oracle tuning.
