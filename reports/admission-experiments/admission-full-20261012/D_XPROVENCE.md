# D — XProvence: первичные evidence и минимальный протокол

Дата: 2026-10-12. **Обновление: R5/P1 ADAPTED, offline diagnostic replay исполнен координатором** в serial slot `coordinator-D-001`: 21 joint forward, CPU FP32. Оба окна с обязательными фактами заняли rank1; оба frozen fact spans сохранились после pruning. Это **не публичный delivery PASS и не host-answer evaluation**; финальный verdict принадлежит G. Подробные измерения и ограничения — §10. Production adoption не рекомендован по двум известным development-вопросам; юридическая ясность и качество полного публичного хода остаются непроверенными.

**§§1–9 ниже — исходный pre-authorization analysis/proposal.** Их NOT RUN/запреты/download statements описывают первый этап, не текущий итог. Позднее владелец разрешил isolated nonproduction runtime/downloads и снял 600M limit; фактический download/execution supersedes соответствующие initial blockers только в разрешённой области. Новых model calls/downloads/installs при составлении §10 D не выполнял.

## 1. Первоначальная граница выполненной работы (до owner authorization)

- Полностью прочитан `MULTI_AGENT_ADMISSION_FULL_PROTOCOL_RU.md`, роль D и общие ограничения. Прочитаны все перечисленные в §1 материалы: оба question files, corpus, manifest, ADR0003, пять q46-admission reports. Последние использованы как навигация, не независимый runtime oracle.
- `git status --short --branch`: clean, `fix/main-flow-compact-evidence...origin/fix/main-flow-compact-evidence`; HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411` совпадает с назначенным. Прочитаны `AGENTS.md`, `v2plan/PR211_CHECKPOINT_RU.md`, актуальные решения `CURRENT_WAVE_DECISIONS_RU.md` и текущий `STATE.md` координатора. Архивные CI результаты не перенесены на HEAD.
- Независимое `sha256sum` frozen inputs совпало с manifest:
  - corpus: `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`;
  - questions: `2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67`;
  - extra40: `5d0618db2bc1ddb18f65ac246b79ecb1adaadeef3a1618ed68d9f5a5784a12dc`.
- Только публичные HTTP GET первоисточников, чтение текста, git identity/status и хеширование данных. Никаких installs/imports/product/model execution/pytest/AST, весов, provider calls, CI, nested agents или изменений repo. Корпус не передавался внешним сервисам. Единственный записанный файл — этот отчёт.
- Сырые scores, retained/dropped spans, model-visible inputs и host answers **не существуют: NOT RUN**, не пустые успешные результаты. Не создан фиктивный measurement receipt.

## 2. Неизменяемые первоисточники

| Evidence | Ссылка / закрепление |
|---|---|
| Статья | [arXiv:2601.18886v1](https://arxiv.org/html/2601.18886v1), 26 Jan 2026, §§2–5; ECIR'26 |
| Revision discovery API | [HF API](https://huggingface.co/api/models/naver/xprovence-reranker-bgem3-v2) |
| Pinned metadata, включая sizes/LFS hashes | [revision API, blobs=true](https://huggingface.co/api/models/naver/xprovence-reranker-bgem3-v2/revision/f2798d357213c40164bdd79557d6d2e43ca7d8d2?blobs=true) |
| Model card | [README @ f2798d…](https://huggingface.co/naver/xprovence-reranker-bgem3-v2/blob/f2798d357213c40164bdd79557d6d2e43ca7d8d2/README.md), Git blob `eeb0f1d3cbe80e3015cc6dba9ae620fa87aa0514`, 9,724 B |
| Actual inference implementation | [modeling_xprovence_hf.py @ f2798d…](https://huggingface.co/naver/xprovence-reranker-bgem3-v2/blob/f2798d357213c40164bdd79557d6d2e43ca7d8d2/modeling_xprovence_hf.py), Git blob `6e3513d66b3b199097635881505d12c6430f5399`, 21,091 B |
| Actual config | [config @ f2798d…](https://huggingface.co/naver/xprovence-reranker-bgem3-v2/blob/f2798d357213c40164bdd79557d6d2e43ca7d8d2/config.json), Git blob `56952660ecfd85335613695be5c17ecc4f0a696e`, 807 B |
| Author training/evaluation repo | [Bergen XProvence @ eb35d6…](https://github.com/naver/bergen/tree/eb35d6e8340fe1052cd9d2813cfa2b06137b3ad4/scripts/xprovence); commit discovered via [GitHub API](https://api.github.com/repos/naver/bergen/commits?path=scripts/xprovence&per_page=1), not a guessed current main |
| Bergen README / architecture | [readme.md](https://github.com/naver/bergen/blob/eb35d6e8340fe1052cd9d2813cfa2b06137b3ad4/scripts/xprovence/readme.md), blob `758777e0d570bb02578aa489769d52746a17bd7c`; [modeling_xprovence.py](https://github.com/naver/bergen/blob/eb35d6e8340fe1052cd9d2813cfa2b06137b3ad4/scripts/xprovence/modeling_xprovence.py), blob `09088ec15c73c507b6e61f46ed2f6730ad350152` |
| Linked license notice | [v1 notice @ 8dd5d7…](https://huggingface.co/naver/xprovence-reranker-bgem3-v1/blob/8dd5d79b6b57b3498a1180352daaf8c457af832b/xProvence%20LICENSE.txt); v1 SHA independently obtained from HF API. This is the notice linked by v2 card, **not a license file included in the pinned v2 tree** |

Metadata retrieved without opening `model.safetensors` or downloading tokenizer/model binary assets. Blob IDs are Git object identities from the official APIs, not newly computed SHA-256 of text bodies. Weight SHA below is **API-reported**, not independently verified against downloaded weights.

### Exact model identity and storage

- Repository: `naver/xprovence-reranker-bgem3-v2`.
- Immutable revision: **`f2798d357213c40164bdd79557d6d2e43ca7d8d2`**; API lastModified `2026-03-09T08:44:18Z`; public, `gated=false`, `disabled=false`.
- API safetensors metadata: **567,757,827 F32 parameters**, total identical. 0.567757827B ≤ 0.6B; card rounds to 568M.
- `model.safetensors`: **2,271,080,220 bytes** (~2.115 GiB), LFS SHA-256 `be4ca7a7ac5a426b5dfec1c949dfbf7f3324ce38a95a95e2ac517f6234860e09`.
- `tokenizer.json`: 17,083,151 B, API LFS SHA `5d704acb9b49c8315d60393b34ec989aa0d6c2e3e0682f6b5cf6ab79649ca685`; SentencePiece file 5,069,051 B, SHA `cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865`.
- API usedStorage 2,293,232,422 B is a repository aggregate, not runtime peak memory or a license grant. No quantized checkpoint assumed; canonical precision is FP32.

## 3. Что действительно поддерживается

### Languages / evidence limits

Card and article training languages: **ar, bn, en, es, fa, fi, fr, hi, id, ja, ko, ru, sw, te, th, zh** (16). Русский включён; `fr` — французский, опечатка card “France” не отдельный язык. “100+ languages” — заявленный перенос от multilingual BGE-M3, не 100+ независимых QA validations. Card отдельно заявляет evaluation 26 languages / 6 datasets, тогда как эта версия статьи описывает четыре downstream QA benchmarks и ограничение generator Aya Expanse-8B на 23 языка. Эти разные формулировки не сводятся в одну подтверждённую таблицу.

В статье русский присутствует в MKQA/TyDiQA; это не repository-docs admission, не OtherAPI false-positive control и не доказательство отрицаний/условий в нашем корпусе. Авторское 40–60% pruning без ухудшения конкретной metric — не прогноз экономии или полноты DocAtlas. Cross-lingual query/context quality отдельно не измерена здесь.

### Context and implementation semantics

Backbone `BAAI/bge-reranker-v2-m3`, XLM-RoBERTa: 24 layers, hidden 1024, 16 heads, intermediate 4096, vocab 250002. Card advertises **8192 tokens**; pinned config `max_position_embeddings=8194`, но constructor устанавливает **`self.max_len = ... - 4 = 8190`**. Query и special tokens вычитаются из доступного context budget. Это не 8192 токенов текста passage плюс вопрос. Training был paragraph-sized; длинные документы не подтверждены этим training regime.

В pinned `TestDataset.create_dataset` длинный passage режется на blocks; очень длинное предложение — на token chunks. В `process` ranking score записывается **только для `si == 0`**: поздние blocks prune-ятся, но score целого документа фактически берётся из первого. Для R5 и P1 нельзя незаметно заменять это max/mean по blocks; такое изменение было бы отдельной адаптацией. Для oversized inputs сначала отдельное решение, не silent truncation.

Query нормализуется `lower`, удалением ASCII punctuation и схлопыванием whitespace внутри официального runtime. Original public question сохраняется, transformed model input тоже записывается. Нормализация может затронуть identifiers/условия; не добавляем перевод, lookups или benchmark-specific normalization.

### Содержательные расхождения article/card/code

| Деталь | Статья/card | Pinned HF code |
|---|---|---|
| Default threshold | Card 0.3; recommends 0.3 conservative, 0.7 stronger | `process(... threshold=0.1)` |
| Default title keep | Card interface `always_select_title=True` | `always_select_title=False` |
| Sentence rounding | Article §2: sentence retained iff >50% tokens relevant | Token probability `p > threshold`, затем доля бинарно выбранных tokens **также `> threshold`** в `sentence_rounding` |
| Reranking output | Relevance score | Raw first ranking logit, regression/MSE target; не calibrated probability |
| Compression metric | Context pruning ratio | `compression_rate=(len(original)-len(decoded))/len(original)*100` по **characters**, не model/billing tokens |
| Exact-source output | Card returns pruned string | Sentence `.strip()`, leading-space reinsertion, token concatenation + `tokenizer.decode`; original offsets не выдаются |

Не разрешается назвать использование pinned HF defaults точным воспроизведением формулы статьи. При threshold=0.3 code сохраняет предложение с долей >0.3, а не >0.5; при 0.7 — >0.7. Не менять это молча. Минимальный кандидат ниже использует **explicit pinned-code semantics**, и маркируется ADAPTED к статье/DocAtlas, если будет исполнен. Для article-faithful rounding нужна отдельная ветвь и budget; сейчас она не предлагается как дополнительный sweep.

### Runtime requirements, не проверенная установка

Фактические imports HF code: PyTorch, Transformers, NumPy, tqdm, spaCy; `spacy.load("xx_sent_ud_sm")` происходит уже при import remote code. Card требует отдельную установку spaCy sentence model. Tokenizer artifacts нужны наряду с weights; подходящий tokenizer backend/SentencePiece dependencies определяются согласованным environment lock, не предполагаются установленными.

Config содержит `transformers_version=4.51.3` и `torch_dtype=float32`; это provenance hint, не полный совместимый requirements lock. Author example использует `AutoModel` с `trust_remote_code=True`. На CPU нет явного `.cuda()` требования в HF implementation: tensors направляются на `self.device`. Значит CPU execution структурно возможен, но его работоспособность и latency **NOT RUN**. A100 в статье — evaluation hardware авторов, не доказанный минимальный VRAM requirement.

Нужны audited pinned remote code, offline tokenizer resolution, `eval`/no-grad inference, фиксированные runtime/threads/seed. Внутренний `AutoTokenizer.from_pretrained(config._name_or_path)` не получает явный revision: одного outer revision недостаточно для доказательства tokenizer pinning; после разрешённого download использовать проверенный единый local snapshot без сети и записать actual loaded files. Ошибки load, missing spaCy model, skipped empty/too-long query, None ranking score, chunking/truncation — отдельные receipts, не успех fallback.

Context7 requested для документации Transformers custom-code pinning; ответ: **Monthly quota exceeded**. Fallback прочитан у первичного автора: [Transformers v4.51.3 custom models](https://huggingface.co/docs/transformers/v4.51.3/custom_models). Совместимость XProvence с этой или новой версией не испытывалась; не предлагалась установка.

## 4. License: самостоятельный blocker

Metadata и конец card: **CC BY-NC-ND 4.0**. Начало card противоречиво называет “Attribution-NonCommercial-ShareAlike” рядом с “CC BY-NC-ND”; v1 linked notice повторяет SA/ND путаницу, включая ссылки на BY-NC-SA legalcode. Веса нельзя объявить Apache-2.0 из-за лицензии backbone.

Особенно существенные слова linked notice:

> “Adapted Material” ... includes ... “any output produced using the xProvence models and/or checkpoints”

> “commercial advantage” ... includes ... “any use ... in other than in a virtual test environment” ... “even if no monetary compensation is received”

Таким образом, **не обещать бесплатное разрешение на production, даже некоммерческий**. Требуются решение владельца/юридическая проверка применимости notice к v2, разрешённости offline virtual-test experiment, span adapter и хранения/распространения outputs. Нельзя делать юридический вывод о недействительности оговорок из текстовых противоречий. Pinned v2 tree не содержит самостоятельного license file, поэтому сохраняем происхождение notice как linked-v1, не приписываем его v2 binary автоматически. Модели/outputs не распространялись, внешние обращения к правообладателю не выполнялись.

## 5. Zero-cost: правильный знаменатель

Уже имеющийся XProvence reranker кодирует question+passage один раз; маленький token-classification head использует те же hidden states. Поэтому pruning не требует **второго encoder/LLM forward** сверх такого reranking. Это смысл “zero-cost”, а не нулевая стоимость модели.

Платим за download/storage/load, sentence splitting/tokenization, все passage forwards, две heads, masks, source-span reconstruction/validation и generator. Сравнение **R5 → P1** может разделить один encoder computation; **B1 → R5** добавляет полноценный новый reranker. Существующий другой ranker нельзя считать уже оплаченным XProvence inference. Head/postprocessing overhead мал, но не буквально нулевой; CPU долгий контекст особенно не бесплатен.

Net saving измерять по всему ходу: дополнительный ranker runtime + pruning/validation против фактического уменьшения host input/latency/billing. Character compression, o200k DTO tokens, XProvence tokenizer tokens и host billed tokens — четыре разных измерения. Без generation невозможно утверждать net saving или отсутствие quality loss.

## 6. Раздельный comparison protocol (proposal only)

### Общий frozen input / contract

1. Координатор/G фиксируют exact code SHA, existing public harness, policy-valid candidate pool **до прежнего topical veto**, original question, candidate IDs/order/spans, current source/catalog/generation hashes, scope/version/access/consent. Недопустимые источники не поступают ranker и не становятся допустимыми благодаря score. Один и тот же pool для B1/R5/P1; не считать архивный low-level window list доказанным полным production pool.
2. B0/B1 собирает координатор, не D. R5 должен подключаться до admission-dependent удаления полезных windows; reranking пустого final payload не восстановит Q46. Это явный experimental contract delta, не bypass общего защитного delivery veto.
3. Один заранее выбранный host model/version/prompt/settings, один ответ на arm/case, clean session; no retries/lookups/oracle to model. All-irrelevant case допустим: top rank не свидетельствует relevance/sufficiency. Не вводить raw-score `0.5` veto. Количество selected candidates K и operational work bounds берутся из согласованного сравнения B1, не из Q46 oracle или HF default top_k=5. Rank-only cannot certify empty-source negatives.
4. Сначала existing smoke: Q46, Q16, OtherAPI, unrelated topic, numeric negative и public source isolation с положительным indexed-document control. Затем frozen old10 + direct40, прежние 28 успешных IDs отдельно; lookup arms только по необходимости затронутого пути. Ни один negative oracle не переписан.

### R5 — ranking ONLY

- Pinned XProvence FP32; score каждого policy-valid question/passage pair; stable descending score order, deterministic tie break by original pool order/ID.
- Сохраняем **полные исходные выбранные windows**, никакого decode/pruned text. Именно original source slices отправляются публично и host. Вызов joint forward может вычислить token logits, но R5 их игнорирует.
- Same selection K/budget как B1. Record all candidate scores и selected/rejected IDs; raw logit не probability; отдельно отметить выбранные нерелевантные sources. Привязка score к first block при split не скрывается.
- Сравнение B1→R5 отвечает только: дал ли **reranking** больше обязательных фактов/source-supported ответов за дополнительную стоимость, не pruning.

### P1 — SAME ranking + pruning

- **Те же R5 scores/order/selected IDs, тот же K**. Не rerank decoded/pruned passage, не refill пустые passages нижними ranks: иначе эффект ranking смешивается с pruning.
- Explicit initial parameters: pinned HF algorithm `threshold=0.3` (card conservative recommendation), `title=None`, `always_select_title=False`, original sentence order; batch_size=1 для initial CPU budget. Это не default code .1 и не article >50% sentence rounding; зафиксировать название `P1-HF-v2-span-adapted-t0.3`. Не настраивать по known50; дополнительного 0.7 sweep нет.
- `title=None` нужен для обычных project docs: “first sentence” не обязательно настоящий title; первый list item нельзя считать контекстом всех следующих. Реальный source title/header передавать только как отдельно bound source span, не generated model text. Любой иной title/closure rule — отдельная заранее зафиксированная адаптация, не скрытый fallback.
- Retain/dropped masks выводятся из того же joint inference, затем применяются **к original spans**, а не decoded string. P1 отличается от R5 только удалением source intervals и сопутствующим framing.
- Сравнение R5→P1: какие обязательные факты/ограничения/связи исчезли, изменились ли citations/answers, и сколько **whole-turn** tokens/time сэкономлено. Empty prune output не источник достаточного ответа.
- Статус после разрешённого испытания будет **ADAPTED**: использование авторского checkpoint с pinned HF semantics + source-preserving integration, не reproduction полного Bergen/Aya-8B paper experiment. Сейчас оба **NOT RUN**, а не “ADAPTED выполнен”.

## 7. Exact source spans: обязательные safeguards

Official `process` не выдаёт offsets и не гарантирует substring equality: segmentation `.strip()`, whitespace изменения и tokenizer decode могут изменить текст. Нельзя восстановить цитату простой поисковой привязкой decoded output, особенно при повторяющихся одинаковых предложениях. Нельзя указывать parent span вокруг дырявой склейки как одну непрерывную цитату.

Минимальный adapter, только после отдельного assignment:

1. При **том же** sentence segmentation сохранить исходные `.start_char/.end_char` и strip-boundary offsets каждой единицы; сопоставить их с official token chunks/mask. Использовать исходные координаты, не AST и не product-private helper tests. Если matching/token alignment неоднозначен — P1 case BLOCKED, не approximate quote. Для >max_len sentences chunks не являются полноценными предложениями: initial protocol останавливает такой case, а не выдаёт partial sentence за целую.
2. Source snapshot неизменен. Для каждого retained interval сохранить `[char_start,char_end)`, отдельные UTF-8 byte/line coordinates, source/document hash, raw substring hash, candidate/evidence ID. Char и byte нельзя смешивать. Дословный fragment — только `raw[start:end]`, проверяемый независимо.
3. После удаления выдавать **список отдельных цитат** в source order, с явными gaps между ними. Не соединять синтаксически два оставшихся куска в новое утверждение; separators/ellipsis — display framing, не текст источника и не span. Rebind публичный envelope digest отдельно от document и fragment hashes.
4. Для dropped intervals сохранить те же exact raw spans/hashes, probabilities/masks и причину удаления. Private diagnostic ledger не отправляется host как oracle. Proposal receipt fields: `source_id`, `source_sha256`, `candidate_id`, `candidate_span`, `sentence_id`, `sentence_span`, `token_block`, `token_selected_fraction`, `threshold`, `retained`, `raw_span_sha256`, `selected_rank`, `snapshot_generation`, `public_evidence_id`.
5. Не присваивать `answer_supported`, `answer_available`, `edit_ready` на основании score/mask. Final existing source validation после pruning обязательна; source-policy violation — stop/not recommend, не relevance compromise.
6. Exact substrings не доказывают смысловую полноту: предложение может зависеть от соседнего bullet, исключения, заголовка или условия. G проверяет **пакет и host answer**, отдельно missing dependencies/negation/numeric conditions. Shared encoding не гарантия сохранения этих связей.
7. Для initial research P1 не добавлять oracle-driven rescue/hidden retries. Если dependency потеряна — сохраняем FAIL. Можно позже отдельно одобрить general conservative closure (например весь structural block), но это новая адаптация со своей ценой, а не притворное воспроизведение pruning. При unsafe mapping не публиковать подменённый текст; отметить blocked arm/case.

Независимые fixed obligations уже видны в corpus: Q46 полное отрицание `[6952,6996)`; Q16 completion с **обоими** полями `[1152,1209)`, включая newline/attribution. Эти spans доступны только oracle, не ранжирующей модели. R5/P1 фактическую доставку не проверяли.

## 8. Resources / calls budget — конкретное предложение, НЕ разрешение

Hardware из coordinator/user: i9-12900K, 24 logical CPUs; 62 GiB RAM, ~30 GiB available; disk 27 GiB free. GPU pending. Возможность хранить 2.27 GB checkpoint очевидна по metadata; runtime peak/throughput не измерены.

| Resource | Proposed initial ceiling / accounting |
|---|---|
| Download | Один exact pinned snapshot, ~2.294 GB model+tokenizer metadata estimate; spaCy `xx_sent_ud_sm` и locked runtime dependencies отдельно с manifest/sizes до разрешения. Никаких training data/Google Drive archives/8B teachers/generator weights |
| Disk allocation | До 8 GiB суммарно включая один snapshot, dependencies/caches и receipts; остановиться до превышения, не чистить чужие файлы. 8 GiB — запрошенный experiment allocation, не доказанный размер установки |
| Memory | Один FP32 XProvence process, requested RSS cap 10 GiB, batch=1, 8 CPU threads, без одновременно загруженных competitor models. Weights alone ~2.115 GiB; loading copies/activations/attention/spaCy добавляются. Cap не обещание успешного fit |
| GPU | Никаких предположений о наличии или VRAM. CPU canonical FP32 первым после разрешения; GPU optimization отдельным device-tagged run только если CPU budget blocker, не mixed precision скрыто |
| Context safety | Initial resource reservation предполагает pair ≤1024 actual tokenizer tokens и ≤20 candidates/case. Если существующий pool/input больше, **не обрезать и не менять benchmark**, остановить/пересогласовать exact resource budget. Production operational bounds не заменены этими experiment caps |
| Time | Запросить до 15 min cold load+smoke; после качества до 60 min regression CPU, один проход, без повторов ради удачи. Это ceilings, не measured latency |

### Logical cases и настоящие calls

- Smoke reservation: **7 logical public requests** — Q46/Q16/OtherAPI/unrelated/numeric/foreign-scope и положительный indexed-source control. Если existing harness требует больше public calls для control, координатор фиксирует actual workload до запуска; “7” не скрывает preparation/diagnostic operations.
- При pool ≤20 и без splits: ≤**140 encoder pair-forwards** на smoke. Batch1 — до 140 forward invocations, не семь. Пустой pool даёт ноль forwards и отдельный measured failure, не модельный PASS.
- Можно получить R5 rank+P1 masks в **одном joint pass**, reusing saved outputs: не требуется второй inference sweep. Forward обычно считает обе heads. Record actual pair/block/forward counts; deployment standalone R5 и P1 каждое всё равно оплачивает один joint pass. Timing masks/reconstruction измеряется отдельно; общий экспериментальный compute не “double charged”.
- Host: **14 ответов для R5/P1 на smoke** (2×7), без скрытых reruns; B0/B1 максимум ещё14, если у координатора нет сопоставимых разрешённых receipts. Итого максимум28 generation calls для полного четырёх-arm smoke. Public context requests аналогично до28 плюс **отдельно** фиксированное число prepares/control calls по существующему harness; cached offline replay не объявлять публичными вызовами.
- Regression: reuse smoke Q46/Q16, затем оставшиеся known50 и пять smoke controls: **55 unique cases суммарно**, при сохранении pools ≤20 ≤**1100 encoder pair-forwards**, ≤**110 R5/P1 host calls** за smoke+regression. Полные четыре arms ≤220 generation/context calls + явно учтённые prepares. Если controls состоят из нескольких запросов, totals увеличиваются прозрачно до одобрения. Smoke не запускается второй раз в regression без новой причины.
- Lookup24 не включён автоматически; его добавление требует решения о затронутом механизме и нового explicit calls budget. Holdout G — отдельный заранее frozen budget, пока не включён. Нет full ranker×threshold×compressor grid.
- Внешние provider/model calls **0 разрешено / 0 выполнено D**. Для будущего host требуется approved existing model и **явное согласие на место обработки данных**; предпочтительно разрешённый local host. Token/$ ceiling фиксируется координатором после выбора host; без model pricing нельзя честно написать денежную стоимость. Corpus нельзя отправлять provider по умолчанию.

Измерять cold load и warm inference раздельно, total time/RSS, pair lengths, skipped/split cases; host actual visible input, generation input/output/billed tokens, citations. Не выдавать один run за p95. До runtime proposed costs не считаются нулевыми measurements.

## 9. Первоначальные verdict matrix / blockers / next permission (до исполнения)

| Method | Model / precision | Status | Facts / grounded answers / unsupported answers / false refusals / excess context / policy violations | Cost |
|---|---|---|---|---|
| R5 ranking only | naver/xprovence-reranker-bgem3-v2 @ f2798d…, 567,757,827, FP32 | **NOT RUN** | Все **NOT RUN**, не нули | Model inference/download/generation not performed; latency/RAM/tokens not measured |
| P1 same ranking + pruning | Та же модель; proposed source-span adapter, explicit HF threshold .3 | **NOT RUN**; prospective **ADAPTED** | Все **NOT RUN**, включая retained/dropped spans и смысловые зависимости | Net whole-turn saving **NOT RUN** |

Concrete blockers:

1. Запрещены local runtime/import/install/weights/model calls; отсутствует exception для именно этой revision, spaCy resources и location.
2. Linked licensing notice противоречив и содержит ограничения virtual-test use/outputs; owner/legal clearance до execution/publication/deployment.
3. Нет назначенного публичного extension point/policy-valid candidate capture и source-preserving adapter; прежний literal veto нельзя игнорировать как защитный bug fix. R5 all-irrelevant поведение требует contract decision; current empty-source negatives остаются unchanged.
4. Неизвестны actual installed runtime/dependencies, pool sizes/token lengths/CPU peak; GPU pending. Никакого доказанного fit/performance.
5. Host model/version, data-handling consent и money/token budget не определены. Следовательно generation/citation correctness нельзя заменить article metric или sufficiency prompt.
6. Context7 quota exhausted; первичная fallback documentation прочитана, но compatible runtime lock остаётся не проверенным.

**Один минимальный следующий запрос координатору/владельцу:** одобрить только изолированный non-production virtual-test **R5→P1 paired smoke** на exact `f2798d357213c40164bdd79557d6d2e43ca7d8d2`, локальном i9 CPU FP32, один checkpoint ≤2.294 GB + заранее перечисленные spaCy/runtime assets, общий disk ≤8 GiB/RSS ≤10 GiB/8 threads/15 min, ≤140 pair forwards и ≤14 R5/P1 host calls на семь заранее frozen public cases; назначить adapter owner/public harness, подтвердить linked-license applicability и разрешённость outputs, зафиксировать approved host/location/данные и host token/$ ceiling **без внешней передачи corpus**. Если нельзя одобрить product runtime или host/data условия, оставить **NOT RUN**, а не запускать обходной offline benchmark. Regression ≤55 cases/1100 pairs/110 host calls — отдельное разрешение только после smoke.

Данных недостаточно для выбора XProvence вместо B1 или обещания, что pruning сохранит факты. Полезный итог D — pinned первоисточники, конкретные legal/runtime/span blockers и ограниченный сравнимый протокол, а не model efficacy claim.

## 10. Фактическое исполнение coordinator-D-001 и независимый receipt review

### 10.1 Evidence identity / scope

Координатор выполнил `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/D_xprovence_runner.py` один раз: **2 cases, Q16/Q46; 21 исходный question-window pair, 21 joint author forward**, `complete=true`. D только прочитал receipts и выполнил stdlib JSON/hash/span/mask inspection; **не повторял inference**, не добавлял provider/host calls, installs/downloads, unit tests, CI или repo edits. Вопросы, corpus, обязательные факты и исходные assertions unchanged.

Артефакты (пути относительно каталога этого отчёта):

| Артефакт | SHA-256 / назначение |
|---|---|
| `D_assets/R5_P1_receipt.json` | `85ef56ff7487b605db41cf8de90acf8ca91ea5ffa26b809cec5fdd4a6a96ae45`; все raw probabilities/masks, scores, original windows, retained/dropped spans |
| `D_assets/execution.log` | `7a1c56401ec9682ec9b225f8009559046c72feaaedf48967a1f2e8393159628d`; только deprecation `torch_dtype` и предупреждение config xlm-roberta→XProvence, не ошибки исполнения |
| `D_xprovence_runner.py` | `8c5eaeb20b40598ac85b16c628079ffa91ff32d89f1071f0d4bc92dc3d7f0326`, совпадает с runtime receipt |
| `D_assets/Q46_Q16_pool.json` | `8ba3d4bc7b861d1ca2b04339dafd724777c8d9a8c78ec3e51dfcf7260cc24c76`, совпадает с runtime input hash |
| `C_SMOKE_INPUT.json` | `c2a3ef5b8bea7b69dc95813204819b5d19950c7a5f9d61f29431fe2224fa4a8a` |
| `D_assets/MEASURED_SUMMARY.json` | Новый stdlib-only receipt review: полная rank table с IDs/hash/spans, C input crosswalk, независимые raw slice/mask/partition проверки и измеренные агрегаты |
| `D_assets/download_receipt.json`, `metadata.json` | Один pinned snapshot: **2,293,266,400 B**, independently verified weight LFS SHA `be4ca7a7…`; не metadata-only размер |
| `D_assets/AUDIT_AND_READY.md`, `spacy_wheel_receipt.json` | Remote-code text audit и provenance sentence resource; устаревшее “waiting” относится к подготовке до coordinator slot |

Неподменённый source/corpus hash: `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`. Candidate pool восстановлен из **всех observed member windows текущего HEAD**, архив run38232527945; Q16 11 windows, Q46 10, omissions0. Это **не новый публичный acquisition**, не live revalidation access/consent/version и не доказанный полный initial retrieval pool за пределами observed member boundary.

### 10.2 Сопоставимость с C

Независимый ordered crosswalk сравнил original question и **все21** candidate ID, text, text SHA и полный `source_metadata` между receipt original windows, D pool и `C_SMOKE_INPUT.json`: **оба cases совпадают полностью, включая acquisition order**. JSON file hashes различаются из-за дополнительного D envelope/offset fields, не из-за разных question/passage pairs. Полные matches зафиксированы в `MEASURED_SUMMARY.json` как `same_ordered_pool_as_C=true`.

Это same candidates, не одинаковые tokenized model inputs: D использует author question normalization + sentence-based tokenization, C — собственный официальный model format. Никто не переводил вопросы, не делал oracle-specific lookup и не отбирал для D только answer-positive passage. Model-visible source text и normalized question сохранены; **raw input token IDs отдельно не persisted**. Runtime author token-to-sentence alignment proof записан в receipt, но независимый повтор tokenizer inference для review **не выполнялся**.

### 10.3 Измеренные calls/resources/time

| Метрика | Фактическое значение |
|---|---|
| Model/revision | `naver/xprovence-reranker-bgem3-v2 @ f2798d357213c40164bdd79557d6d2e43ca7d8d2` |
| Runtime | torch `2.10.0+cpu`, Transformers `4.57.1`, spaCy `3.8.11`, sentence model `xx_sent_ud_sm 3.8.0` |
| Device/precision | CPU, actual parameter dtypes только `torch.float32`, no quantization; batch1, 8 threads, seed0 |
| Configuration | threshold .3, title None, always_select_title false, max pair1024; pinned HF two-stage threshold semantics, не fixed article50% |
| Loads / forwards | Один model load; **21 forward calls**, Q16 11 + Q46 10. Ranking+pruning из одного joint output, **не 42** |
| Overflow / split / ambiguity | **0 / 0 / 0**; все21 windows scored, оба `full_pool_scored=true` |
| Cold-load receipt interval | **3.436568 s** |
| Loaded-model forward aggregate | **3.673959 s**: Q16 **2.415951 s**, Q46 **1.258009 s** |
| Total runner interval | **7.262841 s**, включая preprocessing/postprocessing после start |
| Peak RSS | **2,234,490,880 B = 2.081032 GiB**, ниже12GiB; OS ru_maxrss, не размер weights и не VRAM |
| Generator/provider calls | **0 D host answers**, generation/citation quality **NOT RUN** |

“Cold load” в этом runner включает snapshot rehash/import of author module/model load; interval начинается **после imports torch/Transformers/spaCy**, не включает download и process startup. Диск/cache не приводились к cold state. Forward sum включает первый forward после load, **без отдельного warmup**: это measured loaded-model aggregate, не steady-state benchmark, не p95. Один CPU run не доказывает устойчивую latency или прирост относительно B1. Известное предупреждение config было сохранено, не подавлено и не скрыто как failure-free compatibility guarantee.

### 10.4 Полный ranking: исходные windows не переписаны

Raw logit не вероятность. Same rank/order применяется к P1, **rank после pruning не пересчитывался**. В run не был выбран top_k, не вводился threshold admission/refill; ниже приведён полный scored observed pool. Короткие hashes в таблицах — только display prefixes; полные SHA/IDs находятся в raw receipt и summary.

**Q16**

| Rank | Original char span | Score | Window SHA prefix | Exact retained chars |
|---|---|---|---|---|
| 1 | [1024,2100) | -0.995121 | `fca78e50498a…` | 203 |
| 2 | [7384,7543) | -5.034868 | `740e148e1367…` | 0 |
| 3 | [671,1002) | -6.131386 | `302012e1c45e…` | 83 |
| 4 | [7770,8589) | -6.542629 | `ffb01d4bbd0b…` | 0 |
| 5 | [1002,1024) | -7.838579 | `57df29ab45b5…` | 0 |
| 6 | [3148,3399) | -8.375803 | `3b6205d65916…` | 69 |
| 7 | [2113,2518) | -8.436953 | `c917fbc6df7e…` | 0 |
| 8 | [8810,9305) | -8.689288 | `c66fb248f431…` | 0 |
| 9 | [3399,3600) | -9.135704 | `915a60ebbf03…` | 76 |
| 10 | [6723,6919) | -9.248529 | `0bef7f982603…` | 189 |
| 11 | [3600,3770) | -10.130051 | `10ba0e4b69ae…` | 0 |

**Q46**

| Rank | Original char span | Score | Window SHA prefix | Exact retained chars |
|---|---|---|---|---|
| 1 | [6919,7107) | 3.148400 | `a4999c80a4ff…` | 44 |
| 2 | [6723,6919) | -4.286935 | `0bef7f982603…` | 157 |
| 3 | [7770,8589) | -4.945852 | `ffb01d4bbd0b…` | 0 |
| 4 | [6694,6723) | -6.035044 | `74993a31adac…` | 0 |
| 5 | [6327,6495) | -6.986945 | `5ead6c8d219a…` | 0 |
| 6 | [4000,4198) | -7.493463 | `8784daeb3c3e…` | 126 |
| 7 | [2648,2843) | -7.697085 | `a78917acc9c3…` | 0 |
| 8 | [1024,2100) | -8.780191 | `fca78e50498a…` | 0 |
| 9 | [671,1002) | -8.900126 | `302012e1c45e…` | 0 |
| 10 | [7543,7726) | -10.233189 | `0919ce1ff4c3…` | 0 |

Окна R5 — untouched original source slices; независимый rehash/source equality прошёл для всех21. Rank1 Q16 — `child-697e1c5afe5701899bc1aecd13e99492ff433418`; rank1 Q46 — `child-460bf5decf12245e2c132591e1fdb1a4b62187aa`. Отрицательный raw score Q16 не является основанием отбросить содержащий факт rank1 или ставить arbitrary .5 threshold.

### 10.5 Exact-span P1 adaptation и исходные обязательства

В runtime используется **реальный author joint forward**, author dataset и author `sentence_rounding`; дополнительный adapter возвращает отдельные **original slices**, а не декодированную склейку. Runtime receipt пометил all21 `span_mapping_proven=true` и `source_coordinates_bound=true`. Независимый stdlib review затем сверил:

- original corpus slices/window SHA;
- **75 sentence spans** (11 retained, 64 dropped): source char/UTF-8 byte coordinates, exact substring/hash;
- probability>.3 → token mask; token-selected proportion>.3 → sentence decision, одинаковую rounded decision внутри каждого token interval;
- retained intervals + dropped raw complement целиком и без overlaps/gaps покрывают каждое original window.

Ошибок этих проверок **0**, ambiguities0. Это bounded receipt/source verification, не независимое повторное выполнение tokenizer и не окончательный G verdict. Отдельные retained fragments не получают право притворяться одним непрерывным parent span; dropped whitespace тоже учтён. Public envelope/source-policy validation свежего продукта и host citations не проверялись этим replay.

**Q46:** frozen обязательство `[6952,6996)` «Одинаковые неправильные ответы не дают PASS.» находится целиком в rank1 original window `[6919,7107)` и retained span **ровно `[6952,6996)`**. Negation `не` не потеряно. P1 не сохраняет в этом passage окружающие предложения о неизменности прав/числа вызовов; это pruning, не перенос всего paragraph context.

**Q16:** frozen обязательство `[1152,1209)` «завершение содержит `duration_ms`\n  и `trace_incomplete`.» находится целиком в retained **`[1110,1313)`**, rank1 `[1024,2100)`. Сохранились обе поля, attribution completion и исходный newline. Exact retained text:

```text
Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms`
  и `trace_incomplete`.
- Покрыты CLI `query`, `context` и публичный диспетчер Docs MCP
  (`operation=call_docs_tool_payload`).
```

Предыдущая sentence о связи request_start/end через request_id **отброшена**. Поэтому полное frozen fact span сохранено, но вывод о достаточности сравнительного ответа «чего нет в начале» и корректности host answer не следует из этого автоматически.

**Observed adaptation risks:** sentence segmenter слил completion sentence и следующий Markdown bullet в один retained span; в другом window выделил **`[6760,6761)` = `*`** как самостоятельную retained sentence (в обоих cases). Также Q16 retained `[3329,3398)` — конец уже **обрезанного acquired window**, текст заканчивается «(исходная», не полноценное предложение. Source mapping exact, но это не semantic closure guarantee. Независимое чтение показывает, что некоторые низкоранговые unrelated/fragmentary pieces retained; pruning не заменяет selection/all-irrelevant calibration и не доказывает отсутствие лишнего контекста. Дополнительные closure/rescue rules не добавлены ради успешного результата.

### 10.6 Измеренное сокращение, не net saving

Счёт ниже суммирует **все observed windows каждого question pair**, сохраняя multiplicity (один документ/окно, встретившееся в двух questions, считается дважды). Это R5 full-pool vs P1 masks diagnostic, **не выбранный final public packet**. Separators, evidence metadata, host prompt/history и output answer не включены.

| Case | Original chars → exact retained chars | Char reduction | Author passage tokens → retained tokens | Token reduction |
|---|---|---|---|---|
| Q16 all11 | 4125 → 620 | **84.970%** | 1148 → 193 | **83.188%** |
| Q46 all10 | 3383 → 327 | **90.334%** | 901 → 74 | **91.787%** |
| Both, all21 | 7508 → 947 | **87.387%** | 2049 → 267 | **86.969%** |

Author-passage token counts рассчитаны из recorded sentence token spans, excluding query/special tokens; не o200k_base, не provider billing. Decoded raw strings дают другие character totals: Q16 **618**, Q46 **328** (exact-source totals620/327). Именно это показывает, почему нельзя выдавать `tokenizer.decode` за исходную цитату.

Rank1-only illustration (не новое post-hoc selection правило): Q16 1076→203 chars (**81.134%**), 323→76 author passage tokens; Q46 188→44 chars (**76.596%**), 42→13 tokens. Оба frozen required spans остались. Top1/K selection не исполнялся через публичный путь и не сертифицирован здесь.

**Loss outcome:** для двух заранее существовавших **mandatory fact spans** потерь в retained source нет; surrounding text/low-rank context реально удалён. Это не доказательство сохранения всех semantic dependencies corpus. Новых host answers у D нет, следовательно supported/unsupported answers, false refusals, full-turn token saving, net monetary/latency saving **NOT RUN**, не ноль.

### 10.7 Текущий verdict и handoff G

| Method | Execution status | Измеренный outcome | Непроверенная граница |
|---|---|---|---|
| R5 | **ADAPTED — executed offline author-checkpoint replay** | Полный observed pool scored21/21; fact-bearing windows rank1 в обоих cases; original hashes/spans preserved | Public admission/delivery/negative controls, host answers, calibrated relevance |
| P1 | **ADAPTED — executed source-span-preserving wrapper** | Shared21 joint forwards; masks/raw diagnostics; exact spans mapped21/21, ambiguities0; оба mandatory spans retained | Dependency sufficiency, public quote envelope/source-policy, generator citations, net cost |

Model runtime/download blocker снят для **этого** owner-authorized nonproduction experiment. Licensing ambiguity не интерпретирована как legal guarantee; deployment/distribution не разрешены этой записью. Нет статуса REPRODUCED для article/Bergen/Aya full experiment. G получает raw receipt + `MEASURED_SUMMARY.json` и назначает финальные fact/delivery/answer verdicts независимо. Метод выглядит применимым для следующего ограниченного comparison с B1, но на двух известных development questions superiority/generalization/default deployment не установлены.
