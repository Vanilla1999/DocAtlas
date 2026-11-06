# Recovery entry — review candidate, inference не выполнялся

Единственный изменённый ранее bound файл:
`eval/blind_project_context/step10-multidoc-gate/runner.py`.
BEFORE bytes/hash: `history/runner-before.py`, `history/sha256.json`.
Diff относительно reviewed capability repair: `runner.patch`.
Production/scorer/runtime core pins/recipe/threshold/fixtures не изменены.
Старые approved manifest, repair-manifest.json и все historical receipts сохранены.

## Entry и authority

Новая ветка `command=recovery` переиспользует существующие `phase`, `packet_check`,
`gates`, read-only/counters и resource checks в тех же местах. Никакого нового
evaluator или вызова fitter. Требуются одновременно:

1. Новый manifest в status `FROZEN_APPROVED_FOR_INFERENCE`, прошедший current-file
   hash verification. Сейчас новый файл **DRAFT_AWAITING_PARENT_REVIEW**.
2. Exact original policy из `step10-qwen-calibration/run-01/policy.json`, SHA256
   `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`,
   tau0.8670357465744019. В output сохраняется byte-exact copy, не новая policy.
   Её historical calibration_sha256 остаётся прежним, не подменяется new manifest.
3. Prior failure остаётся ERROR_NOT_PASS. Его hash привязан в manifest.recovery.
   Historical calibration PASS не требуется и не фабрикуется.
4. Отдельный parent recovery authorization JSON (сейчас НЕ создан):

```json
{
  "status": "PARENT_APPROVED_RECOVERY",
  "manifest_sha256": "SHA256 нового manifest ПОСЛЕ parent approval",
  "policy_sha256": "16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11",
  "prior_failure_sha256": "значение recovery.prior_failure_sha256 в manifest"
}
```

Authorization проверяется до любых public prepares/queries. Missing approval
не вызывает product/model calls. Этот документ не является authorization.

## Run contract

2 public prepares,8 calibration queries только final-policy. Resource reads —
existing first/last source + replay сразу после первого nonempty packet каждого
проекта, не переносились в конец. Больше нет запроса equality selected sets со
старыми offline predictions. Required complete units/facts/noanswer/hardnegative/
source provenance/read-only и summed source-token reduction>=50% неизменны.
Успешный recovery требует ровно8 final records и PASS всех existing gates.
Quality FAIL не запускает fit или retry. Runtime error сохраняет work receipts,
attempted counts/failure и process receipt.

Fresh public prepare создаёт новый root/generation. Историческая TemporaryDirectory
DB удалена; ручного восстановления UUID/binding нет. Old/new token hashes
сравниваются по `(source path,char_start,body_char_start,char_end)` для каждого
вопроса в `*-input-comparison.json`; old input берётся из8 сохранённых diagnostic
observations calibration run-01, которые относятся к тому же semantic scorer,
но прежнему native identity. Missing hash записывается null/equal=null, не equality.
Сравнение выполняется после raw work/counters persistence, вне production calls,
не служит admission/fit/quality oracle. Все исходные files сравнения pinned новым
manifest. Changed input hashes ожидаемы, но не маскируют утрату обязательных facts.

Summary `phase=recovery`, boundary:
`public in-process fresh-prepared recovery acceptance, not exact historical replay/validation/installed/client`.
Actual MCP wire/client tokens остаются null; source/rendered/Qwen tokens отдельно.
`process_total_seconds` в summary и `process-receipt.json` измеряет время от входа
в `run()` (включая manifest verification, prepare, audit, fit-free evaluation),
но не interpreter startup/import до run. Finally receipt есть и при runtime error
в execution block; отказ manifest до output creation не создаёт run artifacts.

## Будущая validation compatibility — сейчас НЕ разрешена

`--calibration` может указывать каталог verified recovery PASS. Summary phase
допускает `calibration` либо `recovery`, new manifest hash должен совпасть.
Для recovery дополнительно проверяется exact original policy hash. Отдельное
`PARENT_APPROVED_VALIDATION` по-прежнему обязательно, с new manifest/policy hashes
и hash успешного recovery summary. Existing field `calibration_summary_sha256`
сохранён для совместимости, в recovery case означает hash его `summary.json`.
Никакого автоматического перехода recovery→validation. Эти8 validation queries
не оценивались и не запускались в этой задаче.

## Точная команда ПОСЛЕ approval (сейчас не выполнялась)

```sh
HF_HUB_OFFLINE=1 TMPDIR=/tmp/opencode /tmp/opencode/step10-qwen-gpu-py312/bin/python -m eval.blind_project_context.step10-multidoc-gate.runner recovery --manifest /tmp/opencode/step9-gap-resolution/eval/blind_project_context/step10-qwen-recovery-entry/recovery-freeze-ready-manifest.json --recovery-authorization /tmp/opencode/step10-qwen-recovery-authorization.json --model /tmp/opencode/step10-qwen-reranker-06b-assets --out /tmp/opencode/step10-qwen-recovery-01
```

Новый manifest связывает current repaired production+runner, неизменные gate
sources/tasks/labels/scoring contract, original policy/prior failure/all8 old input
receipts и successful lifecycle repair receipts. Old manifests bound как
historical bytes, не как рекурсивные current-code hash validators.
Связи previous approved87585... и reviewed repaircf794... явны.
Final static receipt `static-checks.json`: только syntax/import/whitespace/hash
invariants, никаких public diagnostics/legacy tests/model calls.
