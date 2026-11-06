# Контракт для review, НЕ freeze

Статус: `DRAFT_AWAITING_PARENT_REVIEW`. `freeze-ready-manifest.json` запрещает
runner запускать inference. Ни calibration, ни validation, ни T01 не запускались.
Исторический `step10-open-scorer/recipe-draft.json` сохранён как proposal;
точная актуальная спецификация — `recipe-freeze-ready.json`, включая production
`CONTRACT` и его SHA256. Этот текст и manifest также требуют review родителя.

## Scorer и структура

Opt-in требует `DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1`,
`DOCATLAS_MINIMAL_CONTEXT_RECIPE=qwen3-contextual-own-body-evidence-v1` и абсолютный
`DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH`. Frozen policy передаётся через
`DOCATLAS_MINIMAL_CONTEXT_POLICY`; без него только diagnostic full scan.
MiniLM recipes, schema1/2 и structural v1 остаются отдельными. Default off.

Qwen — passage reranker, не EXIT и не доказанная sentence evidence classifier.
Exact original question не переводится/не переписывается. Canonical JSON:
`ensure_ascii=False,sort_keys=True,separators=(',',':')`.
`context.containing_document` — весь исходный документ. `incoming_references`
содержит все прямые anchor references к target или ancestors, найденные только
в checked scope. Каждый entry: `source_identity` (SHA256 full canonical native
identity), `path`, `heading_path` (array), `char_start`, `char_end`, `text`.
Dedup по native identity+parent index, сортировка по полной identity, затем
parent start/end. Entry offsets охватывают own body без heading.
Target: `heading_path`, `char_start=body_char_start`, `char_end`, `text`.
Все offsets — zero-based half-open Python Unicode characters, НЕ bytes.
Каждый parent полного containing document и каждого incoming body проходит
native hydration/qualification до tokenization и повторно перед forward.
Missing/ambiguous/unavailable anchors — explicit dependency gaps, без fetch.
Score-rejected valid link не означает доказанной ненужности.

Prefix/suffix encode с `add_special_tokens=False`, body с `True`, везде
`truncation=False`. Полная длина prefix+instruction+query+JSON+suffix должна быть
`<=32768`; выше весь scan incomplete. Preflight всех bodies до первого forward.
BF16, SDPA, batch1, CUDA, no CPU fallback, `use_cache=False`, `logits_to_keep=1`.
FP32 softmax последних logits `[2152(no),9693(yes)]`, finite logits/score/difference.
Model cache только loaded model под RLock, score memo отсутствует. Runtime pins
и все девять asset hashes проверяются при каждом scoring call; provenance.json
должен совпасть с model/revision/hash map. OFF не сохраняет prompts/unit traces;
ON добавляет score diagnostics вне protocol packet и не меняет selection.

Structural v2 закрывает own bodies, ancestor introductions, definitions.
Ни selected parent, ни anchor не включают subtree автоматически. Явный public
source-read сохраняет прежний whole-section контракт.

## Независимый gate и fit

На query конкурируют все шесть project docs; седьмой module doc индексируется,
но исключён scope. Labels/expected text берутся из authored files/ATX inventory,
не production parser; labels не передаются сервису/scorer. Проверяются complete
required bodies,81 quotes, child source order, no-answer только после complete
scan, hard negatives, hashes, scope/version/root identity, resource reads/replay,
неизменность source files и логического SQLite dump после prepare.
Fixtures не содержат reference/footnote definitions; offline closure fit здесь
только ancestors. Изменение этого ограничения требует review evaluator.

Calibration: ровно8 вопросов diagnostic и8 final policy replay (реальные
повторные forwards), два prepare. Один и тот же fixture root/generation на оба
прохода. Distinct finite scores сортируются по убыванию без округления; выбран
самый большой observed breakpoint, сохраняющий required final obligations.
Membership `score>=tau`, все ties вместе. Empty boundary отдельно вычисляется
через `math.nextafter(max_score,+inf)` и не является observed threshold.
Optional witnesses не снижают tau. Затем no-answer/hard-negative/reduction gates;
FAIL останавливает процесс, threshold ради этих gates не подгоняется.
Реальный final replay обязан совпасть с predicted delivered unit sets.

Schema3 policy: model/revision, recipe/structural recipe, exact-original lane,
contract SHA256, calibration recipe, threshold (JSON binary64 roundtrip),
`calibration_sha256` = SHA256 approved input manifest. Policy hash отдельно
фиксируется в PASS summary. Никакого автоматического validation chaining.
Validation — отдельные8 вопросов, два prepare, только после calibration PASS
и отдельного parent authorization JSON со status `PARENT_APPROVED_VALIDATION`,
manifest/policy/calibration-summary SHA256. Такой authorization не создан.

## Метрики

Source metric: vendored offline `o200k_base` (tiktoken0.11.0 vocabulary/regex).
Для каждого answerable query denominator — сумма tokens полных шести allowed
originals. Numerator — original delivered intervals, merge overlap/adjacency
внутри документа, каждый раздельный interval токенизируется отдельно. Ни model
full-doc repeats, ни повторные seed rows denominator не увеличивают.
По каждому split aggregate numerator <= denominator/2. Все optional/unlabelled
tokens учитываются; exact false-positive rate не заявляется. Role token totals
токенизируются отдельно и из-за BPE не обязаны складываться в overall numerator.
No-answer требует0 rows независимо от labels. Packet JSON и supported rendering
tokens показаны отдельно; actual MCP wire/client model-visible = null: это
in-process public proof, не installed stdio/реальный клиент/Terra.
Каждый query сохраняет Qwen inputs/forwards/cache/load/time/peak VRAM receipt;
counts суммируют и diagnostic, и replay. Failure не превращается в PASS/empty.

## Команды ПОСЛЕ разрешения, сейчас не выполнялись

Из repository root, GPU env, `HF_HUB_OFFLINE=1`, `TMPDIR=/tmp/opencode`:

```sh
python -m eval.blind_project_context.step10-multidoc-gate.runner calibration --manifest /absolute/approved-manifest.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /absolute/new-calibration
python -m eval.blind_project_context.step10-multidoc-gate.runner validation --manifest /absolute/approved-manifest.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /absolute/new-validation --calibration /absolute/new-calibration --validation-authorization /absolute/parent-authorization.json
```

## Public diagnostic — выполнен после отдельного разрешения R3/R4

Использован только `DOCUMENTS/QUESTION` из `probe_minimal_structure.py`;
`probe_minimal_delivery.py` содержит T01 и НЕ запускался. Raw artifacts:
`../step10-qwen-public-preflight/run-01/`.2prepares+3queries,16forwards/6608tokens.
Exact OFF/ON packets/source spans/hash/scope/read-only PASS. Empty heading,
definition owner+continued footnote/reference destination сохранены; missing
private anchor явно gap. Это diagnostic keep-all, не semantic sufficiency.
Отдельная oversized copy вернула scan_incomplete/evidence_prompt_overflow:35263
с0forwards.32K inference не проверена. Resource reads0: definitions continuation
проверялась непосредственно в source-exact packet, source-read API не вызывался.

## R3/R4 — учёт работы отдельно от delivery

Observer получает ровно один work observation немедленно после scorer, ДО
selection/closure. Scorer error также записывается. Receipt не исчезает при
последующих closure/rebuild/terminal/finalization failures. `delivery_status`
остаётся `not_confirmed` до нормального финального return; не является semantic
PASS. OFF не удерживает extra scores/traces. MiniLM selection semantics не менялись.
Evaluator считает attempts prepare/query/resource до вызова, пишет query receipt
и counters в finally. Unsupported missing receipt означает
`lost_trace_unknown_work`, `model_totals_complete=false`: totals тогда только
известная работа, а не доказанное0. Duplicate observation также делает totals
неполными и останавливает gate assertion.
Per-project/phase `readonly.json` сохраняет before/after source+catalog hashes,
logical DB digest и полные observed asset hash maps (включая provenance.json),
даже при failure; unknown trace не считается read-only proof. Это не DB copy.
Historical review candidate до R3/R4 сохранён отдельно в
`history/review-candidate-before-r3-r4/`, manifest SHA256
`24749af395d3dbd7e39ab65f102ea83844eca9249441969611502b58959f7531`.
