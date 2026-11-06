# Recovery run-01 — PASS, fresh-prepared public acceptance

Один разрешённый запуск, без retries/repair/fit. PASS определяется реальными
конечными packets и unchanged gates, а не exit0 или observer counters.
Исторический calibration ERROR_NOT_PASS и прежние predictions не изменены.
Validation/T01/installed/client/Terra/L2 не выполнялись; provider savings не измерялись.

## Команда / привязки

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-multidoc-gate.runner recovery --manifest /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery-entry/recovery-freeze-ready-manifest.json --recovery-authorization /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery-entry/parent-recovery-authorization.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-recovery-01
```

- Approved manifest SHA256:
  `2bcebef52ab6268e091f5e28de12acc8837988bff36c2068432e2a4b73ebe066`.
- Exact original policy SHA256:
  `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`.
  Threshold0.8670357465744019, не refitted.
- Real recovery summary SHA256:
  `93f8f93787c0c4a50a424d22295c2ed85a94df6cc73d7e349ef1ccde6da08604`.
- Все618 bound hashes повторно сверены после run и неизменны.

`run-01/` — byte-exact copy48raw files/529302bytes, SHA map `raw-sha256.json`.
Original runtime root `/tmp/opencode/step10-qwen-recovery-01` сохранён буквально
в receipts; repository copy не является новым prepared root.
`authorization.json`, `policy.json`, `summary.json`, `process-receipt.json`,
packets/observations/resource responses/read-only audits находятся в raw copy.

## Реальные final-policy outputs

| Query | Complete required units | Required fact quotes | Source tokens delivered/allowed | Hard negatives |
|---|---:|---:|---:|---:|
| C-T1 |5/5|7/7|250/742|0|
| C-T2 |3/3|6/6|113/742|0|
| C-T3 |3/3|5/5|135/742|0|
| C-T4 |no-answer|no-answer|0/742|0|
| C-L1 |3/3|6/6|135/682|0|
| C-L2 |5/5|8/8|149/682|0|
| C-L3 |5/5|8/8|179/682|0|
| C-L4 |no-answer|no-answer|0/682|0|

Итого24/24 required unit obligations и40/40 fact quotes calibration split.
Оба no-answer — empty successful **complete scans**, не ошибки/overflow.
Source-token denominator исключает no-answer queries, как frozen contract:
**961/4272**, reduction **77.50468165%**. Optional/unlabelled tokens включены.
Required/no-answer/hard-negative/reduction gates — все PASS.

`offline-packet-audit.json` содержит per-query exact fact quotes/delivered flags,
required/delivered unit keys, optional/unlabelled delivery, source token metrics,
no-answer/scan status. Это отдельная offline сверка final packet с original files/
labels: source text и spans буквально совпадают, content hashes/scope/version/
authority проверены; все required facts присутствуют. Source-token totals взяты
из reviewed runner с pinned codec; отдельного нового tokenizer не вводилось.

## Работа, расходы и read-only

**2public prepares,8final-policy queries,8resource reads**. Existing resource
read+replay checks выполнены сразу после первого answerable query каждого проекта.
Никаких8diagnostic queries и threshold-search/breakpoints.

- **176forwards,76022 actual Qwen input tokens**; independently summed raw receipts.
-1model load,7runtime-cache hits,0score-cache hits; lost trace0.
- Inference2.534988912s; scorer total10.533927946s.
- Process elapsed22.163166315s (finally receipt; run-entry to completion,
  без interpreter startup). Summary был записан чуть раньше:22.162638737s.
- Peak VRAM allocated1,221,184,512 bytes; reserved1,245,708,288 bytes.
- Per-query latency/runtime/costs в raw query receipts/results.json; per-project
  prepare latency в prepare.json. Wire/model-visible client tokens остаются null:
  это in-process public boundary, не client/provider measurement.

Оба `recovery/*/readonly.json` содержат полные before/after source+catalog hashes,
logical SQLite digest и assets/provenance hashes. Значения совпали, trace complete;
offline audit независимо сверил сохранённые before/after. Source/catalog и DB
не мутировали при query/read sequence; prepare отдельно является authorized mutation.

## Новые inputs, не exact historical replay

Сравнены176 own-body model inputs по source path/char spans:
**16 changed,160 equal,0missing**. По каждому TideGauge question3changed/18equal;
по каждому Loom question1changed/22equal. Полные old/new SHA256 в raw
`*-input-comparison.json`, historical files/hashes также указаны.

New public prepare создаёт новые roots/generation UUID. Incoming source identity
хеши меняют часть prompts; equality остальных inputs не превращает весь run в
exact replay. Никакого восстановления historical DB/generation или замены binding.
Совпадение aggregate961/4272 со старым offline fit prediction — наблюдение,
не критерий этого PASS. Критерий — нынешние final packets и unchanged obligations.

## Следующий шаг

Parent review summary/policy/raw. Никакой validation query до отдельного нового
authorization; recovery PASS сам по себе не разрешает следующий run. Никаких
новых tests/smoke, commit/push/delegation или изменений parent v2plan не было.
