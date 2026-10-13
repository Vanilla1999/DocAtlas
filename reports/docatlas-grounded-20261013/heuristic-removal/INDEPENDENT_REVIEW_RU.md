# Независимый reviewer F — предварительное заключение

**Статус: PENDING COMPARATIVE ADDENDUM; НЕ PRODUCT READY. Promotion запрещён.**
Дата: 2026-10-13. Reviewer не автор кода, вопросов или oracle. Выполнены phase1 и статическая phase2; никаких product/import/test/benchmark/model/network вызовов, делегирования или polling работающего coordinator. Использованы чтение файлов, stdlib JSON/hash/ZIP и офлайн расчёты. Единственная неуспешная попытка `python` завершилась отсутствием executable; далее только `python3` stdlib. Изменены только данный отчёт и `review/INDEPENDENT_SEMANTIC.json`.

## 1. Порядок независимой оценки

Сначала прочитаны AGENTS/OWNERSHIP, затем `review/BLIND_NEW20_PACKETS.json` и четыре оригинальных документа `eval/heuristic_removal_holdout/corpus/{click,requests,pytest,tox}/`. Все 20 question+delivered-text judgments с буквальными цитатами и source paths сохранены в `review/INDEPENDENT_SEMANTIC.json` **до** открытия mapping/oracle, worker reports и реализации. Tool-read длинных JSON snippets усекал отдельные строки; полный текст этих snippets дополнительно прочитан stdlib, а не восстановлен по oracle.

Это label-hidden semantic review, **не engine-blind эксперимент**: уже исходное поручение сообщало, что все пакеты baseline, поскольку ALL halted. Reveal подтвердил V0 для всех NEW01–NEW20. Не было независимой human validation или измерения generated-answer correctness.

### Phase1, неизменённые оценки

| Класс | Количество | После reveal |
|---|---:|---|
| Достаточно для всех документированных фактов положительного вопроса | 5 | NEW02–NEW06 |
| Частичная выдача | 6 | NEW07, NEW08, NEW09, NEW12, NEW13, NEW14 |
| Потеря поддерживаемой части | 3 | NEW01, NEW10, NEW11 |
| Вопрос содержит только неподтверждённые гарантии | 6 | NEW15–NEW20 |

«Partial» не означает полный PASS вопроса. NEW09/12/13 сохраняют документированную часть, но не обосновывают неподтверждённую гарантию. NEW07 теряет именно отношение dash → ignored failure; NEW08 обрывается после `environments were`, не доставляет missing-interpreter condition и CLI precedence. NEW14 показывает `:default: <empty list>` **для labels**, а не allowlist: переносить соседний default запрещено. NEW01/10/11 пусты вопреки наличию исходных фактов. Все непустые source rows имеют `version_binding=unversioned`; semantic sufficiency не сертифицирует version binding.

### Сверка с sealed oracle после сохранения phase1

Прочитаны все required-fact statements и unavailable obligations `sealed/oracle.json`; независимые выводы о relations/default/negation совпадают. Офлайн буквальная сверка witness sets дала:

- Положительные NEW01–08: все факты присутствуют у **5/8**; NEW01 0/2, NEW07 3/4, NEW08 1/2.
- Mixed NEW09–14: полная поддерживаемая часть у **3/6** (09/12/13); NEW10 0/1, NEW11 0/1, NEW14 1/2.
- Строгий frozen negative `sources=[]`: **2/6** (NEW15/17); **4/6 FAIL** (16/18/19/20 непусты).
- Совокупно documented facts **19/26**; это exact witness coverage, не 19 правильных ответов и не универсальная semantic accuracy.

Для неподтверждённых вопросов исходные тексты не содержат придуманных encryption/signing/rollback/isolation guarantees. Возвращение topical документа не является поддержкой этих propositions. Пустая выдача совместима с abstention, но packet без answer text не доказывает корректную сформулированную отказную реплику. Никаких gold/expectation/contract изменений для PASS не сделано.

## 2. Главный stop: версия — классификация по фактическому API

`stdio-receipts/EXECUTION_LEDGER.jsonl` фиксирует installed MCP `get_docs_context` call4 с `project_path` и `version="99.0.0"`. `call-2.json` и `call-4.json` содержат одинаковый source `docs/auth.md`, одинаковый snippet `# Auth\n\nAuthenticate with OAuth tokens.\n`, source identity/span/hash и `version_binding="unversioned"`. `answer_supported`, `answer_available`, `edit_ready` остаются false; source validity не выдана за answer authority. `stdio.log` действительно падает на неизменённой проверке empty sources для версии. Это **реальный FAIL frozen guard**, не path-matcher artifact.

Однако attribution «удаление нарушило ранее работавший project-version guard» не доказана:

1. Public schema `mcp/_docs_server_tool_data.py:574–606` принимает version вместе с project_path и обещает «Keep exact literals and explicit project/library/version/scope/path»; одновременно инструкция говорит «Current project: omit version; exact/historical versions only if explicit». Она не задаёт отдельную реализацию исторических local-project snapshots.
2. MCP `interfaces/mcp/context_tools.py:316–342` передаёт version в unified API; `_unified_context_service_part01.py:195–201` передаёт её в project context.
3. **Разделение реализации**: `_project_context_service_part01.py:89–104` строит `project_docs_kwargs` без version и вызывает `get_project_docs`; version используется в dependency/library `get_docs` на 215–221. `_unified_context_service_part02.py` имеет отдельный exact-library/version/fallback путь.
4. Независимое офлайн чтение baseline wheel ZIP (без импорта) подтверждает тот же local-project kwargs без version и ту же единственную функциональную передачу version dependency ветке. Diff не добавляет эту потерю параметра.
5. Final projection `model_visible_projection.py:497–504` активирует requested exact version только при retrieval exactness metadata; отсутствие forwarded project version не исправляется нижележащими canonical source checks.

**Классификация:** унаследованный local-project routing/API-contract gap (либо неподдерживаемая комбинация без явного отказа), плюс конфликт guard/public обещания с фактической поддержкой project-version. Не proven removal regression, не доказанный foreign/access breach, не допустимый exact-version PASS. Baseline runtime parity для этого запроса не запускалась и не заявляется. Нельзя объявить guard неправильным и переписать ожидание ради зелёного результата; потребуется отдельное owner contract решение и независимый сценарий поддерживаемого exact-library пути. Консервативный halt ALL обоснован: явное ограничение запроса не подтверждено end-to-end.

## 3. Guards: что реально исполнено и что не доказано

| Артефакт | Фактический результат | Граница |
|---|---|---|
| `guards.log` | collection error, 0 tests / 0 contexts | diagnostic shard setup, не качество продукта |
| `guards02.log` | lifecycle: 1 context, FAIL absolute-path matcher; restriction: 0 contexts, foreign snapshot setup FAIL | matcher искал absolute source, public paths relative |
| `restrictions.log` | после исправления multiroot setup: 1 context, FAIL того же matcher | module/version/foreign branches не достигнуты |
| `stdio-receipts/*`, `stdio.log` | 1 confirmed prepare, 2 context calls, 1 resource read; второй context version FAIL | installed wheel/stdio, не production client smoke |

Всего guards/stdio **4 context calls**, а не плановые 15 (13 integration +2 stdio), и не ceiling20. Confirmed prepare: 1 lifecycle +2 restriction setup +2 restriction-only +1 stdio = **6**, не «четыре успешных lifecycle проверки». Collection setup не считается продуктовым запуском. Поздние trace off/on/off, partial, stale/sync, unauthorized mutation, module/foreign isolation и read-only postconditions не прошли: ранние assertions прервали сценарии.

`GUARD_SNAPSHOT_AMENDMENT.md` первоначально ошибочно назвал lifecycle «real quality FAIL». Более поздний `SAFETY_STOP.md` корректно отделяет matcher от продуктового результата. Исправление offline relative matcher и multiroot snapshot setup сохраняет вопросы/факты/bytes; **не создаёт rerun/PASS**. Installed `call2` доказывает delivery OAuth факта, identity и false authority; `integrity.json` errors=[] относится к этому source, не ко всем невыполненным guard веткам. Сам raw SHA исходника отличается от projection `content_sha256`: последнюю нельзя ошибочно считать raw byte hash.

Дополнительный **статический blocker harness**, пока не достигнутый: `tests/test_heuristic_removal_public_integration.py:26–28` использует `dict(..., scope="project", **extra)`, а строка145 передаёт `scope="module"` через extra. Повторный keyword приведёт к TypeError до module context вызова. Это не продуктовая module-isolation регрессия. Reviewer ничего не исправлял и не запускал; будущая авторизованная проверка должна отдельно документировать такой measurement fix без смены expected scope.

Полные initial integration payload receipts в report tree reviewer не обнаружил; FAIL traceback не сохраняет полный sources. Поэтому достаточность optics/shutter не реконструирована из matcher FAIL. Никаких guessed PASS.

## 4. Удаление действительно bypass, но не абсолютное heuristic-free

### Q: acquisition

По source/diff `_sqlite_store_part03.py:197,307–386,587–609` Q имеет ранний путь: один quoted literal-token OR FTS5 запрос, `bm25(retrieval_children_fts)` без field weights, ascending native rank с deterministic ties, batch256 и resource admission 131072 stored estimated tokens /1MiB display bytes на lane. Ручной `_ranking_candidate`, weighted(6,2,.5), AND-first union, финальный-limit reserve и score penalties остаются control-кодом, а не новым скрытым Q scorer. `_strip_stopwords:561–563` несмотря на название не имеет omission dictionary: только word tokenization. Dispatcher ранний Q branch оставляет metadata postfilter, bypass diversity/truncation/expansion; lexical-only mode, не hybrid reproduction.

Это реальное removal соответствующих handcrafted adjustments, но **SQLite BM25 lexical engineering baseline**, не BEIR reproduction (Lucene k=.9,b=.4 против FTS5 1.2/.75), не Anthropic contextual retrieval, не reranker. Три существующих indexed поля, metadata/title prefixes, tokenization и native chunking сохраняются. Два root reads (общий и authority-filtered) — два фактических backend вызова с одинаковым question, не один batch256 total. Ограничения returned rows не ограничивают postings work/raw accounting/CPU/RSS. Finite batch и whole-row skips могут потерять witness. Q-only retains A/S legacy behavior: нельзя называть его полным removal.

### A: source-valid admission

`domain/evidence_qualification.py:240–307` возвращает source-only false qualification **до** body relevance parsing; исходные policy/reference checks не заменены keyword predicate. `literal_context_admission`, `ordinary_body_context`, `query_reference_binding` имеют отдельные A/ALL routes и live/raw/window recheck. `qualified=False`, covered IDs empty, `coverage_credit=False`, `relevance_unassessed=True`; в stdio видны false answer/edit authority и `source_only_heuristic_removal_v1`.

Это bypass whole-question overlap/exact/name/number gates, **не доказательство sufficient context**. Broad admission принципиально может ухудшить strict-empty negatives; frozen metric не переопределён. A-only оставляет legacy selection/assembly, некоторые non-original/library/ineligible lanes сохраняют старые gates. Сам canonical version check не может гарантировать сохранение отсутствующего upstream request binding.

### S: native selection/packing и поздняя wrapper граница

Source/diff подтверждают ранний S projector до facet-aware ranking; native occurrence dedupe вместо similarity/top-two/condition-priority. `_project_context_service_part01.py:121–190` bypass prefit/rerank/intermediate fitting; shared service bypass placeholder/low-value filter сохраняет lifecycle/taxonomy. `docs_context_projection.py:241–254` после attribution/source continuation возвращает terminal recheck `restore_native=False` **до** joint/query-block/recovery. В `experimental_context_finalization.py:523–620` native whole-row greedy fit не перебирает меньшие parent alternatives. Это закрывает C handoff blockers по коду, не runtime guard PASS.

S-only сохраняет acquisition/admission baseline; ALL объединяет три стадии, но halted и не сравнен. Native order плюс authority/supplemental lane architecture остаётся policy; greedy packing не SetR/optimal coverage/RAPTOR. Отдельные raw native spans могут потерять parent-only факты (включая известные P03/E01 риски); больший pool не гарантирует полезность.

### Остаточные активные правила и область доказательства

Upstream requirements/intent/lifecycle/support/completeness ещё вычисляются; `project_native_rank_context:60–96` сохраняет `_explicit_delivery_block`, exact-snapshot и lifecycle-recheck. `_explicit_delivery_block` читает `delivery_decision.deliverable=False`/confirmation, а не просто `qualified`; но весь upstream producer chain не доказан semantic-neutral через завершённые guards. Source policy/taxonomy, inferred lifecycle intent, locator resolution, input/renderer limits, finite resources и lane order остаются активными. Qualified re-attribution у S диагностическая, у S-only baseline admission всё ещё обязателен. Корректно говорить «specified candidate bypasses»; некорректно «все эвристики удалены из продукта». Default/control legacy сохранён, selector exact Q/A/S/ALL с unset/unknown OFF (`experimental_heuristic_removal.py:11–14`).

## 5. Freeze, execution counts и cost границы

Reviewer офлайн пересчитал SHA текущих frozen product inputs: **0 mismatches** относительно `CODE_FREEZE.json` для docmancer paths. Wheel hashes совпали с manifest: baseline `d62bb5f7…c6c97`, candidate `16fc2daf…021f`. `SOURCE_PATCH.patch` SHA `22f08748…255d6` совпал с `SOURCE_PATCH_MANIFEST.json`. Baseline audit сообщает 402 Python members /0 mismatches; data freeze 27/27 /0 mismatches. Исходные manifest сохранены; V2/V3/V4 документируют measurement-only changes, halt и interruption recovery. Это подтверждение неподменённых code/wheel bytes, не proof product correctness.

Авторитетный завершённый baseline `comparison-receipts/V0/SUMMARY.json`: **80 returned contexts**, 13 preparations, 0 resources, 0 models; installed baseline origin; 80/80 records `integrity_errors=[]`, database/files unchanged. Это публичный in-process MCP dispatcher с реальным storage и установленным пакетом, **не installed stdio для 80 кейсов** и не production smoke. NEW20 — только его baseline subset, никакого ALL improvement comparison.

Офлайн сумма baseline context durations 240.276s; summary total249.435s включает более широкую worker границу. Сумма raw payload tokens237620 не является billing/spend модели и не равна delivered packed cost. Raw baseline H20-R01 показывает12162 tokens: common12000 host packing нужно проверять по `packed.json`, а не объявлять raw baseline budget violation либо сравнивать raw с packed. Budget estimator смешивает offline o200k и UTF8/4, включает JSON attribution; cap equality не spend parity. Сравнительный latency/cost addendum пока отсутствует.

Первоначальный prospective план340contexts: V0=80, Q/A/S=60 каждый, ALL=80. После halt ALL сравнительный план **260 starts максимум**. `INTERRUPTION_RECOVERY.md` сообщает на checkpoint: baseline80 returns, Q45 starts/44 returns, один NOT_RETURNED **не replayed**; recovery только15 never-started Q IDs +VA60 +VS60, единый исходный1800s deadline. Если всё дальнейшее завершится, получится260starts/259returns, не340 completed и не260 successful. Этот отчёт **не читает текущие completion/status фоновых Q/VA/VS и не выдаёт их будущие counts за фактические**; ожидается единый coordinator addendum с завершёнными ledger/assessment/costs. Recovery roots/generations нельзя смешивать в source identity или silently substitute missing packet.

Grounded comparator0/blocked, generator0/not measured, unit0. Ни completed full five-arm comparison, ни superiority, ни answerquality, ни production readiness не установлены.

## 6. Решение и необходимые условия addendum

**Не продвигать candidate; сохранить legacy default/control, ALL halted.** Остановка не доказывает, что каждое изменение Q/A/S дефектно; наличие authentic snippets не доказывает safety всех request bindings.

Addendum допустим только по готовым offline материалам единственного coordinator: фактические starts/returns/errors/NOT_RETURNED на общий denominator; пары неизменённых V40/H20 input IDs; отдельные strict negatives, full/partial/missing facts, source integrity и read-only; raw versus packed costs, preparation/backend/resource counts, timing boundary и wall deadline; отсутствие tuning и posthoc oracle edits. NEW20 не имеет candidate measurements — не заполнять его вымышленными ALL FAIL/PASS/empty results. Версионный risk и недостигнутые guards остаются отдельными blockers независимо от сравнительной quality. Будущие разрешённые guard/contract действия — отдельное решение владельца, не скрытый replay ради PASS.
