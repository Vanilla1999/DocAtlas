# PR #211 — выполнение самостоятельных downstream gates

Дата: 2026-10-08. Автор: root. База:
`f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`.

## Проблема и точный diff

В [CI 37819292857](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292857)
advanced pytest завершился с 524 PASS / 98 FAIL. Все десять substantive downstream
steps оказались SKIPPED. Поэтому этот run не проверил их фактические gates.

В `.github/workflows/ci.yml` добавлены только два step IDs и десять условий `if`.
Команды, selectors, dependencies, порядок, timeout, permissions, artifact uploads,
thresholds, exit codes и required-ci aggregation сохранены. После обратного удаления
этих 12 строк файл побайтно равен f0. `continue-on-error` и успешные catch не добавлены.

Девять самостоятельных checks требуют:

```yaml
if: ${{ !cancelled() && steps.advanced_dependencies.outcome == 'success' }}
```

Это recovery contract/mutation, hermetic chat, legacy live report+lineage,
V2 acceptance, question surface, Agent Developer, full adversarial/token и critical
mutation. Install step по-прежнему выполняет прежний `pip install -e ".[dev]"`.
Провал advanced pytest больше не скрывает эти самостоятельные результаты.

У adversarial mutation дополнительно сохранён обязательный зелёный полный baseline:

```yaml
if: ${{ !cancelled() && steps.advanced_dependencies.outcome == 'success' && steps.agent_adversarial.outcome == 'success' }}
```

Его script сам проверяет baseline только через SELF_TEST, но три мутанта запускают
FULL_GATE и считают nonzero результатом KILLED. Без внешнего green full baseline
обычная исходная ошибка setup могла бы ложно засчитываться как смерть мутанта.
Поэтому при красном full adversarial этот dependent mutation останется SKIPPED.

Recovery mutation имеет собственный обязательный baseline до source edits.
Critical mutation требует свой зелёный трёх-node baseline с валидным JUnit и
отличает assertion failure от runtime/collection errors. Их существующие guards
не удалены. Legacy report и его lineage check остаются одной shell-командой
с прежним fail-fast порядком.

[GitHub expression reference](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)
подтверждает, что явный status-check function управляет выполнением после failure;
`!cancelled()` сохраняет отмену workflow. Используется `outcome`, без преобразования
исходного nonzero в success. Красный advanced pytest продолжает делать весь job и
обязательный CI красными, даже если другие checks пройдут.

## Scope реального исполнения

До patch отдельно прочитаны entrypoints и их call graph:

- Recovery, Agent Developer и adversarial checks используют authored local fixtures,
  temporary home/SQLite и local non-vector calls.
- `--live` в legacy/V2 quality commands вызывает собственный in-process self-host
  runner: чтение текущего reviewed CI checkout и temporary index/extracted paths.
  Здесь нет live provider или application client. Lexical configuration и
  `with_vectors=False` сохранены. `DOCATLAS_OFFLINE` не объявляется самостоятельным
  сетевым sandbox; вывод основан на конкретных entrypoints.
- Mutation runners используют временные копии либо ephemeral CI checkout.
  Recovery mutation восстанавливает изменённые source files в `finally`; порядок
  остаётся последовательным. При cancellation следующие gates не запускаются.
- Новых package/model downloads, network/provider calls, user-index операций,
  Git pushes или публикации сообщений этот diff не добавляет.

Запуск этих уже предусмотренных gates нужен для запрошенного совместного acceptance.
Изменена только зависимость исполнения от несвязанного общего pytest. Реальные
script prerequisites сохранены. Существующие legacy sync fixtures могут дать
PermissionError; эти failures должны проявиться и не считаются PASS.

## Verification и границы

Reviewed workflow SHA256:
`b8812ad66fc739900bcb1de07eda3cebc90567ec07363c5953e4beafeed29f40`.

Автор проверил exact 12-line diff, reverse-removal byte equality и
`git diff --check`. Локально workflows/scripts/runtime не исполнялись;
результаты нового CI пока NOT RUN. Нужен independent exact-diff review.

Frozen gold, retrieval 800-token gate, required-ci `needs` и критерий success
advanced-contract не менялись. Общий результат остаётся FAIL при любом необходимом
провале. Инструментирование даёт фактические результаты дополнительных gates,
но само по себе не закрывает эти gates и не делает PR готовым к merge.
