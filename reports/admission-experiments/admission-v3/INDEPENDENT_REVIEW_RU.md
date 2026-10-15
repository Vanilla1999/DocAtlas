# Независимый FINAL review V3: admission и coordinate citations

2026-10-12. **Узкий admission gain подтверждён; default включать нельзя.** На новом frozen corpus V3 увеличил полную positive delivery/ответы с **1/4 до 3/4** относительно B1. Однако один составной calibration вопрос остаётся partial, strict negative empty-source контракт нарушен в **6/9** negative scenarios B1 и V3, а координатная citation adaptation меняет generator contract и существенно увеличивает submitted prompt. Это не full multifacet/relevance/production readiness.

## Исполнение и независимость review

Один непрерывный coordinator run: **7 preparations / 57 public context attempts / 28 real host endpoint attempts / 0 neural forwards**, 136,946346 s, execution errors0. Все28 ответов завершены; UNKNOWN0. Дополнительно ledger отдельно записывает **1 documentation lookup** до experiment, insufficient_evidence/source_unavailable: общий context accounting58, evaluation denominator57. Setup `python` alias error127 не потребил product/host/model вызовов.

C создал новый corpus/cases/oracle до outputs, выполнил static preflight и теперь открыл private oracle для окончательных verdicts. Прочитаны индивидуально все28 original raw answers и supporting quotes/источники. `review/semantic_annotations.json` фиксирует manual judgments каждого ответа. `review/audit_saved_v3.py` и `review/build_results_v3.py` — только stdlib обработка saved artifacts; ни product/adapter/host/private-helper imports, ни runtime/tests/AST/compile/models/повторного inference не было. Inputs/oracle/FREEZE не менялись, дополнительных агентов/кейсов/retune нет.

Основные результаты: **`RESULTS_V3.json`** содержит все57 public и28 host per-case verdicts; **`review/RAW_AUDIT_V3.json`** — independent saved operand checks и cost arithmetic. Execution0errors не заменяет quality verdict ниже.

## Source/operand audit: ошибок проверенных operands не обнаружено

Независимо проверены:

- **40 execution frozen hashes**, **17 original C frozen hashes**, **397 product Python file identities после run**, совпадение config с RUN_RECEIPT и SOURCE_IDENTITY;
- полная inventory **315 raw artifacts** и их hashes; seven finite indexed-path/prepared allowlists, document/catalog/member hashes, реальные family project/generation/unversioned bindings;
- before/after states **всех57 public reads**, identical family state across cases/arms, generation_sources bytes/hash/document identities и сохранённые source/catalog file hashes;
- **65 final public source rows**: projected_source equality, canonical original-source envelope digest, full-document SHA, allowlist/path/project/scope/generation, source_of_truth, точные raw char spans и единственное соответствующее occurrence snippet с declared lines;
- все38 B1/V3 observer captures: complete original windows, pool/excluded ordinals и partition/dedup, immutable source bytes/order/bindings. **На19/19 cases complete original universe B1↔V3 совпадает**; admitted memberships могут различаться — это исследуемый admission эффект;
- structural owner raw text/containment; original question/root traces; native discovery fingerprint operands и local scalar-label spans, все query digit tokens, maximal original token/operator context, witness containment и unassessed/no-coverage flags;
- authority flags строго false во всех57 outputs; observer selected_indices=None, no selector/ranker membership intervention;
- все28 actual host messages/request-wrapper/request hashes/model identities, original question/public source operands, transport response/raw/parsed answer equality и отсутствие repair/retries;
- четыре citation packets/extractions: тот же parent source content/IDs, original claims, unchanged raw bytes, exact snippet/document char/UTF8-encoding/LF-line coordinates и quote hashes.

**Actual source-policy defect в перечисленных saved operands не найден; impacted source-policy BLOCKED cases0.** Native fingerprint проверен как сохранённый operand, live receipt/qualifier/validator не переисполнялся. Не объявляются доказанными произвольные ACL/consent/foreign-version denial состояния. Complete-universe observer DefaultOff не активен: его `pools=[]` не является наблюдением пустого universe и не даёт all-three-arm universe equality. Его actual final sources/snapshots/state всё равно проверены.

Temporary project/catalog hashes и source rows сохранялись до/после public reads; отдельного live store reopen или after-host project-state replay review не делал. Host имел text-only endpoint input без tools, но backend capabilities/provider internals не измерялись. Это настоящий **in-process public MCP/SQLite** experiment, не installed stdio/real client/production smoke.

## Новый frozen corpus: delivery и полный смысловой ответ

Четыре positive scenarios: 2 calibration печатного счёта, 2 independent holdout направленного маршрута; 19 required exact witnesses и10 semantic fact groups. Общий source corpus не получает synthetic version: actual binding unversioned.

| Ось, только4 новых positives | DefaultOff | B1 | V3 |
|---|---:|---:|---:|
| Полная exact-witness delivery |1/4|1/4|3/4|
| Полная semantic public sufficiency |1/4|1/4|3/4|
| Delivered required witnesses |4/19|6/19|17/19|
| Supported fact groups в public sources |2/10|4/10|8/10|
| Полные base-host ответы |NOT_RUN|1/4|3/4|

Exact witnesses и semantic sufficiency оценены отдельно; в этих четырёх случаях final sufficient sources и полный frozen witness набор совпадают. Не вводится произвольное требование числа документов.

- **V3CAL01:** B1 empty/insufficient; V3 доставляет тариф и host считает **10×3+(14−10)×2=38**, показывает обе части суммы. Query14 не требуется буквально в source threshold10. Новый полный admission gain.
- **V3CAL02:** V3 тоже доставляет тариф/38 рублей, но **disputes source отсутствует**. Бухгалтер и передача исходного заказа+выданного счёта не доставлены и честно missing у host. **Full semantic/exact-witness FAIL**,1/3 fact groups,3/5 witnesses. Это не исправленная multifacet задача.
- **V3H01:** уже DefaultOff получает canonical qualified routes; B1/V3 имеют идентичные routes+roles. **4+6=10≤12** полно в обеих host ветках. Это НЕ admission gain V3; ненужный roles context B1 не становится доказательством расчёта.
- **V3H02:** B1 доставляет только roles и отвечает partial: dispatcher/checks есть, сравнения путей нет. V3 добавляет routes при том же original universe, сохраняя roles: **через весы10≤12**, прямой15>12, утверждает диспетчер движения, проверяет направленные переходы и расход. **Полный independent holdout gain**. Сохранение ненумерического facet здесь обеспечено прежним B1 пути roles, а не новым general cross-document contribution механизмом.

Calibration full delivery0/2→1/2; holdout1/2→2/2. Семейства всего два и набор мал; нет claims об универсальном numerical/multifacet reasoning. Параметры/вопросы после outputs не менялись. Base ranking/presentation/host prompt неизменны; gains относятся к добавочному **admission**, не Mini/selector/pruning.

## Known V2 diagnostics — отдельно от нового holdout

| Case | B1 base-host complete | V3 base-host complete | Итог |
|---|---|---|---|
| DIAG_HOLD03 |FAIL|PASS|Доставлены loading+cooling; одинаковая масса через12 часов,100≤120 приоткрыть неглазурованную;100>40 не выгружать;100>80 глазурованная закрыта.|
| DIAG_HOLD05 |FAIL|FAIL|V3 правильно даёт1,3<1,4/отмену независимо от пассажиров, но refunds/captain record/cashier/ticket/full cost отсутствуют.|
| DIAG_HOLD06 |FAIL|FAIL|B1/V3 sailing одинаков; captain inclusive1,4/pier есть, cargo/матрос до посадки/газовый запрет отсутствуют.|

Known numeric full delivery0/3→1/3; required witnesses1/11→6/11. На общем семисценарном positive base-host срезе (4 новых+3 known numeric) complete **1/7 B1→4/7 V3**. Q16/Q46 base host запускался только B1, owner/unrelated host толькоV3 — поэтому все12 B1 и12 V3 host aggregate denominators/costs не являются полностью парными.

Не требовали unasked деталей ради FAIL: например вопрос DIAG_HOLD03 не спрашивает имя выгружающего печника; отсутствие этого имени в answer не отменяет правильные запрошенные разрешения/запреты. Его источник/witness всё равно отдельно включает печника и точно доставлен.

## Negative empty-source ≠ honest host refusal

Всего9 negative public scenarios на arm: 3 новых плюс old priority7/range7-9/OtherAPI/compound/Setext/unrelated.

| Ось | DefaultOff | B1 | V3 |
|---|---:|---:|---:|
| Все9 strict empty-source negatives |9/9 PASS|3/9 PASS,6 FAIL|3/9 PASS,6 FAIL|
| Три новых negatives |3/3 PASS|1/3 PASS,2 FAIL|1/3 PASS,2 FAIL|
| Old priority7 и7-9 |2/2 PASS|2/2 PASS|2/2 PASS|

V3CAL03 остаётся empty во всех arms. **V3H03/V3H04** имеют irrelevant nonempty contexts B1/V3: shelf12 и generic/dispatcher rules не дают priority-savings или controller route-approval relation. **V3H04 V3 добавляет routes поверх старого roles**: binary empty-source FAIL уже был у B1, но дополнительная доставка не является negative quality gain. Новый scalar-label fallback не отличает main relation/owner entailment.

OtherAPI/compound/Setext/unrelated также остаются nonempty CURRENT_CONTRACT FAIL B1/V3. Source/hash/structural-owner validity не означает semantic owner/relation correctness. Setext control может доставить generic raw body вместе с heading; heading/body distinctions gate не решают empty-source semantic relevance сами по себе.

**Все8 законченных base negative host answers честно не дают запрошенный unsupported affirmative relation:8/8 refusal PASS, unsupported grant/численная скидка/priority очередь0.** Это не чинит12 failed negative public calls. V3H04 host отвечает «никакая подпись», правильно различает dispatcher route и controller inventory; дополнительный10≤12 вывод supported routes. Его `status=complete` одновременно с missing unasked dispatcher-signature form — reporting inconsistency, отмеченная WARNING в annotations; не требуем эту неподанную владельцем detail как обязательный факт и не превращаем корректный отказ в grant hallucination.

DefaultOff на12 legacy/known cases совпадает с ограниченными исходными ожиданиями: short fact delivered, six legacy negatives и Q16/Q46/numeric diagnostics empty. На всех19 final DefaultOff outputs источники только в H01/SHORTFACT; all9 negatives empty. Это **limited baseline-expectation slice**, не парный повтор baseline implementation и не full40/50 default parity. DefaultOff host NOT_RUN.

## Literal citations и coordinate adaptation

Все24 base answers разобраны: **15 literal PASS /3 FAIL /6 N/A без evidence**. N/A refusal/empty evidence не является completeness PASS.

Literal FAIL:

1. **Q16_B1:** newline+indent между `duration_ms` и `trace_incomplete` заменены пробелом. Semantic fields верны, quote не дословна.
2. **V3H01_B1 иV3H01_V3:** host склеивает route-edge предложения с sum rule, пропуская находящееся между ними предложение о direct15. Meaning/arithmetic верны, concatenated quote не substring источника.

Q46_B1 literal PASS в этом новом run: ответ выбирает exact clauses и отрицание сохраняется. Старые V2 quote failures не переписываются новыми выводами.

**Coordinate4/4 exact extraction PASS и4/4 independent claim entailment/complete-answer PASS.** Сопоставлены конкретные original claims с поддерживающими exact quotes:

- V3CAL01 parentV3: whole tariff paragraph поддерживает38=30+8; question задаёт14;
- V3H01 parentV3: contiguous graph/budget paragraph содержит оба edges, direct clause, sum и budget rules; claim10≤12 корректен;
- Q16 parentB1: full completion/start paragraph сохраняет newline/indent и оба дополнительных fields;
- Q46 parentB1: exact passage сохраняет `**Два независимых PASS и паритет.**`, независимые проверки и «одинаковые неправильные ответы не дают PASS».

В каждой паре **те же public source IDs/text/provenance**, packet/hash/offsets/full-source bindings подтверждены; не было fuzzy alignment, repair исходного raw, добавления facts или новых public sources. Claim text unchanged после extraction. Base-parent strict2/4→coordinate4/4 — узкий диагностический результат **нового generator+presentation/extraction contract**, не гарантированное исправление того же старого generator, не ranking/admission gain и не automatic semantic benefit произвольных spans. Все четыре выбранные заранее packets оказались совместимы с narrow whole-reference-span adapter; generic merged/trimmed packet support не доказан.

## Actual costs и accounting

Независимый пересчёт всех COSTS rows по actual raw requests/receipts:

| Timed stage | Actual count | Seconds sum |
|---|---:|---:|
| Prepare |7|0,835779|
| Public context |57|17,372907|
| Host endpoint |28|117,571351|
| Citation assembly+reconstruction |4|0,051683|
| **Observed lower-bound sum** | |**135,831720**|

Whole continuous run136,946346s; difference1,114626s не распределяется произвольно по cases. Assembly/reconstruction конкретных4 citation stages измерены и посчитаны один раз; generic COSTS `limits` wording о reconstruction «not separately timed» следует читать с этой оговоркой. Остальные process/import/serialization/tokenization/transport/billing детализации UNKNOWN; stage sums lower bounds, не complete production turn latency. Baseline/citation parent public calls не дублируются в actual workload, но новый host каждой ветки посчитан отдельно.

Для4 строго парных citation host inputs:

| Pair | Base chars→coordinate chars | Base UTF8 bytes→coordinate bytes |
|---|---:|---:|
| V3CAL01 |2229→2758|3404→3910|
| V3H01 |3128→4793|4780→6868|
| Q16 |21156→46517|32477→67966|
| Q46 |7147→13149|10510→18684|
| **Sum** |**33660→67217 (+99,7%)**|**51171→97428 (+90,4%)**|

Helper lines повторяют текст и увеличивают prompt; savings не подтверждены. All28 submitted prompts146381chars/218735UTF8bytes. Backend revision, sampling, actual provider HTTP retries/counts, billing tokens/prices UNKNOWN; chars/bytes не выдаются за tokens. Neural forwards0; Mini/X/training/downloads отсутствуют. Одно наблюдение не доказывает p95/скорость/денежное преимущество.

## Окончательный вывод

**Продолжать только целевое engineering исследование admission**, сохранив opt-in/defaultOFF и source-policy границы. Подтверждены новые CAL01/H02 complete gains и known HOLD03 восстановление; HOLD01 не новый gain. Scalar-label правило не решает nonnumeric contribution для CAL02/refunds/cargo и не решает strict semantic empty-source. Coordinate citations дают точные поддержанные quotes на4 фиксированных parent packets, но меняют generator contract и почти удваивают submitted chars.

Не объявлять этот run production/default gate, не retune frozen holdout и не добавлять Mini без самостоятельной bounded-selection задачи. Никаких новых executions/patch tuning требуется из этого review автоматически. Все FAIL/N/A сохранены в machine results; отсутствующих UNKNOWN не придумано. Финальный review завершён, дальнейший runtime только по новому отдельному разрешению.
