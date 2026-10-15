# C — компактные rerankers: реальный CPU smoke и admission protocol

## Актуальный вывод после двух coordinator negative forwards/model

**Ни для mMiniLM, ни для Qwen один глобальный monotone `score >= threshold` не может одновременно сохранить наблюдённый Q16 native-positive window и отвергнуть наблюдённый OtherAPI public-negative packet.** Отрицательный OtherAPI score выше положительного Q16 score в той же raw модельной шкале:

| Canonical CPU model | Q16 native-positive score | OtherAPI actual-public-negative score / tokens | unrelated actual-public-negative score / tokens | Всего calls / tokens |
|---|---|---|---|---|
| mMiniLM FP32 |1.6600364446640015|**2.7502760887145996** /42|-5.951602935791016 /34|**23 /2601**|
| Qwen BF16 |3.625|**8.4375** /104|-2.6875 /98|**23 /4460**|

Для сохранения Q16 требуется threshold<=positive; тогда более высокий OtherAPI тоже admitted. Для rejection OtherAPI требуется threshold>negative; тогда Q16 lost. Sigmoid не меняет этот порядок. Это ограниченное опровержение **одного глобального monotone threshold на этих конкретных scored inputs**, не доказательство невозможности произвольного selector, per-query calibration, native owner-local closure или другого input construction. Такие альтернативы не измерены и не разрешают ретроспективно менять эти inputs/scores ради PASS.

**Границы не смешаны:**21pair/model — сохранённые original member-return native windows Q16/Q46 из current-head CI (диагностика позитивных вопросов, не21 независимо размеченных positive passages); ещё2pair/model — **полные реально emitted B1 public packets** OtherAPI/unrelated, по одному candidate/case, omitted0. OtherAPI packet содержит и OtherAPI credentials section, и отдельную DeliveryEngine packet-delivery section: перенос relation между owners источником не поддержан. Полный публичный packet не равен native owner-local candidate. Эти две pool types не дают одну integration quality rate и не показывают, что reranker включён в public product path.

Coordinator выполнил negative calls, C только прочитал и независимо сверил saved files, без новых forwards/install/downloads/output repairs. `ACTUAL_PUBLIC_NEGATIVE_POOL.json` SHA256 **`3ee108441d9fdcafb357cbc49847940dc07b00c932dc03ac8b50f79a0f22601f`** совпал с обоими receipt input_sha256; runner SHA256 **`a83c4315c82ec063a23e0fad4fb1756e96f9693567211a43a36543a325724e3e`** совпал. Candidate IDs/text hashes и model-visible original question/document inputs сверены; canonical revisions/dtypes/actual_parameter_dtypes совпали со smoke, truncation=false, quantization=null. Qwen negative yes-no arithmetic: OtherAPI20.125−11.6875=8.4375, unrelated13.0−15.6875=−2.6875. Receipt token totals76/202 равны сумме rows42+34/104+98; **повторная токенизация/модельные calls не выполнялись**.

Negative receipts: `C_MINI_NEGATIVE_RECEIPT.json` SHA256 `88facaf46d848f6f1bf101246bfc271ec445ceb36828e1a2f30ae3749868562e`; `C_QWEN_NEGATIVE_RECEIPT.json` SHA256 `905ecd1bcbedc5ddc804d3adbb4ce8e0612f078a9448a1472839d66fad09cf24`. Independent saved-data verification: **`C_NEGATIVE_REVIEW_RECEIPT.json`**.

Measured negative wall/load: Mini0.724/0.641s, RSS756,285,440 bytes; Qwen1.634/0.350s, RSS1,649,152,000 bytes. Sum measured runner walls **1.866s Mini /37.243s Qwen** (по две раздельные загрузки/model; не full pipeline/install/startup). Итого **46 forwards**, две pool types,4 model loads,0 host/provider calls. Пиковые RSS across runs остаются Mini1,029,652,480/Qwen1,659,297,792 bytes. Initial smoke21 calls и его timing ниже сохранены как отдельная граница, не заменены.

**Cost decision:** rank1 на Q46/Q16 недостаточно для рекомендации score-only admission. Более дорогой Qwen тоже не устранил OtherAPI/Q16 inversion, поэтому наблюдённая CPU стоимость не обоснована доказанным улучшением protective selection сверх дешёвого Mini или B1. Нельзя объявлять обе модели бесполезными вообще: comparator/public calibrated path/holdout отсутствуют. Threshold остаётся UNCALIBRATED; public reranker integration и host correctness **NOT RUN**. Сначала coordinator решает сохраняемый owner/relation contract и native/public pool granularity, затем независимая calibration, не подгонка по этой inversion или Q46.

## OWNER UPDATE — выполненное isolated execution (актуальный итог)

**Canonical CPU inference обеих моделей выполнен.** Владелец явно снял600M limit и разрешил isolated install/import/weights/model execution. Это supersedes запреты и NOT RUN записи первоначального report-only этапа ниже; они сохранены как история. Product installation/runtime/CI агентом C не выполнялись.

**Результат:** все11 observed original member windows Q16 и все10 Q46 оценены каждой моделью, omitted=0, без clipping/truncation и без overflow. Обе модели дали нужному полному source window rank1. Это **REPRODUCED official scoring / diagnostic replay**, не публичная интеграция нового admission, не calibrated threshold и не доказательство host answer/citation correctness. Selection не выполнялась, selected_ids=null, threshold=null/UNCALIBRATED. Нельзя выбирать threshold по полученным Q46 scores.

| Модель | Canonical precision / device | Q16 [1024,2100), raw score / rank | Q46 [6919,7107), raw score / rank | forward calls | input tokens | load / forward / measured wall seconds | peak RSS |
|---|---|---|---|---|---|---|---|
| mMiniLM | FP32 / CPU, все parameters FP32 | 1.6600364446640015 / 1 | 7.319156169891357 / 1 |21|2525|0.674 / 0.458 / 1.142|1,029,652,480 bytes (~0.959 GiB)|
| Qwen | BF16 / CPU, все parameters BF16 |3.625 / 1|10.1875 / 1|21|4258|0.372 / 35.225 / 35.609|1,659,297,792 bytes (~1.545 GiB)|

42 forwards всего, batch1,8 threads, seed0, две загрузки моделей, **0 product/provider/host calls**. BF16 поддержан фактическим forward; никаких precision conversions/quantization/fallback. Qwen yes/no logits приведены к float только **после** BF16 forward для score arithmetic. `logits_to_keep=1` вычисляет официальный last-position score без материализации ненужных logits предыдущих positions; use_cache=false, SDPA обеим моделям. Этот resource optimization сохранён в runner, source texts/pairs и score formula не изменены.

Measured wall включает load/tokenization/forwards/output внутри runner, **не Python startup/import, installation или download**. Первые forwards без отдельного warmup, входят в реальные21; load отражает доступный OS cache, не обещание cold filesystem performance. Один pass не p95. Qwen на этих inputs значительно дороже mMiniLM; это два известных cases, не обобщающий выбор победителя.

Second-ranked windows: Q16 [7384,7543) mMiniLM=-1.5825095176696777, Qwen=1.3125; Q46 [6723,6919) mMiniLM=-2.7457687854766846, Qwen=6.0625. Положительный Qwen score дополнительного passage не доказывает отдельную полноту ответа. **Все scores/ranks/token counts и model-visible inputs**, включая остальные отрицательные и heading windows, сохранены в raw receipts, а не только oracle-bearing windows.

### Источник diagnostic pool

Точный saved current-head CI run38232527945, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`, файл `current-head-ci/extra40-results.json` SHA256 `8395cc9c62f2f9d1fc3d4a1ca60786b996b6f990c277a8272d28e442118dd285`. Обе пары исходных questions — без lookup; граница `payload.diagnostics.delivery_observations.returns[0].result.result_windows`, counts11/10, omitted0. Взяты **все items в acquisition order**, без oracle filtering, дедупликации или предварительной model selection. Это полная записанная member-return граница, не автоматически весь первый retrieval pool/B1.

Для каждого item source text восстановлен через **собственные записанные char spans** из неизменного repo corpus, document SHA256 `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`; exact UTF8 window SHA256 сравнен с display_content_hash. Corpus bytes полностью совпали с recorded project_doc_content_hash. Oracle spans не использовались для отбора/scoring. Q16 needed candidate ID `child-697e1c5afe5701899bc1aecd13e99492ff433418`, Q46 `child-460bf5decf12245e2c132591e1fdb1a4b62187aa`.

### Общий environment и handoff D/F/E

**Единственный installer C завершил установку и свои model runs. Environment свободен; D/F/E должны сериализовать inference, не устанавливать/обновлять packages и не запускать одновременно.**

- Exact executable: `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/model-runtime/bin/python` (CPython3.12.3).
- Pins: torch **2.10.0+cpu** (official CPU index; CUDA не установлен), transformers **4.57.1**, accelerate **1.12.0**, sentencepiece **0.2.1**, safetensors **0.7.0**, numpy **2.2.6**, spacy **3.8.11**, llmlingua **0.2.2**; transitive deps зафиксированы.
- `MODEL_RUNTIME_FREEZE.txt`: полный package freeze; **финальный после D wheel** SHA256 `673b76ec7e98a45c8cdfcc595fc861df3364f8967ec7cac0e03b7cc1e7f432ad`. Initial smoke freeze hash `1f70298a7afdeb19607db36d5a19ed2add011e456b82fc1916f7e130b35793d8` сохранён в runtime summary как исторический.
- `MODEL_RUNTIME_LOCK.txt`: полный pinned hash lock, uv pip compile с official CPU extra index и generate-hashes; **финальный** SHA256 `710465c07b4673ff0351b6a6cbf3ee3ee8f1519a40b40fe1f08d59e37fbef16d`. Initial smoke lock hash `60d851f0c86595a22e9c14c50df7bd151554fd65daeeafa653c7469605c623ad` исторический. Вторая установка по lock не выполнялась (нет ненужного повторного install).
- По отдельному запросу D установлен **только** local wheel `D_assets/xx_sent_ud_sm-3.8.0-py3-none-any.whl`, SHA256 `1b5fb9321723b395f76458d2a13b7a3673c537eb58c0a9df3778f4e0950180b4`, 4,324,421 bytes. Совместим с уже pinned spaCy3.8.11 (>=3.8,<3.9); другие pins не изменились. `C_ENV_FINAL_RECEIPT.json` фиксирует install и final lock hashes. Qwen/Mini не повторялись после добавления независимого spaCy model. Никакие forwards D/E/F не запускались. T5/SentencePiece dependencies для E уже доступны через Transformers4.57.1 и sentencepiece0.2.1; фактический E load проверяет сам E в coordinator serial slot, не C.
- Assets: `model-assets/qwen/e61197ed45024b0ed8a2d74b80b4d909f1255473/` и `model-assets/mini/1427fd652930e4ba29e8149678df786c240d8825/`. Выбран safetensors, не pytorch duplicate/ONNX/quantized exports. LFS SHA256 обоих весов **реально пересчитаны и совпали** с immutable API; остальные LFS assets также сверены, sizes всех файлов сверены. `C_ASSET_RECEIPT.json` содержит URL/size/hash/pinned metadata. Allowlist cards содержат license metadata; отдельный LICENSE в данных repos metadata отсутствует.
- Download+hash verification65.380s (отдельно от model timing). Directory logical bytes: runtime1,138,993,981; assets1,700,233,047; всего ~2.644 GiB C-owned. Это оставляет существенный запас в owner-wide18GiB, но **не учитывает** будущие assets D/F/E. Не разрешает скачивание CUDA stack или иных моделей C.

### Runner input / raw receipts

**F dependency readiness, 2026-10-12 11:27 UTC:** прочитан `F_assets/C_DEPENDENCY_NEEDS.md`, actual installed distribution metadata подтверждена: torch2.10.0+cpu, transformers4.57.1, accelerate1.12.0, numpy2.2.6, tiktoken0.14.0, nltk3.10.3, pydantic2.14.1, safetensors0.7.0. Всё уже установлено, missing=[]; дополнительных installs/resolution/package mutations не было, E running environment не менялся. Финальные freeze/lock hashes выше остаются актуальными; regeneration без изменения deps не требуется. `C_F_DEPENDENCY_RECEIPT.json` содержит timestamp/actual versions/provenance/hash verification. NLTK corpora не скачивались; model/library/product imports/forwards не выполнялись. **F dependencies READY; execution только после coordinator serial slot**, author-source PYTHONPATH и offline tokenizer cache назначает F.

Runner `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/C_model_runner.py`:

```text
model-runtime/bin/python C_model_runner.py --model mini|qwen --input CASES.json --output NEW_RECEIPT.json
```

JSON input: `{"boundary":"diagnostic replay", "cases":[{"id":16,"pool_id":"stable-pool-id","question":"original question","observed_count":11,"omitted":0,"candidates":[{"id":"stable candidate ID","text":"complete unchanged text","text_sha256":"sha256 of UTF8 text"}]}]}`. Дополнительные top-level/source metadata допускаются и сохранены в `C_SMOKE_INPUT.json`. Max20pairs/case,40pairs total/model invocation. Без silent truncation; case с любым input>512 полностью NOT RUN_OVERFLOW; существующий output не перезаписывается. Каждый forward выполняется ровно один раз, raw scores — без sigmoid/probability интерпретации. При exception runner пишет BLOCKED receipt, без fallback. Дальнейший public B1 pool execution требует coordinator assignment; этот smoke не повторять.

Artifacts рядом с отчётом:

- `C_prepare_runtime.py`: allowlisted downloader + independent hash/span reconstruction, без product imports.
- `C_SMOKE_INPUT.json`: обе original questions, все21 candidate texts/IDs/spans/hash/lineage, input SHA256 `c2a3ef5b8bea7b69dc95813204819b5d19950c7a5f9d61f29431fe2224fa4a8a`.
- `C_MINI_SMOKE_RECEIPT.json`: все21 FP32 scores/ranks/tokens/calls/timing/memory/full visible inputs.
- `C_QWEN_SMOKE_RECEIPT.json`: все21 BF16 scores, yes/no token IDs/logits, остальные receipts поля.
- `C_ASSET_RECEIPT.json`: actual download hashes/bytes/metadata URLs.
- `C_RUNTIME_SUMMARY.json`: сводка всех42 scores с spans/ranks и SHA256 входов/runner/freeze/lock/raw receipts.

Repository runtime/tests/CI/product environment не запускались и не устанавливались C. На финальном read-only git status появились concurrent изменения A в трёх domain files; C их не редактировал/не откатывал. Smoke кодовую продуктовую path не исполнял и относится только к **saved CI HEAD** выше, не к ещё незафиксированному A patch.

**Следующий конкретный шаг:** координатор получает public B1 policy-valid pool и G calibration/holdout, назначает один сериализованный replay/public integration budget; threshold фиксируется независимо, не на Q46. Host correctness и новые public source-policy negatives пока NOT RUN. Полный final comparison не заменяется этим smoke.

---

## Первоначальный report-only этап (исторический; runtime статусы superseded обновлением выше)

Дата: 2026-10-12. **R2/R3 runtime NOT RUN.** Никаких измеренных scores, latency, RAM или улучшений качества нет.

## Решение

Обе официальные модели укладываются в лимит 0.6B и в доступную память/диск по размеру весов. Для первого CPU smoke предпочтителен **mMARCO FP32**: существенно меньше, стандартный encoder runtime. **Qwen BF16** оставить вторым сериализованным вариантом; CPU feasibility по размещению не доказывает практическую скорость или поддержку всех BF16 kernels. GPU неизвестен, GPU-прогон не планируется без уточнения.

Нельзя рекомендовать новый admission до сравнения с B1 на одинаковых кандидатах и независимого review G. Reranking после буквального veto не вернёт потерянный Q46: scoring должен видеть policy-valid native windows **до topical veto**, не отменяя source-policy или delivery protections целиком.

## Рабочая точка и границы

- Проверены read-only `git status --short --branch` и `git rev-parse HEAD`: чистая `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`.
- Полностью прочитан `MULTI_AGENT_ADMISSION_FULL_PROTOCOL_RU.md`; initial роль C. Прочитаны AGENTS.md, PR211 checkpoint, STATE.md, все материалы §1 протокола, включая frozen questions/corpus/manifest, ADR0003 и пять q46-admission reports.
- Архивный продукт `d8af387de507007f2b8c83f04aac78feb9b6760c` не выдаётся за новый runtime HEAD. Архивные успехи — навигация/регрессия, не oracle для калибровки модели.
- Только публичные HTTP GET metadata/cards/config/docs и статические чтения. Веса, tokenizer binaries и model code не скачивались; providers, inference, imports, product runtime, pytest, AST, install, CI, repo edits, nested agents не выполнялись.
- Единственный записываемый файл: этот отчёт. STATE.md не редактируется агентом C.

## 1. Official HF metadata: immutable revisions и точные размеры

Первый GET `api/models/{id}?blobs=true` вернул SHA; затем **отдельный GET revision API по этому SHA** подтвердил immutable revision, dtype/count и weight LFS metadata. Все четыре metadata GET — HTTP 200. Это metadata verification, не независимый пересчёт tensors из весов.

| Поле | R2: Qwen/Qwen3-Reranker-0.6B | R3: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 |
|---|---|---|
| Immutable revision | `e61197ed45024b0ed8a2d74b80b4d909f1255473` | `1427fd652930e4ba29e8149678df786c240d8825` |
| HF safetensors metadata | BF16: **595,776,512**, total **595,776,512** | F32: **117,641,089**; I64: **514**; total **117,641,603** |
| Параметры модели | **595,776,512** floating-point parameters; 0.595776512B | **117,641,089** floating-point parameters; 0.117641089B. 514 integer elements — buffer, не trainable параметры |
| Архитектура | Qwen3ForCausalLM, 28 layers, hidden 1024, intermediate 3072, 16 attention / 8 KV heads, head_dim 128, vocab 151669, tied embeddings | XLMRobertaForSequenceClassification, 12 layers, hidden 384, intermediate 1536, 12 heads, vocab 250002, один output logit |
| Canonical checkpoint precision | **BF16**, и metadata, и config `torch_dtype=bfloat16` | **FP32**, metadata F32 и config `torch_dtype=float32` |
| Только model.safetensors | **1,191,588,280 bytes**, ~1.110 GiB | **470,592,698 bytes**, ~0.438 GiB |
| LFS SHA-256 | `27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b` | `5daeca2481a76b5976a2bdc32f0a78532b6716da4f8cd3ff59460ef8d2f359b4` |
| Доступ | public, gated=false, disabled=false при metadata GET | public, gated=false, disabled=false при metadata GET |
| Лицензия | Apache-2.0 по official card metadata | Apache-2.0 по official card metadata |

API `total` mMiniLM не следует называть точным числом trainable параметров: оно включает I64. Согласно XLM-R архитектуре 514 — position_ids buffer; floating count — корректная величина для модельного лимита. Ни проверка trainability каждого tensor, ни hash downloaded weights не выполнялись.

Размеры обоих safetensors вместе: **1,662,180,978 bytes**, ~1.548 GiB. HF `usedStorage` (Qwen 1,203,010,934; mMiniLM 4,396,370,528 bytes) — не требуемый download и не resident RAM. mMiniLM repo содержит дубликат pytorch_model.bin и ONNX/OpenVINO/quantized exports; **не скачивать весь snapshot**. Выбрать один safetensors + необходимые config/tokenizer/license assets. Примерно <1.7 GB основных assets для обеих моделей; runtime/dependencies/cache оплачиваются отдельно.

### Языки и context: не смешивать разные пределы

**Qwen:** card заявляет **100+ languages**, multilingual/cross-lingual и programming languages; точного исчерпывающего списка в этой card нет. Русский benchmark admission и качество отрицаний **не проверены**. Card context **32K**, config `max_position_embeddings=40960`, tokenizer `model_max_length=131072`, card Transformers example `max_length=8192`. Эти числа не взаимозаменяемы: tokenizer ceiling не доказывает модельную ёмкость 131K. Для claim использовать card 32K; initial comparative run ограничен полными inputs <=512 tokens каждого собственного tokenizer, включая Qwen wrapper.

**mMiniLM:** card: обучение на machine-translated mMARCO, **14 languages**, теги `en, ar, zh, nl, fr, de, hi, in, it, ja, pt, ru, es, vi`; `in` сохранён как официальный tag (индонезийский), не исправлен в metadata. Хорошая работа на других языках — качественное утверждение авторов, не доказанная нами гарантия. Tokenizer **512 tokens для общей query+passage sequence**, включая specials; config position embeddings 514 — не 514 доступных input tokens. Не давать passage отдельные 512 поверх query.

## 2. Canonical runtime и CPU feasibility

Использовать официальный Transformers путь обеих cards с pinned model/tokenizer revision, no remote custom code, eval/no-grad, без генерации и без quantization. Qwen card требует Transformers >=4.51.0; config сохранён при 4.51.3. mMiniLM config исторически 4.18.0, это **не требование downgrade**. Один общий совместимый Transformers runtime должен быть зафиксирован координатором в receipts до запуска. Устанавливать сейчас запрещено.

Context7 `resolve-library-id(Transformers, CPU inference...)` был вызван согласно инструкции, но вернул **Monthly quota exceeded**. Fallback — официальные cards/config и versioned HF Transformers docs [9–10]; новые credentials не создавались. Web docs main/model URLs дали 404, после этого прочитаны официальные raw docs v4.51.3. Qwen doc там placeholder, поэтому usage обоснован model card, а не отсутствующим содержанием docs.

Qwen текущая card также имеет Sentence Transformers wrapper (config_sentence_transformers: ST 5.4.0, torch 2.10.0+cu128). Это provenance сохранённого wrapper config, **не доказательство необходимости CUDA** и не проверка установленного runtime. Для минимальных зависимостей проект протокола использует direct Transformers путь.

| Hardware / свойство | Статическая оценка, НЕ measurement |
|---|---|
| i9-12900K, 24 logical CPUs | FP32 encoder CPU smoke разумен. Не предполагать AVX512/BF16 hardware acceleration по имени CPU; конкретные flags/kernels не проверены |
| 62 GiB RAM, ~30 GiB available | Веса обеих моделей помещаются с большим запасом; запускать по одной, batch=1, общий process RAM ceiling 12 GiB. Activation/logit buffers и runtime overhead не равны размеру весов |
| ~27 GiB disk | Allowlist assets <2 GiB реалистичны; отдельный budget 8 GiB на assets+CPU deps+cache+receipts, без CUDA stack и дубликатов |
| Qwen BF16 CPU | По памяти возможно; execution/speed **UNVERIFIED**. При unsupported kernel или медленном smoke остановить R2, не незаметно переводить в FP32/INT8 |
| GPU | PENDING, никаких предположений о VRAM или CUDA; последующее разрешение должно назвать устройство и precision отдельно |

BF16→FP32 Qwen — отдельный **precision-adapted** arm (2,383,106,048 bytes tensor storage до overhead), а не canonical BF16 результат. INT8/ONNX/OpenVINO и FP16 — отдельные arms только после обоснованной ресурсной необходимости/разрешения. Сегодня ни один не предлагается вместо canonical. Card CUDA FP16/flash_attention_2 example не переносится на CPU.

Начальный предел <=512 tokens нужен для честного сравнения с mMiniLM и ограниченного smoke, **не новый production output ceiling**. Полный 32K Qwen CPU input нельзя обещать при этом RAM/time budget; особенно naïve attention и materialized vocab logits могут увеличить память. Ни tokens/s, ни p95 не выводятся из model size.

## 3. Одинаковый pool/pairs protocol — проект до утверждения G/координатором

1. Координатор/A фиксирует публичную точку получения **того же native candidate pool**, что у B1, до lexical topical veto. Не вводить новый retrieval, новый embedding provider, lookup, retry, fallback или дополнительные source reads ради R2/R3.
2. Детерминированная source-policy validation остаётся до scoring и повторяется перед публичной выдачей: project identity, current catalog/generation, scope/version, access/consent, owner, source hash, exact original spans и same-call provenance. Metadata-only и запрещённые источники не становятся candidates по model score.
3. Один frozen pool manifest на вопрос: исходный question verbatim, lookup arm отдельно, упорядоченные stable candidate IDs и исходные **полные window texts**. Дубликаты устранить только по одинаковым source identity+generation+span+hash, общим правилом до обоих scorers; не сливать похожие тексты и не терять discovery lineage.
4. Семантические пары **одинаковы**: `(original_question, unchanged_candidate_text)`. Модели не видят oracle, expected answer/span, lexical qualification verdict, чужие scores или объяснение Q46. Модельные wrappers/tokenizers различны по архитектуре, это явно записывается.
5. Qwen — exact official Transformers prefix/suffix из pinned card, fixed instruction: `Given a web search query, retrieve relevant passages that answer the query`. Не подгонять instruction под PASS, Q46, DocAtlas, отрицания или русский benchmark. Left padding, собственный tokenizer, последнее input position; не chat generation.
6. mMiniLM — official joint query/passage tokenization и один sequence-classification logit, Identity activation. Не добавлять Qwen instruction в query mMiniLM, поскольку это уже иная семантическая пара.
7. **Не использовать silent truncation обеих cards.** До forward проверить собственные token lengths вместе с specials/wrapper. Любой input >512: зарегистрировать OVERFLOW и не исполнять эту пару. Весь case исключается из primary full-pool comparison для обеих моделей, с сохранением исходного pool и честным denominator; не объявлять его negative FAIL или complete PASS. Нельзя выбрасывать только длинный candidate и называть pools одинаковыми. Если overflow затрагивает Q46/Q16/значимую долю regression, остановить вывод об общей пригодности mMiniLM. Shared deterministic span splitting — отдельный явно ADAPTED эксперимент после назначения, не скрытое clipping. Qwen long-context-only arm отдельно, не сопоставимый primary result.
8. Initial budget максимум20 native unique candidates/case: это **лимит разрешённых вычислений**, не новый retrieval/source ceiling. При большем pool остановить case с BUDGET_EXCEEDED и запросить увеличение, а не предварительно срезать по выгодному рангу. Все scores допустимых cases сохраняются, включая отрицательные и невыбранные.
9. Rank descending по raw score, stable tie-break исходным acquisition index, затем ID. Selection по calibrated per-model threshold плюс общий frozen operational k; пустое множество разрешено. Ни best rank, ни k не требуют возвращать хоть один source. Далее одинаковая existing projection/compaction и одинаковый host B0/B1 prompt/settings; защищённый source-policy veto не обходится.
10. Offline replay после разрешения полезен для diagnostics/scores, **не публичная integration проверка нового admission**. Архивные return windows нельзя автоматически объявить полным первым retrieval pool; взять только реально записанную границу и отметить omitted/unknown stages. Новая product path доказывается только public integration на назначенном SHA.

## 4. Scores — не calibrated probabilities

- **Qwen raw `s = logit(yes) - logit(no)`**. Записать отдельно оба next-token logits и exact token IDs. Official softmax по двум tokens даёт `sigmoid(s)`; это normalized yes/no preference модели, **не вероятность корректного ответа, sufficiency или source-policy validity**. Current ST wrapper по умолчанию возвращает raw logit differences; card числа `7.625, -11.375` — пример авторов, не наш прогон.
- **mMiniLM raw `s = logits[0]`**, Identity по config. Опциональный sigmoid имеет тот же порядок, но не калибрует correctness. Между R2/R3 scores не сравнивать численно и не усреднять; отдельные thresholds в raw шкале.
- Не применять `0.5`, `0`, lexical score cutoff или margin как необоснованный готовый admission. Rank metric отдельно от package fact coverage, relevance false admissions и host answer/citation correctness.

### Предварительно фиксируемая calibration процедура (threshold пока НЕ существует)

G до scores готовит **20 независимых calibration questions**: 10 с полезными фрагментами (включая partial/multi-fragment), 10 all-irrelevant с hard negatives. Не использовать Q46/Q16, old10/direct40, их paraphrases или benchmark-derived словари. Бюджет calibration pool <=10 native candidates/case; больше — отдельное разрешение, не clipping. Calibration facts/relevance labels берутся из независимых источников G; модели labels не получают.

G отдельно замораживает **12 holdout questions** с перефразированием, отрицанием, multi-fragment relations и hard negatives, без близких вариантов calibration. Известные 50 — regression/development, не holdout. G хранит IDs/hashes/split до исполнения. Если этих данных/labels нет, **threshold UNCALIBRATED**, production admission NOT AUTHORIZED; permitted rank-only diagnostics можно измерять отдельно.

Calibration по сохранённым единожды scores без дополнительных model calls:

1. Per-model candidates thresholds: границы между уникальными calibration raw scores + all-reject endpoint, с заранее фиксированным `score >= threshold`. Рассмотреть общий k из `{1,2,4,8,20}` (calibration actual pool<=10, поэтому20 означает all eligible); k — экспериментальный work budget, не восстановление отменённого потолка3 sources.
2. Операционное требование — **ноль admissions на all-irrelevant calibration cases**, ноль source-policy нарушений. Среди допустимых threshold/k выбирать максимальную independent mandatory-fact coverage positive packages, затем минимальные irrelevant admissions на mixed cases, затем меньше доставленных model tokens; финальный tie-break — меньший k, затем более строгий threshold. Один общий k обоим rerankers выбирается до regression/holdout по агрегированному calibration результату этого же правила; per-model thresholds отдельны.
3. Если доступен только all-reject или positive обязательства существенно потеряны, report failure to calibrate practically useful admission; не ослаблять требования ради Q46. Зафиксировать threshold/k, precision, prompt/hash и split/hash **до** Q46/holdout scores/answers.
4. На holdout никаких изменений. Любой false admission сохраняется с CURRENT_CONTRACT verdict. Ошибку можно изучить, но новый threshold требует нового versioned protocol и нового независимого holdout, не повтора до PASS.
5. Ноль false admissions на10 negatives — слабое основание: one-sided95% upper bound query false-admission rate около26%, не доказательство production safety. Holdout и реальные public negatives обязательны; corpus-shift риск остаётся.

Сравнение фактов всего пакета необходимо: passage может быть релевантен, но один не содержать полный ответ. Reranker не sufficiency evaluator. OtherAPI unrelated own-owner body обязан проверяться независимо; корректный refusal хоста не превращает нерелевантные public sources в CURRENT_CONTRACT PASS.

## 5. Receipts / measurements после разрешения

Сейчас сырых scores/measurement receipts **нет**, потому что calls=0. Не создавать фиктивные JSON с нулевыми качественными метриками. Coordinator назначает будущие raw files отдельно от единственного текущего ownership.

Будущая одна row на пару: run/case ID, code SHA, model ID/revision, runtime versions/device/dtype/quantization=none, seed, pool hash, original question/hash, lookup arm, candidate ID/source/generation/scope/version/hash/span/text hash, full model-visible input/hash, own token lengths, no-truncation/overflow flag, raw logit(s), optional sigmoid preference, rank, calibrated threshold/k, selected/dropped reason. Сохранять public payload отдельно от private diagnostics, final source IDs/spans/hash, host input/answer/citations и независимый G verdict.

Measurement receipt: model loads (cold once per model), load seconds, **все настоящие forward calls и scored pairs**, batch size, input tokens, warm latency, peak process RSS, device usage, errors, overflow/budget-denied cases, total cold+warm walltime и full pipeline cost. Batch=1 значит один forward на scored pair; модель не вызывает provider и не генерирует output tokens. Warm calibration pair используется в основном результате, не повторяется для красивого timing. Одна попытка — не стабильный p95.

Сериализовать модели и host experiments. FP32 conversion или retry не включать молча. Frozen old10/direct40 и previous28 success IDs проверять без oracle drift; lookup arms и generation correctness остаются NOT RUN, пока coordinator не разрешит их отдельно.

| Метод | Точная модель / параметры | Статус | Факты / ответы / false admissions / policy | calls/time/RAM |
|---|---|---|---|---|
| R2 | Qwen revision выше; 595,776,512 BF16 | **NOT RUN** (metadata/card verified; не REPRODUCED) | NOT MEASURED | 0 model calls; time/RAM NOT MEASURED |
| R3 | mMiniLM revision выше; 117,641,089 FP32 | **NOT RUN** (metadata/card verified; не REPRODUCED) | NOT MEASURED | 0 model calls; time/RAM NOT MEASURED |

## 6. Конкретный разрешительный запрос координатору/владельцу

**Разрешить один staged CPU experiment только этих двух pinned моделей** на i9-12900K в изолированном каталоге `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/`, после назначения adapter/raw ownership; без external inference providers и без передачи корпуса вовне:

- Allowlist HF download только pinned safetensors/config/tokenizer/license assets; **<=2 GiB model assets**, **<=8 GiB total additional disk** включая CPU-only runtime/deps/cache/receipts. Явно разрешить изолированный install/import/model inference, которые сейчас запрещены; repo/product runtime этим автоматически не разрешается.
- По очереди **mMiniLM FP32**, затем **Qwen BF16**, batch=1, <=512 complete input tokens, до8 CPU threads, <=12 GiB process RSS; общий предел **4 часа walltime**, включая download/install/load/scoring. Qwen BF16 load+первые две ранее неоценённые calibration пары — smoke с пределом10 минут; ошибка/timeout/память >12 GiB => STOP/NOT RUN remainder, без повторов/precision fallback.
- Однократное scoring: calibration20×10<=200 pairs, frozen50×20<=1000, G holdout12×20<=240, до8 existing positive/negative public-control cases×20<=160. Итого **<=1600 pairs/model, <=3200 forward calls всего**, **2 model loads**, **0 host/provider calls в этом разрешении**. Реальный pool не скрывается под лимитом: превышение фиксируется, case останавливается. Smoke входит в эти counts, повторных benchmark calls нет.
- Первоначально разрешить лишь bounded offline replay **существующих** saved candidate windows для diagnostics и подготовленных G calibration/holdout pools после их получения разрешённым публичным путём. Недостающий complete policy-valid pool — blocker, не повод импортировать private helper. Публичное получение новых pools/product integration требует отдельного явного разрешения координатору: <=90 unique cases (20cal+50reg+12holdout+8controls), reuse acquisition, затем <=180 R2/R3 public context calls + до3 shared prepares, в разрешённом existing CI/harness. Это дополнительный call budget, **не уже выполненные вызовы**, не разрешение агенту C запустить CI и не установленный production/stdio/client proof. B0/B1/host генерация и их calls остаются отдельным бюджетом общего протокола.
- Если GPU предпочтителен, вместо CPU запроса сначала назвать GPU/VRAM и подтвердить canonical BF16 поддержку; новый GPU budget/revision/runtime receipt отдельно. Никаких автоматических CUDA downloads.

До ответа на этот конкретный запрос обе runtime ветви остаются NOT RUN. Ни calibrated threshold, ни интеграционный PASS, ни польза сверх B1 не заявлены.

## 7. Первичные источники URL

Проверены 2026-10-12. Immutable URLs выше main/card latest приоритетны для воспроизведения.

1. Qwen discovery metadata: https://huggingface.co/api/models/Qwen/Qwen3-Reranker-0.6B?blobs=true
2. Qwen **pinned revision metadata**, counts/weight size/LFS: https://huggingface.co/api/models/Qwen/Qwen3-Reranker-0.6B/revision/e61197ed45024b0ed8a2d74b80b4d909f1255473?blobs=true
3. Qwen pinned official card, language/context/usage/scoring/license: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/raw/e61197ed45024b0ed8a2d74b80b4d909f1255473/README.md
4. Qwen pinned config, precision/architecture/context: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/raw/e61197ed45024b0ed8a2d74b80b4d909f1255473/config.json
5. Qwen pinned tokenizer config: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/raw/e61197ed45024b0ed8a2d74b80b4d909f1255473/tokenizer_config.json
6. mMiniLM discovery metadata: https://huggingface.co/api/models/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1?blobs=true
7. mMiniLM **pinned revision metadata**, counts/weight size/LFS: https://huggingface.co/api/models/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/revision/1427fd652930e4ba29e8149678df786c240d8825?blobs=true
8. mMiniLM pinned official card, languages/license/usage: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/raw/1427fd652930e4ba29e8149678df786c240d8825/README.md
9. Official Transformers Qwen3 v4.51.3 doc (placeholder, только наличие architecture): https://raw.githubusercontent.com/huggingface/transformers/v4.51.3/docs/source/en/model_doc/qwen3.md
10. Official Transformers XLM-R v4.51.3 doc: https://raw.githubusercontent.com/huggingface/transformers/v4.51.3/docs/source/en/model_doc/xlm-roberta.md
11. mMiniLM pinned config, FP32/Identity/architecture: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/raw/1427fd652930e4ba29e8149678df786c240d8825/config.json
12. mMiniLM pinned tokenizer config,512: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/raw/1427fd652930e4ba29e8149678df786c240d8825/tokenizer_config.json
13. Qwen ST wrapper versions/default instruction/Identity: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/raw/e61197ed45024b0ed8a2d74b80b4d909f1255473/config_sentence_transformers.json
14. Qwen ST modality forward/config: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/raw/e61197ed45024b0ed8a2d74b80b4d909f1255473/sentence_bert_config.json

Локальные источники frozen inputs/contracts: `eval/main_flow_comparison/compact_review/EVIDENCE_MANIFEST.json` (hashes/archival SHA), `docs/adr/0003-context-first-project-reads.md`, `/tmp/opencode/docatlas-review-evidence/q46-admission/{A_CAUSE,B_EVIDENCE,C_REVIEW,RESULT_RU,ADMISSION_RESEARCH_RU}.md`. Их runtime claims не переизмерялись C; первичное исследование этого отчёта — HF metadata/cards и статическая protocol feasibility.
