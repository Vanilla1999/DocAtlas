# Финальное бюджетирование: актуальная диагностика, не исправление PR

## 1. Что подтверждено и на каком коде

Remote PR211 head проверен до и после измерений:
`a011c7298f0731455799de2b19b4b7bb304876e8`; base `main`.
Никакого отката remote, merge в main, commit/push или нового PR нет.
Исходный checkout `/home/viadmin/StudioProjects/hermes/docmancer` был на другой
ветке, с изменённым `uv.lock` и untracked историческими отчётами: оставлен
нетронутым. После проверки worktrees создан worktree **указанной ветки**
`/tmp/opencode/docatlas-budget-diagnostic`; локальная ветка fast-forward от
f41885ba к актуальному remote. AGENTS.md прочитан; cleanup тестов не выполнялся.

Новые измерения: установленный **не editable** пакет текущего checkout,
Python3.13.12 `-I`, реальные immutable sources, cold confirmed preparation,
member SQLite, публичный `call_docs_tool_payload`. **4 context calls,2 prepares**:
off/on для каждого case в одном root/service/generation, без повторной подготовки.
Off: profiler/query trace выключены. On: generic BoundaryObserver + query trace;
в budget-return observer отдельно проверяется диагностическая копия пакета.
Product return, selector, retrieval и validators не подменяются. Дополнительные
**2 diagnostic rechecks** отдельно от штатных проверок, на копиях внутри live
receipt scope; никаких новых semantic/source permissions они не выдают.

Оба off/on DTO равны **целиком**, следовательно одинаковы и реальные JSON bytes:

| Case | Final rows | Full DTO cost | SHA-256 actual serialized DTO, off = on |
|---|---:|---:|---|
| P03 |41|11884|`5d8241bb6033e80c06dcb4e807f12f84b9201fb83d44401c5c6b716de1f3e0b8`|
| E01 |39|11819|`72d28f35bd8bcb05b1b2efe6adcfcb14c90dd4a2e73d2164329c9f5eab7c75cb`|

Source/hash/span integrity4/4, read-only4/4, observer errors0, frozen inputs
unchanged462/462. Это installed **in-process MCP**, не stdio/client/production
smoke и не latency benchmark. Источник: `MEASUREMENTS.json`, `FREEZE.json`,
unique per-case traces в архиве. Observer event count848/1293.

До public calls зафиксированы code files, источники, вопросы, oracle, evaluator,
uv.lock, harness, зависимости и config. `FREEZE.json` SHA-256:
`bbc797b686f99fb79cdaeba6b4161b07d39db64806b6b70b3374b421b625aa69`.

| Input | SHA-256 |
|---|---|
| source_plan.json |`8ec8b19323f4bc4f7d0737aced62527b210ee4ba1c50cf77b62ccafc38594e9a`|
| questions.json |`67afaaa42ad71d0036d2cde4f5a7da1b4e9c9b836b53b62ef2658ffdb8af80b5`|
| gold_spans.json |`3a78745249900056d98870850add167e9cc0ceaeb284e0db759b78b94303eacc`|
| evaluate.py |`32cf91a78807d1cb5709edb140cc1ff62ad4027023cb4a382c702403188921fa`|
| uv.lock |`dc0556cb2b3fddd1633a9d8526c72bb3a3afe27373816b45847749e6a1c7463a`|

Corpus upstream Poetry=`6de19222e44a948bc64f215ea3539b93ecf08719`,
ESLint=`3c0b7c6e1fe2dec778b97a996018126f22d437ae`.
Все corpus file hashes в FREEZE; actual prepared config/catalog/generation hashes
в `run/*-preparation.json` архива. Cap12000, offline, vectors disabled, default
native selection, no model. Не смешивать SHA code/corpus/window/saved JSON.

Отдельно проверен **CI V40 на этом же SHA**, не новый локальный40-case запуск:
[run38552651643](https://github.com/Vanilla1999/DocAtlas/actions/runs/38552651643),
artifact11887353099. CI wheel product files побайтно совпадают с checkout.
Результат: positives22/24, documented-partial8/8, strict-empty0/8;
P03/E01 FAIL. `CI_V40_RECEIPT.json` содержит artifact identity, hashes и оба
исходных case receipts. Красный CI не означает, что диагностические public
integration gates тоже красные: все3 Python integration jobs — success.

## 2. Первая граница потери

Независимый неизменённый evaluator и pinned original text подтверждают полный
witness на каждом output search → acquisition → admitted selection → native
projection → source recheck → project projection. **После terminal budget — FAIL**.
Source recheck167/167 и256/256; acquisition/admission не потеряли целевые окна.
Для каждого диапазона сохранены точные upstream positions и admission receipts,
source-native binding, независимые raw-file intervals, executed trial и omission.
Источник: `BOUNDARY_ASSESSMENT.json` → `cases[].stages/targets/ledger`.

| Case/window | Evidence ID | Whole chars / lines | Position | Selected before trial | Trial full DTO cost | Result |
|---|---|---|---:|---:|---:|---|
| P03 rule |`ev-4ee38ec394d37817`|2805–3247 /102–111|10/167|9|3023|retained|
| P03 example |`ev-de9f17e55b14ffb8`|3247–3446 /112–121|74/167|41|**12141**|over cap|
| E01 filenames |`ev-c47c2b1fdeb26ffb`|584–993 /19–29|137/256|39|**12131**|over cap|
| E01 placement/example |`ev-6d6e478eedb2ef59`|993–1324 /30–45|141/256|39|**12125**|over cap|

Chars — полуоткрытые исходные диапазоны, lines — включительные. Полный ESLint
gold584–1141 доставляется двумя **целыми** окнами584–993 и993–1324, без crop.
Raw document SHA Poetry=`d42823b26bb63d5a1db3c5c6fef14429499c07383fafd9e75704bc7130ffa810`,
ESLint=`59290b53aa9d4a63e830090e72433db12a71407c70895f1554fc218c18373c7d`.
Snippet SHA-256 потерянных окон:

- P03: `5c7af9651799241fe6a73013580691e0f3aed2179eeeaa0a7f2ef75e47116689`.
- E01 first: `806e04ca3f9cec0dccecd0879ffdb4d8909a546cd0e6d8710f98fc8e62a69afb`.
- E01 second: `2df6394c74e954a23c3660fc0505a1f190571772f63282e05a9bb26dcb46e4d4`.

Причина: `experimental_candidate_selection.py:124–153` сохраняет native order
после source admission/exact dedupe. `experimental_context_finalization.py:570–608`
делает first-fit: добавляет whole row, при cost>cap — `continue`, не заменяет
ранние выбранные rows поздними взаимодополняющими. Native alternatives здесь
не используются. Final omitted126/217, original gold FAIL2/2.
Это не ошибка соблюдения cap: cap соблюдён, полнота набора не оптимизируется.

Исторические8605cbdb результаты12130/12139/12133 **не новые измерения**.
Текущие числа и root/generation иные; также current-code budgets/selection могут
отличаться от старого запуска. Причину каждого межмашинного расхождения не
изолировали. Новый общий off/on pair устраняет прежний пробел equivalence.
Historical MiniLM FAIL не выдаётся за измерение MiniLM на a011c729.

## 3. Существует ли правильный пакет при12000

**Да, отдельно для обоих запросов**, даже в прежнем DTO формате.
Из уже admitted/rechecked **целых** окон собраны witness packets:

| Case | Whole windows | JSON UTF-8 bytes | ceil(bytes/4) | Actual codec tokens / cost | Original documented gold |
|---|---:|---:|---:|---:|---|
| P03 |2|2431|608|**743**|complete|
| E01 |2|2551|638|**811**|complete|

Production `_rebuild`, `validate_model_visible_projection`, live
`recheck_experimental_context`, `check_experimental_context_budget` прошли;
исходный evaluator отдельно подтвердил raw source bytes/hash/intervals и полный
неизменённый witness. Actual serializer: `json.dumps(..., ensure_ascii=False)`;
сохранённый pretty JSON **не** бюджетная wire representation.
Проверка использует тот же codec и serializer, что public path:
`experimental_context_finalization.py:147–155,625–629`,
`docmancer/mcp/_docs_server_part01.py:330–335`.

Gold открыт **после решения продукта**, только в диагностическом observer для
доказательства существования и offline scoring; рабочий selector gold не видел.
Diagnostic payload не возвращается вместо product DTO. Это не product PASS,
не оптимальность и не семантическая достаточность генерации. Текущий public
payload по-прежнему FAIL. Packets и validation receipts в архиве/MEASUREMENTS.

## 4. Структура расхода полного конечного DTO

Действующий cap = `max(o200k_base(JSON), ceil(UTF8(JSON)/4))`.
В обоих текущих DTO ограничивает **codec**, не UTF-8/4.

| Компонент | P03 bytes | P03 codec delta | E01 bytes | E01 codec delta |
|---|---:|---:|---:|---:|
| Общий envelope, включая empty sources/read_next |743|194|743|194|
| Source metadata и framing |21917|8315|20913|7940|
| Escaped snippets в JSON |13224|3375|14909|3685|
| **Full public DTO** |**35884**|**11884**|**36565**|**11819**|
| ceil(full bytes/4) |8971|—|9142|—|

Token attribution — **ordered counterfactual deltas**: envelope → same rows с
empty snippet → full DTO. BPE не аддитивен: это не универсальные независимые
«токены поля». Измерение полных строк в каждом шаге делает эти deltas аддитивными
по выбранному порядку, но не меняет их в byte shares. В этой декомпозиции source
metadata69.97%/67.18% codec, snippets28.40%/31.18%; их byte shares иные.
Неэкранированные исходные snippets отдельно:12805/14354 bytes и сумма
standalone codec counts2978/3231. Они **не равны** стоимости JSON snippets.

Continuation `read_next=[]`, поля recommended continuation отсутствуют:
фактического continuation content0. Standalone `{"read_next": []}`17 bytes/6
tokens — диагностическая стоимость отдельного объекта, не независимая доля DTO.
Top-level field measurements сохранены; весь общий envelope194 tokens.
Источник: `MEASUREMENTS.json` → `diagnostic.public_budget`; full budget hash
совпадает с конечным public DTO, не только preterminal approximation.

### Отдельная оценка представления A: выбранный текст/набор не меняются

| Только representation counterfactual | P03 cost / saving | E01 cost / saving | Совместимость |
|---|---:|---:|---|
| Убрать JSON whitespace |10868 /1016|10850 /969|Та же JSON schema; serializer/checker надо менять согласованно|
|4 общих row fields один раз |9008 /2876|9201 /2618|Нужен новый decoder/schema negotiation|
|+ действительно равные document-group fields |8875 /3009|8949 /2870|Нужен новый decoder/schema negotiation|

Общие поля: **version_binding, project_identity, authority, scope**.
Document grouping только по равным значениям, с точным roundtrip whole DTO;
hashes конкретных окон **не** объявлены document-common. Сохраняются source
text, hashes, URI, section, ranges, scope/version и прочие поля после decoding.
Roundtrip2/2 для каждого варианта, но это **не** public compatibility test нового
формата. Старый клиент не понимает defaults/table сам собой; дублировать прежние
row fields для него означало бы потерять основную экономию. Без смены schema
измеренная альтернатива — только whitespace1016/969 codec tokens.

Ни один A counterfactual не изменял selection, поэтому **не восстановил**
P03/E01: после exact decoding gold остаётся тем же FAIL. Не доказано, что A
невозможно довести до полного PASS при последующем пересчёте packing; такого
runtime arm здесь нет. Равным образом снижение cost не доказывает recovery.

## 5. Рекомендация: B первым для исправления полноты

**Budget-aware learned set compatibility**, не ещё один independent reranker.
Ближайшая научная постановка — ParaSet/SetCE; это рекомендация objective и
архитектуры, **не утверждение о доступном проверенном готовом checkpoint**.
SetR аналогично рассматривает коллективную полезность, но готовые weights и
full-pool input не подтверждены. Полный разбор пяти направлений, моделей,
лицензий, input/compute limits и оставшихся приближений: `RESEARCH_RU.md`.

Основания: первая потеря именно выбор набора; полноценные пакеты существуют
за743/811 без изменения DTO. A реально уменьшает overhead, но при фиксированном
тексте не возвращает отсутствующее дополнение, а сильная нормализация меняет
публичную схему. B прямо проверяет полноту при прежнем формате и cap.
Не утверждаем, что learned B обязательно PASS или что A бессмысленен.

Нет готового подтверждённого drop-in B среди исследованных artifacts. Если
preflight ниже не проходит, **не запускать prompted substitute** и не подставлять
gold; зафиксировать blocker. Новое обучение — отдельное разрешение, не часть
этой рекомендации/текущей задачи.

## 6. Один следующий эксперимент: atomic set-selection pilot B

Эксперимент пока **NOT RUN**. Product code/contract/budget сейчас не менялись.

1. **Preflight до inference:** получить официальный trained ParaSet/SetCE
   inference bundle; зафиксировать weight/config/tokenizer/encoder/license SHA,
   implementation revision и hardware. Проверить точный целевой scorer и
   совместимость encoder dimensions. Прогнать только input-size accounting:
   исходный полный вопрос, все167/256 целых окон, без gold, top20 и silent
   truncation. Нет weights/license/полного input → BLOCKED, не «воспроизведение».
2. **Контракт selector:** immutable original question + **весь** admitted pool;
   существующие evidence IDs, исходные snippets, validated identity/hash/span,
   scope/version; cap12000 и pure exact-cost oracle, который собирает полный
   предполагаемый конечный DTO с metadata/continuation и действующим serializer.
   Output — атомарный subset **существующих IDs**, без нового текста/authority;
   неизвестные/повторные IDs — error. Model/input/compute budget отдельно.
3. **Единая policy, до открытия результатов:** learned set scores;
   approximate beam width2, singleton evaluation всехN кандидатов, whole-set
   expansion по всему pool, exact set dedupe; depth не большеN, только cap-feasible
   sets. SetCE reranks10 лучших предложенных целых feasible sets. Это явная
   приближённая search policy, **не ручная семантическая эвристика** и не
   exhaustive optimality guarantee. Никаких keywords/library/neighbor bonuses,
   обязательного добавления детей/соседей, увеличения cap или изменения gold.
   Предел wall600s/2 prepares/4 context calls; максимум50000 scored sets на
   experimental case. Достигнут compute limit → explicit experiment failure,
   не скрытая урезка candidate universe.
4. **Atomic terminal handoff:** final source validation и exact full DTO cost
   выполняются до публикации. Oversized set возвращается selector как infeasible
   **целиком**; можно выбрать другой уже scored feasible set. Если такого нет —
   явный budget/selector failure, без выдачи молча обрезанного дополнения и без
   объявления semantic abstention. После resource/continuation registration
   проверить actual final bytes снова; cap excess — error, не first-fit crop.
   Текущий callback принимает только complete permutation
   (`experimental_candidate_selection.py:54–60,140–145`); он **не** реализует этот
   set contract. Отдельный внутренний opt-in handoff потребует разрешённого
   будущего изменения кода, не нового MCP wire API и не текущего commit.
5. **Paired installed pilot:** baseline native и B на общей подготовке/SQLite,
   root/generation/input/state, alternating arm order по двум cases;4 context,
   2 prepare. Gold только независимому offline evaluator. Требовать полный
   прежний P03/E01 witness, final cap, source/hash/span/scope/version integrity,
   read-only; измерить inference input tokens, scorer calls/scored sets, load/
   execution wall+CPU/RSS/GPU-memory отдельно от emitted context tokens.
6. **Decision gate:** если оба development cases PASS и integrity/cap/read-only
   gates PASS, один conditional установленный immutable V40 run:24/24 positives
   и8/8 documented-partial.8 strict-empty учитывать **отдельно**; packing fix
   не доказывает semantic refusal. При pilot FAIL full V40 не запускать и
   параметры/gold не подкручивать. P03/E01 раскрыты, V40 не новый blind holdout;
   generalization требует отдельного нового holdout вне этого эксперимента.

## 7. Что не проверено; воспроизведение

- Не выполнялись model inference/training/paid API, latency benchmarks,
  production client/stdio smoke, новый full40 локальный прогон, semantic refusal.
- Доступность trained SetR/ParaSet bundle и SetCE exact input cap не подтверждены;
  CPU/GPU minimum/runtime для нашего pool не измерены. Licenses местами неполны
  или противоречат prose; legal/deployment approval не заявлен.
- Structural A format не проверен со старыми SDK/клиентами, runtime packing на
  новом serializer не выполнялся. Экономия измерена, completeness fix нет.
- Первый local setup остановился **до prepare/context** из-за TMPDIR ancestor
  `/tmp/opencode`775. Raw состояние сохранено вне репозитория, краткий receipt —
  `SETUP_ATTEMPT.json`; fallback только
  для host fixture temporary home в private `/home/viadmin/.cache/...`, без
  изменения production storage policy. Повторены не product calls, а cold setup.
- Observer и feasibility diagnostics замедляют on arm; он не performance
  benchmark. Полное равенство результата2/2/read-only4/4 доказано именно для
  этого pair; не универсальная гарантия отсутствия влияния любых observers.

`receipts.tar.xz` **416600 bytes**: уникальные per-case полные traces, DTO,
подготовка, feasibility packets, primary sources, CI receipts. Тяжёлые raw traces
и CI wheel повторно в git не копировались. Архив проверен per-file SHA-256,
индекс `RECEIPTS_ARCHIVE.json`; scratch `boundaries/call-1.json` не используется,
поскольку generic observer instances перезаписывают это имя между cases.

Воспроизведение в **свежих** output/work (не перезаписывать выполненные attempts):

```sh
UV_PROJECT_ENVIRONMENT=/tmp/opencode/docatlas-budget-runtime uv sync --frozen --no-dev --no-editable
# TMPDIR должен иметь безопасных ancestors; /tmp/opencode775 не подходит SQLite.
TMPDIR=/home/viadmin/.cache/docatlas-budget-private-20261014 HF_HUB_OFFLINE=1 /tmp/opencode/docatlas-budget-runtime/bin/python -I reports/docatlas-grounded-20261014/budget-diagnostic/diagnose.py --repo "$PWD" --work /tmp/opencode/docatlas-budget-fresh-work --output /tmp/opencode/docatlas-budget-fresh-output
/tmp/opencode/docatlas-budget-runtime/bin/python -I reports/docatlas-grounded-20261014/budget-diagnostic/summarize.py --repo "$PWD" --run /tmp/opencode/docatlas-budget-fresh-output --output /tmp/opencode/docatlas-budget-fresh-output/BOUNDARY_ASSESSMENT.json
```

Существующий TMPDIR в этой машине создан mode700; на другой машине выбрать
такой же безопасный host temporary root, не менять source corpus/gold.
Новые paths требуют нового FREEZE; IDs/cost зависят от identities/root длины.
Подтверждённой сущностью остаётся исходный raw document/window, не переносимый
runtime evidence ID. PR не объявляется готовым.
