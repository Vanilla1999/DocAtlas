# Validation run-01 — QUALITY FAIL, остановлено

Первая inference validation8 Meridian/Cairn выполнена один раз. Exit0, но
**summary.status=FAIL**, required_pass=false. Никакого tuning/retry/repair,
дополнительных tests/smoke/T01/installed/Terra/L2. Default off, bound files неизменны.

## Команда и provenance

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-multidoc-gate.runner validation --manifest /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery-entry/recovery-freeze-ready-manifest.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-validation-01 --calibration /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery/run-01 --validation-authorization /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery-entry/parent-validation-authorization.json
```

- Approved manifest SHA256:
  `2bcebef52ab6268e091f5e28de12acc8837988bff36c2068432e2a4b73ebe066`.
- Exact original policy SHA256:
  `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`.
  Threshold0.8670357465744019 unchanged, fitter не запускался.
- Validation summary SHA256:
  `14e5f1f2512b16d7795083c7fb992d346b401aa20201c98b1f770878bc08a1a2`.
- Все618 current bound hashes сверены до/после run и неизменны.
- Byte-exact raw copy `run-01/`:38files/473594bytes, map `raw-sha256.json`.
  Original runtime root `/tmp/opencode/step10-qwen-validation-01` в receipts не
  переименован. Parent authorization и exact policy дополнительно скопированы в
  `provenance/`, отдельно от неизменённой raw output directory.

## Конечные packets, не observer verdict

| Query | Required complete units | Required facts | Source tokens delivered/allowed | Result |
|---|---:|---:|---:|---|
| V-M1 |3/5|5/8|158/688|FAIL: weather conditions missing|
| V-M2 |3/3|6/6|116/688|required PASS|
| V-M3 |3/3|5/5|168/688|required PASS|
| V-M4 |no-answer|no-answer|0/688|empty complete scan|
| V-C1 |3/3|6/6|260/664|required PASS|
| V-C2 |5/5|8/8|219/664|full-section required children PASS|
| V-C3 |5/5|8/8|148/664|required PASS|
| V-C4 |no-answer|no-answer|0/664|empty complete scan|

Итого **22/24 required units,38/41 required fact quotes** validation split.
Hard negatives0 во всех8 packets; no-answer оба PASS. V-C2 explicit
`recovery.md#Recovery procedure` required bodies/children доставлены полностью,
исходный порядок preserved. Полные unit keys/quotes и per-fact delivered booleans
в `offline-packet-audit.json`, source rows/order — в actual packets.

Aggregate validation source metric: **1069/4056 tokens**, reduction
**73.64398422%**. Denominator включает только6answerable queries; optional/
unlabelled source tokens учитываются. Required FAIL не компенсируется reduction,
no-answer или отсутствием hard negatives. Exact false-positive rate не заявляется.

Offline независимая сверка packets с original files/labels подтвердила missing
units/facts, exact spans/text/content hash/scope/version/authority и source order.
Token totals — reviewed runner с pinned codec. Никакой смены expected facts,
label roles или оценки по внутреннему selected flag.

## Один original-question offline trace: V-M1

Exact question:
«Как передать подтверждённое ночное наблюдение другому наблюдателю при активной
блокировке обслуживания и погодной приостановке?»

В final packet отсутствуют:
- `weather.md#Weather decisions` (required ancestor intro);
- `weather.md#Suspension` (complete own body).

Три отсутствующих обязательных факта:
1. `Suspend outdoor observations when the wind interlock opens.`
2. `Preserve reservation identifiers during suspension.`
3. `Resume only after the interlock closes and the duty operator records a restart approval.`

Actual complete scan scores: Suspension0.43782350420951843,
Weather decisions intro0.03308597952127457, оба ниже frozen tau0.8670357465744019.
`reservations.md#Transfer` содержит explicit link к `weather.md#suspension` и
предупреждение, что transfer не изменяет suspension. Structural v2 по контракту
не расширяет anchor subtree автоматически. Поэтому link/transfer statement
не заменили required weather body/conditions в конечной выдаче.

`V-M1-offline-trace.json` сохраняет exact question, weather score rows/input hashes,
threshold, missing facts и closure receipt. Это score rejection/coverage failure
на реальном complete scan, не прежняя capability lifecycle ошибка и не overflow.
Не выполнялись counterfactual threshold search/prompt edits или дополнительные
forwards. Причин, почему модель дала именно такой score, по этим receipts не
выдумываем; наблюдаемая недостаточность final evidence установлена независимо.

## Полная работа и readonly

**2prepares,8queries,8resource reads,176forwards,75136 model-input tokens**.
1model load,7runtime-cache hits,0score-cache hits, lost traces0.
Counters независимо сверены суммированием8 scorer receipts.

- Forward time2.671420043s; scorer total10.658170435s.
- Process finally elapsed22.637281029s; summary elapsed22.637163401s.
  Это run-entry elapsed, не interpreter startup.
- Peak allocated1,220,989,952 bytes, reserved1,245,708,288 bytes.
- Per-query latency/tokens/VRAM, prepare latencies и actual source/rendered packet
  metrics сохранены в raw. Actual MCP wire/client/provider tokens не измерены.
- Оба project readonly audits: before/after source+catalog hashes, logical SQLite
  digest и model asset/provenance hashes совпали, trace complete. Полные maps в
  `validation/*/readonly.json`, не только bool. Resource reads/replay не убирались.

## Review boundary

Это **public in-process synthetic validation FAIL**. Успешный recovery остаётся
предыдущим отдельным результатом; он не делает этот validation PASS. Нет installed,
real-project, real-client/provider-token proof. Все originals/questions/labels/
recipe/policy исторические результаты сохранены. Следующий этап не запускался;
ожидается parent review failure без автоматического продолжения.
