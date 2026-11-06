# Review corrections R1/R2

Новые measurements, старые `step10-fit-correction/*` не перезаписаны.

## R1 — opt-in интервалы

`complete_context_scoring.py`: `record_intervals=False` по умолчанию. В V4
без флага `intervals=None`, per-pair list/dicts не создаются. Остаются только
per-unit и aggregate `intervals_recorded` / `intervals_omitted`. С флагом
записываются все реально обработанные pair intervals. Batch membership,
model inputs, logits aggregation и semantic gate не зависят от этого флага.

`minimal_context_selection.py` передаёт `record_intervals` только для V4 и
только как `(_OBSERVER.get() is not None)`. Старые recipe вызовы не получают
новых kwargs. Рецепты/threshold/fingerprint semantics не изменены: это
отключаемая диагностика, не новый semantic recipe.

Исправление прежнего отчёта: на этапе2 интервалы действительно записывались
всегда, а не только observer. Тот исторический отчёт/receipts оставлены как
история; актуальная реализация opt-in только после этого diff.

### Public verification

Расширен тот же `probe_minimal_structure.py`, режим `--observer-parity`.
Выполнены только V4 OFF/ON. Passive Python return hook записывает фактические
возвращённые scorer scores/receipts, не включает product observer для OFF,
не меняет retrieval/scoring/selection/source validation и не делает доп. calls.

```sh
PYTHONPATH=. /tmp/opencode/step10-v3-py313/bin/python -m eval.blind_project_context.probe_minimal_structure --fit-correction --observer-parity --model-dir /tmp/opencode/step10-mini-assets --work-dir /tmp/opencode/step10-review-r1-public-01 --output /tmp/opencode/step10-review-r1-public-01/receipt.json
```

PASS с первой попытки после review diff:

| Показатель | OFF | ON |
|---|---:|---:|
| Units | 9 | 9 |
| Model pairs | 11 | 11 |
| Forwards | 9 | 9 |
| Model input tokens | 3837 | 3837 |
| Intervals recorded | 0 | 11 |
| Intervals omitted | 11 | 0 |

- Полные public packets равны **точно, без исключения полей**.
- Scores равны точно, различаются только diagnostic interval fields.
- OFF не содержит `pair_token_intervals` у любого unit; ON counts совпадают
  с длинами списков. Сохранились факты/условия, включая хвост длинного body.
- Каждая строка проверена на exact source slice, canonical hash, project scope,
  authority и identity. Source files и logical SQLite digest read-only.
- 1 preparation +2 public queries,22 model pairs,18 forwards. V1 не запускался:
  прежнее сравнение26→11 берётся из старого receipt, не нового inference.
- Tokenizer предупреждает о длинном исходном body; оконный путь по-прежнему
  использует физические пары не длиннее512. Это не ошибка model execution.

Проверка in-process public pipeline, diagnostic keep-all/unverified; не installed
stdio/client, не semantic acceptance и не CPU/memory benchmark. Cold/warm timing
не используется как доказательство улучшения. Raw packets и receipts в `r1-public/`.
Исходный prepared state остался в `/tmp/opencode/step10-review-r1-public-01/state`;
в repo скопированы только inputs/packets/receipt, не runtime DB.

## R2 — immutable study plan

`run_gap_agent_study.py`: plan строится/сверяется до любых config writes/session
calls. Если существующий JSON plan отличается — `study plan changed`, отказ.
Если plan отсутствует, но в arm любого corpus есть case artifacts —
`case artifacts exist without study plan`, отказ. Config-only directories не
считаются завершённым case. Для совпадающего plan сохраняется resume и plan
вообще не перезаписывается. Новый plan создаётся в exclusive mode `open('x')`.
CLI stdin transport correction сохранена; исторический positional-run не
может получить новую transport provenance через повтор этого evaluator.

### CLI integration

```sh
PYTHONPATH=. /tmp/opencode/step10-v3-py313/bin/python eval/blind_project_context/step10-review-corrections/probe_plan_guard.py --out /tmp/opencode/step10-review-r2-cli-01 --prepared-root /tmp/opencode/step8-corpora2
```

Два настоящих CLI вызова evaluator, без mocks и без dry-run API:

1. Historical plan + sentinel jsonl/config → ожидаемый отказ, exit1.
2. Case artifacts без plan → ожидаемый отказ, exit1, новый plan не появился.

В обоих случаях все sentinel bytes/hash и inventory output неизменны. strace
`execve` фиксирует только начальный Python evaluator: никаких subprocess
OpenCode/session/model запусков. 2 CLI calls,0 session calls,0 model calls.
Exact-plan resume сохранён по code inspection; отдельный runtime resume не
заявляется проверенным. Команды каждого evaluator вызова, before/after hashes,
stderr и execve traces сохранены в `r2-cli/`.

## Остаток

EXIT weights по последнему metadata check недоступны; новых download/auth/model
попыток не делалось. Classifier и closure v2 не реализовывались. Gate остаётся
**DRAFT ONLY**, без freeze/preparation/inference. Parent approval для classifier
не заявляется. Segmentation, full-section binding и anchor amplification открыты;
synthetic dataset не template-disjoint. Terra и полный suite не запускались.

Финальные статические проверки выполнены один раз по итоговому code diff:
AST parse и trailing-whitespace check5 Python-файлов PASS; targeted tracked
`git diff --check` PASS. Три прежних measurement JSON побайтно совпадают с
исходной `/tmp/opencode/step10-fit-v4-public-02` копией. Все hashes draft manifest
совпадают, `frozen_before_inference=false`; draft data не изменены.
