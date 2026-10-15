# Итог независимого review primary selection → answer

## Решение

**Mini показал узкую измеримую пользу сверх Budget-control: продолжать целевое исследование выбора membership, но не включать experimental admission в default и не объявлять pipeline качественно готовым.** На HOLD01 при одинаковом pool/k=2/presentation Mini сохраняет полный grounded ответ, Budget теряет два обязательства. По сравнению с B1 Mini сохраняет доставленные обязательства при меньшем контексте, но не улучшает полноту уже пустых/частичных pools и получает дополнительный strict citation FAIL на Q46. Это не доказательство универсального превосходства или production safety.

Условный X pair теперь также независимо разобран: `X_REVIEW_RESULTS.json`, `X_FINAL_REVIEW_RU.md`. Его две известные диагностики не заменяют независимый holdout. Pruning сохраняет необходимые факты, но общий submitted-token proxy растёт: при этой exact-span/framing адаптации внедрение X-prune не обосновано. Это не опровержение метода или статьи.

## Что действительно выполнено и проверено

Primary: **7 preparations,54 public calls,40 Mini forwards,36 host endpoint attempts,35 законченных raw answers,1 UNKNOWN**. После conditional X: **7/56/56/40**,39 законченных ответов и тот же1 UNKNOWN. Endpoint requests — не измеренные provider HTTP calls или billing tokens.

Во время review появились ещё2 отдельные default-off public smoke calls без preparations/models/host; актуальный ledger теперь **7 prepares/58 context/56 forwards/40 host attempts**. Их saved outputs пусты, authority=false, состояния совпадают с исходным main fixture. Это только два diagnostic smoke, не full40/50 parity, не новые primary/holdout observations.

Review выполнен той же независимой ролью, которая написала corpus/oracle до inference. Сначала проверен `FROZEN_SELECTION.json` с k=2, затем открыт holdout oracle. Все35 primary raw answers прочитаны индивидуально; manual verdict каждого находится в `semantic_annotations.json`. Новых models/product/host/tests/runtime imports, retries или субагентов нет. Только stdlib saved-data audit; source/inputs/frozen labels не менялись.

`audit_saved_v2.py` → `RAW_AUDIT.json` независимо проверяет:

- hashes всех frozen files; original main corpus/questions hashes; seven prepare/catalog/file hashes и finite indexed paths;
- исходные вопросы, raw-document SHA, project/generation/member/catalog binding, exact char spans и structural owner bounds;
- полный original candidates sequence, selectable pool, exclusions с original ordinals, dedup, selected indices, Mini score input/row/order identities;
- равенство complete universe/pool/exclusions/state across arms на всех18 cases;
- exact final snippet bytes/lines, public-source vs validation snapshot equality и envelope SHA отдельно от full source SHA;
- source files/catalog/generation/stored rows неизменны до/после54 calls и across arms;
- фактический host model input соответствует public sources, generator prompt общий, окончательный transport wrapper/request hashes, raw response/parsed answer equality, source IDs и literal quotes.

**Ошибок перечисленных saved-source operands, common universe, score binding и host input boundary не найдено.** Это аудит сохранённых operands, не новое исполнение validators/SQLite и не доказательство всех source/access/version состояний. Live same-call receipt не переисполнялся reviewer; проверены статический механизм и записанные discovery fingerprints. Public read context нигде не получил answer/edit authority.

Артефакты: `REVIEW_RESULTS.json` — итоговые per-case verdicts/counts; `PRIMARY_RAW_HASHES.json` — hashes проверенного raw. Скрипт намеренно включает только B1/Budget/Mini; X проверен отдельно, его появление не меняет primary denominators.

## Calibration: честная, но фактически гораздо уже заявленных6 вопросов

- CAL01/CAL02: upstream acquisition содержит документы и нужные факты, но admitted pool и final sources пусты во всех arms. Нельзя объявить эти positive calibration задачи решёнными.
- Только CAL04/CAL05 дали positive targets:11 отдельных required witnesses, **одно предметное семейство stage_rigging**. k1 теряет обязательства; k2 сохраняет все11 в native Mini union и final public confirmation. Budget при том же k также сохраняет11.
- Полная frozen-witness доставка: **2/4 positive calibration cases**,9/16 обязательных fact groups, не4/4. CAL03/CAL06 — nonempty irrelevant sources, CURRENT_CONTRACT FAIL во всех arms. Host для calibration не вызывался.
- k=2 не выбирался по holdout labels и не менялся после holdout. «Retention targets все сохранены» верно, но не означает, что calibration доказала полную достаточность pool/selection для разных числовых задач.

## Независимый holdout: retention ≠ полный oracle

Шесть positive cases и два all-irrelevant. Frozen fact groups содержат все условия/отрицания/ответственных, не только ключевые слова.

| Ось | B1 | Budget k2 | Mini k2 |
|---|---:|---:|---:|
| Positive полный exact-witness delivery | 2/6 | 1/6 | 2/6 |
| Frozen fact groups с полным exact-witness support | 11/22 | 9/22 | 11/22 |
| Доставленные обязательные witnesses | 14/25 | 10/25 | 14/25 |
| Полные semantic positive answers | 3/6 | 1/5 завершённых +1 UNKNOWN | 3/6 |
| Grounded semantic fact groups в известных positive answers | 12/22 | 7/19 завершённых;3 UNKNOWN | 12/22 |
| Честные all-irrelevant host refusals | 2/2 | 2/2 | 2/2 |
| CURRENT_CONTRACT empty-source negatives | 1/2 | 1/2 | 1/2 |
| Ошибки actual project/hash/span/generation operands | 0 | 0 | 0 |

Mini удерживает **14/14 B1-доставленных positive holdout witnesses**. Но B1 сам доставляет лишь14/25 и11/22 полных fact groups. Два пустых positive cases дают vacuous retention, не full quality PASS.

### По каждому positive holdout

- **HOLD01:** B1/Mini полны. Budget выбирает cooling+incident, не loading, теряет C1/C2/C3/C4: запрет влажного дна/непригодность номера и мастер/контрольные12 часов. Его host честно отвечает partial, оставляя80/40/печника. Mini выбирает loading+cooling; полный ответ и обе стороны условий подтверждены точными источниками. Это чистая ranking membership польза, не host rescue или отличающийся бюджет.
- **HOLD02:** все arms полны: нельзя открыть по времени; печник отключает/записывает; электромеханик допускает после замены и измерения; неглазурованная партия приоткрывается≤120. Дополнительная выгрузка≤40 поддержана corpus. Budget prose «открывают» неточнее «приоткрыть», но точная supporting quote задаёт приоткрытие; разрешение полного открытия при120 не утверждается.
- **HOLD03/HOLD05:** все arms source-empty и honest insufficient. Full corpus позволяет ответить, но admitted pool не доставляет данные. Это upstream selection/admission loss, не доказательство плохого host или недостаточного ranker k.
- **HOLD06:** один из четырёх fact groups — капитан/включённая1,4/проверка причала — доставлен во всех arms. Незакреплённый груз, матрос/до посадки, запрет газовых баллонов отсутствуют; все raw answers honest partial. Не считать правильную первую часть полным решением.
- **HOLD07:** B1/Mini семантически отвечают на все вопросы по **универсальному sailing rule**, включая ноль пассажиров и обязательный причал. F1 «независимо от числа пассажиров» не содержит cargo exemption, F2 задаёт общий допуск после причала; F3 подтверждает спасательные средства. Это допустимое alternative entailment, не использование missing cargo из памяти. Но explicit F7 из cargo и frozen two-document delivery rule **не доставлены**: exact-witness/multi-document metric FAIL остаётся. Заявление нашего frozen oracle «каждый positive требует два документа» для этого вопроса оказалось чрезмерным структурным ограничением; oracle не переписан, а semantic и literal-delivery оси разведены. HOLD07_Budget raw answer отсутствует: UNKNOWN даже при идентичном Mini packet.

Не добавлялись unasked обязанности в semantic verdict. Frozen metrics сохраняют все исходные required facts; например CAL01 дополнительно задаёт подписанта листа, HOLD03 — ответственного за выгрузку. Это не основание изобретать новое semantic требование сверх вопроса. Здесь calibration host отсутствует, а HOLD03 вообще не получил источников, поэтому эти дополнительные детали не объясняют Mini/Budget разницу.

## Negatives, owner и strict citations

Все12 законченных primary negative host answers (HOLD04/HOLD08/OtherAPI/unrelated ×3) правильно отказываются, **unsupported affirmative answer0**. OtherAPI не присваивает DeliveryEngine поведение OtherAPI/recovery: source headings и actor bindings прочитаны правильно. HOLD08 missing содержит общий инженерный checklist, а не corpus-backed новую рецептуру или численные параметры; checklist не засчитывается фактической доставкой.

**CURRENT_CONTRACT:** CAL03,CAL06,HOLD04,OtherAPI,unrelated имеют irrelevant nonempty sources во всех arms. HOLD08 один остаётся empty. Итого **1/6 PASS,5/6 FAIL на каждом arm**, или3 PASS/15 FAIL по18 negative public calls. Правильный host отказ это не исправляет. Compound/Setext/numeric старые controls здесь не исполнялись, их прежние verdicts не заменяются этим срезом.

Primary literal citations: **30 PASS,5 FAIL,1 UNKNOWN**, но14 PASS — ответы без цитат: это не доказательство полноты. Среди21 законченного ответа с citations:16 PASS/5 FAIL. Failures:

- Q16_B1/Budget/Mini: смысл и оба поля completion верны, но newline+indent заменены пробелом. Дословность исходному source/fragment FAIL.
- Q46_Budget/Mini: сняты Markdown `**` вокруг «Два независимых PASS и паритет». Literal FAIL, semantic отрицание PASS верно. Q46_B1 выбрал более короткую exact цитату и PASS.

У всех35 законченных answers substantive утверждения не противоречат submitted sources; partial/insufficient positive answers при этом остаются **FAIL полной пользовательской задачи**, а не hallucination. Source-policy PASS не делает эти cases complete. Цитаты не исправлялись и не нормализовались ради PASS.

## Common universe, dedup и итоговые bytes

Во всех18 cases complete original sequence, pool и excluded ordinals одинаковы across B1/Budget/Mini. Дубликаты `(source,chunk_index)` имеют одинаковые text/span/source bindings; metadata/score/query traces различаются. Видимого удаления уникальных source bytes из-за first-item dedup не найдено. B1 всё ещё использует исходный candidates и прежнее merge/veto; Budget/Mini — deduplicated original-admitted pool. Это original-delivery comparator, не B1 rank-only comparator на абсолютно одной selectable universe.

Budget↔Mini имеют одинаковые final public source bytes/order на13/18 cases; различаются CAL03,HOLD01,HOLD04,Q16,Q46, а CAL06 отличается preselection order, но final bytes одинаковы. k2 не равен двум final sources: downstream packing/expansion может произвести3 sources (Q16) и включить факт вне узких выбранных native windows (Q46 Budget). Нельзя выдавать score/native-window retention за окончательную presentation; проверены реальные final bytes.

Source adaptation: actual family projects и hashes подтверждены; synthetic version2026.1 не выдана как public provenance. **Requested-version filtering NOT TESTED; буквальная transport version2026.1 UNSATISFIED.** Произвольные access/consent denial NOT TESTED. Нет production/installed-stdio/client/ACL assurance.

## Diagnostic corpus и recovery

Q16/Q46 original questions, source bytes и frozen spans совпали с прежним oracle. Оба facts/semantic answers восстановлены во всех primary arms; прежние archived FAIL не переписаны и current host ответы не объявлены парой старым из-за иной provenance.

OtherAPI: все пять relative paths и полные source bytes совпадают с old raw control. Unrelated: **text/hash совпадают, relative path изменён `docs/store.md`→`docs/fixture.md`**. Следовательно фраза «unchanged unrelated fixture» неточна. Это новый корректно bound диагностический instance той же semantic negative, не exact replay прежней fixture; old evidence IDs/project/generation ожидаемо другие. Новый CURRENT_CONTRACT всё равно FAIL, нарушение не спрятано.

Foreground120s deadline прервал HOLD07_Budget после44 public/20 host attempts. Recovery не повторяет consumed request: raw receipt остаётся STARTED/completion UNKNOWN. Доставлены только missing10 public и16 host, без preparations/scoring. Recovery source states/generations/full universes совпадают с B1 и исходными prepared fixtures. Это не единственный непрерывный benchmark run: process/environment materialization и timing origins изменились. UNKNOWN не удаляется из знаменателя, не объявляется FAIL или inferred PASS и не ретраится.

## Стоимость и практический следующий выбор

| Срез / actual мера | B1 | Budget | Mini |
|---|---:|---:|---:|
| Holdout source chars,8cases | 4282 | 3277 | 3061 |
| Holdout submitted prompt chars,8attempts | 22093 | 20017 | 19799 |
| Holdout DTO product token proxy | 4494 | 3660 | 3554 |
| Holdout public observed seconds | 0,917 | 0,680 | 0,663 |
| Diagnostic source chars,4cases | 19480 | 5600 | 6003 |
| Diagnostic submitted prompt chars | 32348 | 14711 | 14779 |

Mini40 FP32 CPU forwards: resident measured forward sum0,740s; **два cold loads**0,648+0,631s,11 calibration +29 evaluation, peak RSS≈844MB. Не накидывать обе загрузки на каждый future production request и не скрывать actual two-stage loads. DTO proxy, model tokenizer count, source chars, submitted prompt chars/o200k proxy и billing — разные меры. Host revision/sampling/tokens/billing UNKNOWN; single-pass latency и incomplete Budget host total не позволяют заявить p95 или provider-cost superiority.

**Whole-path accounting:** таблица public seconds выше показывает отдельный call каждой ветви, не полную experimental turn цену. Фактически Budget/Mini требуют первоначальный B1 capture **плюс** свой новый public read того же pool, а Mini ещё scoring; acquisition/qualification не стала бесплатной. Сохранённый `COSTS_V2.json` учитывает это. Reviewer пересчитал arithmetic по raw: holdout completed turn lower bounds B1=34,829s,Mini=35,790s; Budget=42,255s только для7 завершённых answers (сравнивать этот total с8 нельзя). Diagnostic lower bounds B1=24,298s,Budget=26,309s,Mini=22,331s. Эти sums исключают cold load и отдельно не распределённые tokenizer/process/import/serialization costs; это **lower bounds**, не complete latency, не доказанный inline one-call speedup. Shared initial capture считается один раз в workload, но включён одинаково при расчёте потенциальной Budget/Mini turn. o200k counts взяты из saved costs без повторного tokenizer исполнения; char/byte lengths и timing sums проверены независимо.

Большая часть экономии B1→Budget/Mini — **само ограничение отбора**, особенно на уже известных diagnostics. Mini сверх Budget имеет одну подтверждённую quality разницу HOLD01, не систематическое throughput преимущество. На независимом holdout Mini максимальный пакет всего865 source chars: большой самостоятельной pruning задачи здесь нет. Conditional X оправдан как ограниченная диагностика оставшегося Q16 context, не автоматический дополнительный stage для tiny holdout.

**Приоритет дальше — upstream admission/numeric contract и отдельная honest citation presentation, не увеличение k по holdout и не pruning отсутствующих фактов.** `UPSTREAM_BLOCKER_RU.md` верно разделяет observed empty/null admission от static reconstruction: all numeric query literals required в одном body block достаточно, чтобы отсеять11/8 против threshold9,100 против80/120/40,1,3 против1,4 и cargo facet без1,4. Более ранние причины также возможны; уникальная runtime numeric branch не записана. Нельзя исправить это простым снятием guard, защищающего старые7/7-9 negatives, без отдельного контрактного решения. Этот review ничего в продукте не исправляет.

Итог: обоснован следующий **узкий Mini engineering выбор**, не завершённый production gate. Один missing host comparator остаётся UNKNOWN, но не мешает установленному HOLD01 ranking gain; exact citations, relevance contract, upstream completeness и version axis не закрыты. Непроверенные методы не объявляются проигравшими.
