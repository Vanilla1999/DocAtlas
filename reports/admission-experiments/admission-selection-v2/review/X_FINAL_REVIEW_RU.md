# Independent conditional X pair review

## Решение

**Общая польза этой X-prune адаптации для внедрения не установлена.** Q16 submitted proxy уменьшается лишь1653→1479, а Q46 увеличивается1141→1506 из-за excerpt framing. По сумме двух diagnostics **2794→2985 (+6,8%)**, несмотря на уменьшение source text. Факты и semantic answers сохранены; один Q46 strict citation стал правильным, Q16 citation FAIL остался. Это узкий результат client-exact-span presentation, не опровержение XProvence или paper benchmarks.

X-rank не добавил selection качества относительно Mini на этих двух случаях: memberships и final public sources bytes полностью совпадают. Pruning не исследован на независимом holdout; k/threshold не подбирались по нему. Primary ranking gain и primary limitations сохранены отдельно в `FINAL_REVIEW_V2_RU.md`.

## Проверенные границы и данные

Прочитаны `X_PROTOCOL_RU.md`, `run_x_pair.py`, old pinned `D_xprovence_runner.py`, joint receipts/bindings/public snapshots/submitted inputs и все4 raw answers. Models/product/host/tests/import execution не выполнялись. `audit_saved_x.py` — исключительно stdlib saved-data reconstruction; результат `X_REVIEW_RESULTS.json`.

Независимо подтверждено:

- joint input — точные ранее acquired Q16/Q46 native pool10+6, вопросы/text/spans/source SHA/IDs совпадают с primary;
- complete original universe/pool/excluded ordinals настоящих X-rank public calls совпадают с primary, состояние источников/catalog/generation не изменилось;
- pinned runner hash/revision,16 EXECUTED FP32 CPU forwards, input hash, no pool overflow, token-selected masks=probability>.3 и sentence-rounding mask на сохранённых sentence spans=fraction>.3;
- retained/dropped sentences имеют точные оригинальные char/UTF-8 byte spans/hash. Это проверка сохранённых координат и mask arithmetic, не повторная tokenization/spaCy inference или neural воспроизведение;
- X-rank top2 Q16[0,2],Q46[3,4] равен Mini; final public source bytes равны Mini. Score и authority не смешиваются;
- X-prune использует те же joint masks/native IDs и один и тот же actual X-rank parent packet. Parent public source/span/hash/snapshot/authority checks PASS;
- отдельная **char-wise** реконструкция policy дала ровно те же excerpt runs: вне evaluated selected-native windows retain-all, внутри mask-retained sentences, все Markdown headings parent snippet сохраняются, только contiguous runs объединяются. Никакой oracle-aware closure/decoded repair не обнаружено;
- каждый excerpt text — exact непрерывный source run, ID/hash/parentID/parent span/source SHA совпадают; model input равен saved view, final transport wrapper и raw answer bindings верны.

**X-rank — real public selection/validation. X-prune — adapted client view после валидированного parent, НЕ fabricated public DTO и НЕ pruned native public validator path.** Native validation к child excerpt packet не применялась по дизайну. Sidecar задаёт точные child spans; inherited `line_start/line_end` в host provenance являются parent envelope ranges, не пересчитанными exact child line ranges. Это ограничение locator presentation, не повод выдать inherited metadata за новый validated DTO. В этой проверке source binding разрешается через parent и sidecar; deployment/API claim требует отдельного доказательства.

## Факты, ответы, owner и цитаты

| Case/arm | Required source span | Semantics / требуемые отношения | Literal citation |
|---|---|---|---|
| Q16 X-rank | PASS | PASS: оба completion поля, отличие от начала | FAIL: newline заменён пробелом |
| Q16 X-prune | PASS | PASS: duration_ms и trace_incomplete относятся к завершению | FAIL: та же newline-normalization |
| Q46 X-rank | PASS | PASS: одинаковый неправильный ответ не даёт PASS | FAIL: удалены Markdown ** |
| Q46 X-prune | PASS | PASS: явный запрет PASS и проверка обоих режимов | PASS: короткие exact source-run quotes |

Дополнительных unsupported affirmative claims в4 answers не найдено. Не требовали unasked подробного lifecycle/audit перечня как обязательного ответа. Q16 не обязан повторить request event identifiers; Q46 не обязан перечислить все state/scope audit поля. При этом исходные required spans/negations не изменены.

Q16 prune сохраняет exact поле-предложение и оба identifiers, но оставляет крупные public expansion blocks вне evaluated native windows целиком. Q46 pruning создаёт6 excerpt IDs вместо2 parent sources, включая standalone `*` и оборванный на границе run с «продуктовый». Эти bytes настоящие и не образуют fabricated цитату через gap; дополнительный framing/неполезный punctuation fragment объясняют overhead и не доказывают качественную semantic sentence closure.

Q46 exact citation improvement — наблюдение paired presentation на одном answer, не гарантированная функция ranker/pruner: X-rank и prune используют один score pass и одинаковые memberships, а хост выбрал иные короткие цитаты. Semantic correctness одинаковая. Не считать, что persistent Q16 failure опровергает ranking или source preservation.

## Стоимость: полностью submitted view, не только retained text

| Case | rank→prune source chars | source/excerpt count | snippet proxy | actual submitted proxy (o200k, не billing) |
|---|---:|---:|---:|---:|
| Q16 | 3627→2595 | 3→4 | 911→659 | 1653→1479 (−10,5%) |
| Q46 | 2175→1992 | 2→6 | 519→476 | 1141→1506 (+32,0%) |

Вместе source chars5802→4587 (−20,9%), snippet proxy1430→1135 (−20,6%), но submitted proxy2794→2985 (+6,8%). Actual submitted prompt chars10734→11152 (+3,9%); UTF-8 bytes16627→16262, что демонстрирует, почему chars/bytes/token proxies не взаимозаменяемы.

o200k proxies взяты из сохранённого `X/COSTS.json` с явно указанным codec; reviewer не переисполнял tokenizer. Длины действительно отправленных chars/UTF-8 bytes и source runs пересчитаны независимо stdlib. Billing и фактические provider token counts остаются UNKNOWN.

Joint forward CPU sum **2,699s**, cold load **2,904s** отдельно, peak RSS **2,231GB**. View assembly0,0090+0,0072s; reconstruction cost conservatively charged pruning arm. Host observed times Q16 rank6,186/prune3,220s; Q46 rank3,520/prune2,679s. Это четыре единичных endpoint наблюдения с UNKNOWN backend/sampling/billing: меньший latency не доказывает causally cheaper pruning, тем более при выросшем Q46 prompt.

**Accounting уточнение к X/COSTS.json:** `actual_public_requests=2` и `public_seconds` каждой строки включают прежний B1 capture **плюс** один новый X-rank call для данного case. Prune parent повторно не получает. Эти значения нельзя складывать по четырём строкам как8 новых public calls: X добавил только **2**. B1 capture уже был потрачен на primary; hypothetical turn comparison может включать shared acquisition одинаково в обе arms, но ledger его повторно не считает. Новые X-rank call times0,322/0,324s. Значения observed_actual_turn_seconds12,700/9,743 и7,293/6,458 включают старый B1 cost и исключают cold load; не представлять их как новые incremental execution times или production p95. Shared model pass/parent acquisition считаются один раз в actual workload.

После обеих фаз ledger **7 prepares/56 public/56 neural forwards/40 host attempts**,39 finished+1 UNKNOWN. X не повторял primary scoring/preparations и не чинил HOLD07_Budget attempt. Остаток разрешения не обязывает выполнять новые модели/сценарии.

Позднее появился ancillary default-off smoke ещё2 public calls: актуальный ledger58 context. Это не additional X calls/forwards, исходные X workload counts остаются2/16/4.

## Ограничения и следующий выбор

Known diagnostics, два вопроса одного прежнего документа, а не4 независимых задач. Threshold.3 и structural retention зафиксированы до X inference; это author joint forward с adapted source reconstruction/presentation, не полное paper reproduction. Лицензионные ограничения прежнего checkpoint не переоценены: только isolated authorized nonproduction evaluation, без legal/deployment assurance.

Synthetic version/filtering axis остаётся NOT TESTED/UNSATISFIED согласно общему transport mapping; ни X score, ни valid parent не дают новую scope/version/access authority. Pruned-native-DTO validation NOT APPLIED. Потерянные upstream facts ranker/pruner не восстанавливают. Независимый holdout Mini context ≤865 chars не создал большой pruning задачи; основная экономия уже достигнута ограничением selection.

Практически: продолжать узкое Mini membership направление при отдельном решении upstream numeric/query-condition контракта и citation presentation. **Не добавлять X-prune автоматически в pipeline на основании этого pair.** Если возникает реальная задача длинного контекста, нужен отдельно зафиксированный comparable large-input slice; здесь он не проверен и метод не объявляется глобально бесполезным.
