# Первый budget-aware set-selection pilot: BLOCKED

Дата проверки: 2026-10-14. Репозиторий `Vanilla1999/DocAtlas`, PR #211 открыт,
не merged; base `main`, head `integration/stage3-v2-identity-pr1`.
**Локальный HEAD, remote branch и PR head: `a011c7298f0731455799de2b19b4b7bb304876e8`.**

Итог: пригодный **trained inference bundle не подтверждён**. Artifact gate
BLOCKED; learned B, новые live integration calls и новый V40 **не запускались**.
Не использованы prompted substitute, ручной scorer, MMR, boosts или соседние окна.
Production code, main, DTO, cap 12000, access и gold не изменялись.
Коммитов, push, merge и обучения нет. Подготовлены контракт и условный протокол,
а не работающий selector или исправление PR.

## 1. Перепроверка исходных доказательств

Прочитаны `../budget-diagnostic/FREEZE.json`, `BOUNDARY_ASSESSMENT.json`,
`MEASUREMENTS.json`, `RESEARCH_RU.md`, `CI_V40_RECEIPT.json`; проверен harness
`diagnose.py:110–158` и production first-fit
`docmancer/docs/application/experimental_context_finalization.py:570–608`.

Новый `audit.py` выполнил **offline** проверку всех frozen input hashes,
установленных product files, архива и всех его **47 файлов**. По сохранённому
trace проверено равенство **полной public row**, а не только snippet, между
двумя окнами каждого feasibility packet и полным source-rechecked pool.
Допуск каждого окна подтверждён admission receipts. Raw document SHA,
точные char spans и snippet SHA сверены с frozen исходными файлами.
Стоимость заново вычислена установленным настоящим `experimental_context_cost`.
Результаты: `EVIDENCE_AUDIT.json`. Это аудит старых live receipts, не новый
MCP/stdio/production runtime и не повтор live validator вне request context.

| Case | Полный допущенный pool | После terminal | Mandatory raw range | Final coverage | Отклонение нужного окна |
|---|---:|---:|---|---|---|
| P03 |167|41|`docs/configuration.md`, `[2805,3320)`|442/515 chars, FAIL|rank74, trial12141 >12000|
| E01 |256|39|`docs/src/use/configure/configuration-files.md`, `[584,1141)`|0/557 chars, FAIL|rank137/141, trials12131/12125 >12000|

Во всех записанных upstream stages, включая admission, native selection,
projection и source recheck, полное покрытие присутствует и integrity errors
пусты. Первое исчезновение — `enforce_experimental_context_budget.output`.
Терминальный цикл пробует целые rows в исходном порядке; ранее занятое место
не пересматривается ради совместной полноты. Это доказательство first-fit loss
на этих двух вопросах, не утверждение обо всех вопросах/режимах продукта.

| Диагностический feasible packet — **не B** | Целые допустимые окна | Full DTO cost |
|---|---|---:|
| P03 |`ev-4ee38ec394d37817` `[2805,3247)`; `ev-de9f17e55b14ffb8` `[3247,3446)`|743|
| E01 |`ev-c47c2b1fdeb26ffb` `[584,993)`; `ev-6d6e478eedb2ef59` `[993,1324)`|811|

Все окна `scope=project`, `version_binding=unversioned`, с исходной identity и
authority. Эти диапазоны целиком покрывают обязательные raw ranges; нет crop,
синтеза или нового допуска. Старые live recheck и budget checker PASS,
независимый unchanged oracle PASS **для диагностических копий**.
Цены привязаны к замороженным root/identity/DTO; на новом root требуется новый
freeze, нельзя гарантировать буквально те же IDs/стоимость.

**Oracle separation:** gold открывается только в observer после return
терминального budget function; продукт уже выбрал ответ. Observer строит
gold-informed feasibility copy, не заменяет аргументы или возврат продукта.
Observer off/on выдаёт одинаковые DTO в обоих cases; model_calls=0.
Boundary assessment и gold evaluation — отдельная диагностика. Feasibility
подтверждает существование допустимого набора, **не способность learned selector
его найти**. Эти witness IDs не попадут в inference, training или tuning.

CI receipt на том же SHA: **22/24 positives, 8/8 documented-partial,
0/8 strict-empty**. Это исторический native результат, не новый B gate.
CI identity/root отличаются: например P03 CI source_count42, здесь41;
нельзя смешивать это в парную таблицу или переносить runtime IDs.

## 2. Artifact discovery и первичные источники

Новые raw responses, URL, access timestamps и SHA-256 сохранены в
`primary/SOURCES.json` и соответствующих `.txt`. Никаких weights не скачано.
Использованы именно статьи/официальный repo, а не результаты поисков как
доказательство качества:

- SetR: https://arxiv.org/html/2507.06838v2 (§3–6, Appendix A),
  https://aclanthology.org/2025.acl-long.861/ (ссылка из предыдущего исследования),
  https://github.com/LGAI-Research/SetR . Repo revision
  `d1ac78b7e41f7c6a2cd8d582934fbba02893f343`: README, tree, train script,
  `License.md`; releases пусты; issue #1 «Release SETR model on Hugging Face»
  имеет 0 comments и не предоставляет checkpoint.
- ParaSet / SetCE: https://arxiv.org/html/2607.05712v1 и актуальная abstract page
  https://arxiv.org/abs/2607.05712 (Mooho Song, Jay-Yoon Lee), §3–4, Appendix A,
  D.1, E.1/E.4/E.5, F, G.2. Статус: preprint, не deployable model card.
- HF model API: `search=ParaSet` и `search=SetCE` вернули `[]`;
  `search=SetR` дал 10 совпадений, ни одно не связано с авторами/этой RAG работой
  (в том числе segmentation SETR). GitHub repo search дал8/21 совпадение,
  но official trained bundle не обнаружен. Два одноимённых `paraset` — Haskell
  repo с последним push2023 и HTML repo2023; они не paper implementation.
  Неудачный общий web search давал нерелевантные результаты и не используется
  как основание отсутствия артефакта.

**Ограничение поиска:** это проверка перечисленных публичных поверхностей,
не доказательство, что веса нигде не существуют. Private/gated bundle или
другая публикация авторов возможны. Не подставлять base model за trained scorer.

| Свойство | SetR | ParaSet | SetCE |
|---|---|---|---|
| Trained artifact |Ссылка на готовые SetR weights не подтверждена|Weights/config не подтверждены|Weights/tokenizer/config не подтверждены|
| Точная лицензия |Repo code BSD-3-Clause; base Llama-3.1 имеет отдельные Meta terms; лицензия released SetR bundle не установлена|Статья CC-BY-4.0, **не лицензия weights**; trained weights license неизвестна|То же; лицензия базового encoder не заменяет лицензию trained bundle|
| Представление |Distilled Llama-3.1-8B-Instruct выбирает set IDs|Attention над query/passage embeddings, 5.5M Contriever /8.3M Qwen3|DeBERTa-v3-base,183M; jointly encodes query и set text|
| Published input regime |20 passages; script source_max_len6144, target_max_len2048; это не доказанный inference cap bundle|Search pool до50; cardinality и encoder token cap требуют config|Standalone pool20; rerank наборов ParaSet из pool до50; точный tokenizer/context cap не установлен|
| Наши167–256 |Не подтверждено; в §6 большие пулы даже100 — future work|Архитектура позволяет рассмотреть все embeddings, но256 не проверено, совместимый embedding backend обязателен|Все candidates могут участвовать через предлагаемые sets, но каждый целый set должен реально помещаться без truncation|
| Technical docs/code |Benchmarks multi-hop QA; code/CLI/version completeness не проверена|То же; domain transfer — гипотеза|То же; полные sets с code fences/длинным текстом требуют проверки|
| Offline reproduction |Training code есть; готовый exact inference bundle нет|Нет подтверждённого bundle|Нет подтверждённого bundle|

### Память и стоимость: измеренное авторами ≠ наш benchmark

SetR8B: приблизительно16 GB только bf16 weights (2 bytes/parameter), **не**
runtime minimum. KV cache/activations/runtime дополнительно. Paper training16
A100, repo script8 CUDA devices; это не измерение inference. §5.4 использует
token counts как proxy, не воспроизводимый CPU/GPU timing нашего selector.
Реальные RAM/VRAM requirements, inference latency/cost для167–256 неизвестны.

ParaSet fp16 weights-only11/16.6 MB, SetCE366 MB, но отдельно нужны embedding
backend, tokenizer, activations/cache/runtime. Нет подтверждённого CPU minimum
или throughput для полного pool. Статья §4/Table1: ParaSet+SetCE0.116s
(Contriever) /0.164s (Qwen3), standalone SetCE0.555/0.585s; retrieval excluded.
Appendix D.1/Table8, **K20**, single RTX3090/24GB: peak allocated GPU memory
ParaSet0.44GB, SetCE4.09GB, ParaSet+SetCE2.01GB. Это режимы авторов, не
необходимые device minima, не total reserved memory и не перенос на pool256.
Embedding всех наших окон — дополнительная работа, native baseline embeddings
не считает; cache-hit/cold нужно учитывать раздельно.

Важная оговорка Appendix E.1: их «SETR-style» comparison использует frozen
GPT-4o-mini вместо trained SetR. Это **не найденный SetR checkpoint**; его
timing нельзя выдавать за trained SetR inference. В этом pilot такую замену
делать запрещено. Actual selector latency/RSS/VRAM здесь **NOT MEASURED**,
а не0. Model inference calls0, финансовых inference расходов нет.

## 3. Artifact gate: BLOCKED

Для PASS нужны одновременно:

1. Official trained weights/adapter + точный base, encoder, tokenizer, head
   shapes и preprocessing; immutable revisions и hashes всех файлов.
2. Явные лицензии weights/code/base/encoder/training data, право на нужный
   offline use; не переносить CC-BY статьи на weights.
3. Полный runnable pinned inference bundle, deterministic settings, input
   token/cardinality caps и overflow errors; без net/API и silent truncation.
4. Документированная/проверяемая способность обрабатывать полный pool167/256,
   всю question и целые окна. Pool не урезается до20/50. Encoder и SetCE
   limits считаются **их** tokenizer, не только DTO tokenizer.
5. Hardware capacity и resource ceilings для выбранного bundle; cold/warm
   profiling и явный failure на превышение limits. Не обещать CPU запуск,
   опираясь на RTX3090 measurements.

Пункты1–5 в совокупности не подтверждены. Нет готового запуска B, поэтому
production handoff и model integration tests не добавлены «для галочки».

### Реалистичный путь к обучаемому scorer (NOT RUN)

Сначала запросить у авторов официальные ParaSet/SetCE weights, tokenizer,
encoder revision, architecture/head config, license, inference entrypoint,
max set length/cardinality и полную evaluation configuration. Для SetR —
также distilled checkpoint, не только teacher data/prompts. Контакты указаны
в papers/SetR README; сообщения/issue автоматически не отправлялись.

Если bundle недоступен, отдельный проект обучения ParaSet-подобного **set-level
neural scorer**, не формульная имитация: разрешённый frozen embedding backend,
trainable attention/FFN head над query и целыми native windows; margin-based
preference complete > missing-part > corrupted/noisy sets. Составить независимый
licensed technical-doc корпус с annotated required spans, code examples,
scope/version distinctions и multi-source questions. Использовать реальные
source-native окна и реальные pool sizes167–256; split по repository/version
и near-duplicate clusters. Budget feasibility считать настоящим DTO cost, а
не длиной raw text. После проверки базового scorer можно отдельно обучать SetCE.

Не использовать V40, P03/E01 или их witness IDs в train/tuning. P03/E01 —
раскрытые development diagnostics; заморозить pilot policy до результатов,
не делать цикл fine-tuning ради их PASS. Gold допустим только как training
label на **отдельном** training corpus, не как runtime selector input.
Понадобятся разрешение на обучение, data/license audit, GPU allocation,
training/eval manifests и новый независимый holdout. Длительность и стоимость
обучения неизвестны до dataset/model/resource выбора; они не оценены выдуманными
цифрами. На выходе — честно новый DocAtlas-trained scorer, не «ParaSet reproduced».

## 4. Контракт и необходимые изменения

Подробный проект: `SELECTOR_CONTRACT_RU.md`. Это **проект внутреннего opt-in
контракта**, не изменение wire API и не реализованный callback.

| Файл / точка | Необходимое будущему B изменение |
|---|---|
| `docmancer/docs/application/experimental_candidate_selection.py:54–60,140–145` |Не использовать permutation callback как subset API; сохранить A без изменений, добавить отдельную internal atomic-set policy/config identity|
| Новый `docmancer/docs/application/experimental_set_selection.py` |Immutable source-rechecked pool/IDs, learned scorer adapter, полный pool search, exact full-DTO cost callback, model/resource/decision diagnostics|
| Новый `docmancer/docs/infrastructure/learned_set_scorer.py` |Pinned local bundle loader, manifest/license gate, input overflow, deterministic inference, profiling; без retrieval/access/gold dependencies|
| `docmancer/docs/application/experimental_context_finalization.py:524–629` |Opt-in selection **после** source recheck; pure exact final DTO builder/pricing; atomic final recheck/validation; B не проходит first-fit и native fallback; oversized/rejected set целиком infeasible|
| `docmancer/docs/interfaces/mcp/context_tools.py:510–526` |Согласовать late decorations и continuation registration с exact pricing; проверить equality accepted/emitted IDs и cost после регистрации; rollback/staging refs при failure, не частичная выдача|
| `eval/heuristic_removal/run.py`, `receipts.py` + installed integration harness |Парные A/B на общей реальной SQLite generation, gold-hidden selector inputs, real public MCP/SDK final DTO, независимый range evaluator и resource receipts|

Публичный формат DTO, existing validators/access/authority и cap менять не нужно.
Whitespace compacting — только контроль, не изменение production serializer.
Существующий internal `_rebuild` пригоден как материал для builder, но сам
callback ещё не контракт; pricing не должен создавать resources или менять DB.

## 5. Таблица A/B и контроль форматирования

Это **audited A из предыдущего installed public MCP run**, не новый paired run.
Нельзя записывать gold-informed packets743/811 в колонку B.

| Arm / case | Coverage | Integrity, scope/version, read-only | DTO cost | Selected / omitted | Selector latency / memory |
|---|---|---|---:|---|---|
| A P03 |FAIL,442/515|PASS по сохранённым receipts|11884|41/126 из167|Нет learned selector; first-fit-only latency/RSS не выделялись|
| A E01 |FAIL,0/557|PASS по сохранённым receipts|11819|39/217 из256|То же|
| B P03 |NOT RUN|NOT RUN|—|—|NOT MEASURED: artifact BLOCKED|
| B E01 |NOT RUN|NOT RUN|—|—|NOT MEASURED: artifact BLOCKED|

126/217 native omissions — terminal capacity; ledger native_fallbacks0,
upstream source-recheck errors0. Все omitted IDs есть в full archived ledger
(`all_omitted_evidence_ids`), не только первых64 display IDs. Trial costs и
причины нужных окон сохранены в `BOUNDARY_ASSESSMENT.json`.
B отклонённых окон/sets и их причин пока нет — не подставлять числа A.

Отдельный **повторный offline контроль** `audit.py`: тот же final A JSON object,
только `separators=(',', ':')`; exact decoded equality, source text/IDs/schema
не меняются. P03 **10868**, экономия1016; E01 **10850**, экономия969.
Coverage по определению остаётся442/515 и0/557: **FAIL**. Это не runtime arm
«first-fit заново с compact serializer», его результаты неизвестны; нельзя
приписывать эту экономию learned selection или обещать recovery.

## 6. Gates и условный интеграционный протокол

| Gate | Статус |
|---|---|
| Head + frozen evidence + whole permitted packets |PASS (offline audit; старые live receipts сохранены)|
| No oracle in product/inference |PASS для проверенного diagnostic harness; B ещё не существует|
| Suitable trained reproducible artifact |**BLOCKED**, prerequisites not established|
| A full P03/E01 coverage |**FAIL / FAIL**|
| B full P03/E01 coverage при прежних validators/12000 |NOT RUN — BLOCKED|
| B integrity/scope/version/read-only/budget |NOT RUN — BLOCKED|
| Один полный unchanged V40 после B PASS |NOT RUN — preceding gate не пройден|
| Цели24/24 +8/8 без integrity/budget regression |NOT ACHIEVED этим экспериментом|
|8 strict-empty negatives |Отдельно historical0/8; semantic refusal не проверялся/не исправлялся|

После artifact PASS и реализованного handoff: **две** реальные подготовки
P03/E01 документов в изолированную SQLite; **четыре** context calls — P03 A→B,
E01 B→A, тот же root/generation, вопросы, pool/order, windows, DTO format,
cap12000 и validators. Hash полного pool сравнить в A/B, независимые gold files
открывать evaluator только после final public DTO. Не patch/mock retrieval,
storage, selection или validation. Model disabled для A; одинаковый transport.
Runtime только в разрешённом CI/checkpoint, не новый большой локальный suite.

Независимый evaluator проверяет полноту raw mandatory ranges, полное равенство
каждой emitted row исходному pool, pinned document/snippet hashes, spans,
identity/scope/version, authority неизменна, DB и source tree не изменились,
фактический full DTO cost<=12000 и accepted_ids==emitted_ids.
Budget PASS/exit0/лог сами по себе не coverage PASS. Тесты только integration
или выше, устанавливают пакет и проходят public MCP/SDK. Нужный defensive
failure проверять через настоящий opt-in boundary, не mocked retrieval.

Latency: отдельно model load, encoding cold/cache-hit, learned scoring/search,
exact DTO pricing, finalization и full public call; wall/CPU, peak process RSS
включая workers, GPU max allocated+reserved/NVML peak, device/driver/dtype,
seed, input counts/tokens, scored/priced sets, batches и timeout reason.
Новых замеров B нет; observer-on timing A не годится как fair latency baseline.

Только если **оба B cases полностью PASS**, один неизменённый full V40 на
зафиксированном package/bundle/policy. При FAIL остановиться без V40, без
подкрутки questions/gold/budget. P03/E01 не holdout; full V40 тоже уже раскрыт
частично, новый blind holdout нужен отдельно для generalization.

## 7. Воспроизведение и ограничения

Из корня текущего worktree; fresh output paths обязательны:

```sh
git rev-parse HEAD
git ls-remote origin refs/heads/integration/stage3-v2-identity-pr1
gh api repos/Vanilla1999/DocAtlas/pulls/211 --jq '{head_sha: .head.sha, head_ref: .head.ref, base_ref: .base.ref, merged: .merged}'
/tmp/opencode/docatlas-budget-runtime/bin/python -I reports/docatlas-grounded-20261014/set-selection-preflight/audit.py --repo "$PWD" --output /tmp/opencode/docatlas-set-audit-fresh.json
python3 reports/docatlas-grounded-20261014/set-selection-preflight/research.py --output /tmp/opencode/docatlas-set-primary-fresh
```

Первая audit command требует уже установленного frozen package; инструкция
`uv sync --frozen --no-dev --no-editable` и воспроизведение **старых** live
P03/E01 находятся в `../budget-diagnostic/RESULT_RU.md:270–283`.
Повторять live вызовы сейчас не требуется: code/data/config не менялись.
На другой машине заменить interpreter path и безопасный private TMPDIR,
зафиксировать dependencies/root/identity; access rules не ослаблять.
`research.py` скачивает только metadata/papers и errors, никаких моделей;
remote discovery изменяется со временем, сохранённые responses — receipt
проверки2026-10-14, не гарантированно вечный BLOCKED.

**Команды B нет:** отсутствуют trained bundle и implementation. Выдумывать
работающий CLI или объявлять воспроизводимость inference было бы неверно.
Дальнейшие риски: domain shift, embedding loss of code detail, unsupported
long sets, beam approximation и compute ceiling, non-monotone full DTO cost,
late continuation overhead, licensing, over-inclusive learned sets и отсутствие
semantic refusal. Никаких deployment/performance/quality гарантий из papers
не переносится на DocAtlas. Все изменения этой задачи — только отчётные файлы.
