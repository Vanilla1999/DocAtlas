# R3/R4 — public preflight checkpoint, НЕ freeze

## Исправления

`docmancer/docs/application/minimal_context_selection.py`: observer work receipt
записывается сразу после scorer, до selected-set/closure/rebuild; failed scorer
receipt — в exception handler. Один observation, затем к нему добавляются scores
только при активном observer. `delivery_status=not_confirmed` до успешного
завершения finalization. Не менялись inputs, threshold/selection, protocol packet.

Static control-flow review R3:

| Граница | Доступный учёт |
|---|---|
| scorer completed → selected/closure error | уже сохранён completed work receipt |
| scorer JointSemanticRelevanceError | receipt сохранён до stop_packet |
| _rebuild/terminal validation/emergency stop | тот же observation, без повторного count |
| finalization exception | тот же work receipt, delivery не подтверждена |
| unsupported interruption без receipt | evaluator lost_trace_unknown_work; totals неполны |
| observer OFF | record_work не создаёт observation/extra score traces |

Искусственных exceptions/monkeypatch tests не было. Late-failure branches
проверены control-flow review, а не заявлены как runtime failure injection proof.

`step10-multidoc-gate/runner.py`: attempts prepare/query/resource считаются до
вызовов, query work receipts/counters сохраняются в finally, raw resource response
сохраняется до JSON parsing. Missing/duplicate trace явно делает totals неполными,
а не доказывает0. Новый локальный evaluator `readonly_audit` сохраняет фактические
before/after source+catalog hashes, logical SQLite digest, asset/provenance hashes
и errors даже при failure. Никакого global logging framework/DB copy.

## Разрешённый runtime — один запуск, без retries

Driver: `diagnostic.py` здесь. Только `DOCUMENTS/QUESTION` из
`probe_minimal_structure.py`, плюс отдельная oversized copy с5000 повторениями
обычного procedural sentence. Исходный fixture не изменялся. Gate datasets и T01
не импортировались/не запускались.2prepares+3queries,0resource reads.

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-qwen-public-preflight.diagnostic --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-public-preflight-01
```

Raw byte-exact copy: `run-01/` (17 files), исходные artifacts остаются во внешнем
run directory. `receipt-audit.json` содержит hashes каждого raw файла и независимое
offline сравнение сохранённых before/after receipts с фактическими source copies.

| Query | forwards | actual model-input tokens | query seconds | forward seconds |
|---|---:|---:|---:|---:|
| OFF |8|3304|5.913651118|0.374598444|
| ON |8|3304|0.900528026|0.105510988|
| overflow |0|0|1.614894784|0|

Итого **16 forwards,6608 model-input tokens**,1 model load,2 loaded-runtime cache
hits,0 score cache hits. Initial two-pair smoke НЕ повторялся; cumulative со старым
smoke18 forwards/6797 tokens. Public diagnostic peak allocated1,217,832,448 bytes,
reserved1,245,708,288 bytes (оба parity calls). Overflow receipt не содержит
VRAM measurement: отдельный peak для него не заявляется; forward0 подтверждён.
Prepare latency и полный scorer total/verification/runtime находятся в raw JSON.
OFF wall time включает passive profiler overhead; это не perf comparison ON/OFF.

## Что доказано этим public boundary

- OFF/ON public packets совпали буквально, по8forwards/3304tokens. OFF diagnostic
  rows0/omitted8, ON recorded8. OFF passive profile удерживает только scalar
  receipt, не scores/prompts; scorer/retrieval/storage/validation не подменялись.
- Source spans/text/hash/scope/version/root identity проверены по исходным files.
  Empty heading, footnote definition owner+continued line, reference definition
  с destination на следующей строке сохранены. Private anchor остаётся explicit gap.
- Source/catalog hashes, logical SQLite digest и asset hashes до/после совпали
  для обоих isolated scenarios. Значения сохранены в `*/readonly.json`, не только bool.
- Oversized public query дошёл именно до scorer: `evidence_prompt_overflow:35263`,
  `scan_incomplete`,0forwards,0selected sources. Это не успешный no-answer/partial
  и не более ранний guard.35263 — полный первый oversized prompt после tokenization,
  НЕ actual model-input tokens (они0). Preflight aborted до первой completed unit.
- Полный public path прошёл с первой попытки, новых runtime bugs не обнаружено.
  R3 accounting defect исправлен; R4 evidence receipts добавлены. Проверка final
  audit trace completeness дополнительно усилена после run, без повторного runtime;
  offline receipt audit подтверждает все сохранённые значения независимо.

## Freeze-ready review

Предыдущий506-file candidate сохранён в
`../step10-multidoc-gate/history/review-candidate-before-r3-r4/`, SHA256 manifest:
`24749af395d3dbd7e39ab65f102ea83844eca9249441969611502b58959f7531`.
Новый manifest/contract в `../step10-multidoc-gate/`, status остаётся
`DRAFT_AWAITING_PARENT_REVIEW`. Model-input contract SHA256 неизменен:
`65dcde1445c86fe3d8245022e1b9db84f4c79cca4cd2ee868aa9d5234b863991`.
Gate sources/tasks/labels hashes неизменны, проверены относительно прошлого
review candidate. Public diagnostic sources находятся отдельно, не в gate.

Final bounded static receipt: `static-checks.json` здесь. Никаких unit/private
helper tests/full suite/Terra/L2. Parent-owned v2plan документы не редактировались.
Freeze/calibration/validation по-прежнему требуют review/разрешения. Этот keep-all
diagnostic не доказывает semantic sufficiency,50% reduction или32K forward runtime.
