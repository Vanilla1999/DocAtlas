# DocAtlas admission V3 — ограниченный эксперимент

2026-10-12. **V3 завершён, включая независимый review: узкий admission gain подтверждён; default не менять.** Полные новые positive ответы B1 **1/4 → V3 3/4**, coordinate exact+semantic citations **4/4 PASS**, но strict empty-source negatives **6/9 FAIL** в B1 и V3. Полного multifacet/relevance/deployment решения нет.

## Пять итоговых вопросов

1. **Какие исходные задачи теперь решены?** Новый CAL01: тариф для14 страниц даёт38 рублей (10×3+4×2). Новый независимый holdout H02: путь через весы10≤12 допустим, прямой15>12 нет; диспетчер утверждает маршрут и проверяет переходы/расход. Known DIAG_HOLD03: равная масса через12 часов подтверждает просыхание; при100 градусах неглазурованную дверцу можно приоткрыть, выгружать нельзя, глазурованная остаётся закрытой. Это новые полные grounded host answers относительно B1. H01 с расчётом4+6=10≤12 уже решался B1, не новый gain. CAL02/refunds/cargo multifacet части остаются неполными.
2. **Какие прежние требования сохранены/нарушены?** Независимый audit всех57 packets/65 source rows не нашёл дефектов проверенных source/hash/span/generation/project/envelope/line/authority/state operands; complete original universe B1↔V3 совпал19/19. Priority7/7–9 во всех arms пусты; все authority flags false. Но строгие semantic negatives остаются6/9 FAIL B1/V3 (два новых и owner/compound/Setext/unrelated); H04 V3 ещё добавляет нерелевантный routes context к старому roles. Все8 фактических negative host answers корректно отказали в unsupported relation — это не исправляет empty-source FAIL. DefaultOff9/9 negatives пусты и12/12 ограниченных historical expectations совпали; не full40/50 parity.
3. **Чем обусловлена разница?** Новый scalar-label admission, без изменения retrieval/ranking/selector/packing/base prompt. Citation arm отдельно меняет generator schema/presentation/extraction; raw claims не ремонтируются, факты не добавляются. Ни candidate count, ни EXTRACTED не quality PASS.
4. **Оправдан ли Mini после исправления pool?** Здесь NOT_RUN: calibrated bounded-selection польза после patch не установлена. Новые семьи имеют по два source документа, upstream полнота compound вопросов не гарантируется. Включение Mini автоматически только добавило бы смешанный эффект; прежний V2 HOLD01 gain остаётся отдельным узким результатом.
5. **Что готово opt-in и что блокирует default?** Реализован и независимо проверен только узкий host-only `scalar_label_candidates_v3`; универсальная relevance/empty-source и безчисловая multifacet contribution не решены. Coordinate adapter дал4/4 точных поддержанных полных ответов на fixed packets, но это новый generator contract с почти2× prompt framing и неподтверждённой generic packet совместимостью. Ни default, ни deployment не разрешены.

## Основные независимые результаты

| Ось | B1 | V3 |
|---|---:|---:|
| Новые4 positives: полная public delivery/semantic answer |1/4|3/4|
| Новые required witnesses |6/19|17/19|
| Новые semantic fact groups в public выдаче |4/10|8/10|
| Calibration positive complete |0/2|1/2|
| Independent holdout positive complete |1/2|2/2|
| Known3 numeric diagnostics complete |0/3|1/3|
| Все9 strict empty-source negatives |3 PASS/6 FAIL|3 PASS/6 FAIL|

Общий **парный** positive base-host срез4new+3known:1/7→4/7. Это не7 независимых domains; known diagnostics не holdout. Frozen exact-witness и semantic оси сохранены отдельно. CAL02 остаётся1/3 fact groups,3/5 witnesses: тариф доставлен, бухгалтер и документы для спора отсутствуют. HOLD05/HOLD06 refunds/cargo не восстановлены. Ненумерический roles facet H02 уже допускался B1; новый режим не реализует общий cross-document contribution механизм.

## Дизайн и исполнение

C независимо заморозил 3 calibration/4 holdout на новых задачах печатного счёта и ориентированных маршрутов. Сохранил отдельные exact-witness и semantic критерии, владельцев, отношения и empty-source/refusal оси. Известные V2 числовые вопросы и Q16/Q46 — diagnostics, не новый holdout. Никакой настройки по holdout или переопределения oracle после outputs.

Контракт CONTRACT_DECISION_RU.md допускает source-bound unsigned scalar + общий буквальный label с отличающимся значением, без source/owner/hard-exact bypass. Numeric condition/relevance unassessed; coverage/answer/edit false. Безчисловые fragments не наследуют право доставки от другого документа. В новом fallback original full-raw syntax context не может скрыть sign/operator за краем source window; delivery window не расширяется. Старые Default/B1 numeric routes сохранены.

До исполнения C нашёл и помог закрыть конкретные static blockers: wrong envelope-hash operand в adapter, неполный authority guard, source-edge syntax gap, empty execution freeze и null-source handling. Их исправили **до первого public integration run**; никакого подбора по outputs или двух неудачных runtime repair циклов не было.

Один continuous run: **7 preparations / 57 evaluation contexts / 28 host endpoint attempts / 0 local neural forwards**, 136.946345699s. Все 28 raw answers сохранены, errors0, retries0, UNKNOWN0. Отдельно preliminary Docs MCP documentation lookup1 вернул insufficient_evidence/source_unavailable: полный stage58 context requests, внутри потолка80. Setup python alias error127 не потребил public/model/host budget и записан в ledger.

Настоящий in-process public MCP/SQLite на изолированных finite-catalog projects. Не installed stdio, реальный клиент или production smoke. Existing runtime/host переиспользован без downloads/installs/provider/model substitutions. Version — actual unversioned; explicit version filtering и arbitrary ACL/consent denials NOT_TESTED. Source-state проверяется по сохранённым operands, не объявляется глобальная неподвижность всех filesystem/SQLite bytes.

Host alias `openai/gpt-5.6-luna#medium`, single-attempt `/api/experimental/generate`, прежняя conversation-JSON wrapper. Backend revision/sampling/provider retries/billing/token usage UNKNOWN. Sources/provenance — только конечная публичная выдача, без gold facts/spans/labels. Citation ID/offset helpers относятся к тем же source bytes; extractor использует private binding sidecar, не передаёт whole-document oracle модели.

## Цитирование — отдельная adaptation

Fixed до outputs: V3CAL01/V3H01 parentV3 и Q16/Q46 parentB1. Base и coordinate host используют одно и то же публичное evidence content. Новый output содержит claims + source ID/диапазоны; extraction выдаёт точные исходные source slices, сохраняя raw ответ и исходные claims отдельно. Нет fuzzy matching, whitespace/Markdown repairs, добавления missing facts или retries. Независимый review: **4/4 exact extraction PASS и4/4 claim entailment/complete-answer PASS**.

На этих4 base-parent answers literal2/4→coordinate4/4: Q16 base заменил newline/indent пробелом; H01 V3 base склеил несмежные предложения, пропустив direct15 clause. Coordinate выбирает contiguous exact paragraphs с исходными условиями/Markdown. Все24 base answers:15 literalPASS/3FAIL/6N/A без evidence; третий FAIL — H01 B1 с той же склейкой. N/A не completeness PASS. Q46 base в этом run уже exactPASS. H04V3 refusal корректен, но status=complete с unasked missing detail имеет reporting WARNING, а не hallucinated authority grant.

Это не literal-quote PASS прежнего generator contract: модель перестала генерировать quote text. Сравнивается generator/presentation/client contract, не ranker. Q16/Q46 старые V2 failures не исправлены задним числом.

## Стоимость

Actual costs в COSTS_V3.json, не только source-text proxy. Каждый base B1/V3 turn имеет один public acquisition и host; citation использует тот же captured parent (shared acquisition однажды в workload), плюс assembly/reconstruction и отдельный host. Neural acquisition/scoring0. Prepare0.835779s, public17.372907s, host117.571351s, reconstruction/assembly4cases0.051683s: lower-bound sum135.831720s. Весь runner136.946346s; разница1.114626s не распределяется произвольно per-case. Это observed run, не p95 или production turn latency.

На **10 парных base cases** submitted prompt chars B1 **20866 → V3 25952** (+24.4%); UTF8bytes32588→39892. B1 содержит пустые/неполные evidence, поэтому это не equal-quality cost comparison. Host wall29.509→48.903s — единичные наблюдения разных outputs, не доказательство causal latency deterioration/acceleration. Totals двенадцати host requests каждого arm имеют разные дополнительные cases и напрямую не сравниваются.

На **4 citation pairs** base prompt chars **33660 →67217 (+99.7%)**, UTF8bytes51171→97428 (+90.4%). Text повторяется в raw field и line-coordinate framing, особенно дорог Q16 с полным B1 context. Это конкретный overhead текущей presentation, не опровержение exact extraction вообще. Token proxy NOT_MEASURED; actual billing tokens/backend/billing UNKNOWN. Дешёвое внедрение этой adaptation не доказано.

Все артефакты порядка25MB, существенно меньше4GiB. Models CPU limits не расходовались; neural forwards0. Cost timing sums lower bounds, не complete speedup/p95/financial advantage.

## Репозиторий и артефакты

HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`, branch `fix/main-flow-compact-evidence`. Дополнительный V3 delta только в original_body_discovery.py/ordinary_body_context.py. Прежние literal_context_admission.py, selector/hook и eval driver сохранены без новых изменений. SOURCE_IDENTITY.json и POST_RUN_IDENTITY.json подтверждают неизменность40 execution operands после runtime. V3_PRODUCT.patch сравнивает saved V2 baseline с actual tree; повторно не применять.

Основные: PROTOCOL_V3_RU.md, CONTRACT_DECISION_RU.md, EXECUTION_CONFIG.json, LEDGER.json, COSTS_V3.json, COMPACT_CHECKPOINT_RU.md. Raw: public/, host/, citation/, prepares/, bindings/, RAW_HASHES.json. Frozen inputs/oracle: review/. Independent final: RESULTS_V3.json (все57public+28host verdicts), INDEPENDENT_REVIEW_RU.md, review/RAW_AUDIT_V3.json, review/semantic_annotations.json. Проверены40execution/17freeze/397product identities и315raw hashes. Drivers сохраняются для воспроизводимости, **не запускать заново автоматически**.

Commit/push/merge/release/default changes/CI/tests deletion/unit/private-helper/AST/compile checks не выполнялись. V1/V2 raw evidence не перезаписывались. Этап завершён; новых запусков не запланировано. Следующий приоритет только по новому запросу: source-bound nonnumeric contribution и relevance/empty-source контракт; затем более экономное coordinate framing с отдельной проверкой claim entailment. Mini — лишь при самостоятельной calibrated bounded-selection задаче, не автоматически.
