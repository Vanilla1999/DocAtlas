# Independent static review: минимальный selection patch

Дата: 2026-10-12. Статический review до inference; models/product/host/tests/import/compile не запускались. Прочитаны исходники, протокол и fixture/observer зависимости; выполнены только read-only `git diff`, `git status`, `sha256sum`. Implementation, frozen inputs и старые данные не изменены. Holdout oracle в этом review не открывался; holdout labels здесь не раскрываются.

## Решение

**Product hook: допустим как узкий host-only experimental extension point для последующего bounded public integration. Полное сравнение в предъявленном состоянии: PRE-INFERENCE BLOCKER.**

Это не обнаруженный обход source guard и не доказательство runtime PASS. Блокируют отсутствие законченного driver/schema binding, несовпадение frozen source-policy с фактическим fixture transport и неполная проверка common input universe для B1. Не запускать inference/host до явного устранения этих пунктов и фиксации orchestration. Product hook сам по себе не требует изменения retrieval/storage/validation.

Preparations по уточнению владельца: **5** — calibration, holdout, old main corpus, OtherAPI fixture, unrelated fixture; общий предел ≤8. В PROTOCOL_V2_RU.md:13 пока записано ≤4: это устаревшая локальная цифра, её следует явно согласовать до запуска, не считать разрешённую пятую preparation превышением общего лимита.

## 1. Правильная граница acquisition / selection / presentation

`_project_docs_service_part03.py:232–269` выполняет обычное acquisition и второй authoritative read с `query_expand=effective_expand or "page"`. `reference_context.prepare` и запись discovery выполняются в wrapper:224–230. Затем идут объединение candidates, cross-qualification и admission-priority sort:314–335. Hook:336–337 стоит **после всех этих шагов**, до `selected`/`retained` и downstream projection/snippet expansion.

Поэтому pool — native **upstream acquired** raw-bound окна, которые могут уже быть page-expanded. Это не обещание исходных коротких retrieval children и не изменение upstream acquisition. Protocol:4–6 корректно раскрывает границу. В отчёте нельзя приписывать экономию selection удалению upstream expansion или экономии уже выполненных acquisition reads.

Никакой observed/model score не передаётся в source authority, binding или coverage. Selector меняет только выбранное подмножество/порядок на этой границе; прежнее downstream ranking может затем изменить порядок. Корректный claim Mini здесь — ranking для выбора membership перед общей presentation, не гарантия сохранения Mini order в host input.

## 2. Source safety product patch: bounded acceptance

`experimental_candidate_selection.py:27–30`: при отсутствии callback либо active admission scope возвращается исходный candidates. ContextVar сбрасывается через finally:20–24. Wire аргумент для подключения selector не добавлен.

Pool:31–45 требует одновременно:

- существующий original trace с qualified=True либо literal admission;
- `original_body_discovery_binding` для exact question/body/metadata текущего call;
- отсутствие повторения `(source, chunk_index)` в selectable pool.

`original_body_discovery.py:82–164` проверяет live scope, root/question/catalog completeness, project/snapshot/member/catalog hashes, raw-document SHA, точный body/span и наличие receipt в текущем original read. Scoped handler закрывает receipts при выходе; сериализованные старые metadata сами не становятся новым receipt. Qualification и literal admission по-прежнему принадлежат настоящим компонентам.

Selection:46–54 принимает только уникальные int-индексы в диапазоне (bool отвергается), возвращает ссылки на существующие pool objects, не создаёт источники. `None` возвращает **весь исходный candidates**, не только deduplicated pool: B1 действительно сохраняет прежний downstream путь.

Source guards не удалены hook diff: lifecycle filtering и прежний selected/retained logic остаются в part03:345–418. Literal admission заново проходит canonical qualifier с source/window/owner/lifecycle checks (`literal_context_admission.py:248–300`); downstream projection/validation остаются прежними. `_call_with_snapshot` оборачивает реальные функции, в частности validator вызывается, а не заменяется результатом mock (`scripts/run_project_docs_self_host_gate.py:480–500`). Это observer boundary, не installed stdio или отдельный настоящий MCP client.

**Оговорка к слову immutable:** фактический `RetrievedChunk` (`docmancer/core/models.py:21–27`) — BaseModel без frozen config, metadata — mutable dict. Tuple(pool) делает immutable контейнер, не объекты/вложенные bindings. В представленном `run_public.py:85–94` callback только читает objects и возвращает индексы; write-back отсутствует. Таким образом safety допустима в доверенной host-only experiment роли, но не является sandbox/capability boundary против произвольного Python callback. Не заявлять enforced deep immutability. До/после hashes выбранных объектов полезны как проверка дисциплины callback; нельзя удалять source validators вместо такой проверки.

Pool admission не равен доказательству relevance/answer sufficiency. Hook сам не прогоняет полный final guard заново; гарантия допустимости публичной выдачи зависит от сохранённых downstream проверок и raw receipts. Ложно уверенный ответ на нерелевантном контексте и nonempty negative payload остаются разными FAIL.

## 3. Блокирующие вопросы harness / policy / comparability

### B1. Frozen policy не отображена в реальную публичную source-policy

`cases.json` фиксирует семейный scope и version `2026.1`; corpus содержит owner/access и семейный scope каждого документа. `run_public.py:97–98` игнорирует эти поля, всегда запрашивает `scope='project'`. `integrity:69–75` принимает только source version `''` / `version_binding='unversioned'`; проверяет принадлежность `documents` всего fixture, а не document_group текущего case. `runtime.write_project:68–71` пишет project-scoped каталог без данных frozen owner/version. При пяти preparations calibration/holdout каждый содержит несколько семейств: простой membership в documents не запрещает cross-family источник.

Это **не** доказательство source-policy product defect: продукт может корректно вернуть unversioned источник текущего проекта. Это расхождение обещанного evaluation контракта и реально проверяемого harness. Сейчас нельзя заявить, что family scope, frozen version и owner проверены публичным API.

До inference нужен отдельный явный transport-binding документ: какие frozen поля — annotation/domain identity, а какие реально выражены project/generation/catalog metadata; таблица относительный corpus path → canonical path/document identity/hash/actual scope/version и allowed document_group для каждого запроса. Не переписывать frozen JSON/labels или подставлять `2026.1`/owner в host provenance как будто их выдал public API. Если исходный frozen version/scope контракт остаётся буквальным, текущий unversioned/project harness его не удовлетворяет: это BLOCKER или соответствующий policy FAIL. Изменение policy интерпретации допускается только явно как отдельный контракт, не скрытая коррекция ради PASS.

При любой такой явно принятой адаптации минимум нужен per-case allowlist по corpus metadata с fail-closed на cross-group источнике, и проверка source bindings всех admitted pool windows, а не только уже projected sources. Annotation owner нельзя объявлять реальным bound structural owner; grounding action actors по исходному тексту оценивается отдельно.

### B2. run_public.py пока содержит helpers, не завершённый эксперимент

Предъявленный файл заканчивается ledger declaration:142. Нет main/driver, чтения corpus/cases/calibration_labels, создания пяти fixtures, prepare accounting, установки experiment admission в правильном live isolated environment, захвата pools, запуска scoring process, выбора/заморозки k и dispatch public/host calls. Импорт/прямой запуск этого файла сам по себе не исполняет описанный experiment.

`isolated_service` удаляет прежние DOCATLAS_* env при входе (`runtime.py:85–89`); opt-in должен задаваться host driver внутри действующего scope, иначе selector не вызовется и `len(observed)!=1` даст blocker. Это правильный fail-closed, но нужная orchestration ещё не предъявлена.

Ни fixture schema adapter, ни k-selection code нельзя считать проверенными здесь. Код ledger только увеличивает counters без hard ceilings; runtime/time/artifact watchdog, five-prepare count и import/execution boundaries будущего driver должны быть явными. Host unavailable/overflow/source mismatch должны останавливать соответствующую ветвь без retry/repair. Это необходимые условия bounded integration, не просьба добавить tests.

### B3. Common pool проверяется не полностью относительно B1

`public_call:86–91` хеширует selectable `rows`, но не `excluded`/complete original candidate sequence. B1 возвращает все original candidates; Budget/Mini — только original-admitted deduplicated pool. Поэтому квалифицированные lookup-only candidates, дубликаты и иные кандидаты, исключённые из pool, всё ещё могут участвовать в B1 downstream выдаче. Их изменение между calls не обнаруживает сравнение одного `pool_sha256`.

Протокол честно раскрывает extra B1 candidates, но тогда B1 — original delivery comparator с более широкой вселенной, **не** чистый all-vs-top-k comparator на ровно одном pool. Budget↔Mini остаётся чистой гипотезой эффекта ранжирования при равных pool/k/presentation, если raw подтвердит равенство.

До общего сквозного claim нужно сохранить complete original IDs/order/text/bindings и exclusions с original ordinal, проверить одинаковость полной upstream последовательности во всех requests, отдельно перечислить B1 sources вне selectable pool. Нельзя приписать Mini-vs-B1 разницу только ranker, если control использовал дополнительные windows. Если для обязательства B1 нужны excluded sources, это failure preservation бюджетной ветви, не повод добавить oracle rescue.

Dedup `(source, chunk_index)` также требует проверки: B1 дальше объединяет matches и выбирает higher-score duplicate:349–369/412–417, а pool сохраняет первый экземпляр. Нужно выяснить по raw, совпадают ли text/spans/metadata всех дублей. Если нет — эффект dedup/merge включить в comparator difference. Текущая product реализация не mint источник, но full input equivalence не доказана.

### B4. k-sufficiency на native pool не доказывает final delivery

Protocol:9 задаёт выбор минимального k по всем B1-delivered положительным обязательствам; protocol:13 предлагает offline exploration без дополнительных public calls. Offline union witnesses в native windows полезен для **provisional** выбора, но downstream projection/packing может пропустить условия или owner relations. Прежний аудит прямо требует финальной выдачи.

До holdout выбранный k необходимо подтвердить по реальным final public calibration payloads обеих бюджетных ветвей против сохранённого B1 delivery и calibration_labels. Если ни один operational budget не сохраняет обязательства, остановиться. Не объявлять достаточность raw top-k доказательством конечной выдачи. Не тратить скрытые calls и не выбирать k по holdout/Q16/Q46. Отдельно зафиксировать, требуется ли один k достаточный одновременно Budget и Mini; текущая формулировка этого не уточняет.

## 4. Статическая оценка score_mini.py

Допустимая bounded scoring схема при наличии проверенного capture: local pinned mMARCO Mini, FP32 CPU, ≤8 threads, одна пара question/window на forward, no truncation, >512 tokens отмечается explicit full-pool overflow, stable ties by original index. Hash-check assets и target.exists защита от повторного output есть. Pool целиком не обрезается до model budget; primary pool count >500 даёт стоп до inference.

Оставшиеся условия для driver:

- вход score_mini — отдельный **список capture cases**, не `cases.json` целиком: `[{id,question,pool_sha256,pool:[{id,text,...}]}]`;
- точно сверять score input hash/pool_sha256, row IDs/count/index/order и model revision, прежде чем выбирать indices; сейчас run_public принимает order извне и не делает эту связь сам;
- no forward для overflow case — честный blocker, не разрешение отбросить длинное окно и доранжировать остаток;
- учитывать failed forwards, cold load, timings и process RSS; проверка RSS после forward — наблюдение, не OS memory cap;
- общий ≤1000/≤60/≤80/≤8/2h/4GiB budget относится к будущему driver; файл score_mini сам его не обеспечивает;
- исключения после загрузки/между cases имеют receipt; ранее завершённые receipts нельзя потерять при ошибке. Pre-inference отказ import/assets/oversize должен также попасть в общий ledger.

Scoring JSON не должен содержать gold facts/spans/labels; к хосту уходят только final public snippets и настоящая публичная provenance. Host prompt остаётся общим, без адаптера исправления цитат; `host_call:125–137` этому соответствует по видимому code path, но допустимый owner/version transport ещё не решён (B1 выше).

## 5. Удобное чтение frozen schema без доступа к holdout labels

Executor может читать только:

```python
corpus = json.loads((review / 'corpus.json').read_text(encoding='utf-8'))
documents = corpus['documents']  # list, NOT dict[path] directly
cases = json.loads((review / 'cases.json').read_text(encoding='utf-8'))['cases']
cal = json.loads((review / 'calibration_labels.json').read_text(encoding='utf-8'))
cal_by_id = {row['id']: row for row in cal['cases']}
cal_witnesses = cal['witnesses']
```

Для двух новых fixture documents выбирать по `split`, затем строить `{doc['path']: doc['content']}` без изменения content. Сохранять относительные пути полностью, материализовать bytes UTF-8 как есть. Отдельно строить canonical absolute path map для integrity, поскольку public path не обязан быть относительным. Проверить raw file SHA against frozen manifest до prepare. Никакие annotations не индексировать.

Case поля: `id`, `document_group`, `split`, `scope`, `version`, `question`. Required facts намеренно отсутствуют в cases.json. Calibration labels: `cal['cases'][...]['required_facts']` содержит `fact` и `source_witnesses` — список witness IDs, не inline quote. Разрешать их через `cal['witnesses'][wid]['source_path'/'quote']`. Для ALL_IRRELEVANT calibration required_facts пуст, но это не автоматический PASS: применять expected_behavior и CURRENT_CONTRACT отдельно. Это описание schema, без вывода каких-либо holdout labels.

Calibration export содержит calibration-only facts/witnesses; oracle.json не нужен executor для выбора k. Нельзя читать полный oracle, фильтруя его после чтения: holdout leakage уже произошло бы. Выбранный k, candidate budgets, dedup/length rules, final presentation/prompt hashes, policy mapping и решение calibration фиксировать в отдельном dated/hash-bound receipt **до** независимого разбора holdout outputs. Сам manifest не раскрывает holdout per-case labels, но не заменяет процедурную изоляцию reviewer-only oracle.

## 6. Что требуется для снятия blocker и следующей raw review

1. Предъявить только минимальный driver/schema/receipt binding и явное решение frozen-vs-transport policy; inputs и labels не менять.
2. Согласовать 5 preparations и меньший точный workload; live generations не пересоздавать ради arms; budgets/stop conditions зафиксировать до inference.
3. Complete upstream sequence capture + одинаковость across arms; dedup/extra-B1 differences явно учитывать.
4. Первые bounded public capture calls допускаются после этих пунктов как проверка общей границы. До подтверждения policy/pool не запускать model/host. Public FAIL тоже расходует бюджет.
5. Calibration final delivery проверяется до holdout; затем frozen k и все raw inputs/outputs направляются той же независимой review-роли. Никакой итоговый PASS/production recommendation на основании этого static review не выдаётся.

Для raw review сохранить pool/excluded/original ordinals, исходные source bindings и state, selected/dropped IDs, scores, фактические public payloads, validation snapshots, окончательно отправленный host prompt и raw answer, calls/timing/length/RSS/errors. Проверять semantic answer, отношения/ответственного, exact citations, source-policy и CURRENT_CONTRACT раздельно.

## Зафиксированные reviewed bytes

| Файл | SHA-256 |
|---|---|
| `docmancer/docs/application/experimental_candidate_selection.py` | `d9c5babde7fbd238c9dc5d501969fbfe6c7ca4abfa058ebcd2de997afe26c883` |
| `docmancer/docs/application/_project_docs_service_part03.py` | `5e158284d8516796a977fddf56fb5afaf08c2d2bc8618ca3ba9178f9310e84bb` |
| `admission-selection-v2/PROTOCOL_V2_RU.md` | `89f13fd313c63292b80dce20b38954a588dcc1ff3ec63b2085d0762c37501653` |
| `admission-selection-v2/run_public.py` | `7ce9e29827aae256a184651e40e1016885189af5a5ce7acdb706471eaf91c86a` |
| `admission-selection-v2/score_mini.py` | `c645cc7622333709f5eac9ea46a4eaae253a23ecb47cda324e92c10898560dd9` |

Git diff hook — только import+вызов на этой границе. Четыре прежних экспериментальных изменения сохранены, новый selector untracked. Review относится к указанным bytes; последующие изменения требуют ограниченного delta review, не автоматического наследования допуска.
