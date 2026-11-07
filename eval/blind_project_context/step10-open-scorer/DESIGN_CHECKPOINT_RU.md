# Этап3: один открытый scorer, concrete design checkpoint

Статус: proposal до production classifier diff и любого gate inference.
Выбор владельца «открытая модель» разрешает иной механизм, не воспроизведение EXIT.

## Выбор и проверенные источники

| Official model | Metadata | Решение |
|---|---|---|
| Qwen/Qwen3-Reranker-0.6B | Ungated, Apache2,595776512 BF16 parameters, instruction-aware yes/no, multilingual100+, card32K | Выбран: один небольшой эксперимент с явно указанным target, без fine-tuning/PEFT/remote code. |
| BAAI/bge-reranker-v2-m3 | Ungated, Apache2,567755777 parameters, multilingual scalar query/passage cross-encoder | Подходит как reranker, но не имеет такого документированного instruction interface для target/context relation; не запускаем второй эксперимент. |
| jinaai/jina-reranker-v2-base-multilingual | Ungated,278437633 parameters, multilingual, CC-BY-NC4.0 | Не выбираем: более ограничительная лицензия и нет преимущества для проверяемой target/context гипотезы. |

Metadata revisions: Qwen e61197ed45024b0ed8a2d74b80b4d909f1255473;
BGE953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e;
Jina9cfeff2df7d40d1b78e75e5e9cebec92a99813c9.

Источники:
- https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/blob/e61197ed45024b0ed8a2d74b80b4d909f1255473/README.md
- https://huggingface.co/api/models/Qwen/Qwen3-Reranker-0.6B/tree/e61197ed45024b0ed8a2d74b80b4d909f1255473
- https://huggingface.co/BAAI/bge-reranker-v2-m3
- https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- https://qwenlm.github.io/blog/qwen3/ — English/Russian явно входят в119 языков
  Qwen3 family; reranker card обещает100+ multilingual/cross-lingual, но не даёт
  гарантии русского project evidence recall.
- Context7 `/huggingface/transformers/v4.57.3`: SDPA/dtype loading docs получены.
  Точный `logits_to_keep` дополнительно проверен в official modeling_qwen3.py и
  actual installed4.57.1 forward signature; Context7 выдача не дала точного Qwen3
  signature и не использовалась как доказательство несуществующего API.

Отличие от mMARCO: другая обученная multilingual instruction-aware reranking
модель, длинный контекст и управляемая evidence instruction. Она остаётся
passage reranker, НЕ специально обученным EXIT sentence classifier. Разделение
target/context через JSON и наша instruction — новая проверяемая гипотеза;
model card подтверждает custom instruction, не качество этой конкретной recipe.

## Пины, runtime и ресурсы

Weights1,191,588,280bytes SHA256
`27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b`;
tokenizer.json11,422,654bytes SHA256
`aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`.
Эти expected hashes опубликованы official HF LFS metadata. `prepare_assets.py`
проверяет также фактические downloads, git-blob hashes малых файлов и сохраняет
SHA256 каждого asset. Никаких mirror/gated terms/нового adapter.

Перед download проверены ресурсы:5.36GiB free disk; в uv-cache найдены CUDA
torch2.10.0+cu128 cp312 и все pinned NVIDIA dependencies. Создан НОВЫЙ env:

```sh
uv venv --offline --python 3.12 /tmp/opencode/step10-qwen-gpu-py312
uv pip install --offline --link-mode hardlink --python /tmp/opencode/step10-qwen-gpu-py312/bin/python 'torch==2.10.0' 'transformers==4.57.1'
/tmp/opencode/step10-qwen-gpu-py312/bin/python eval/blind_project_context/step10-open-scorer/prepare_assets.py --out /tmp/opencode/step10-qwen-reranker-06b-assets
```

Offline43 packages установлены hardlinks без скачивания CUDA и изменения старых
envs. Проверка runtime: torch2.10.0+cu128, CUDA12.8, GPU RTX5070Ti, compute12.0,
compiled sm_120, cuda_available=True. Полная provenance сохраняет package versions.
BF16 weights около1.11GiB; inference batch1, SDPA, use_cache=False,
logits_to_keep=1, eval/inference_mode. Не материализуем vocab logits на всех
позициях, не запускаем генерацию. Batch1 ограничивает tensors, не число units.
Полная VRAM/latency реального scorer ещё не измерена; матричный CUDA smoke не
доказывает model quality или успешный32K forward.

Card32K, actual config.max_position_embeddings40960, tokenizer.model_max_length
131072. Это разные пределы; не выдаём tokenizer131072 за поддержанный контекст.
В recipe поддержан полный prompt<=32768 tokens. Overflow даёт scan_incomplete,
без truncation, пропуска units или молчаливого reduced-context fallback. Это
physical support guard, не semantic budget/выбор prefix. Для длинных документов
за этой границей нужна отдельная recipe, пока не обещанная.

## Один фиксированный input recipe

Точные prefix/instruction/suffix и serialization в `recipe-draft.json`.
Original question неизменен, только одна original lane; инструкции English как
рекомендует card, source text не переводится и не пересказывается. Token IDs
`yes`/`no` проверяются как одиночные tokens pinned tokenizer. Score:
`exp(logit_yes)/(exp(logit_yes)+exp(logit_no))` через FP32 softmax для устойчивости.
Также сохраняется logit difference; это нормализованный model score, не
калиброванная вероятность достаточности/истинности ответа.

Segmentation: existing native Markdown own-body sections с исходными offsets;
списки/таблицы/code целиком, без нового sentence splitter. Qwen принимает passage,
поэтому body-level target не притворяется EXIT sentence reproduction.

Document JSON отделяет `target.text` (оцениваемый own-body) от `context`:
полный проверенный содержащий документ плюс ВСЕ прямые входящие anchor source
bodies, ссылающиеся на этот target section или любого его предка. Все контексты
source-checked в том же scope/version/snapshot. Incoming graph фиксирован по
синтаксису до inference, не зависит от scores/выбранных seeds. Нет рекурсивного
включения upstream full documents; одна link-hop контекстуализация — явная
граница гипотезы. Дедупликация только по source identity/offsets, не смыслу.

## Три structural решения

1. **Own-body admission.** Каждый child оценивается самостоятельно тем же
   неизменным query, full containing document и target framing. Положительный
   parent не допускает детей. Для broad/full-section question parent scope и
   child step одновременно видны scorer, но coverage НЕ гарантируется — C-L2,
   V-C2 должны пройти конечным текстом, иначе FAIL без словарного fallback.
   Existing explicit source read сохраняет свой whole-section/subtree контракт;
   source_path в semantic query не объявляется требованием отдать весь документ.
2. **Completeness.** Выбранное собственное тело доставляется целиком с heading,
   ancestor introductions и syntax-bound footnote/reference definitions.
   Нет score для context-only и нет автоматического parent subtree. Условия
   в другом собственном разделе должны пройти общий evidence selection.
3. **Anchors.** Anchor не команда добавить subtree. Он лишь связывает проверенный
   source context с оцениваемой целью; одинаковый classifier решает, содержит ли
   target evidence для query, а не просто navigation. Это НЕ доказанный detector
   типа ссылки и не второй hidden threshold. Нужный linked block допускается
   целиком, children по общему правилу. Если classifier потерял required linked
   condition — FAIL, а не объявление navigation. Недоступные/ambiguous targets
   остаются явными structural gaps. Valid rejected target не сертификат
   ненужности: context_quality остаётся unverified.

Если неделимое тело содержит и обязательное условие, и шум — доставляем всё тело,
считаем noise tokens; целиком такое тело нельзя разметить hard negative. Если
required condition находится у child anchor target, incoming reference context
предка доступен child scorer, но наличие ссылки не даёт automatic admission.
Нельзя одновременно обещать гарантированное сохранение всех dependencies и
идеальное отсечение навигации этим неизвестным classifier. Gate проверяет риск.

## Freeze и smallest diff после review

1. Parent review recipe + rev2 label rationale. Сохранить history, immutable
   manifest design/prompt/segmentation/model/runtime/labels ДО inference.
2. Новый небольшой `context_evidence_scoring.py`: pinned local loader, exact
   prompt, полный stream всех checked units, diagnostics opt-in, overflow/OOM
   explicit. MiniLM V1/V2/V4 не менять.
3. `minimal_context_structure.py`: отдельный v2 dispatch, fixed incoming edges,
   own-only semantic seeds, ancestors/definitions, no automatic anchor subtree;
   v1 и explicit source read сохранены. `minimal_context_selection.py`: новый
   policy schema/recipe/pins/fingerprint, default off.
4. Переиспользовать public runner, заменить one-document grouping на project
   collections и rev2 labels. Calibration8 questions первой; наибольший observed
   breakpoint, сохраняющий все required final obligations. Optional не требует
   retention и не понижает tau. Затем hard-negative/noanswer/50% gates; infeasible
   означает FAIL, не новую серию порогов. Validation8 — один frozen policy run.
5. Scorer computations calibration можно exact-key memo replay для final public
   calls; считать отдельно реальные forwards и memo hits. Независимые факты и
   source fidelity конечного packet определяют verdict, не replay predictions.
6. Только после этого installed original T01 как diagnostic validation. Никакой
   настройки на T01, Terra/broadL2 пока не разрешены.

## Unresolved, требующие согласия на эксперимент

- Target-specific instruction и full-doc/incoming context могут всё ещё давать
  context leakage/слабое discrimination; это основной quality risk, не bugfix.
- Broad child и cross-document/multi-hop condition recall не гарантированы.
- Native parser own-body granularity может ограничить50% reduction даже при
  правильном admission; нельзя лечить это квотой или удалением required facts.
- Full32K runtime/VRAM ещё не проверен, overflow делает весь scan incomplete.
- Dataset rev2 synthetic и не template-disjoint; настоящие project gates нужны.

Никаких production classifier/closure changes или gate inference на этом checkpoint.

## Завершение подготовки assets

Фоновая preparation завершилась успешно. Все9 downloaded files проверены по
official pinned LFS SHA256 либо git-blob SHA1; фактический SHA256 каждого файла
сохранён в `assets-provenance.json` (копия provenance из assets directory).
Веса и tokenizer совпали с ожидаемыми hashes выше. Token IDs: `yes=9693`,
`no=2152`, оба одиночные. CUDA BF16 matrix smoke PASS на RTX5070Ti; это не
model forward. Model inference calls=0, gate inference calls=0. Assets готовы
в `/tmp/opencode/step10-qwen-reranker-06b-assets`; production/gate ждут review.
