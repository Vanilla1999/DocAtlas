# Диагностика неизменённого bb81525d — STOP_INVALID

Общий verdict кандидата остаётся **REJECTED на N10**. Эта попытка не acceptance
rerun. Часть II, I.4, G, full suite и release gates не запускались.

## Baseline и protocol

Branch `next07-feasibility-audit`, HEAD `bb81525d`. До public calls сохранены
`protocol.json` (hashes candidate/wiring/runner/ports/frozen inputs, source manifest,
80-case corpus bytes hashes, порядок controls и правила остановки),
`baseline.patch`, `baseline-status.txt`. По завершении hashes совпали.
Candidate/wiring/packer/guards/fixtures/expectations/policy-delta не менялись.
Изменение только diagnostic runner `v2plan/next07_diagnostic_scope.py` и evidence.

Command: `DOCATLAS_OFFLINE=1 .venv/bin/python -m v2plan.next07_diagnostic_scope
--out v2plan/artifacts/next07/grounded-first/diagnostic-bb81525d-20261004`.
Exit **1**, stdout/stderr `command.log`; результаты `result.json`.

## Фактически выполнено

1. Working positive из существующего read-boundary fixture: свежие N/C public
   calls, C доставил `storage retention behavior is documented in this current
   guide.` вместе с owner. Capture, snapshot и trace сохранены. Это не replay
   historical claim и ему не присваивается выдуманный claim ID.
2. Попытка N1 module control: runner ошибочно передал `module` в MCP request.
   Настоящий public dispatcher вернул `validation_error`:
   `unknown field(s) for get_docs_context: module`.
   Ошибка возникает **до handler**, projection не reached, trace exceptions
   отсутствуют. N получил ту же schema error. Hooks восстановлены.

Это **ошибка диагностического harness**, не source guard PASS, не candidate
quality failure и не доказательство невозможности диагностики без правок wiring.
Неподдержанный wiring scope `all` обнаружен чтением кода, но public replay его
не запускал; его результаты не подменяются предположением.
По прямому правилу пользователя stop при technical invalid execution сбор
остановлен, без исправлений и повторов внутри этого запуска.

## Запрошенные результаты и ограничения

| Измерение | Статус |
|---|---|
| Доставленные/потерянные frozen claim IDs | NOT_RUN, paired 80 не выполнен |
| Historical 49 ID ledger / partial retention | NOT_RUN, ledger не оценивался |
| Лишние packets | Новое корпусное измерение NOT_RUN; прежний N10 irrelevant context остаётся FAIL |
| Source/condition/span/budget violations | Корпус NOT_RUN; schema error не является таким нарушением |
| Первая стадия потери прежних фактов | NOT_RUN, факт потери не установлен |
| N1 module guard | INVALID: schema validation до handler |
| Остальные controls | NOT_RUN после technical STOP |
| Изоляция | Hooks restored; frozen input/code hashes совпали |

Неполученные множества IDs не выдаются за пустые retained/lost sets. Масштаб
quality проблем этим остановленным замером **не определён**. Verdict не повышен.
Rollout: **NOT_AUTHORIZED**.
