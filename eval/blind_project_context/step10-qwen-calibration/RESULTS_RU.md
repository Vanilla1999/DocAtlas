# Calibration run-01: ERROR_NOT_PASS, остановлен без повторов

Один разрешённый запуск, exit1. Frozen code/data/prompt/threshold не менялись.
После run независимо сверены все534 bound hashes и approved manifest hash.
Validation/T01/installed/Terra/L2 и дополнительные diagnostics/tests не запускались.

## Команда и привязка

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-multidoc-gate.runner calibration --manifest /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-multidoc-gate/freeze-ready-manifest.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-calibration-01
```

Approved manifest SHA256:
`87585ea10a1c0a4e6673020368ad51ee0e64bdd9ca3d6de4ca8ddce86a34046a`.
Generated policy SHA256:
`16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`.
Threshold автоматически fitted: `0.8670357465744019`. Это policy не получившая
calibration final PASS; она не разрешает validation.

## Три разные границы результата

1. **Diagnostic keep-all:**8 queries завершены. Их outputs не считаются final-policy
   relevance/no-answer proof. Все raw packets/observations сохранены.
2. **Offline fit prediction:**26 examined breakpoints включая empty boundary;
   largest required-preserving observed threshold прошёл predicted required,
   no-answer, hard-negative и reduction gates. Predicted aggregate calibration:
   **961/4272 source tokens**, reduction **77.50468165%**. Это НЕ final split PASS.
3. **Real final replay:**C-T1 и C-T2 завершились; C-T3 вернул hard-stop
   `source_reference_batch_rejected`. C-T4 и четыре Loom queries НЕ выполнялись.
   Полного final calibration aggregate и calibration PASS нет. Validation не было.

| Final query | Required/facts | Hard negatives | Delivered source tokens |
|---|---|---|---:|
| C-T1 | все доставлены |0|250/742|
| C-T2 | все доставлены |0|113/742|
| C-T3 | packet error; отсутствуют3 required units/5 facts |0, но это error|0; не успешный empty/no-answer|
| C-T4, C-L1..C-L4 |NOT_EXECUTED|не измерено|не измерено|

`offline-review.json` отдельно содержит diagnostic results, все8 fit predictions,
per-query actual final facts (точные quotes и delivered), required units,
hard negatives/no-answer/scan status и source tokens. Missing queries имеют
NOT_EXECUTED, не ложные0/PASS. Failed C-T3 observer scores не заменяют final packet.

## Работа и receipts

**2 prepares,11 queries,4 resource reads,239 forwards,104524 model-input tokens**.
8 diagnostic +3 final queries.1 model load,10 loaded-runtime cache hits,
0 score cache hits. Counts независимо сверены суммированием11 raw work receipts.
Lost traces0, model_totals_complete=true — это полнота accounting, не delivery PASS.

- Sum measured query wall latency16.686887427s; prepare latency0.267229600s.
- Scorer total13.503790887s; forward time3.442691589s.
- Peak VRAM allocated1,221,214,208 bytes; reserved1,245,708,288 bytes.
- Это не полное wall-clock время процесса: offline fit/asset audit/report overhead
  в query latency не входит. Отдельный process wall-clock receipt не записывался.
- Три `readonly.json`: diagnostic TideGauge/Loom и failed final TideGauge.
  Все before/after source+catalog hashes, logical DB и assets совпали, trace complete.
  Final audit также сохранил operation_error. Полные значения в raw, не только bool.

Raw byte-exact copy: `run-01/`,42 files/980580 bytes; SHA map `raw-sha256.json`.
Исходные runtime artifacts остаются `/tmp/opencode/step10-qwen-calibration-01`.
Copy path НЕ является новым prepared/runtime root, исходные paths в receipts
не переписаны. `run-01/failure.json` — итоговый ERROR_NOT_PASS; summary.json не
создан, поскольку runner остановился на assertion. Sources скопированы вместе
с receipts, DB copy не создавалась.

## Offline разбор только C-T3, без исправлений и inference

Runner остановился в `packet_check`: public packet не содержит successful scan,
а имеет status=error, hard_stop=true, sources=[], reason_code=
`source_reference_batch_rejected`. Scorer C-T3 выполнил21forwards/9459tokens;
R3 receipt сохранился несмотря на последующий body-free rejection.

Конкретный подозреваемый конфликт подтверждается сочетанием raw и control flow:

- C-T1 final resource checks потребили URI storage.md Retention, lines5–8:
  `docatlas://source/v2/88618195d80563d484342688`; replay отказан как expired/unknown.
- C-T3 final scores допускают тот же Retention own body. C-T3 diagnostic packet
  ранее содержал ровно этот URI (те же root/generation/source span).
- `_source_continuation_core.py:98–99` отвергает повторную выдачу spent URI;
  `source_continuation.py:310–312,335–336` превращает такой отказ в observed
  atomic batch rejection. `_bind_atomic` также сворачивает другие exceptions
  в тот же reason, поэтому конкретная внутренняя ветка не доказана runtime trace.

Это сильная offline гипотеза о взаимодействии одноразовых source capabilities
и последующих public queries после resource reads. Не объявляем её исправленной
или единственной доказанной причиной. Не обходили resource checks и не меняли
policy/fixture/session lifecycle. Следующий шаг — parent review failure/raw и
отдельное решение; повторного запуска не было.
