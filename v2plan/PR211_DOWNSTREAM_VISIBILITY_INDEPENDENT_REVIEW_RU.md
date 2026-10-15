# PR #211 — independent review downstream visibility

Дата: 2026-10-08. Решение: **APPROVE** для exact workflow diff ниже.
Baseline: `f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`.
Reviewer не изменял workflow или исполняемые scripts и не запускал runtime.

## Проверенные bytes

| Файл / версия | SHA-256 |
| --- | --- |
| `.github/workflows/ci.yml`, f0 baseline | `499d9595af1d9348f238eed233c54042aa32f27b7ba346620a66ca65545a4b40` |
| `.github/workflows/ci.yml`, reviewed patch | `b8812ad66fc739900bcb1de07eda3cebc90567ec07363c5953e4beafeed29f40` |
| `v2plan/PR211_DOWNSTREAM_VISIBILITY_REVIEW_RU.md` | `bfa96bdbe1ac838911b40d104c8ab48068e3900feb32f6af79475d55b13096f7` |

Независимое stdlib сравнение подтвердило только **12 добавленных строк**, ноль
удалённых/заменённых. Все добавления находятся внутри `advanced-contract`:
два IDs, девять одинаковых независимых conditions и один dependent condition.
После удаления именно этих строк результат побайтно равен baseline.
`git diff --check`: PASS.

Значит команды, pytest selector, JUnit output, порядок, package install,
job timeout, permissions, uploads, остальные jobs, required-ci `needs` и
aggregate success predicate сохранены. `continue-on-error`, успешный catch,
новые thresholds или исключения test cases не добавлены.

## Условия стоят на правильных steps

`advanced_dependencies` назначен существующему install step внутри advanced job.
Его setup/checkout prerequisites остаются прежними. Для следующих девяти steps
проверено точное условие
`!cancelled() && steps.advanced_dependencies.outcome == 'success'`:

1. Recovery contract.
2. Recovery mutation.
3. Hermetic project chat.
4. Legacy live report и lineage floor в одном прежнем shell step.
5. V2 project-context acceptance.
6. Question surface.
7. Agent Developer Protocol.
8. Полный Agent Developer adversarial/token gate.
9. Critical mutation gate.

`agent_adversarial` назначен именно полному adversarial/token step, без
`--self-test`. Только следующий adversarial mutation step дополнительно требует
`steps.agent_adversarial.outcome == 'success'`.
При install failure или cancellation эти проверки не запускаются; при failure
самостоятельного gate другой самостоятельный gate может дать собственный outcome.

[GitHub expression reference](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)
подтверждает отмену implicit success-only поведения через явную status-check
function. Здесь `!cancelled()` не переводит предыдущий failure в success.
При красном advanced pytest или другом необходимом gate весь job остаётся
красным; неизменённый required-ci агрегатор требует success этого job.

## Сохранены реальные prerequisites mutation gates

Source grounding выполнен по entrypoints и их существующим baseline checks.
Все 17 ранее прочитанных supporting source files побайтно совпадают с f0;
код runners не меняется этим patch.

- `run_recovery_mutation_gate.py` сначала выполняет собственный полный recovery
  baseline и выходит с 1 до mutations, если baseline красный. Source edits идут
  последовательно и восстанавливаются в `finally`.
- `run_critical_mutation_gate.py` требует собственный зелёный baseline выбранных
  трёх pytest nodes с валидным JUnit. Mutant kill требует exit 1, реальные assertion
  failures, ненулевой case inventory и ноль runtime/collection errors.
- `run_agent_developer_adversarial_mutation_gate.py` проверяет внутренний baseline
  только через SELF_TEST, но три из девяти mutants выполняют FULL_GATE и принимают
  любой nonzero за KILLED. Поэтому green full adversarial prerequisite существенен.
  В exact patch он сохранён явно; исходный fixture failure не сможет сам по себе
  разрешить этот mutation step. Если baseline красный, его SKIP остаётся корректным
  blocked outcome, а не mutation PASS.

## Scope запуска и границы acceptance

Recovery и Agent Developer gates используют authored local fixtures и temporary
home/SQLite. Legacy/V2 `--live` вызывает собственный in-process self-host runner,
читает reviewed CI checkout и использует временные index/extracted paths;
это не установленный MCP client и не LLM provider run. Default lexical retrieval
и `with_vectors=False` сохранены. Один `DOCATLAS_OFFLINE` не объявляется общей
сетевой песочницей: вывод опирается на прочитанные targets и call graph.

Sequential ordering сохраняется, включая recovery mutation в ephemeral checkout.
Legacy report и lineage command остаются в одном step с прежними exit semantics.
Никакой из этих gate scripts не получает нового consent, source membership или
validation bypass. Существующие legacy sync setup failures должны остаться FAIL.
Frozen gold, retrieval 800-token gate и другие budgets не изменены.

Этот review подтверждает instrumentation и сохранение failure semantics.
Результаты нового workflow пока **NOT RUN**. Artifact upload success не заменяет
outcomes его producer gates; SKIP из-за собственного prerequisite, timeout или
cancellation не считается исполненной проверкой. Итоговый acceptance требует
фактического CI на опубликованном конечном SHA.
