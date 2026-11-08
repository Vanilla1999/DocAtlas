# Attempt-02: только исправление capture clocks и десять оставшихся сессий

A/V-M1 и B/V-M1 **не повторяются**. Их original receipts, accounting, raw captures,
`setup-complete.json`, `run-started.json` и run exception сохранены без изменения.
Новые `A/V-M1/accounting-clock-v2.json` и `B/V-M1/accounting-clock-v2.json` — отдельная
переинтерпретация capture. У B успешный transport/cleanup, фактический first-request
language hint и binding подтверждены; timestamp ordering **UNKNOWN**, не FAIL и
не PASS. Старый Python wall timestamp отсутствует и не восстанавливается.

Причина: Bun `process.hrtime.bigint()` process-relative; его эпоха несовместима
с Python `time.monotonic_ns()`. Новый `wall-v2` сохраняет оба исходных monotonic
значения только для локальных измерений, плюс Python `time.time_ns()` и JS
`Date.now()` для cross-process ordering. JS timestamp фиксируется в начале
provider hook до async body read. Сравнение требует полного status response
строго раньше начала millisecond bucket первого provider hook. Это wall-clock
наблюдение с миллисекундной точностью JS; коррекции системных часов не исключены,
remote arrival не измеряется. Остальные B требуют strict timing + hint/binding.

## Проверено без provider

`continuation.py seal` проверил pinned original setup SHA256, все unchanged inputs,
успешные receipts A/B, complete usage/capture, owned cleanup и GPU release,
source/member DB hashes и отсутствие started/runtime/capture у остальных десяти.
Node syntax также PASS. Четыре разрешённых изменения: `run.py`, `account.py`,
`observe_stdio.py`, `observer/index.js`; новый coordinator — `continuation.py`.
Остальные runtime/profile/config/policy/product inputs должны совпадать с setup.

Manifest содержит original/new input hashes, hash coordinator, hashes исходных
доказательств A/B и точный roster. `seal` не запускает provider; manifest уже создан.
Родителю следует review этих изменений и manifest перед командой ниже.

## Единственная команда продолжения после review

Из корня worktree:

```sh
/home/viadmin/.local/share/docatlas-eval/step14/venv/bin/python -B -I \
  eval/blind_project_context/step14-host-language-live/continuation.py run \
  --manifest-sha256 34cf80203ab975649bc312bab63d20d9865ce81831bc14c950fdb32a80bf81fb
```

Она повторно сверяет manifest и входы, создаёт отдельный
`attempt-02/continuation-started.json` и исполняет ровно:
`C/V-M1`, затем `A/B/C` для `V-M2`, `V-M3`, `V-M4`.
Старый `run-started.json` не перезаписывается. После первого старта continuation
повтор запрещён; при любой новой ошибке автоматического resume/retry нет.
Автор исправления эту команду не выполнял: новых provider/inference calls — 0.
