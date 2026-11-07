# Qwen opt-in: implementation checkpoint для родителя

> Это первоначальный checkpoint до R3/R4. Актуальное дополнение с разрешённым
> public runtime и исправлением accounting: `../step10-qwen-public-preflight/R3_R4_CHECKPOINT_RU.md`.
> Указанные ниже «пока не исполнялись» описывают исходный review candidate;
> gate/calibration/validation/T01 по-прежнему не запускались.

**Не frozen. Не semantic PASS. Calibration/validation/T01 не запускались.**
Подготовлен production diff + public evaluator + rev3 labels для review.
Parent-owned review/execution checkpoint не изменялись. Delegation/commit/push,
Terra, full suite и L2 не выполнялись.

## Пути diff

- `docmancer/docs/application/context_evidence_scoring.py` — отдельный pinned
  Qwen scorer, contract, asset/runtime verification, preflight, реальные counters.
- `docmancer/docs/application/context_evidence_structure.py` — полная native
  qualification context bytes, fixed incoming-anchor graph и explicit gaps.
- `docmancer/docs/application/minimal_context_structure.py` — versioned v2
  build/hydrate/recheck/closure; v1 constant/default сохранены.
- `docmancer/docs/application/minimal_context_selection.py` — Qwen dispatch,
  schema3, continuation settings, observer-only retained score diagnostics.
- `docmancer/docs/domain/minimal_context_config.py` — отдельный Qwen model path.
- `runner.py` в этой директории — public prepare/query, independent obligations,
  calibration fit/replay, отдельный validation authorization, source/ref/read-only
  checks. Runtime execution этого evaluator пока не проверен.

## Final draft labels и контракт

`LABEL_REVIEW_REV3_RU.md`, `tasks.json`, `draft-labels.json`,
`draft-manifest.json`, `rev3-invariants.json`; rev2 сохранён в `history/draft-rev2`.
Offline audit:4 проекта,28 docs,16 queries,81 facts,4 no-answer.
Invariant comparison PASS: все28 sources, вопросы, required units/facts и hard
negatives совпадают с rev2.237 role changes включают unlabelled, не237 новых
supporting witnesses. Все task fields кроме optional_support неизменны.

Точный текущий recipe: `recipe-freeze-ready.json`; подробный fit/policy/metric
контракт: `FREEZE_READY_CONTRACT_RU.md`; полный hash inventory:
`freeze-ready-manifest.json`. Manifest status `DRAFT_AWAITING_PARENT_REVIEW`:
runner отвергает его до любой подготовки проекта или inference. Исторический
proposal recipe сохранён, актуальная спецификация находится отдельно.

Manifest связывает все production Python файлы и vendored tokenizer data,
evaluation/runtime код, sources/labels/review artifacts и asset/runtime receipts.
Это учитывает зависимость от уже существующего dirty shared checkout; не означает
присвоения остальных diff этому эксперименту. Threshold пока null. Parent approval
должно быть отдельным действием после review; validation authorization отсутствует.

## Выполненные проверки и стоимость

1. `python3 eval/blind_project_context/step10-multidoc-gate/audit_draft.py` — PASS.
2. Offline rev2/rev3 source/task/unit comparison — PASS, `rev3-invariants.json`.
3. Один итоговый static pass: compile/AST9 файлов, imports production/runner,
   `git diff --check` — PASS, `static-checks.json`. Ни public calls, ни inference.
4. Все9 assets реально перепроверены SHA256 при подготовке manifest. Provenance:
   `../step10-open-scorer/assets-provenance.json`; local download receipts и
   origin URLs сохранены там. Старое `model_inference_calls=0` в provenance —
   состояние на момент подготовки assets, не текущий cumulative model count.
5. Единственный разрешённый model smoke, ранее выполненный по pinned card:
   `model-card-smoke-receipt.json` (байтовая копия внешнего receipt).
   **2 forwards,189 input tokens (85+104),1 model load,0 score cache hits**.
   Load0.601910437s, forwards0.332742404s, total after asset checks0.936675870s.
   Peak allocated1,202,927,104 bytes, reserved1,218,445,312 bytes.
   p_yes0.9994806647 и0.9993737340. Gate/Terra calls0.
   Это feasibility двух коротких published pairs, не доказательство target/context
   discrimination, sufficiency или32K runtime. Дополнительного smoke не было.

Smoke command (НЕ повторять):

```sh
HF_HUB_OFFLINE=1 /tmp/opencode/step10-qwen-gpu-py312/bin/python eval/blind_project_context/step10-open-scorer/model_card_smoke.py --assets /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-model-card-smoke-01
```

DocAtlas установлен offline editable только в новый GPU env:

```sh
uv pip install --offline --link-mode hardlink --python /tmp/opencode/step10-qwen-gpu-py312/bin/python -e .
```

Установка добавила67 packages; post-install versions/executable записаны в
`runtime-post-install.json`. Core model runtime: torch2.10.0+cu128,
transformers4.57.1, tokenizers0.22.2, safetensors0.8.0, CUDA12.8, sm_120.

Artifact-only manifest preparation (не public diagnostic):

```sh
/tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-multidoc-gate.prepare_review_manifest
```

## Открытые риски / следующий gate

- Новый scorer/structure/evaluator публично не исполнялись. Static imports не
  доказывают native qualification, reference checks или observer OFF/ON parity.
- Target-only evidence judgement и broad-child/linked-condition recall остаются
  гипотезой;50% per-split reduction может не пройти. FAIL требует остановки.
- Full-document+incoming input может превысить32K или VRAM; short smoke этого
  не проверяет. Overflow/OOM должны дать scan_incomplete, не partial success.
- Native source identity содержит local project identity/generation: evaluator
  сохраняет их между calibration diagnostic/final replay. Different run paths
  меняют provenance hash в prompts; воспроизводимость зафиксирована в receipts
  конкретного run, не обещана при произвольном переносе project root.
- Synthetic sources/labels не внешний blind benchmark и не installed-client proof.
- Optional existing-fixture public diagnostic описан в контракте для review;
  driver не создан и run не выполнен. Следующий шаг — review родителя, затем
  отдельное разрешение freeze/calibration. Validation только после PASS и нового
  разрешения.32K и semantic acceptance пока открыты.
