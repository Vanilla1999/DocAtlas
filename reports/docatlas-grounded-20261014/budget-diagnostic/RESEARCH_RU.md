# Перепроверка первичных исследований — 2026-10-14

Это desk research, **не запуск моделей** и не доказательство качества DocAtlas.
URL, SHA-256 полученных текстов, ошибки доступа: `PRIMARY_SOURCES.json`.
Первичные тексты/card/config/license сохранены один раз в `receipts.tar.xz`,
под `primary/`; per-file hashes: `RECEIPTS_ARCHIVE.json`.
Никакие weights, платные API, обучение или model inference не запускались.

## SetR

Источники: [ACL paper](https://aclanthology.org/2025.acl-long.861/),
[paper v2](https://arxiv.org/html/2507.06838v2), §3.3, §4, Appendix A;
[official repository](https://github.com/LGAI-Research/SetR), README,
`train_llama_3.1_8B_inst_gcp.sh`, `License.md`.
Проверенный tree: `d1ac78b7e41f7c6a2cd8d582934fbba02893f343`.

- Выбирает **набор passages** совместно по вопросу, с information requirements
  identification; distilled Llama-3.1-8B-Instruct от GPT-4o. Это действительно
  обученный selector, не название для любого prompted LLM.
- Обучение/основная оценка используют **20** retrieved passages. Полнота
  multi-hop evidence учитывается; реальная стоимость JSON DTO, hashes, URI,
  provenance и hard budget 12000 **не являются контрактом статьи**.
- Код открыт, BSD-3-Clause; лицензия базовой Llama отдельная. README по-прежнему
  содержит evaluation `TBD`. Доступный готовый **trained SetR checkpoint**
  в README/tree не подтверждён. Это не доказательство, что checkpoint нигде нет.
- Скрипт задаёт `source_max_len=6144`, `target_max_len=2048`, bf16, flash-attn,
  distributed CUDA. Статья описывает обучение на 16 A100; скрипт перечисляет
  8 CUDA devices и отличается optimizer/LR. Поэтому скрипт не считать точной
  воспроизводимой спецификацией paper без сверки авторов.
- 8B: арифметический минимум только весов ≈16 GB при 2 bytes/parameter;
  KV-cache, активации и runtime **дополнительно**. Это не измеренный VRAM minimum.
  CPU latency/память для нашего pool не подтверждены.
- Наши 167/256 кандидатов нельзя обрезать до20. Ни тренированный input regime,
  ни полный selector input на нашем tokenizer не проверены. Предел базовой
  Llama нельзя выдавать за доказанную способность trained SetR к этому pool.
- Остаются prompting/CoT, preprocessing (`ftfy`), generation/ID parsing,
  decoding и выбор input limits. Модельная полнота не является гарантией.

**Вывод:** концептуально соответствует совместной полноте, но не подтверждён
готовый воспроизводимый артефакт для следующего локального pilot.

## ParaSet / SetCE

Источник: [paper v1](https://arxiv.org/html/2607.05712v1), §3.1–3.3, §4.2,
Appendix A.4, E.4–E.5, F, G.2. Статус — preprint.

- **Query–set scorer**: совместимость полного набора, supervised preference
  complete sets > incomplete/noisy sets. Gold используется при обучении;
  DocAtlas V40/P03/E01 нельзя использовать как training/tuning data.
- ParaSet: attention/FFN по предварительным embeddings; 5.5M для Contriever,
  8.3M для Qwen3 embeddings. SetCE: DeBERTa-v3-base cross-encoder **183M**.
  Embedding backend нужен отдельно: Qwen3-Embedding-0.6B либо Contriever.
- Размер пула CE/SetCE20, ParaSet до50. Совместная полнота учитывается целевой
  функцией; **конечный сериализованный DTO cap не учитывается**. Ограничение
  cardinality/search depth не эквивалентно byte/token budget.
- Approximate beam search: ширина, максимальная глубина/размер набора,
  dedupe наборов, выбор лучшего из accumulated candidates. CE augmentation —
  прямой union. Это **не полностью безэвристический поиск**. Learned semantic
  scorer отличается от ручных library/keyword boosts, но approximation остаётся.
- Latency измерена авторами на RTX3090/24GB, исключает first-stage retrieval.
  Нельзя переносить на CPU или pool256. Минимумы только fp16 весов:
  11/16.6 MB ParaSet, 366 MB SetCE, без embeddings/активаций/runtime.
- В paper нет подтверждённого official repo/checkpoint и точной deployable
  model card. Дополнительный поиск `"ParaSet" "SetCE" github weights` не нашёл
  результатов. Appendix F указывает соблюдать исходные лицензии pretrained
  artifacts; CC-BY статьи **не лицензия новых trained weights**.
- Точный tokenizer/context cap SetCE и совместимая конфигурация encoder/heads
  не подтверждены; не подставлять предположительный512 вместо спецификации.
  Нет воспроизводимого запуска готовых весов без дополнительной информации.
- Для167–256 embeddings архитектурно возможен большой pool, но это не
  опубликованная проверка. Все кандидаты должны участвовать; стоимость
  approximate search, exact DTO pricing и SetCE inputs измеряется отдельно.

**Вывод:** наиболее подходящая постановка **B**; готовый inference experiment
блокируется отсутствием подтверждённых совместимых weights/config/license.

## Provence / XProvence

Источники: [Provence paper](https://arxiv.org/html/2501.16214v1), §3–4;
[Provence card](https://huggingface.co/naver/provence-reranker-debertav3-v1),
[XProvence paper](https://arxiv.org/html/2601.18886v1), §2–4;
[XProvence v2 card](https://huggingface.co/naver/xprovence-reranker-bgem3-v2),
[official training/evaluation](https://github.com/naver/bergen/tree/main/scripts/provence).

- Выбирают **предложения внутри одного passage**, с совместным encoding
  предложений passage. Не выбирают взаимодополняющий набор всех окон.
  Sentence masks извлекают исходный текст; это не право изменять наши whole
  windows или выдумывать новые span/hash bindings.
- Provence: DeBERTa-v3-large reranker, **430M**, input512. XProvence: BGE-M3
  reranker, **568M**, input8192; card предупреждает paragraph-sized training.
  XProvence v1 card теперь направляет на **v2**, не считать v1 актуальной.
- Публичные weights/custom inference code существуют. Provence revision
  `ef49e233e3c6e50efc476c68f1390f8a63add4d4`; XProvence v2 revision
  `f2798d357213c40164bdd79557d6d2e43ca7d8d2`. Не скачивались.
- Metadata лицензирует weights как **CC-BY-NC-ND-4.0**. В prose Provence/card
  и LICENSE есть противоречащие названия ShareAlike/ND; нужен legal clarification,
  а не объявление commercially permissive. Проверен фактический
  `Provence_LICENSE.txt`; несколько guessed license URLs дали404 и сохранены.
- Minimum fp16 weights-only: ≈0.86/1.136 GB; реальная память больше. Card
  Provence содержит F32 weights, что удваивает этот арифметический lower bound.
  XProvence paper: training4 A100, evaluation1 A100. CPU runs/latency для наших
  кандидатов не проверены. «Zero cost» — добавление pruning head к уже выполняемому
  reranking, **не нулевая цена** введения reranker в наш native pipeline.
- Остаются sentence splitter (NLTK/spaCy), token-probability threshold,
  sentence vote >50%, `always_select_title`, optional reorder/top_k.
  Card рекомендует thresholds; это не точное решение полного DTO budget.
- Все167–256 passages можно обрабатывать batch-wise без top20, но global
  compatibility не появляется от batching. Input overflow/cropping и code
  sentences требуют новой span-preserving постановки. Это не минимальная B.

**Вывод:** доступнее по weights, но не отвечает нашему whole-window set contract;
не предлагать pruning/title heuristics как исправление установленной потери.

## Late Chunking

Источники: [paper v3](https://arxiv.org/html/2409.04701v3), §3.1, §4.2–4.3,
Appendix A; [official repo](https://github.com/jina-ai/late-chunking), README/LICENSE;
[Jina v2 base-en card](https://huggingface.co/jinaai/jina-embeddings-v2-base-en).

- Это **представление chunks для retrieval**, не selection набора/предложений:
  transformer по длинному document, pooling по native chunk boundaries после
  encoding. Source text может сохраняться неизменным.
- Доступны код и pretrained embedding weights; дополнительное обучение не
  обязательно. Repo и v2 base-en weights Apache-2.0. Конкретный backend обязателен:
  лицензию одного Jina checkpoint нельзя переносить на все Jina models.
- v2 base-en **137M**,8192 tokens; weights-only fp16≈274 MB. Примеры repo также
  используют small-en; не смешивать его размер с base-en. Long-document
  activations/attention добавляют память; гарантии CPU throughput нет.
- Статья для ряда оценок **truncates documents at8192**; long late chunking
  вводит macrosegments, overlap и maximum length. Это параметры/приближения,
  а не обещание видеть произвольно длинный документ в одном encoder input.
- Нет joint completeness objective или real DTO cost optimization. Наши
  потерянные окна уже найдены и допущены; reindexing/contextual embeddings
  не устраняют непосредственно terminal first-fit.
- Для167–256 окон понадобятся preprocessing/index/embeddings, но число окон
  не является ограничением одного document encoder. Никакого top20 не требуется;
  это всё равно более широкое изменение retrieval, чем диагностика packing.

**Вывод:** не первый метод для установленной terminal loss boundary.

## LongRefiner

Источники: [ACL paper](https://aclanthology.org/2025.acl-long.176/),
[paper v1](https://arxiv.org/html/2505.10413v1), §3.1–3.4, §4.3, Appendix A.3–A.4;
[official repo](https://github.com/ignorejjj/LongRefiner), README/LICENSE;
[released selection adapter](https://huggingface.co/jinjiajie/Global-Selection-Qwen2.5-3B-Instruct).
Ранее найденный `ant-research/long-context-modeling` — **не этот official repo**.

- Выбирает **узлы иерархии document** (section/subsection/paragraph), строит
  XML outline и сопоставляет его исходному content; не existing DocAtlas IDs.
- Учитывает local relevance + global section usefulness и token budget текста,
  но **не стоимость полного DTO**. Формула §3.3: `LS + R_q * GS`, global score
  делится между children; сортировка/последовательное заполнение бюджета.
  Автоматическое включение детей при выборе parent прямо описано в статье.
  Это не прямой безэвристический atomic whole-window set solver.
- Qwen2.5-3B-Instruct +3 task LoRA adapters + BGE-reranker-v2-m3. README quick
  start `max_model_len=25000`, `budget=2048`; paper training task inputs2k/32k/4k,
  training4 A800, bf16, LoRA. Main evaluation retrieves top8 **full documents**,
  не167–256 native windows.
- Доступны код MIT, trained adapters на `jinjiajie`, evaluation scripts.
  Ошибочный guessed HF `ignorejjj/LongRefiner` дал401; это не отсутствие weights.
  Selection adapter revision `1993a8d8d3da7c6af3fa17d92682a4d7aa9e50d6`,
  rank8, alpha16. HF API подтверждает `adapter_model.safetensors` без скачивания.
- Лицензии **не едины**: selection card CC-BY-SA-4.0, query-analysis
  CC-BY-NC-SA-4.0; doc-structuring metadata license отсутствует. Base/reranker
  тоже требуют отдельной проверки. Cards преимущественно template, не полный
  воспроизводимый deployment manifest.
- Minimum weights-only fp16≈6 GB для3B плюс≈1.136 GB reranker; adapters,
  KV-cache/активации/runtime дополнительно. CPU latency и точный production
  VRAM minimum не проверены; опубликованные GPU timings не наши результаты.
- Для нашего pool нужно восстановить documents, проверить XML-to-source
  alignment и выдавать только исходные byte/spans, не model-generated outline
  как evidence. Это новая архитектура; обязательное включение детей запрещено
  условиями текущего задания. Нельзя просто уменьшить pool до8/20.

**Вывод:** weights реально опубликованы, но метод содержит именно те
hierarchical scoring/automatic inclusion и форматные изменения, которые не
являются разрешённым минимальным исправлением B.

## Итог для выбора следующего шага

Learned **set compatibility** — обоснованное направление B, а не доказанный
готовый fix. Из рассмотренных работ ParaSet/SetCE ближе всего к постановке;
SetR полезен концептуально, но не имитировать его prompted LLM.
Готовность trained artifact, лицензия, полный input и реальная budget-aware
адаптация должны стать **preflight gate**, до любого model pilot.
Показатели статей на DocAtlas не переносились; runtime ни одного метода не проверен.
