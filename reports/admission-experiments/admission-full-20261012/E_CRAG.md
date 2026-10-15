# E — CRAG: официальный evaluator, границы воспроизведения и разрешения

Дата: 2026-10-12. **CURRENT RESULT: официальный evaluator реально исполнен координатором на CPU FP32, serial slot `coordinator-E-001`: 17/21 pairs scored, 4 overflow NOT SCORED, без скрытого clipping. Offline replay ADAPTED; полный CRAG NOT RUN.** Лимит 600M снят; received-byte SHA-256 pinning принят владельцем. Первоначальные read-only ограничения/NOT RUN ниже сохранены как исторический checkpoint и не описывают нынешний evaluator runtime. Измеренные результаты — раздел10. Web/refinement/correction/generation не выполнялись; final PASS принадлежит G.

## 1. Выполненная работа и рабочая точка

- Полностью прочитан `MULTI_AGENT_ADMISSION_FULL_PROTOCOL_RU.md` (256 строк), включая роль E.
- Read-only Git: ветка `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`, начальный `git status --short` пустой.
- Прочитаны `AGENTS.md`, `v2plan/PR211_CHECKPOINT_RU.md`, frozen questions/extra40/corpus, evidence manifest, ADR0003 и все пять запрошенных материалов `q46-admission` (research, A/B/C/RESULT).
- Архивный product SHA `d8af387de507007f2b8c83f04aac78feb9b6760c` не выдаётся за проверку нынешнего HEAD. Исторические Q46/Q16 observations не повторно аудированы мной по raw JSON; их независимый oracle остаётся у G.
- Публично прочитаны статья, официальный repository/code и metadata авторского Drive. Корпус/вопросы/проектные сведения не отправлялись внешнему provider или поисковому сервису. Внешние запросы содержали только публичные URLs/file IDs.
- Не было product execution/import, pytest, AST, install, model inference, скачивания весов, provider calls, CI, nested agents или repo edits. Единственный authored файл — этот отчёт. Чтение небольшого `config.json` — разрешённое metadata чтение, не загрузка весов. API/SDK-документация для выводов не требовалась; ниже описана фактически прочитанная авторская реализация, а не инструкция по современному API.

## 2. Primary evidence и конкретный checkpoint — без угаданного HF имени

Первичная статья: [arXiv:2401.15884v3](https://arxiv.org/html/2401.15884v3), 2024-10-07, §§4.2–4.5 и Appendix B.2/B.3. Она сама ссылается на [HuskyInSalt/CRAG](https://github.com/HuskyInSalt/CRAG).

GitHub API `https://api.github.com/repos/HuskyInSalt/CRAG/commits/main` вернул официальный code revision:

`de7c2961ae624a1483a138c5798e1f6d0c4fb0e0` (2024-10-08).

Все приведённые ниже code факты проверены по raw URLs с этим полным SHA, не только по mutable `main`. Recursive tree не содержит весов или LICENSE-файла. Это **immutable code revision**, не revision модели.

### Установленная идентичность evaluator

1. §4.2: fine-tuned **T5-large**, авторская оценка размера **0.77B**. Это не T5-base и не произвольный LLM judge.
2. `scripts/train_evaluator.py`: `T5ForSequenceClassification.from_pretrained("t5-large", num_labels=1)`; tokenizer `T5Tokenizer`; labels `(label - 0.5) * 2`, regression. Сохраняет эпохи `ep0`…`ep7`, но это само по себе не устанавливает выбранную эпоху публикации.
3. [README на зафиксированном SHA](https://github.com/HuskyInSalt/CRAG/blob/de7c2961ae624a1483a138c5798e1f6d0c4fb0e0/README.md) прямо обозначает опубликованные Drive weights как evaluator, использованный в экспериментах.
4. [Авторская папка](https://drive.google.com/drive/folders/1CRFGsyNguXJwKSvFvJm_82GOOlkWSkW7) доступна публично, HTTP 200; заголовок `finetuned_t5_evaluator`. HTML listing даёт:

| Файл | Drive file ID | Наблюдаемая metadata |
|---|---|---|
| `config.json` | `1J2DCva5L6Mmx0JhzVWYiZfLg7YhRoY84` | 1640 bytes |
| `model.safetensors` | `19p2bAYL2QxvUyloKv6udF0R69u1yie-H` | **2,954,943,548 bytes**, около 2.75 GiB |
| `tokenizer_config.json` | `11GRPEmkDQ4h9EKFK5kb8OW0CEhXByyEd` | 20,817 bytes |
| `spiece.model` | `132NL1aJIjdIUCCab6uk3R2EZuayTyy8F` | 791,656 bytes; содержимое не читалось |
| `special_tokens_map.json` | `13LAXfli1JFO-Nan918RwYZnOpEB3nr4E` | присутствует |
| `added_tokens.json` | `1fiYYBunQGs3rQ14y28mCg5Ap_KKBCCDy` | присутствует |

5. Только JSON metadata прочитана через `https://drive.google.com/uc?export=download&id=1J2DCva5L6Mmx0JhzVWYiZfLg7YhRoY84`. Ключевые точные значения:

```json
{
  "_name_or_path": "../checkpoints/finetuned_t5_ep1",
  "architectures": ["T5ForSequenceClassification"],
  "d_model": 1024,
  "d_ff": 4096,
  "d_kv": 64,
  "num_heads": 16,
  "num_layers": 24,
  "num_decoder_layers": 24,
  "vocab_size": 32128,
  "n_positions": 512,
  "problem_type": "regression",
  "torch_dtype": "float32",
  "transformers_version": "4.36.1"
}
```

Таким образом конкретный **официально связанный downloadable checkpoint** — папка `finetuned_t5_evaluator`, config lineage `../checkpoints/finetuned_t5_ep1`, указанный safetensors file ID. `_name_or_path` — сохранённая lineage metadata, не доказательство полного training provenance или независимая проверка того, что веса соответствуют конкретной эпохе.

**Не установлена immutable weight revision.** Drive folder/file ID идентифицирует mutable объект, не гарантирует неизменность содержимого. В README нет checksum/revision весов; содержимое safetensors не читалось, SHA-256 не получен. Доступность listing и config доказана; успешная полная загрузка/целостность/загрузоспособность весов **NOT VERIFIED**. Нельзя выдать SHA официального кода за SHA модели, придумать HF checkpoint либо назвать зеркало авторским без авторской ссылки. Для воспроизводимого запуска нужен авторский immutable snapshot/checksum либо явно одобренная фиксация полученного артефакта SHA-256 после разрешённой загрузки (с честной датой происхождения).

### Лимит параметров

Авторская величина **0.77B > 0.6B**, превышение около 28%. Достаточно для отказа при текущем лимите; точный runtime `numel` не измерялся. Размер файла — storage bytes, не точный подсчёт параметров. Config согласуется с T5-large. Quantization уменьшает bytes, не число параметров, поэтому не устраняет запрет. T5-base/компактный reranker/хост вместо авторских весов — **ADAPTED**, не reproduction этого evaluator. Переобучение меньшей модели также не является готовым авторским checkpoint и здесь не предлагается.

Лицензия конкретных fine-tuned weights и разрешение redistribution не установлены: статья, public Drive и отсутствие LICENSE в code tree не дают автоматически коммерческого/production разрешения. До внедрения это отдельный blocker; не переносить лицензию предполагаемой base-модели на опубликованные веса без проверки.

## 3. Evaluation не равна corrective actions, sufficiency или authority

**Evaluator:** для каждого исходного question/document вычисляет scalar regression logit. В статье обучение на PopQA relevance signals, positive 1 / negative −1, negatives из retrieval. Это не пакетная sufficiency и не проверка правильности ответа, текущего hash, доступа, consent либо версии. Статья описывает scores от −1 до 1, однако прочитанный code не применяет sigmoid/tanh/clamp: нельзя считать logit калиброванной вероятностью или гарантировать такой диапазон.

**Action trigger:** Correct, если хотя бы один document превышает верхний порог; Incorrect, если все ниже нижнего; иначе Ambiguous. В code `process_flag` использует `>=` на обеих границах и группы по `ndocs`, а не строгое `>` статьи. Empty pool не следует padding-ить фиктивными документами; для адаптации фиксировать отдельный `NO_CANDIDATES` и отказ.

**Corrective actions:**

- Correct → internal knowledge refinement: decomposition → повторная relevance evaluation strips → filter/recompose.
- Incorrect → discard initial context → query rewriting + web search + selection web knowledge.
- Ambiguous → internal refinement + external web knowledge.
- Затем generator. `Correct` означает уверенность retrieval action, не PASS источника или ответа.

**Для project scope web correction запрещена**, в том числе пересылка проектного вопроса для rewriting, public search, использование публичных страниц как проектных sources. Прочтение публичной статьи для этого отчёта не является разрешением product web fallback. Нельзя заменять web незаметным all-scope/module widening, новым provider или host memory.

Авторский generator в опытах — LLaMA2/SelfRAG 7B; для DocAtlas сохранять существующий фиксированный хост отдельно. Это не требует нового 7B download и не доказывает повторение paper metrics. Перенос relevance evaluator на русские repository docs не валидирован авторской PopQA accuracy.

## 4. Существенные различия paper ↔ released code

Все ссылки в этом разделе относительно [официального immutable tree](https://github.com/HuskyInSalt/CRAG/tree/de7c2961ae624a1483a138c5798e1f6d0c4fb0e0).

- Appendix B.3: PopQA thresholds `(0.59, −0.99)`, Pub/ARC `(0.5, −0.91)`, Bio `(0.95, −0.91)`. `run_crag_inference.sh` для PopQA задаёт `0.592` и `0.995`; `main` инвертирует знак нижнего: **реально `(0.592, −0.995)`**. Закомментированный PubQA пример даёт `(0.5, −0.915)`. Эти calibration значения не переносить на DocAtlas как обоснованные пороги.
- Appendix B.3: strips top-k=5, filter threshold −0.5. `internal_knowledge_preparation.py` выставляет top_n=3 для `selection`, 6 для других modes. `utils.select_relevants` просто возвращает top_n по score, **не фильтрует по −0.5**; включает и negative strips при наличии. Не называть это faithfully implemented paper filtering.
- `selection` оставляет passage целиком; `fixed_num` использует 50 слов; `excerption` splits по `?`/`. ` и recomposes по три segments. `'; '.join(ctxs)` в score order, newline replacement, punctuation splitting не сохраняют exact source spans/bytes автоматически. DocAtlas должен выдавать исходные span-bound фрагменты, а не переписанную склейку. Такая обёртка — явная ADAPTED provenance policy.
- Training и `select_relevants` используют max_length=512 с `truncation=True`; `CRAG_Inference.inference` задаёт padding/max_length=512 **без явного truncation=True**. 512 нельзя считать гарантированным enforced inference ceiling во всех ветвях. Документировать видимые token lengths и truncation; не засчитывать удалённый хвост как оценённый.
- Inference assumes 10-row layout при `n % 10`, затем grouping по `ndocs`. Перенос на переменные реальные candidate pools требует явного adapter; padding/clipping pool ради этого предположения исказит сравнение.
- External code вызывает `select_relevants(..., mode="cross_encode")`, но прочитанная функция такого аргумента не принимает; `utils` использует legacy `openai.ChatCompletion` при requirement openai 1.4.0. Это статические incompatibility risks, **не наблюдённые runtime ошибки**; внешняя ветка не исполнялась и здесь запрещена.
- Статья Table 6 исключает retrieval/data-processing overhead. Её время не является budget или ожидаемой latency DocAtlas; учитывать evaluator passes, refinement, model load, retrieval и host целиком.

## 5. Зависимости и реальные ресурсные границы

Официальный README: Python **3.11**. `requirements.txt`: `torch==2.1.2`, `transformers==4.36.1`, `sentencepiece==0.1.99`, `safetensors==0.4.1`, `numpy==1.26.2`, `tqdm==4.66.1`; полный release также содержит pandas/scikit-learn, `vllm==0.2.5`, `openai==1.4.0`, CUDA12 libraries, flash-attn, bitsandbytes, deepspeed, xformers и т.д. Это список release, не команда к разрешённому install.

Evaluator-only adapter потенциально может ограничиться CPU PyTorch + Transformers + SentencePiece + safetensors + необходимые фактические imports. Он не должен импортировать весь официальный `utils.py` и незаметно подключать OpenAI/прочую инфраструктуру; subset runtime после отдельного разрешения фиксируется своим lockfile и маркируется adapter. Training/install full CUDA stack/vLLM/новый generator не нужны для первого relevance diagnostic.

Доступное железо передано координатором: i9-12900K, RAM62 GiB (~30 GiB available), disk27 GiB, GPU pending. Модель FP32 storage около 2.75 GiB; evaluator-only CPU inference **ресурсно правдоподобен**, но не измерен, latency/peak RAM неизвестны. Full paper setup использовал A80080GB; Appendix B.2 сообщает >40GB для LLaMA2 generation — это не подходит для обещания полного воспроизведения на текущих ресурсах. Не зависеть от ещё не подтверждённого GPU и не запускать одновременно с другими моделями.

## 6. Feasible bounded protocol — только после разрешений

### E0: evaluator-only diagnostic, без corrective policy

1. Получить разрешённую immutable фиксацию конкретных авторских весов и исключение для 0.77B. Отдельно зафиксировать tokenizer/config hashes, runtime lock, CPU FP32, seed, code/adapter SHA. Никаких quantization/retraining или hidden retries.
2. Использовать **тот же source-policy-valid pre-topical-veto pool**, что B1/C/D, исходный question, стабильные IDs и неизменённые bytes. Не выбирать только oracle-answer окно. Контроль access/scope/version/catalog/generation/hash выполняется до model visibility и после selection; model никогда не снимает запрет источника.
3. Smoke: максимум **7 существующих публичных cases**: Q46, Q16, OtherAPI, unrelated-topic, numeric-negative, positive-indexed scope control, forbidden-scope control. G назначает точные existing IDs до исполнения. Максимум 10 реальных candidates/case, итого **70 pair evaluations**, один проход FP32 batch1; больше кандидатов → stop/пересогласование, не скрытое урезание retrieval pool.
4. В evaluator идёт ровно `question + " [SEP] " + candidate_text`, без oracle/facts/spans/expected answers/чужих scores. IDs и source lineage хранятся вне model text. Preflight token длины: >512 → явный `OVERSIZE_NOT_SCORED` и stop сопоставимого arm, не молчаливый truncation. Это более строгий operational adapter, не идентичная paper inference.
5. Сохранить все logits и would-trigger labels при зафиксированных code thresholds `(0.592, −0.995)` **только диагностически**, не новый unconditional veto. Off-domain пороги не калиброваны. Полный пакет проверяет G; наличие одной relevant пары не доказывает полноту. Offline replay разрешён только отдельным runtime решением и не даёт public integration credit.

### E1: закрытая correction policy — ADAPTED, не полный CRAG

После E0 и отдельного решения о relevance-контракте:

- Сначала сравнить B0/B1 и score-selection **без refinement**, чтобы не смешать benefit evaluator и pruning.
- Отдельный arm с refinement допускает только exact original span units; максимум 6 units/candidate, **420 дополнительных strip evaluations** на 7-case smoke. Не создавать benchmark-specific segmentation или правила Q46/PASS. Результат selection выдаёт исходные units в source order с отдельными IDs, без synthetic quote.
- `Incorrect` → явный no-supported-context/отказ, **никакого web**; `Ambiguous` → только bounded разрешённый internal context с честной неопределённостью. Это изменения двух corrective actions статьи. Не делать вывод «CRAG исправляет retrieval» из одного ранжирования.
- Выбор top-k/порогов для delivery требует отдельной заранее замороженной calibration части G и operational bounds; не настраивать по Q46/Q16/holdout. Если calibration отсутствует, E0 остаётся diagnostic, E1 NOT RUN.
- Хост один и тот же, prompt/settings фиксированы координатором; не более одного ответа/case/arm. Smoke B0/B1/E1 = максимум **21 host calls** (существующие receipts переиспользовать, не дублировать одинаковые наборы). Refinement — отдельный arm/бюджет, не скрытая добавка к этим 21.
- Сохранять раздельно CURRENT_CONTRACT и EXPERIMENT_OUTCOME: нерелевантные sources в OtherAPI — contract FAIL, даже при правильном host refusal; source-policy violation останавливает рекомендацию. `answer_supported`, `answer_available`, `edit_ready` остаются false.

### Расширение и receipts

Только после успешного smoke и отдельного подтверждения: frozen old10 + direct40, **50 cases**, максимум 500 pair evaluations; refinement при разрешении максимум ещё 3000 strip evaluations. Lookup arms не включены автоматически. G проверяет все прежние 28 direct-success IDs отдельно и неизменные negatives; известные 50 не являются holdout.

Receipts: question/corpus hashes, full candidate pool и policy exclusions, exact source IDs/hash/span/scope/version/generation, model/config/tokenizer hashes, logits, thresholds и action label, retained/dropped source units, final public payload отдельно от diagnostics, actual host-visible input/answer/citations, независимые facts/citation verdicts, load/cold/warm timings, model/API invocation count (не только count pairs), model input/output tokens, peak RAM/VRAM, ошибки/oversize/truncation. Tokens/calls/time/RAM и correctness сейчас **NOT MEASURED**, а не ноль.

## 7. Blockers и один конкретный запрос разрешений

**Blockers:** 0.77B выше разрешённого потолка; immutable весов/checksum пока нет; downloads/install/inference/product runtime запрещены; placement/host budget не разрешены; GPU неизвестен; licence fine-tuned artifacts не установлена; public adapter и relevance contract delta ещё не назначены; русский domain/calibration не валидированы. Web branch в project scope не запрашивается как «автоматическое» расширение.

Минимальное следующее решение координатора/владельца, **без абстрактного «продолжать?»**:

> Разрешить ли одно узкое исключение из лимита 0.6B для официального CRAG T5-large (paper 0.77B), конкретно Drive `finetuned_t5_evaluator`, safetensors ID `19p2bAYL2QxvUyloKv6udF0R69u1yie-H`, config ID `1J2DCva5L6Mmx0JhzVWYiZfLg7YhRoY84`, с предварительным author immutable checksum/snapshot либо явно одобренным pinning скачанных bytes SHA-256? После установления pin — разрешить однократную загрузку только evaluator/tokenizer/config, изолированный CPU FP32 runtime (Python3.11, утверждённый lock; без полного CUDA/vLLM stack), no-training/no-quantization/no-network inference, под `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/` в отдельно назначенном coordinator-owned runtime directory. Ресурсный stop budget: 8 GiB новых disk bytes включая env/cache/artifacts, 12 GiB peak RSS, 8 CPU threads, 45 минут smoke, 70 pair evaluations; дополнительных downloads/retries/host calls нет. Данные — только замороженные 7 cases и общие bounded policy-valid candidates, остаются локально, без oracle в model input. Разрешение на public product execution/adapter ownership и до 21 фиксированных host calls в явно названном уже одобренном deployment запросить отдельно; default providers/CI остаются запрещены. Для optional refinement отдельно разрешить 420 strip evaluations; для regression отдельно 50 cases/500 pairs/до 3000 strips и 2 часа, не запускать автоматически.

Эти ceilings — предложенные stop limits, **не измеренные требования**. При недостающем ресурсе/metadata/лицензии — stop + receipt, не precision fallback. Если исключение отклонено, **официальный R4 NOT RUN**; маленькая модель из C может проверять CRAG-inspired триггер/закрытые actions только как новый **ADAPTED** arm с её собственным exact checkpoint/revision, без угадывания здесь.

## 8. Итоговая таблица применимости

| Метод | Точная модель/размер | Статус | Доставленные факты / ответы / policy / ресурсы |
|---|---|---|---|
| Официальный CRAG evaluator | Author Drive `finetuned_t5_evaluator`, config lineage `finetuned_t5_ep1`, T5-large, paper 0.77B; immutable weights pin BLOCKED | **NOT RUN** | Всё runtime NOT MEASURED; выше 0.6B |
| Полный CRAG corrective pipeline | Тот же evaluator + rewriting/web + generator | **NOT RUN** | Web несовместим с project scope; paper reproduction не заявляется |
| Закрытый CRAG-inspired E0/E1 | Официальный evaluator только с исключением, либо separately named <=0.6B substitute | **ADAPTED (PROPOSED), runtime NOT RUN** | Проверяются relevance/action ideas; не paper web correction или paper metrics |

**REPRODUCED нет.** Исследование establishes concrete public artifact identity и размер, но не inference correctness. Один минимальный следующий шаг — решение о 0.77B исключении + immutable фиксации; до него модель не скачивать и не исполнять. Для текущего сравнения рациональнее не блокировать B0/B1 и <=0.6B candidates на полном CRAG.

## 9. OWNER override: подготовка execution (после первоначального checkpoint)

Owner разрешил официальный 0.77B evaluator, локальные изолированные downloads/install/runtime и pinning полученных bytes вместо недоступного author immutable checksum. Redistribution не разрешена и не производится. Полные CRAG corrective actions/web/new generator/training не входят в разрешение. Общий disk budget всех агентов 18 GiB; веса не дублировать.

- `E_acquire_crag.py`: stdlib-only acquisition ровно шести файлов из author-linked folder/file IDs, receipt `E_assets/acquisition.json`. Socket timeout 30s, deadline одного файла 300s, total 600s, weight cap 3,000,000,000 bytes, подтверждение Drive form допускается только с тем же ID и exact `drive.usercontent.google.com` endpoint. Нет автоматических retry/HF fallback. HTTP errors/confirmation HTML сохраняются отдельно, received hashes и timestamps записываются. Одна копия весов, atomic rename после size validation; partial не считается полученным checkpoint.
- `E_crag_runner.py prepare` выполнен stdlib-only: создан `E_native_pairs.json`, **21 пары = все 10 native windows Q46 + все 11 Q16** из current-head CI run38232527945. Frozen question/corpus hashes, каждый char span/window hash и document hash проверены; никаких ручных answer-window selections, deduplication, lookups/переводов. Это observed native replay, не подтверждение всех source-policy guards или публичная интеграция нового пути.
- `E_crag_runner.py run`: только по coordinator serial slot. Shared CPU env `model-runtime` устанавливает исключительно C; E не меняет env. FP32 CPU, batch1, threads8, original question + ` [SEP] ` + complete native window; preflight all token lengths без truncation. >512 — `OVERSIZE_NOT_SCORED`, group `INCOMPLETE_NOT_CLASSIFIED`, остальные eligible pairs scored; ни одного усечённого window. Max20/case, max40 total; никаких retries. Strict `T5ForSequenceClassification` local safetensors loading, проверка loading-info на missing/unexpected/mismatched keys, num_labels1/regression; random reinitialized head запрещён.
- Diagnostic group thresholds из released PopQA code `(0.592, −0.995)` зафиксированы без calibration по нашим результатам; logits/ranks/group labels не считаются answer correctness, sufficiency или нового admission permission. 900s между шагами/12GiB RSS stop ceiling; координатор должен дополнительно поставить finite process timeout, потому что один native forward нельзя прервать этой межшаговой проверкой.
- Receipts сохраняют model/config/tokenizer hashes, received timestamp, loading info, exact inputs/token lengths/token-ID hashes, CPU versions/precision/parameters/load/forward times/RSS, все scored/oversize IDs и group label. No web correction, no host generation, no production defaults.
- Context7 resolution для текущего Transformers loading API был вызван; сервис вернул `Monthly quota exceeded`. Это не весовой/runtime blocker; runner не исполнялся для догадочного подтверждения API.

Команда **только после coordinator serial slot и successful acquisition**:

```sh
timeout 1200s /tmp/opencode/docatlas-review-evidence/admission-full-20261012/model-runtime/bin/python /tmp/opencode/docatlas-review-evidence/admission-full-20261012/E_crag_runner.py run --serial-slot COORDINATOR_ASSIGNED_SLOT
```

До назначения slot model loading/inference остаются **NOT RUN**, generation **NOT RUN**, полный CRAG **NOT RUN**. Статус acquisition передаётся отдельным receipt, не считается доказательством inference.

### Acquisition завершён: READY_NOT_LOADED

Официальный Drive download успешно завершился **2026-10-12 11:20:19 UTC** (начало11:17:28 UTC), 171.24s всего; weight transfer159.51s. Весь snapshot: **2,955,762,797 bytes**, без второй копии весов. Для model получены сначала HTTP200 confirmation HTML, затем HTTP200 binary с matching Content-Length2,954,943,548. Это штатное author Drive confirmation, не retry или альтернативная модель. Receipt с исходными IDs/URLs/status/headers/date: `E_assets/acquisition.json`; сырой confirmation HTML: `E_assets/model.safetensors.confirmation-0.html`.

| Received asset | SHA-256 |
|---|---|
| `model.safetensors` | `cec06c4520a5c3c114f1bbc0e64c40e8375eee61e5bb0a56a38131cf91860af1` |
| `config.json` | `461ccb7bcf02bd80e57086fa943a2466a10df28891aea1923d64f29ac3f87a64` |
| `tokenizer_config.json` | `294d5c94534a121446dbe873dc6d3e736e31c3e71ac628fd6105d1d3f73b7eac` |
| `spiece.model` | `d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86` |
| `special_tokens_map.json` | `7a1985a994c41886db38c719d2a3d2f40606663cc19d7c5d6a85d349320e06d2` |
| `added_tokens.json` | `ea5a91a3234f66ea642c8e672d67f0f493759a9bee6910ae304ea9b9492118b5` |

Это **received-byte experimental snapshot**, не author immutable checksum; owner explicitly approved this provenance boundary. Не распространять assets. Config/tokenizer читаются из той же авторской папки; HF fallback не использовался.

Дополнительное stdlib-only header inspection, без загрузки тензоров: `E_assets/header_receipt.json` — 513 stored tensors, все F32, **738,718,721 stored scalar elements**; присутствуют `classification_head.dense` и scalar `classification_head.out_proj` weights/bias, shared embedding `transformer.shared.weight`. Header68,656bytes; payload end + header +8 совпадает с полным размером файла. Это конкретный snapshot size уточняющий округлённое paper0.77B; runtime unique parameter count подтвердит только последующий разрешённый load. Random head не предлагается.

Frozen `E_native_pairs.json` SHA-256: `d42cbde32816d68b07ca969ffe325e577a56af3b43c0cfb567b286476b616c85`. Runner SHA-256 на передаче: `237afbcf25abee5702f56615ab73ed8e278793204b88ecf96c49f29922769016`. Assets **готовы**; execution только по coordinator serial slot, model runtime всё ещё **NOT RUN**. Команда выше готова, shared env не устанавливался/не менялся E.

## 10. Фактически выполненный evaluator replay — coordinator-E-001

Координатор исполнил подготовленный runner один раз **2026-10-12 11:26:21–11:26:56 UTC**. E только прочитал полученные receipts и независимо сопоставил frozen source spans с rows; новых model/product/provider calls или downloads при этом не было.

### Identity, runtime, measured resources

- Raw receipt: `E_evaluator_receipt.json`, SHA-256 **`8837e4b63721c16defa4adf449de704e2eb257f21c54975e8d69bd14178f0a6c`**. Log: `E_assets/execution.log` (только deprecation warning `torch_dtype` и итоговая summary, не runtime exception).
- Авторские Drive weights загружены как **T5ForSequenceClassification**, scalar regression, **738,718,721 runtime parameters**, все **torch.float32**, CPU, без quantization. `loading_info`: missing/unexpected/mismatched/error keys — все пусты. Head не создавался случайно заново. Model weight bytes2,954,943,548; полный полученный snapshot2,955,762,797bytes. Received model SHA `cec06c4520a5c3c114f1bbc0e64c40e8375eee61e5bb0a56a38131cf91860af1`, не author immutable checksum.
- Python3.12.3, PyTorch2.10.0+cpu, Transformers4.57.1, threads8, seed0. Precision соответствует FP32 author snapshot; software versions отличаются от author Python3.11/Torch2.1.2/Transformers4.36.1. Поэтому не заявлять полное environment/paper reproduction.
- **17 настоящих model forward calls**, **0 generator calls**, 2 diagnostic questions. Все21 observed windows сохранены в input/preflight receipts; 4 pair inputs >512 не передавались model forward. Нет retries, hidden clipping, укороченных вручную passages или model swaps.
- Scored unpadded input tokens **3546**, padded forward positions **8704 =17×512**; overflow preflight tokens **2782**, они не считаются выполненной модельной работой или provider billing.
- Total process elapsed **35.2552s** (включает snapshot integrity hashing/imports/tokenization/load/forwards/receipt writes), model-load API interval **0.1194s**, sum17forward intervals **31.2043s**. Q46 scored forwards12.9708s, Q16 scored forwards18.2335s.
- Первый forward без отдельного warmup **1.7261s**; следующие16: mean **1.8424s**, median **1.7001s**, min **1.4098s**, max **2.6546s**. Это first-versus-subsequent observations одного запуска, **не measured stable cold/warm benchmark или p95**. OS page cache не очищался; быстрый load interval нельзя выдавать за чтение всех3GB с cold disk или полный cold-start. Единственный observed startup-inclusive elapsed35.2552s приводится отдельно от forward latency.
- Peak process RSS **3,596,248 KiB =3.42965GiB**. Нет GPU/VRAM measurements (deviceCPU), нет product latency/generation costs. Acquisition171.24s указан отдельно, не скрыт и не складывается с forward временем как repeated-load latency.

### Frozen facts ↔ конкретные scored rows (независимое сопоставление E, не final PASS)

| Case | Полный native pool / scored | Answer-bearing original window | Факт и результат scoring |
|---|---|---|---|
| Q46 | 10 / **8** | `child-460bf5decf12245e2c132591e1fdb1a4b62187aa`, `[6919,7107)` | Frozen fact `[6952,6996)` «Одинаковые неправильные ответы не дают PASS.» целиком присутствует в actual model input.200tokens, logit **−0.80594957**, **rank2/8 scored**, не rank2/10 полного pool. |
| Q16 | 11 / **9** | `child-697e1c5afe5701899bc1aecd13e99492ff433418`, `[1024,2100)` | Frozen fact `[1152,1209)` «завершение содержит `duration_ms`\n  и `trace_incomplete`.» целиком есть в подготовленном input, но746tokens → **OVERSIZE_NOT_SCORED**: score/rank отсутствуют, модель не оценивала это окно. |

Q46 highest scored row — `child-406ced8f8698b8f1eb1f75f1e9757900f269e813`, `[6694,6723)`, logit **−0.28366077**. Его исходный текст только **«как ожидаемый ответ второго.\n»**, то есть фрагмент окончания соседнего предложения, не полный required negative proposition. Это конкретное предупреждение против top1-as-sufficiency/admission: полезное окно оказалось rank2 среди scored, выше него — неполный фрагмент. Не доказательство общей ошибки модели на всех задачах и не public delivery FAIL; G окончательно оценивает outputs по frozen oracle.

### Overflow — вся потеря явно записана, не спрятана

На **каждый** из двух original questions не scored два windows:

| Candidate | Original span | Полная длина question+window | Pair outcomes |
|---|---|---|---|
| `child-aae7dd2377863cdbf75e03e0a8187a511c8247fc` | `[7770,8589)` | **645 tokens** | Q46 и Q16: OVERSIZE_NOT_SCORED |
| `child-697e1c5afe5701899bc1aecd13e99492ff433418` | `[1024,2100)` | **746 tokens** | Q46 и Q16: OVERSIZE_NOT_SCORED; в Q16 это answer-bearing window |

4 overflow — это **четыре question/window пары**, не четыре разных source windows. Полный pool rank/evaluator judgement **не измерены**. Сравнивать эту17-pair выборку с моделями, оценившими весь21-pair pool, как одинаковую complete evaluation нельзя. Преодоление overflow потребовало бы отдельной явно разрешённой adaptation (другая длина или span-preserving segmentation с новым бюджетом), которой в этом запуске нет; не добавлять её post-hoc ради Q16 PASS.

### Group/action diagnostic — не correction и не калиброванная probability

Receipt status **`PARTIAL_OVERSIZE_NOT_FULL_POOL`**; обе case group labels **`INCOMPLETE_NOT_CLASSIFIED`**, это правильная явная граница данного запуска. На только scored subsets released PopQA trigger `(upper0.592, lower−0.995)` **would trigger AMBIGUOUS для обеих cases**:

- Q46 scored range **[−0.96616328, −0.28366077]**.
- Q16 scored range **[−0.94380635, −0.75523639]**.

Ни один scored logit не достиг0.592; subsets имеют scores≥−0.995. Это **условный would-trigger**, не actually executed corrective action и не verdict полного pool: неизвестные overflow scores могли бы изменить label на Correct. Uncalibrated regression logits не probabilities; нельзя трактовать все отрицательные scores как все-нерелевантно, требовать arbitrary0.5 или объявлять эти PopQA thresholds обобщённым DocAtlas admission proof. Для Q46 top2 retention предположительно сохранил бы scored fact, но selection/public delivery/host answer **здесь не выполнялись**, поэтому это не recovered-answer claim.

### Итог actual scope

**Реально проверено:** загрузоспособность конкретного author-linked received snapshot с правильной regression head и CPUFP32 inference;17 bounded question/window logits, ранги scored subsets, явные4overflow, measured time/RSS. **ADAPTED partial offline replay**, не public integration и не faithful full CRAG reproduction.

**NOT RUN:** web rewriting/search, decompose/filter/recompose refinement, corrective actions всех трёх branches, product admission/public payload change, host generation/citation correctness, source-supported answer benefit, full-pool ranking Q46/Q16, общая threshold calibration/holdout. Source scope/hash lineage из archived native windows не заменяет fresh public access/consent/version validation. Никаких новых claims answer_supported/edit_ready.

**Рекомендация:** не принимать официальный CRAG evaluator как готовый default admission на основании этого запуска: off-domain low scores, Q46 top1 incomplete fragment, Q16 unscored answer window и неполный pool не дают такого основания. Для текущего итогового сравнения честно отнести его к исполненному **частичному diagnostic arm**; финальный PASS/FAIL по качеству и выбор следующего метода — G/координатор. Никаких дополнительных вызовов или downloads E не запросил и не выполнил.
