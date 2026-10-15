# B — Sufficient Context / RankGPT: initial protocol

> **Owner-authorized execution update (2026-10-12):** initial NOT RUN permissions below are historical and superseded only for the specifically authorized synthetic-data execution. `B_HOST_RESULTS.md` / `B_HOST_RESULTS.json` record successful existing-alias readiness and two actual B0 generations, with frozen common HOST_PROMPT_RU.txt. S1/R1 prompts unchanged; their inference remains NOT RUN pending explicit coordinator command. The initial49-call proposal was not adopted; actual3 endpoint invocations, at most14 later calls only on command. New size/runtime restrictions were removed by owner; no new provider/model substitution, private corpus egress or repository changes by B.

## Решение

Следующий разумный срез — **B0/B1 прежде R1**, S1 только как отдельная диагностика полного пакета. Подготовлены неизменяемые S1 и R1 prompts, но **все model/product исполнения NOT RUN**. Достаточность существующего host prompt, качество ranking и генерации пока не установлены. Нельзя рекомендовать production-admission на основании обзора статьи.

Дата проверки первоисточников: 2026-10-12. Repo `/tmp/opencode/docatlas-compact-review`, branch `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`; initial worktree clean. Архивный product SHA `d8af387de507007f2b8c83f04aac78feb9b6760c` не является новым запуском. Прочитаны полный multi-agent protocol, AGENTS.md, STATE.md текущего этапа, PR211 checkpoint, q46 research и A/B/C/RESULT, ADR0003, frozen questions/corpus и manifest. Repo не изменён; запись только B-owned артефактов здесь. Не читались значения credentials, не проверялась auth, provider не вызывался, корпус наружу не передавался. Публичные HTTP reads ограничены статьями и авторским prompt/code; скачивания weights, imports, runtime, pytest/AST/install/CI/nested agents отсутствуют.

## 1. Проверенные первичные источники и revisions

### Sufficient Context

- Статья: https://arxiv.org/html/2411.06037v3 — **v3, 23 Apr 2025**, §§3.1–3.2, 5.1, Appendix A.1/C.1 проверены. Авторская ссылка ведёт на `hljoren/sufficientcontext`.
- Авторский repository HEAD проверен через https://api.github.com/repos/hljoren/sufficientcontext/commits/main : **801b465eb3be5bf5216fbe3301e61daee85ff99c**, 2025-07-22.
- Immutable prompt source: https://raw.githubusercontent.com/hljoren/sufficientcontext/801b465eb3be5bf5216fbe3301e61daee85ff99c/README.md . Локальная дословная копия: `B_SUFFICIENT_AUTHOR_README.md`, секция `Sufficient Context Autorater Prompt`. Это published prompt, не обнаруженный исполняемый evaluator. Не заявляется полный официальный runtime/code reproduction.
- Авторский main autorater: **Gemini 1.5 Pro**, Appendix A.1 API ID **gemini-1.5-pro-0514**, 1-shot. Размер закрытой модели не установлен. Table 1: 115 human-labelled cases, accuracy 0.930/F1 0.935 — авторский результат, не наши метрики. 0-shot accuracy 0.870 не переносится на русский repository corpus.
- C.1/README prompt требует step-by-step questions/answers, EXPLANATION и бинарный `Sufficient Context`; содержит один пример Roald Dahl/BRB. TIMESTAMP — placeholder, не зафиксированная дата inference. Точные sampling settings autorater в проверенном prompt не опубликованы; не подставляем выдуманные temperature/seed.
- Важное несовпадение версий: статья Appendix C.2 инвертирует описания sufficient/insufficient для FLAMe; авторский commit 801b465 исправляет эти строки README. Наш S1 основан на C.1-концепции, **не на ошибочном C.2 и не на FLAMe**. Сохраняем версии, не выдаём исправленный README за дословный PDF prompt.
- Sufficiency — функция question/context **без reference answer**. Совместные фрагменты допускаются; missing links не достраиваются знаниями модели. Наличие plausible supported answer не подтверждает истинность источника. Sufficient context не гарантирует правильный ответ.
- §5.1 selective RAG — отдельная схема: FLAMe PaLM 24B, chunks 1600 tokens/any-sufficient, self-confidence и fitted logistic regression, включая 100 итераций hyperparameter search. P(True) использует 20 samples и 5 judging queries. Ничего из этого не включено в S1, не воспроизведено и не скрыто в call budget. Chunk-wise OR непригоден как замена package-wide sufficiency для multi-fragment relation.

### RankGPT

- Публикация EMNLP 2023: https://aclanthology.org/2023.emnlp-main.923/ , DOI https://doi.org/10.18653/v1/2023.emnlp-main.923 . Проверены publisher record и abstract.
- Полный первичный текст: https://arxiv.org/html/2304.09542v3 — **v3, 28 Dec 2024**, §§3, 6.1, 6.5, Appendix A доступны. Это более поздняя arXiv revision, не утверждение побайтового равенства conference PDF.
- Авторский repository HEAD: https://api.github.com/repos/sunnweiwei/RankGPT/commits/main — **0d62bc3855c7c118048a7c47c18e719b938e291a**, 2024-03-10.
- Immutable code/prompts: https://raw.githubusercontent.com/sunnweiwei/RankGPT/0d62bc3855c7c118048a7c47c18e719b938e291a/rank_gpt.py . Дословная копия `B_RANKGPT_AUTHOR_CODE.txt` (только текст, не исполнялась).
- `get_prefix_prompt`: system `You are RankGPT, an intelligent assistant that can rank passages based on their relevancy to the query.`; user число passages/query; assistant acknowledgement. Затем на каждый passage user `[n] content` и assistant `Received passage [n].`; final `get_post_prompt` требует descending `[1] > [2]` и только identifiers. Полные точные строки остаются в сохранённом author code, не реконструируются по этому пересказу.
- `create_permutation_instruction`: strip, удаление `Title: Content: `, whitespace split/join, **первые 300 whitespace words**, не 300 tokenizer tokens. `run_llm`: `temperature=0`, default `gpt-3.5-turbo`; GPT-4 — отдельный авторский arm. API aliases здесь не immutable snapshots; параметрический размер GPT не подтверждён.
- Paper baseline: BM25 top100, backward sliding windows **20/10**, один проход; порядок влияет на результат. Top20 single-window также рассмотрен. BEIR GPT4 refinement top30 после GPT3.5 — не наш single-model protocol. Distilled 435M/440M — другой метод, не prompted RankGPT и не выбранная нами модель.
- `receive_permutation` удаляет дубли/чужие ID и дописывает пропущенные в исходном порядке, а score переносит из прежних positions: эти scores **не новые LLM scores**. Author transport имеет неограниченный retry loop; импортировать его как есть нельзя.
- Главная граница: permutation всегда ранжирует даже all-irrelevant pool; **не доказывает наличие полезного passage**, не оценивает sufficiency и не даёт authority. Поэтому R1 ниже намеренно добавляет useful/irrelevant partition. Это адаптация, не exact reproduction.

## 2. Статически проверенный configured host path

Найдено больше одного пути; различаем существование класса, workflow wiring и свежий запуск:

1. `scripts/opencode_chat_support.py:16–18,201–225,256–290` фиксирует `openai/gpt-5.6-luna`, variant `medium`; CLI `opencode run --format json --model ... --variant medium --dir <fresh-dir>`, permission deny, conversation/schema embedding (`:106–123`). `format_attempts=2` по умолчанию; существует FORMAT RETRY и export fallback. Использование без изменения attempts нарушит одновызовный бюджет. Реальный executable/auth/provider endpoint/immutable model revision этим чтением **не подтверждены**.
2. `scripts/run_task21_opencode_chat.py:48,61–89` и `scripts/run_agent_developer_opencode_chat.py:69–96` действительно вызывают этот client, но это tool-choice/action planners, **не найденный S1/R1 или source-supported answer generator**.
3. Проверенные workflows `.github/workflows/task21-live-tool-choice.yml:28–34`, `agent-developer-model-benchmark.yml:34–43`, `installed-mcp-agent-benchmark.yml:103–119` реально прописывают **direct OpenAI scripts**, не OpenCode wrappers: `gpt-5.6-luna`, `--planner openai` в installed arm. Credential secret references существуют, их значения не читались и наличие/работоспособность не проверялось.
4. `scripts/run_task21_openai_live.py:29–31,71–86,102–114`: default `https://api.openai.com/v1`, POST `/responses`, reasoning `medium`, output cap 768, timeout90. `scripts/run_agent_developer_openai_benchmark.py:45–59,78–102` также содержит Responses planner с action JSON schema и **четырьмя HTTP attempts** при retryable error. Эти настройки подтверждены **как repo wiring/defaults**, не как effective remote configuration. Нужен назначенный adapter для S1/R1: action schema не подходит, retries требуется явно отключить, output cap изменить согласно согласованному бюджету. Transport retries/format repairs нельзя перенести незаметно.
5. В `eval/main_flow_comparison/run_docatlas.py:53–54,70–89` — offline source-checkout MCP, `DOCATLAS_AUTO_VECTORS=0`, `DOCATLAS_OFFLINE=1`; actual question calls возвращают context, **host generation отсутствует**. Manifest явно помечает answer generation/provider billing/reranker cost как not measured. Нельзя использовать архивное 28/40 как качество host ответов.
6. `docmancer/mcp/agent_config.py:25–54` содержит путь регистрации host MCP `opencode.json` либо `~/.config/opencode/opencode.json`; это логика установщика, **не свидетельство содержимого текущей host config**. Личная конфигурация/auth/session payload не читались ради безопасности.

Таким образом, честный proposal — использовать уже прописанную `gpt-5.6-luna` через согласованный существующий transport, а не текущую модель агента `gpt-6.1-sol`. **Repository-configured alias не означает уже разрешённую передачу frozen corpus.** No-egress execution для этой модели не установлен. Смена модели на Gemini/GPT4 и новый fallback не разрешены. До согласования exact host/version/transport call path блокирован.

## 3. Frozen S1 / R1 specification

Файлы `B_S1_PROMPT.json`, `B_R1_PROMPT.json`, `B_PROTOCOL_PARAMS.json` — final v1 initial specification. Не подстраивать их после просмотра outputs/holdout. Изменение создаёт новую версию и новую причину запуска; исходный v1 остаётся. SHA-256 receipts приведены ниже. Полные prompts находятся отдельно; placeholders заменяются ровно указанной JSON-сериализацией.

| Arm | Что проверяется | Reproduction scope | Execution |
|---|---|---|---|
| S1 | sufficiency всего фактически выбранного пакета по question+context | **ADAPTED specification**: другая модель, source-only правило, zero-shot, JSON без chain-of-thought, partial/none диагностика | **NOT RUN** |
| R1 | listwise order + explicit useful/irrelevant partition тех же policy-valid candidates | **ADAPTED specification**: другая модель/role layout/output, exact text без 300-word crop, strict validation, all-irrelevant support | **NOT RUN** |
| Author Sufficient Context | Gemini 1-shot prompt/115-case experiment | prompt inspected; algorithm/metrics not reproduced | **NOT RUN** |
| Author RankGPT | GPT3.5/GPT4 + BM25/windowing | code inspected; no BM25 benchmark or author model execution | **NOT RUN** |

**Ни одного REPRODUCED метода нет.** Сохранение авторского текста означает reproduction of text only, не runtime reproduction. Предлагаемый host закрытый, размер/weights/revision не установлены; лимит новых локальных моделей 0.6B здесь не обходится: новых моделей нет.

### S1 input/output

- Input: неизменный original question + **весь** final model-visible context packet B0/B1/R1; stable evidence IDs и дословный source text. Не каждый passage отдельно, не OR независимых оценок. Пустой пакет передаётся как `[]`; для сопоставимой диагностики допускается один evaluator call, хотя host может отказать.
- Нет expected/required facts, oracle spans, qualification ratios, diagnostics, чужих answers/verdicts или method names. Char spans/hash/scope — в local provenance sidecar, не oracle-подсказки модели. Суффициентность конкретного публичного пакета не оценивается по более длинному private acquisition pool.
- Output exact JSON: `sufficient` boolean; `context_use` full/partial/none; supporting stable IDs; краткие `missing_information`. Cross-field checks зафиксированы в prompt; неизвестные IDs/extra fields/wrong types/противоречия → **INVALID_OUTPUT**, не insufficient, не PASS. Никаких confidence thresholds.
- В первый срез это report-only: insufficient не удаляет полезный partial context и не меняет host input; sufficient не выставляет `answer_supported`, `edit_ready`, correctness. G отдельно проверяет judge errors по frozen oracle и actual answer/citations.

### R1 input/output/selection

- Одна неизменная policy-valid candidate pool, взятая через настоящую публичную/назначенную product границу **до topical veto**; B1/R1 равные candidate IDs/bytes/provenance и upstream order. Qualification не является source permission и не используется как expected relevance label.
- Не более20 кандидатов целиком за один call, без passage crop, hidden window retries, random shuffles, query translation или benchmark-specific labels. Если реальный pool >20 либо input не помещается — остановить этот arm как NOT RUN/BLOCKED и согласовать новый operational protocol, **не отрезать хвост молча**. Bounds не выбираются по Q46 answer-bearing rank.
- Output: полная точная permutation всех ID; disjoint exhaustive partition useful/irrelevant, обе последовательности в rank order. Никаких synthetic numeric model scores. `useful_ids=[]` является допустимым all-irrelevant исходом. Empty pool — может быть детерминированно отмечен EMPTY_POLICY_POOL с zero ranking calls; это не модельный success.
- Strict validation: unknown/missing/duplicate ID, пересечение partition, wrong order/schema/extra fields → INVALID_OUTPUT; не использовать авторский implicit append/repair или baseline fallback. Ошибка должна быть видна; downstream R1 generation блокируется, результаты не дорисовываются.
- Selection = **все useful_ids**, ordered. Не arbitrary top3/top5 и не произвольный threshold0.5. Это relevance classification adaptation, не утверждение калибровки; её correctness требует независимых positives/hard negatives. Multi-fragment bridges/conditions должны сохраняться. Выбранные source bytes/hash/span не меняются; pruning/compression отсутствуют.
- Source-policy validity, ownership/identity/scope/version/access/consent/catalog/generation/hash и final public validation остаются детерминированными product условиями; LLM не может их обходить. Missing numeric relation и unrelated own-owner facts остаются independent current-contract controls. Новые useful labels не отменяют старый empty-sources oracle.
- Rank-only ordering полезных passages не равен sufficiency. R1 может быть лучшим ranker и всё равно потерять необходимый bridge. S1 измеряется после конечной projection, G проверяет facts и реальные ответы независимо.

## 4. Параметры и стоимость первого среза

**Предложенный ceiling — 49 model calls**, не выполненные calls и не разрешение:

7 существующих case slots: Q46 original, Q16 original, OtherAPI, unrelated topic, absent numeric condition, public isolation negative, indexed-doc positive control к isolation. Точные harness IDs и data receipts должен заморозить G до execution; не добавлять придуманные новые negatives. Если существующий public isolation сценарий требует дополнительных запросов, coordinator пересчитывает product-call ledger до разрешения — число pytest names не равно числу calls.

| Operation | Cases/arms | Max calls |
|---|---|---:|
| R1 reranking | 7 case pools, one call per nonempty pool | 7 |
| S1 final-packet rating | B0/B1/R1 × 7 | 21 |
| одинаковый frozen generator | B0/B1/R1 × 7 | 21 |
| **Всего** | один проход, no retries | **49** |

B-specific overhead максимум28 calls, генерация21 отдельно. Ровно одинаковый S1 model-visible input можно reuse по hash с receipt вместо повторного вызова; уменьшение counts отражать явно. Ошибка/timeout расходует одну попытку, повтор не разрешён. Author RankGPT chat acknowledgements — части prompt, не отдельные model calls; OpenCode hidden retries/extra turns должны быть исключены либо учтены в настоящем потолке. UI session сама по себе не model-call receipt.

Для разрешения proposed per-call bounds: input≤16000 **host tokenizer** tokens, max_output_tokens4096 **включая reasoning**, reasoning medium, timeout180s, attempts1/format repairs0/fallback0, tools denied, fresh independent requests. Temperature/top_p/seed omitted: поддержка и реальные defaults не проверены, детерминизм не заявляется. Это отличается от author RankGPT temperature0 и repo planners output768; не объявлять canonical reproduction. Если reasoning съедает cap, record truncation/INVALID и stop, не автоматический repair.

Aggregate ceilings: **784000 input tokens + 200704 output/reasoning tokens**, ≤8820s (147min) последовательного model wall-time до overhead. Это operational worst case, **не измерение стоимости/latency**. Денежный ceiling не вычислен: цены, billed tokenizer/cached tokens и effective provider version не проверены. Формула invoice budget: actual billed input×price_in + output×price_out + explicit cache/reasoning тарификация без двойного счёта. Coordinator должен согласовать денежный потолок до отправки. Не приравнивать DTO o200k_base к provider billing.

Product API budget отделён: для трёх arms **не более21 оцениваемого public context request** на этот seven-slot срез плюс existing necessary preparation/index/control calls по ledger A/G. Общие B1/R1 candidate acquisitions переиспользовать, не переполучать ради evaluator. Это лишь target cap для оцениваемых requests, не доказанный total harness calls. Исторические14/40/74 calls не переносятся сюда. Offline replay saved pool допустим только после runtime permission и доказывает ranking диагностику, **не интеграцию R1 в public product path**. Если выполняемый existing workflow уже включает эти cases и регрессию, переиспользовать его results, не добавлять повторный public slice.

Frozen host generation prompt/answer schema **не принадлежат B и здесь не создавались**. Он должен быть единым для всех arms, source-only, citations/evidence IDs, условия/отрицания, честный partial/abstain, документы как данные, без запроса скрытой chain-of-thought. S1/R1 messages/verdicts не включаются в generator session. Пока coordinator не предоставит frozen generator artifact/hash, comparison blocked.

## 5. Evidence / независимая проверка

Сохранить отдельные receipts для S1, R1, generation: code SHA, exact host model response ID/revision (если доступен), transport/runtime settings, attempt count, request/session ID, **полный actual model-visible input** и SHA, prompt template SHA, input/output tokens с reasoning/cache breakdown, latency/error/truncation. Original question/hash и corpus hash из manifest; candidate ledger с stable IDs, policy disposition, original order, full exact spans/hash, returned order/partition, public final packet отдельно от private diagnostics.

Wrapper тоже часть prompt: если используется `build_opencode_prompt`, final wrapper/schema/purpose bytes должны быть заморожены и hashed отдельно; hash только B template недостаточен. Нельзя сохранить только decoded JSON и забыть raw response. Strict parsers/JSON checks пока **NOT RUN**, это specification, не существующий adapter.

G независимо оценивает обязательные факты в final sources, actual source-supported answers/citations, false supported answers/refusals, extraneous text и policy defects. Не выдавать method judge собственного quality PASS. CURRENT_CONTRACT и EXPERIMENT_OUTCOME — отдельные verdicts: нерелевантные sources у OtherAPI = current-contract FAIL даже при верном host abstention. Policy failure всегда stop; нельзя объяснить её useful model score.

## 6. Blockers и точный следующий запрос coordinator

1. **Corpus egress/inference запрещены текущей ролью.** Нужна явная авторизация именно seven-case frozen data через выбранный existing host transport (либо подтверждённый no-egress путь); generic «модель уже доступна» недостаточно. Public papers fetch не разрешает corpus inference.
2. **Effective immutable host identity не установлена:** `gpt-5.6-luna` — repo alias, не model revision; current assistant — другой model. Нужен snapshot ID/runtime receipt либо явное решение принять version-unpinned ADAPTED и ограничить reproducibility claims.
3. **Public B1/R1 boundary и source-policy candidate ledger не реализованы/не назначены.** B не делает product patch, не переносит evaluator в unconditional veto. Coordinator/A должны назвать и проверить конкретную границу.
4. **Нет frozen common generator artifact, assigned minimal public harness и final seven IDs.** Их фиксируют coordinator/G; независимые oracle поля не идут моделям. Никакие новые unit/helper tests не предлагаются.
5. **Цена/token preflight/sampling capabilities не проверены**, реальные budgets неизвестны. Согласовать ≤49 total calls, ≤784k input/200704 output, per-call caps и денежный предел; stop on error, никаких provider retries.

Один конкретный следующий шаг: coordinator сопоставляет A/G границу и выбирает existing host/место запуска, затем запрашивает разрешение на этот exact ceiling и передачу только model-visible question/context seven-case среза. До ответа — **S1 inference NOT RUN; R1 inference NOT RUN; generation/citations NOT RUN; public integration NOT RUN; billing/latency/RAM NOT RUN**. Source/prompt inspection завершён, алгоритмы не воспроизведены.

## 7. SHA-256 receipts

Read-only `sha256sum` после записи; `jq -e 'type == "object"'` успешно прочитал три JSON-файла. Это text/JSON validation, **не проверка adapter/schema/model runtime**. Final git status снова clean. Отчёт не self-hashed; hashes фиксируют frozen text, но не исполнение.

| Артефакт | SHA-256 |
|---|---|
| `B_S1_PROMPT.json` | `2c556d0341c494231f7a4d3a584a730da9783bd5f7b2f96a3d442780b5223ad9` |
| `B_R1_PROMPT.json` | `2bce40a9d205c281a9540257058bcb40c2b2037bdf0858d3c0015c7694162dbb` |
| `B_PROTOCOL_PARAMS.json` | `b9295c257282d0de190d52babb85071b087257135cf8d3f1ef4f4db7a8bd8734` |
| `B_SUFFICIENT_AUTHOR_README.md` | `16d34ae4d479b4aff9ea50d83eea46192f1b82e370c2338e1b5840261548e0ff` |
| `B_RANKGPT_AUTHOR_CODE.txt` | `d3ce8dc51a3a4faf7a6b75c6f94d71f5757a6f803484800d3931dc86e4722500` |

Проверенные repo text hashes: corpus `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`; old questions `2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67`; extra40 `5d0618db2bc1ddb18f65ac246b79ecb1adaadeef3a1618ed68d9f5a5784a12dc` — все совпадают с manifest. Host wrapper `scripts/opencode_chat_support.py`: `dc8228556259784c09bf3f74af8e5f62dca9ae6ba8497041cb056b0ce1991292`. Последний hash идентифицирует прочитанную реализацию, не effective rendered prompt будущего вызова.
