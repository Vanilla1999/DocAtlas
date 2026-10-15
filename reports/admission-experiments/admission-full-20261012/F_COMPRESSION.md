# F — SWE-Pruner / LLMLingua-2: initial admission feasibility

Дата: 2026-10-12. **Latest outcome: actual compression and paired host calls EXECUTED by coordinator; independent final G judgments pending.** LLML raw CPU FP32 canonical algorithm, client exact-line wrapper ADAPTED; SWE CPU FP32 eager + exact source-run wrapper ADAPTED. Public product DTO не менялся. Статические NOT RUN/blockers в §§1–7 ниже — история этапов, superseded итоговыми receipts §8; полное воспроизведение эффективности статей не заявляется.

**Measured conclusion:** LLML raw сокращает cl100k tokens примерно вдвое, но текущая exact line-closure **увеличивает** submitted host input: Q16 +7.57%, Q46 +6.30% (o200k content estimate). SWE short Dart smoke сократил host content 575→450 tokens (−21.74%), сохранил все четыре frozen witness spans; long-code/semantic/citation generalization не доказаны. Q16 generated quote не является exact substring из-за удалённого newline; не repaired. G владеет окончательными PASS/FAIL. Новых runtime/model/provider/product calls для этого update не было.

## Решение первоначальной read-only фазы (история; текущий вывод — §8)

Следующий минимальный pruning-кандидат — **LLMLingua-2 XLM-R на одном неизменном пакете выбранного контекста**, только после восстановления candidate delivery и разрешения исполнения. Сравнивать с тем же пакетом без pruning; exact-source wrapper считать **ADAPTED**, а не исходным алгоритмом. Не внедрять token-pruned строку в поле дословной цитаты.

**SWE-Pruner заблокирован строгим лимитом:** официальный checkpoint содержит по HF safetensors metadata **634 337 034 параметра**, то есть больше 600 000 000, несмотря на округлённое название «0.6B». Нужны явное исключение для этого checkpoint и подходящий GPU либо отдельно согласованная CPU-адаптация. Замена на обычный Qwen reranker не воспроизводит SWE-Pruner. Code-результаты не объединять с direct40.

Ни один compressor после admission veto не вернёт Q46/Q16 из пустой публичной выдачи. Измерение compression ratio не доказывает полноту фактов, правильность ответа или допустимость источника.

## Рабочая точка и ограничения

- Проверено: clean `git status --short`, branch `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`.
- Полностью прочитан `../MULTI_AGENT_ADMISSION_FULL_PROTOCOL_RU.md`, в частности роль F, запреты и формат evidence. Прочитаны `AGENTS.md`, `v2plan/PR211_CHECKPOINT_RU.md`, текущий `STATE.md`, frozen questions/corpus/manifest, ADR0003 и все пять назначенных q46-admission отчётов. Их выводы используются как навигация, не новые runtime observations.
- Архивный product SHA `d8af387de507007f2b8c83f04aac78feb9b6760c` не объявляется испытанием текущего HEAD. В этой роли raw baseline не переаудировался.
- Только этот внешний файл записан; repo, тесты, oracle, corpus не менялись. Ни imports/pytest/AST/install/model execution, ни weights downloads, providers, CI, nested agents не выполнялись.
- Hardware из подтверждённого coordinator checkpoint: i9-12900K, 24 logical CPUs, RAM 62 GiB, около 30 GiB available, disk 27 GiB available; GPU pending. Это не измерение доступного model runtime.
- SHA-256 трёх frozen файлов независимо проверены `sha256sum`, совпадают с manifest:
  - `questions.json`: `2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67`;
  - `questions_extra40.json`: `5d0618db2bc1ddb18f65ac246b79ecb1adaadeef3a1618ed68d9f5a5784a12dc`;
  - `corpus.md`: `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`.

## 1. Первичные источники, revisions и metadata без весов

Revisions ниже получены из публичных GitHub/HF JSON API 2026-10-12, затем configs/code прочитаны по immutable URLs. Это фиксация выбранного snapshot, не утверждение, что именно эти commits использовались авторами для всех таблиц статьи. Размеры/parameter counts — опубликованные metadata, не локальный пересчёт загруженной модели.

### SWE-Pruner, не SWE-Pruner Pro

- Paper: **SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents**, `https://arxiv.org/html/2601.16746v4`, 07 May 2026, CC BY 4.0. Прочитан текст §§3–5, приложения B/D/F/J. Не смешивать с v1 или SWE-Pruner Pro `2607.18213`, использующим hidden states большой coding-модели.
- Official repo связан прямо в paper и checkpoint card: `https://github.com/Ayanami1314/swe-pruner`.
- Default branch **public**, pinned commit **`96171b5f3ecaf89745cbeb436c8893b57f3400bd`**, commit date 2026-06-30. Запрос `commits/main` дал 422; это исправленный branch lookup, не отсутствие репозитория.
- Checkpoint **`ayanami-kitasan/code-pruner`**, immutable HF revision **`863cee3198c715c9df1faa422a3490e0832bb734`**, card license **MIT**; repo/package MIT. Backbone Qwen3-Reranker-0.6B имеет Apache-2.0, сохранить оба license notices.
- Config: `SwePrunerForCodeCompression`, backbone `Qwen/Qwen3-Reranker-0.6B`, bottleneck 256, CRF head, multilayer fusion, one fusion layer, 8 heads, BF16 declaration. Custom implementation необходим: card рекомендует авторский repo, не произвольный `AutoModel`.
- HF safetensors metadata: BF16 **595 776 512** + F32 **38 560 522** = **634 337 034**. Backbone сам по себе ниже лимита; полный pruner выше на **34 337 034 (5.72%)**. Quantization уменьшает bytes, не число параметров, и лимит не исправляет.
- `model.safetensors` size **1 345 834 856 bytes**; LFS SHA-256 **`373b77f5262c3298b803303d49ea38949d3e92f08dc3bbb90b03f490413adae9`**. Прочитан только JSON tree/LFS pointer metadata, ни один byte весов не получен.
- Nested dependency snapshot: `Qwen/Qwen3-Reranker-0.6B` revision **`e61197ed45024b0ed8a2d74b80b4d909f1255473`**. `swepruner.py:75–77` запрашивает backbone config по mutable name без revision; одного outer checkpoint SHA недостаточно для полностью offline/pinned загрузки. Нужны предварительно согласованные pinned config/tokenizer files, offline load и запрет неожиданных downloads; backbone weights отдельно не нужны при корректной загрузке полного checkpoint.
- **Контекст:** tokenizer metadata 131072 — не рабочий лимит wrapper. `prune_wrapper.py:528–529` жёстко задаёт **8192 tokens**, включая hint/instruction overhead; длинный code разбивается на chunks, overlap default 50. Не заявлять 128K joint reasoning или считать chunked input одним forward.
- Official inference README: Python >=3.12, PyTorch >=2.8.0, Transformers >=4.57.1, Flash Attention 2/CUDA; package 0.1.1. Torch/flash-attn закомментированы в dependency list и не устанавливаются надёжно одним package install.
- `model_structure.py:215` default `attn_implementation="flash_attention_2"`; wrapper auto-selects CPU при отсутствии CUDA, но это **не доказательство CPU compatibility** при таком attention backend. CPU FP32/eager/SDPA — отдельная **ADAPTED** конфигурация, требующая разрешения и runtime проверки. Нельзя переносить paper latency на i9.

Immutable evidence URLs:

- `https://huggingface.co/api/models/ayanami-kitasan/code-pruner` — counts/card (API current snapshot зафиксирован SHA выше).
- `https://huggingface.co/api/models/ayanami-kitasan/code-pruner/tree/863cee3198c715c9df1faa422a3490e0832bb734` — size/LFS hash.
- `https://huggingface.co/ayanami-kitasan/code-pruner/raw/863cee3198c715c9df1faa422a3490e0832bb734/config.json` и `README.md`.
- `https://raw.githubusercontent.com/Ayanami1314/swe-pruner/96171b5f3ecaf89745cbeb436c8893b57f3400bd/swe-pruner/README.md`, `pyproject.toml`, `src/swe_pruner/prune_wrapper.py`, `model_structure.py`, `swepruner.py`.

### LLMLingua-2

- Official paper: **LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression**, Findings ACL 2024, pp.963–981, DOI **10.18653/v1/2024.findings-acl.57**; `https://aclanthology.org/2024.findings-acl.57/` и linked PDF. Здесь прочитана официальная publication page/abstract и авторский implementation; полное PDF не анализировалось, paper-table reproduction не заявляется.
- Official repo: `https://github.com/microsoft/LLMLingua`, pinned commit **`5a4c78ae18ab17a98cf997e8259354e546081d64`**, MIT. README явно связывает оба следующих checkpoints с LLMLingua-2.

| Official checkpoint | HF immutable revision | Parameters / precision metadata | Model license | Context |
|---|---|---|---|---|
| `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | `ebaba9b0e874dadd3003ffcff828e4397e568089` | **558 945 282**, F32 | MIT | config positions 514; implementation sequence **512**, content chunks <=510 |
| `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` | `5f0c82792b7ea14c6484e015b6a072009496b7f2` | **177 341 186**, F32 | Apache-2.0 | config positions **512**, same chunked implementation |

Оба ниже строгого лимита 600M. mBERT — официальный small alternative, не скрытая замена XLM-R при сравнении: результаты/model IDs должны быть отдельными. Для первого сравнения рекомендован XLM-R, small пока metadata-only.

| File | Bytes | HF LFS SHA-256 (metadata, weights NOT downloaded) |
|---|---:|---|
| XLM-R `model.safetensors` | 2 235 829 648 | `a33a153b2493bff6be06af6921e69de9c0d0bb6ff06fe5bbb68670ba8d980ae2` |
| mBERT `model.safetensors` | 709 388 104 | `22b9ecde52fec5c97e8c54a293be768727df95a81c6c8dccb03f262a50c58324` |

Config cards indicate Transformers 4.38.2/F32 training-save metadata; это не требование точного installed runtime. Repo `setup.py`: Python >=3.8, transformers>=4.26, accelerate/torch/tiktoken/nltk/numpy; конкретные совместимые dependency versions нужно freeze до execution. CPU путь прямо есть в `prompt_compressor.py:119–158`, CPU F32 default. В отличие от SWE, CUDA/flash-attn не обязательны для этой архитектуры. Реальная latency/RAM/русская factual retention неизвестны.

LLMLingua-2 — task-agnostic token classification, не relevance/admission/sufficiency evaluator. Model multilingual не означает подтверждённую корректность русского отрицания Q46. Long input допустим через последовательность 512-token chunks; это не длинный совместный attention. Репозиторий использует token decoding/word aggregation, не возвращает готовый exact-source char-span contract.

Immutable URLs:

- `https://raw.githubusercontent.com/microsoft/LLMLingua/5a4c78ae18ab17a98cf997e8259354e546081d64/README.md`, `llmlingua/prompt_compressor.py`, `setup.py`, `LICENSE`.
- `https://huggingface.co/microsoft/llmlingua-2-xlm-roberta-large-meetingbank/raw/ebaba9b0e874dadd3003ffcff828e4397e568089/config.json`.
- `https://huggingface.co/microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank/raw/5f0c82792b7ea14c6484e015b6a072009496b7f2/config.json`.
- HF JSON `/api/models/{model}` counts/card и `/api/models/{model}/tree/{revision}` size/hash, без скачивания safetensors.

**Library docs:** обязательный Context7 resolve запрос `LLMLingua` был сделан без repo/corpus данных; ответ **Monthly quota exceeded**. Документационный канал недоступен, API claims выше основаны на pinned первичном implementation/README. Не заявляется успешный Context7 lookup; повторные запросы не делались.

## 2. Exact-source incompatibility и безопасная граница адаптации

ADR0003:29,55,79–88 требует исходные bytes и координаты вместе с evidence, с сохранением admitted occurrence. Existing integration oracle (`tests/test_project_context_quality_v2_protocol.py:402–429`) проверяет непрерывную подстроку source window и independent canonical envelope hash.

**LLMLingua token deletion:** retained tokens из разнесённых позиций не образуют одну непрерывную цитату. Detokenization также может менять whitespace. Нельзя объявить compressed string исходным `[start,end)`, назначить ей полный source hash или считать её дословной только потому, что слова пришли из источника. Удаление `не`, условия, antecedent или одного члена сравнения может создать неверное утверждение без новых слов.

**SWE line deletion:** отдельные сохранённые строки могут быть дословными, но их склейка через исключённые строки не является одним span. Official `prune_wrapper.py:262` использует `splitlines()` (теряются raw line endings); `:277+` добавляет filtered markers и иногда возвращает ранее удалённый single-line gap. Поэтому использовать `kept_frags` + frozen raw bytes, а не `pruned_code` как цитату. CRLF fidelity проверяется отдельно.

Минимальная **source-span-preserving wrapper, ADAPTED (пока только спецификация)**:

1. Модель получает только уже policy-valid, зафиксированные candidate/source texts. Она не расширяет catalog/scope/version/access/consent и не создаёт authority.
2. Keep mask/line IDs переводятся в исходные char/UTF-8 byte offsets **во время scoring/tokenization**, не поиском отдельных повторяющихся слов в финальной decoded строке. Для LLMLingua нужен минимальный mask/offset adapter; ambiguous alignment не допускается как валидный evidence.
3. Public excerpts строятся исключительно `original[start:end]`; каждый непрерывный run отдельно идентифицирован. Между ними omission marker вне quote. Retained/dropped maps сохраняются в private evidence, исходный document hash, generation, scope/version/catalog binding неизменны; новый excerpt/envelope hash пересчитывается по прежнему контракту.
4. Для совместимости с нынешним substring oracle предпочтительнее расширить token mask до **полных исходных structural atoms** (предложение/пункт/code block) и вернуть каждый atom отдельно, без синтетической склейки. Это меняет granular selection и compression ratio, поэтому отдельный ADAPTED arm, не оригинальная token compression.
5. Сохранить все обязательные admitted seed occurrences; если pruning их удаляет, исходный алгоритм и current contract расходятся. Не скрывать это rehash. Консервативная wrapper восстанавливает содержащие atoms, что может полностью обнулить экономию. Semantic dependencies между atoms восстановлением bytes автоматически не гарантируются.
6. Отдельные verdict: `CURRENT_CONTRACT` (source fidelity/admitted lineage/authority/negative expectations) и `EXPERIMENT_OUTCOME` (facts + real host answer/citations + net cost). Новые поля/representation не внедрять без решения владельца.

Прямой compressor output допустим только как ясно обозначенный derived/non-quote auxiliary input в отдельно разрешённом host experiment. Если вместе с ним хосту передаётся весь оригинал для цитирования, считать **все** эти tokens: чистой экономии может не быть. Если исходные цитаты недоступны хосту, верная цитата из памяти не засчитывается.

## 3. Existing code-oriented public integration: что подходит и что нет

Найден **реальный существующий code-oriented integration seed**:

`tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_finds_relevant_source_files_by_exact_terms` (`:223–261`) и соседний `::test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded` (`:311+`). Реальные временные Dart files, finite `code_files` catalog, `LibraryDocsService`, handler `handle_project_tool("get_patch_plan_context", ...)`, без retrieval/model mocks. Второй уже независимо проверяет original hashes/source line refs через `_assert_selected_source_evidence` (`:50–72`). Fixture содержит `MenuLine -> MenuPageBuilder`, `SystemLine -> MenuIcon`, `MenuNotifier` flags. Это не unit private-helper тест по фактической границе.

**Но недостаточно для полноценного P3:** advanced/compatibility handler, не текущий advertised `get_docs_context`/installed stdio; fragments очень короткие, нет живого host answer или repository-edit outcome. Вопрос «Plan ... changes» не задаёт достаточного независимого intended patch outcome. Нельзя заявлять воспроизведение SWE-Bench или long-code savings на этом примере. Dart out-of-domain относительно основного Python evaluation paper — явно ADAPTED.

`tests/test_mcp_code_context_tool.py::test_get_code_context_filters_unconnected_generic_keyword_matches` (`:77–96`) имеет navigation chain fixture, но `_tab_fixture` **не объявляет finite code catalog**, а assertions проверяют исключения, не положительное наличие answer-bearing snippets. Не выбирать его как готовый positive pruning benchmark: универсальная пустота могла бы удовлетворить такой negative. Private scanner tests (`test_dictionary_exit_local_callers.py`, `tests/docs/test_source_map.py`) не годятся как public P3 harness.

В осмотренных текущих public main-flow/host-scope integrations catalog `code_files=[]`, факты — prose docs, не длинный code. Подходящий **готовый advertised long-code + actual host outcome** сценарий не установлен; это ограниченный поиск, не доказательство отсутствия такого сценария во всём repo.

### Один минимальный P3 план при разрешении

Не новый benchmark framework: переиспользовать isolated prepare/index/public-call orchestration из `test_project_context_quality_v2_protocol.py` / `eval/main_flow_comparison/run_extra40.py`; отдельный nonfrozen code case, не изменять их frozen corpus/questions. Предпочтительно owner G сначала найдёт действующий подходящий code case в общем eval; если его нет — одна интеграционная задача, а не матрица или приватный helper тест.

- На изолированных данных поместить **один hash-pinned Python code listing** в явно admitted documentation source (например `docs/code-reference.md` с целым fenced listing), реальные SQLite/retrieval/selection/validation, настоящий `prepare_docs` и `get_docs_context`. Так публичная граница текущая, не скрытый get_patch_plan_context. Эффект на произвольный raw shell tool output или edit-agent не объявлять доказанным.
- Минимальная задача: «При каких условиях обработчик повторяет запрос и что происходит после исчерпания попыток?» Hint — **та же исходная формулировка задачи**, frozen до просмотра oracle; не перечислять правильные branches/identifiers из expected answer. Для single-turn это соответствует paper §3.4 (task description как hint), без дополнительного hint-generation call.
- Independent input должен содержать retry branch, прекращение при non-retryable response, окончательный error после exhaustion и соседнюю unrelated функцию. Полные facts/oracle/source hashes G фиксирует из fixture до результатов; F не задаёт expected через production parser. Достаточный context length выбирается естественным listing, не тысячами скрытых операций ради ratio. Если полученный code packet короток, честно отметить smoke-only, не добавлять искусственный шум после результатов.
- Один actual public acquisition сохраняется и используется в обеих чистых host sessions: full packet vs SWE line selection + exact runs. Fixed threshold **0.5** — авторский validation-set default (paper appendix D), не калиброванная probability и не Q46 tuning; first-fragment false, overlap50, hard 8192 wrapper window. Протокол serialized model calls.
- Oracle проверяет все условия/ветви и source-supported host answer; отдельно exact snippets/span/hash, wrong-scope exclusion, неизменное состояние, false authority. При отсутствии достаточного публичного code packet P3 остаётся NOT RUN / blocked upstream, не заменяется private offline benchmark.
- Это **ADAPTED DocAtlas single-turn code-QA integration**, а не полное воспроизведение multi-turn agent paper. Source wrapper тоже ADAPTED. Edit/patch correctness не проверяется и не заявляется. Code score только отдельно.

## 4. LLMLingua-2: fixed-context paired comparison

Минимальный первый срез после разрешённой delivery фазы: **Q46 + Q16** с исходными вопросами, полный unchanged selected source packet на каждую задачу. Только если выбранный packet реально доставляет нужные факты до compression; использовать source-policy-valid B1 packet после независимого audit. Baseline B0 empty packet не является осмысленным испытанием compressor.

1. Публичные existing calls не дублировать ради методов. Coordinator сохраняет один пакет/candidate IDs/порядок/границы/hash/generation и его точный model-visible serialization; selection/retrieval не перезапускаются под compressor.
2. Два host arms: **P2-control no pruning** и **P2-SP LLMLingua-2 + atom/source-span wrapper ADAPTED**. Сравнение в пределах одного и того же вопроса/контекста; не смешивать с ranking improvements. Raw token-pruned output сохранить privately как diagnosis; если нужна отдельная raw-method efficacy ветвь — отдельное разрешение и derived-text contract, не подмена P2-SP.
3. XLM-R pinned revision выше, CPU F32, `use_llmlingua2=True`; заранее freeze retain-rate **0.5** как один operational target, не лучший результат sweep. Это proposed target, не утверждение об авторском лучшем гиперпараметре. Question/instructions/source identity metadata **не сжимать**. Без question-conditioned reranking/context deletion: fixed context order, token compression only. Force tokens не пополнять Q46/PASS/negation/DocAtlas предметным словарём; никаких oracle spans в model input.
4. Fixed host prompt/model/version/temperature/budget координатора, одинаковые чистые сессии. Не передавать required facts, source oracle spans, чужие results или private diagnosis; source coords допустимы как публичная citation metadata, не hidden gold annotations. Docs — данные, не инструкции. Реальный ответ и citations обязаны сохраниться в receipts.
5. Independent mandatory facts: для Q46 полная negative proposition `[6952,6996)`; для Q16 совместная attribution окончания + **duration_ms и trace_incomplete**, `[1152,1209)`. Раздельно оценить source fact delivery, достаточность пакета, factual/citation correctness хоста, ложные отказы/unsupported claims. Rate/token reduction не oracle.
6. До wider run: source/citation/authority defect, потеря отрицания/условия либо alignment ambiguity — stop и preserve receipt, без повторов до PASS. Нулевой/больший размер wrapper не FAIL качества, но это отсутствие cost-benefit.
7. Только если smoke полезен: переиспользовать уже frozen old10/direct40 packets; максимум один predeclared retain-rate и одна модель. Previous28 успехов фиксируются IDs, не общей суммой. B0/B1 и raw/wrapped pruning не усреднять. Holdout/negative obligations принадлежат G.

## 5. Результаты и resource feasibility

| Метод | Точная модель / размер | Статус | Facts / real host answers / source-policy verdict | Calls/tokens/time/RAM |
|---|---|---|---|---|
| P2 raw LLMLingua-2 | XLM-R revision `ebaba9b…`, 558 945 282 | **NOT RUN**, direct exact-source incompatible | NOT RUN | NOT RUN |
| P2-SP source-span wrapper | та же модель, fixed packet | **NOT RUN**, planned **ADAPTED** | NOT RUN | NOT RUN |
| P2-small | mBERT revision `5f0c827…`, 177 341 186 | **NOT RUN**, metadata-only alternative | NOT RUN | NOT RUN |
| P3 SWE-Pruner | code-pruner revision `863cee3…`, 634 337 034 | **NOT RUN**, exceeds strict limit; GPU pending | NOT RUN, separate code-QA ADAPTED plan | NOT RUN |

Существующее железо вероятно достаточно для **последовательного LLMLingua CPU F32 smoke**, но это planning estimate, не measured fit: XLM-R weights ~2.08 GiB, mBERT ~0.66 GiB; activations/runtime/temporary load/host память сверху. Предложенный hard reservation **12 GiB RAM**, batch1, 8 CPU threads, **6 GiB disk** для одной XLM-R environment/cache. Download/env allowance не означает занимать весь RAM/disk; OOM/timeout фиксируются без молчаливой precision/model замены.

SWE stored weights ~1.25 GiB; CPU full FP32 tensor storage примерно2.36 GiB до overhead, однако FlashAttention blocker важнее размера. GPU reservation предложить только после inventory: один CUDA GPU с **>=8 GiB free VRAM**, serial batch1, <=8192-token chunks, не параллельно с другими agents/models. Это requested ceiling/planning assumption, не гарантия worst-case memory fit. Default mixed saved precision и wrapper casting/autocast фактические dtypes должны быть записаны; не называть unmodified wrapper «pure canonical BF16» без проверки. CPU/backend/precision modification — ADAPTED, quantization не включать в первый срез.

## 6. Передача координатору: permissions / calls / бюджет

**Текущее разрешение:** только read-only source/text/hash inspection + этот report. Все inference, downloads, installs и product calls запрещены; разрешения не выводятся из доступности HTTP/API инструмента. Corpus/questions/candidate texts вовне не передавались. Public-source HTTP содержит только публичные names/revisions; Context7 query тоже только library-level.

**Фактически выполненный research budget:** 33 read-only HTTP requests через `execute.fetch` (GitHub/HF metadata/text; из них 422 wrong main branch и 404 root pyproject), 2 primary-page webfetch, 1 discovery websearch, 1 неуспешный Context7 library resolve. Ноль weight bytes, model/product/host inference calls, installations, providers, CI. Локально только чтение/search, git identity/status и sha256sum. Фактические HTTP response bytes/latency не измерялись. Tool-managed вывод статьи — incidental tool artifact, не дополнительный authored report.

**Один конкретный request на следующий минимальный этап (не разрешение, действие не выполнено):**

1. Разрешить координатору изолированный local CPU runtime/install/download **только** LLMLingua pinned repo `5a4c78ae…` и XLM-R checkpoint `ebaba9b…`, один environment/cache под `/tmp/opencode/docatlas-review-evidence/`, dependencies заранее lock и review; веса максимум2.24GB плюс tokenizer/config, общий disk ceiling6GiB. CPU8 threads, peak RAM ceiling12GiB, whole smoke timeout30min, no retries, no quantization, network disabled после подготовки.
2. Разрешить **4 host calls total**: Q46/Q16 × {no-pruning, source-span ADAPTED}. Reuse existing public acquisitions; если fresh нужны для exact-SHA integration — максимум **1 prepare_docs + 2 get_docs_context**, только approved isolated public harness, отдельно от host calls. Compressor **2 compression requests**, один cold model load; forwards/chunks считать реально, proposed cap **32 total encoder forwards** (512-token batch1 chunks), при превышении stop, не truncate frozen inputs молча. Host budget **<=16k input / 1k output tokens per call**; превышение — blocker, не переписывание вопроса. Dollar ceiling назначить после выбранного host tariff, при отсутствии tariff/provider consent host execution NOT RUN; новых providers не добавлять.
3. Только coordinator назначает adapter/harness file owner; F сейчас никаких code files не получил. Изменение source representation и admitted-seed lineage сначала G review/owner contract decision, никаких отключений validator.
4. SWE отдельное последующее разрешение: **explicit parameter-limit exception до 634 337 034** для `863cee3…` (иначе окончательный NOT RUN), pinned repo `96171b5…`, pinned Qwen config `e61197e…`, CUDA inventory и dependency/backend review. Один isolated code-QA acquisition (1 prepare +1 get), **1 pruning request**, <=2 actual 8192-token forwards, 2 host calls total (no-pruning/pruning), без hint-generation extra call; 8GiB VRAM reservation/12GiB RAM/6GiB disk/30min timeout. Не разрешать до установления подходящего public code packet; не скачивать веса заранее. При CPU-only предложение backend ADAPTED согласовать отдельно, не автоматический fallback.

Дальнейший direct40 compression run, raw-derived host arm, small model comparison, holdout, CI и retries **не входят** в этот минимальный budget и требуют отдельного решения. Full-turn accounting включает retrieval, model load/warmup, compressor forwards/chunk overlap, source wrapper bytes, host input/output/billing и auxiliary evaluation calls. `o200k_base` historical DTO, model tokenizer и billing считать отдельно. Один smoke не p95 и не статистическое доказательство превосходства.

**Итог:** применимость LLMLingua-2 по размеру/runtime статически установлена, exact-source выдача требует ADAPTED wrapper и может убрать всю экономию. SWE-Pruner официальный checkpoint точно идентифицирован, но превышает strict600M и готового advertised long-code outcome harness в осмотренном срезе нет. Ничего не воспроизведено runtime, source-supported ответы и pruning benefit остаются **NOT RUN**.

## 7. Новое разрешение владельца: подготовка actual execution (supersedes size/download blockers)

Владелец **снял strict600M**, разрешил изолированные assets/download/runtime для обоих checkpoints и указал serial model slots координатора. Поэтому прежний size blocker SWE в §§1/5/6 **снят**, но count634337034 остаётся установленной metadata. Downloads/install/runtime запреты первоначальной фазы выше — исторический checkpoint, не действующее blanket запрещение для одобренного эксперимента. F не получил serial slot и не изменяет общий environment: **model forwards/host calls пока NOT RUN**, это ожидание расписания/inputs, не отказ от исполнения.

### Файлы F вне repo

- `F_assets/prepare_assets.py`: system-Python downloader, exact model revisions, allowlisted files, SHA-256 weight verification, pinned source files и pinned nested Qwen config. Общие binary weights **3 581 664 504 bytes (~3.34GiB)**, не вторые копии в HF cache. Ни pip/install, ни model imports/inference в downloader.
- `F_assets/run_compression.py`: один actual LLML CPU runner и один actual SWE CPU runner; args требуют coordinator-issued serial slot через `F_SERIAL_SLOT`; никаких product/provider calls.
- `F_assets/C_DEPENDENCY_NEEDS.md`: передача единственному installer C. Нужны CPU torch/transformers/accelerate/numpy/safetensors/tiktoken/nltk/pydantic. FastAPI/server/pytest/llmlingua pip package/CUDA/flash-attn **не требуются**. Используются pinned author sources через изолированный PYTHONPATH.
- `F_assets/F_CODE_REFERENCE.md` и `F_CODE_CASE_PROPOSAL.md`: один независимый существующий Dart fixture из `tests/test_mcp_code_context_tool.py:16–65`, вопрос+hint про openHelpChat/openWeb/default current. Это предложение G до inference, не новый frozen oracle или fabricated public capture. Нужен настоящий public prepare/get path и независимый G review.
- `F_assets/READY_COMMANDS.md`: точные команды, schema actual selected public input, serial dependencies и stop criteria.

### Конкретная адаптация исполнения

**LLML:** неизменённый pinned author token classifier/compress path, CPU FP32, batch1, retain-rate0.5, fixed source order, context-level filter false, без force facts/digits/словари/threshold sweep. Transparent forward pre-hook считает <=32 реальных encoder forwards; observer author `__compress` записывает words/labels, не меняет outputs и не служит correctness oracle. Сам raw compressed output и его official statistics сохраняются отдельно. Wrapper монотонно сопоставляет **весь original word sequence, включая drops**, допускает в пропусках только whitespace, затем closes selected words до полных исходных строк. Если tokenizer изменил символы либо сопоставление не exact, outcome **UNSUPPORTED_EXACT_ALIGNMENT**, без fake source spans. Этот conservative line closure — ADAPTED, может вернуть почти весь исходник; экономия считается по actual wrapper с gap markers, не raw ratio. Нельзя самовольно назвать это public product payload или оставить старый envelope hash после изменения snippet.

**SWE:** pinned author model/fusion/CRF-head/scoring/line-aggregation/checkpoint, **не generic reranker replacement**. В отдельной adapted source copy изменён один backend default literal `flash_attention_2 -> eager`; original copy остаётся неизменной. Runtime subclass отключает FP16 autocast, использует FP32 CPU и убирает только trailing masked padding после прежних prefix/query/code/suffix. Это explicit compute/precision/input-shape **ADAPTED**, не canonical CUDA reproduction. Оригинальный pruning threshold0.5/first-fragment false/chunk-overlap50/aggregation сохраняются. Backprop/train отсутствуют. Веса загружаются с loading_info: любые неожиданные/mismatched/untied missing keys остановят попытку; допускается только авторский omitted shared embedding alias при реально совпавших data_ptr. Max2 forwards, input truncation запрещён, exact retained/dropped spans восстанавливаются из исходных raw строк, не decoded `pruned_code`.

Адаптация **подготовлена**, её фактическая CPU viability ещё **NOT RUN**. Если architecture/backend/loading не совместимы с установленным C runtime, сохранить настоящий FAILED_ACTUAL_ATTEMPT receipt, не утверждать заранее поддержку/успех. RTX5070Ti16GB известна, но CUDA torch в shared env не разрешён: GPU model execution/install **не делается**.

### Обновлённые ресурсы, разрешения и blockers

- Owner global additional disk18GiB; F planned assets3.34GiB weights + small tokenizers/source (одна копия), no shared-env installs, no huge stack. Downloader оставляет>=2GB free; pinned source/license hashes и фактические bytes пишутся в ASSET_RECEIPT.json.
- CPU8 threads, conservative **12GiB address-space hard cap** (строже RSS; может остановить жизнеспособную RSS конфигурацию), timeout1800s на отдельный serial command; 2 LLML compression requests max32 actual forwards, 1 SWE request max2 forwards. Zero warmup forwards, zero retries, no quantization, no hidden host calls. PeakRSS/time/version/actual shapes/input/runner hashes и exception receipts сохраняются.
- tiktoken author algorithm использует cl100k_base для token-weighted percentile. Скачать только фиксированный public tokenizer dependency, SHA256 `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`, offline runtime cache. Ни OpenAI API/provider, ни corpus egress не нужны.
- **Блокер inputs:** actual `LLML_FIXED_PUBLIC_CONTEXTS.json` с двумя nonempty выбранными публичными пакетами Q16/Q46 пока не передан. Vetoed acquisition не переименовывать public selected context. Нужен capture identity и G policy/fact audit.
- **Блокер SWE inputs:** G ещё должен freeze source/independent expected facts минимального code case и owning public harness получить реальный selected packet. F_CODE_REFERENCE — preparation asset, не доказательство public integration.
- **Блокер schedule/dependencies:** C подтверждает готовый runtime versions/dependencies, coordinator даёт отдельные LLML/SWE serial slots. Присутствие venv не разрешает F его менять или самостоятельно стартовать forwards.
- **Граница outputs:** runners сохраняют actual compression diagnostics/host-view exact runs; generation/citation correctness и deployed public source-wrapper integration **NOT RUN** до настоящих отдельных host/product стадий. Никаких новых providers, CI, nested agents/repo edits; корпус наружу не отправлялся.

Команды находятся в READY_COMMANDS.md и готовы к serial запуску после inputs/assets/env. Downloader был запущен в фоне system Python (без model imports); receipt окончательной загрузки должен быть проверен перед launch. Это actual asset preparation, не inference PASS.

### Completed asset preparation receipt

Downloader завершился успешно (shell `sh_12fd5eb1c001Yk4pXzDsHFgV54`), `F_assets/ASSET_RECEIPT.json` содержит **ASSETS_READY_NO_INFERENCE**, 29 pinned allowlist downloads, SHA256 каждого файла. Оба binary model hashes совпали с заранее установленными HF LFS SHA256; cl100k tokenizer hash также совпал. Фактический disk `du -sh F_assets`: **3.4GiB**. ASSET_RECEIPT SHA256 **`9140394cc312fbb6079a2cab317ede7ac909751be4bcc934eed0fc13bd18363e`**. Source reference SHA256 **`151a1fc34cbb0d4ebfb768a0fa341ed15f576527304a718524d36f01e693432b`**.

Original author model_structure SHA256 `a9985c6b45260b51a20d94afe087a7307753d0616e0a3a69cc52ce83440e911c`; separate eager adapted copy **`9a919869c80ccd88af0b08dda5b890b8ff1eae95bb86285d4fac076f8aab2a0a`**. До slot F не импортировал torch/transformers/модели и не выполнял syntax/AST/compile/unit проверки. Runtime result files **ещё не созданы**, числа forward/host calls **0**.

Wrapper coordinates явно имеют `coordinate_space="original_selected_excerpt"`: это точные offsets внутри неизменного captured snippet, **не** выдуманные document-global offsets. Для public source contract G/owning harness должен связать их с настоящим raw reference span/snapshot и пересчитать новый envelope digest; original public source сохраняется отдельно. Сам F adapter не является production validator и не сертифицирует такую связь.

Последний `git status --short` показал concurrent изменения A в трёх domain admission файлах; F их не писал/не откатывал. Первоначальный clean статус выше относится только к началу исследования. Размер/скачивание blockers сняты; остаются **actual selected inputs, подтверждение env C и coordinator serial slots**. После их получения команды READY_COMMANDS запускают реальные модели без дополнительных downloads/install.

## 8. Actual coordinator runs: измерения и saved-only follow-up

Координатор выполнил оба serial commands, затем настоящие host comparisons. F в этом follow-up только прочитал сохранённые JSON/text и посчитал cached tokenizer statistics; **0 новых forwards / model loads / host / product / network / install calls**. Для token accounting использован существующий C runtime, только `tiktoken0.14.0`; cache-only `read_file` guard запрещал любую загрузку при cache miss. Это не product execution и не новая проверка unit/private helper.

### Runtime identity и стоимость compressor

- Receipts: `F_assets/LLML_RESULTS.json`, `F_assets/SWE_RESULTS.json`; serial slots **coordinator-F-LLML-001**, **coordinator-F-SWE-001**. Общий реально выполненный runner SHA256 **`ca24714deb53deafb205555fc07a09825159645b3fa534927bf3f9d559af7f07`**; source/checkpoint revisions те же pinned, что выше.
- LLML actual input SHA256 `4a3cbd3632bde4b1f4f8995eb9dd8b689c958cfd44defedcba6db3494de05c0a`; SWE input SHA256 `34794186f4c968acf6b190c5751aecc8c0f0bd88701125a4bd51ad005119c5e5`.
- Runtime: **torch2.10.0+cpu, transformers4.57.1, accelerate1.12.0, numpy2.2.6, safetensors0.7.0, pydantic2.14.1, tiktoken0.14.0, nltk3.10.3**. CPU8 threads/FP32, no CUDA/quantization/training; loading saved parameter counts LLML558945282, SWE634337034. SWE loading_info missing/unexpected/mismatched/errors **все пусты**.

| Actual execution | Cold model-load time | Resident-model compression time | Actual forwards / shape | Whole process time | Peak RSS |
|---|---:|---:|---|---:|---:|
| LLML Q16 then Q46, one load | 0.5472s | Q16 **6.8038s**, Q46 **3.7002s** | Q16 **13**, Q46 **7**, total**20**, each `[1,512]` | **13.1103s** | **2 182 088KiB = 2.081GiB** |
| SWE one F-CODE-01 | 0.3903s | **0.3828s** | **1**, `[1,266]` | **2.5770s** | **4 219 700KiB = 4.024GiB** |

Cold load здесь означает один measured load interval в новом процессе, **не** cleared OS disk cache. Q16 — первый compression call после load без warmup; Q46 — тот же resident model, другой меньший input. Эти две latencies нельзя объявлять cold/warm repeats одной задачи либо p95. В compression interval входят author processing/tokenization, не только kernel; Python imports/remaining overhead входят в whole-process time. Wrapper построение/token accounting не полностью входит в per-case compression interval, поэтому full process — честнее общий overhead. Оба RSS меньше12GiB; дополнительный resource/runtime sweep не проводился.

LLML log предупреждает tokenizer sequence712>512 на accounting encode; **реальные 20 forward shapes все512**, successful receipt, не запуск712-token encoder. Не скрывать предупреждение, но не объявлять его actual truncation/indexing failure без такого факта. SWE author DTO `model_input_token_cnt=265`, фактический forward266 — author count estimator/prefix/instruction mismatch; для model work использовать actual266, не приписывать отсутствующий token. Trailing padded8192 tokens не исполнялись в CPU adaptation.

### Raw ratio ≠ стоимость exact client line-closure ≠ public DTO

`F_assets/SAVED_MEASUREMENTS.json` сохраняет saved-source/citation/span observations и независимые токен-счётчики. **cl100k_base** здесь — author LLML percentile/accounting codec, не XLM-R tokenizer и не реальные billing tokens. **o200k_base** — исторический DTO/content counter с canonical `ensure_ascii=False,sort_keys=True,separators=(",",":")`; actual host content counts берутся из уже отправленных `messages.json` (system+user content), без выдуманных protocol/billing overhead.

| Case | Raw pruning count | Exact closure: saved model-token sums incl gap markers | Client input JSON o200k, full→excerpt | Actual system+user content o200k, full→excerpt | Real public DTO o200k |
|---|---|---|---|---|---|
| Q16 | LLML cl100k **6200→2988**, −51.81%, ratio2.075x | XLM-R **4228→4355**, +3.00% | **4297→4645**, +8.10% | **4599→4947**, +7.57% | **6002→6002**, savings0 |
| Q46 | LLML cl100k **1291→611**, −52.67%, ratio2.113x | XLM-R **789→824**, +4.44% | **952→1031**, +8.30% | **1254→1333**, +6.30% | **2236→2236**, savings0 |
| F-CODE-01 | SWE Qwen **168→84**, −50%; raw includes `(filtered N lines)` | Two exact retained runs; **Qwen token count wrapper не пересчитывался**, use o200k columns | **273→148**, −45.79% | **575→450**, −21.74% | **709→709**, savings0 |

Для SWE wrapper Qwen count не измерялся повторным tokenizer/model loading; столбец raw168→84 не подменять новой wrapper стоимостью. O200k snippet-text joins: Q16 **3993→3957** (малая36-token экономия текста), Q46 **773→773**, code **172→67**. Причина LLML роста actual input: консервативное закрытие до строк сохраняет почти всю содержательную прозу, делит10 родителей на34 excerpt IDs (Q16),7 на12 (Q46); JSON/IDs/границы дороже небольшого удаления blank lines. В run receipt XLM-R counters с omission markers — другая serialization, нежели фактически отправленные отдельные excerpts; обе величины обозначены отдельно, не смешаны.

**DTO savings именно0**, потому что pruning выполнен client-side после существующего публичного read, новый public DTO никогда не создавался. Code capture's `public_packet` включает runner-added private diagnostics: captured whole wrapper19557 o200k **не** public cost. Статически проверено `scripts/run_project_docs_self_host_gate.py:507–514`: observer добавляет `diagnostics` к payload; после исключения только этого ключа canonical public DTO **709**. Validation snapshot остаётся отдельным capture field. Не считать уменьшение helper/model input с273до148 экономией самого server/MCP DTO или общей истории/billing.

### Source spans: наблюдения без семантических гарантий

Actual code public acquisition: `CODE_PUBLIC_CAPTURE.json`, **1 prepare_docs +1 get_docs_context**, real SQLite/public B1 dispatcher; generation `gen-279c559611be4f75ab9829079da671eb`, source hash `151a1fc34cbb0d4ebfb768a0fa341ed15f576527304a718524d36f01e693432b`. G independently froze `G_CODE_ORACLE.md` до SWE scoring/host answers. Code task/hint неизменный, две публичные sources `ev-e0efec6b257099b5`, `ev-e7a3222673e90603`, baseline actual packet reused. Нет вставки отсутствующих oracle code lines после retrieval.

`CLIENT_EXCERPT_BINDINGS.json` связывает **все**34/12/2 emitted client excerpts с исходными public evidence IDs и неизменными parent snippets. Saved-only recheck: **48/48 exact parent slices**, **48/48 excerpt SHA256 matches**; никакой tokenizer-reconstructed цитаты. SWE global concatenated offsets `[303,450)`, `[627,738)` были разбиты/перебазированы по source boundaries; second run соответствует native second parent's `[168,279)`, а не выдуманному одному whole-document snippet. Local excerpt offsets не заменяют full source/reference contract. Client excerpt fields/source_id — host view; не новый public DTO/hash authority. G отдельно проверяет native source snapshot/source-policy связь.

Полные source witnesses в client excerpts фактически присутствуют:

- Q16 corpus `[1152,1209)`: **завершение содержит `duration_ms`\n  и `trace_incomplete`.**, целиком внутри first retained run.
- Q46 corpus `[6952,6996)`: **Одинаковые неправильные ответы не дают PASS.**, целиком retained.
- Code independently frozen complete source `[738,813)`, `[817,882)`, `[1060,1104)`, `[1108,1168)` — обе notifier methods/arguments, initial web и controller assignment. Все четыре целиком сохранены в exact client runs.

Это **span/text retention observation**, не semantic guarantee при произвольном контексте. LLML raw output **не содержит** полный required fact ни Q16, ни Q46; Q16 raw вовсе не содержит identifier `duration_ms` (есть trace_incomplete в другом месте), Q46 exact negative sentence тоже не сохранилась. Это доказательство буквального text loss, не оценка гипотетического host raw answer: **raw-compressed generation NOT RUN**. Raw не направлялся хосту как exact quote. SWE raw склеивает строки/markers и опускает class/import boundaries: snippets пригодны для чтения только с provenance/gap mapping, не объявляются syntactically executable code.

### Actual host calls, quotation observations и граница G judgment

Существующие сохранённые pairs: `B_later_B1_Q16_generation` / `B_later_LLML_Q16_generation`, `B_later_B1_Q46_generation` / `B_later_LLML_Q46_generation`, `B_later_CODE_baseline_generation` / `B_later_SWE_CODE_generation`. Все six endpoint receipts **EXECUTED**, attempts1, без retries/format repairs. B1 two baseline generations переиспользованы, не новые duplicate baseline вызовы ради F. Дополнительные actual F-related host calls: **2 LLML views +2 code baseline/pruned =4**, raw-token host arm0.

| Pair | Existing no-prune host latency | Exact-client-pruned host latency | Saved literal citation observation (не final PASS) |
|---|---:|---:|---|
| Q16 | 6.731455s | 4.830945s | в обоих **quote не exact substring**: newline+indent между duration_ms и `и` заменены пробелом |
| Q46 | 3.260286s | 2.822415s | все2 цитаты каждой ветви exact substrings; ответы говорят, что одинаковые неправильные ответы не дают PASS |
| Code | 3.120634s | 4.109315s | все3 цитаты каждой ветви exact substrings, answer texts одинаковы; host не цитирует `current = type` implementation отдельно |

Q16 несмотря на сохранённые точные исходные bytes и правильный-looking semantic text **не получает F PASS**: не ремонтировать цитату, не менять quote oracle/промпт/вопрос ради успеха. Code literal substring checks не доказывают полноту поддержанной связи: G frozen oracle требует связь notifier→switchTo→assignment; наличие только call/default citations не автоматически сертифицирует assignment justification. Никакой окончательный G verdict здесь не заменяется собственной оценкой F.

Requested generator в сохранённых receipts — existing alias **openai/gpt-5.6-luna, variant medium**, stateless text-only existing authenticated OpenCode endpoint. Actual immutable model revision, temperature/seed/output limits/token usage/provider HTTP count не exposed; one endpoint invocation — не измерение provider subcalls. Input o200k values выше — estimates, **не billing**. Компрессоры saved `host_generation=NOT RUN` описывают их собственную фазу; later separate actual host receipts её уже дополнили, не перезаписываем raw model receipts.

Даже observed host times не доказывают ускорение всего хода: LLML добавил10.504s resident compression плюс загрузку/прочие overhead, а host-input стоимость выросла. SWE host latency в этом singleton выросла на0.989s сверх added compressor0.383s/load0.390s; нельзя вывести стабильный latency win из token savings. Price/full history/wire/cache billing **NOT MEASURED**, повторных сравнений/p95 не делалось.

### Итоговая применимость и завершение

- **LLML raw canonical CPU FP32 actual executed**, source-span client line-closure **ADAPTED executed**. Raw ~2.1x token ratio **не** обосновывает exact-source экономию: в этих двух фиксированных публичных пакетах client adaptation дороже без улучшения source fact retention сверх baseline. Не рекомендовать её внедрение как cost-saving решение на основании этого smoke.
- **SWE official architecture/checkpoint CPU eager FP32 ADAPTED actual executed**, retained frozen spans, measured code host-input savings; не «unsupported assumed», но также не canonical FlashAttention/paper reproduction. Только короткая Dart source-reading toy fixture; **zero Dart app execution/UI/code-edit/patch proof**, zero SWE-Bench/long-code/generalization claims.
- Source-policy окончательный audit, complete source-supported answer/citation PASS/FAIL — **G final review**, не числовой model score (SWE0.99868) и не self-claimed `status=complete`.
- GPU inference, installed client/source-wrapper deployment, raw LLML host arm, statistical repeats/holdout/generalization, real downstream edit outcomes **NOT RUN**. Новых calls для закрытия этих пробелов не запрашивать/не выполнять в этой фазе.
- File ownership соблюдён: обновлён F report + F saved-only measurement assets; repo/shared env/model/host results/oracle/citations не менялись.

### Финальные artifact checksums этого follow-up

| Saved artifact | SHA-256 |
|---|---|
| `F_assets/LLML_RESULTS.json` | `3a574e6fba0c7bf5d3f5eae1b44b3c4f34690334e5735258919428be4af620da` |
| `F_assets/SWE_RESULTS.json` | `70b00b35ea9cf4d3350a168bb044b03618179d99270491a5739e5ed25ad97c58` |
| `F_assets/SAVED_MEASUREMENTS.json` | `307f4785ac054b9af7e39d0a4de70d1016e881f1b616e590ec7d62c618e1f21b` |
| `CLIENT_EXCERPT_BINDINGS.json` | `a0dda918291eb4a37542a373e4e8069a943ff7525b8c7c37aae964a168436cf6` |
| `CODE_PUBLIC_CAPTURE.json` | `0a31726d63f255b7747405658cca3c8df1a13a45c18d3cbc41d1f1c72ae72734` |
| `G_CODE_ORACLE.md` | `32f4b0d4192c4fd9995f5bd8625d88d6e5901bc61b0110c9abd9c7d494d3ec4f` |

SAVED_MEASUREMENTS public code DTO counter явно исключает **только verified runner-added diagnostics**; intermediate wrapper19557 tokens также сохранён под отдельным непубличным полем. Никакие цитаты/ответы/inputs/method receipts не исправлялись. Budget closure: coordinator actual compressor requests **LLML2/SWE1**, forwards **20/1**, F follow-up новых model/provider/product calls **0**; окончательные quality verdicts ожидают G, дополнительных попыток F не планирует.
