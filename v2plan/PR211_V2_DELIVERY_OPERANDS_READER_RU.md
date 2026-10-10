# PR #211: компактные operands всех трёх V2 failures

## Фактическое ограничение наблюдения на 113

PR HEAD `441cdefd2b251d63f716bfa75b053413bbe09c76`;
merge checkout `ceea2571e9847a71515feda4e1e1441fafdede44`.

[Acceptance reader job](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263)
завершился успешно. Его декодированный log: **569005 UTF-8 bytes**,
SHA-256 `ad44754505bf41a660a8312924380d8989915f6cf776a0579ae84f45edbf0f59`.
Console receipt: **29 selected artifact records, 1 omitted row**.
Прочитаны два полных `V2_FOCUSED_STAGE`: cache-reset и architecture.
Третий, request-flow, не попал в console budget. Его operands **не получены из доступного console на 113**;
значения предыдущего checkout не подставляются.

Полный selected ledger уже записывался в artifact до console output.
Ограничение **384000 bytes** здесь относится только к транспортной диагностике.
Оно не задаёт лимит sources, evidence или ответа продукта.

## Изменение

Перед крупными существующими records reader выводит по одному компактному
`V2_DELIVERY_OPERANDS` для трёх focused case IDs; наличие и неоднозначность исходных
records сохраняются в record_counts/issues.
Запись содержит ссылку на artifact, его SHA-256/размер, case/request, stage
statuses, actual member/project/unified return counts, eligibility и trust,
а также сохранённые metadata окон: source/path/id, source class/scope,
spans и qualified-query IDs. Body в новый summary не копируется.

Вложенные списки читаются как обычные lists либо как существующая ограниченная
обёртка `{items: [...]}`. Значение `None` помечается
`observation: unavailable`; оно не превращается в наблюдённый ноль.
Сохраняются `observation_error`, исходные counts и omission markers.
Это важно для различения ошибки observer, пустого результата и пропуска данных.

Старые полные V2 records, shared formatter, исходные reports и complete
selected ledger остаются. Для новых уже обработанных summaries не применяется
повторная рекурсивная упаковка. Общий console budget и reserve 512 bytes
сохранены; если они всё же исчерпаны, reader продолжает явно считать omissions.

Постобработка двух фактически полученных JSON records в чистом JavaScript дала
**22447** и **20215 bytes** компактного содержимого. Это проверка данных,
не исполнение Python reader и не новый CI PASS. Третий record на 113 отсутствует
в доступном console, поэтому его размер здесь не заявляется. Новая очередность
даёт всем трём summary приоритет перед крупными qualification/window ledgers; её
фактический результат должен подтвердить следующий обычный CI.

## Review и границы

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| scripts/summarize_acceptance_artifacts.py | bc9ce82a80bbb7279f962a1d2587372c2975fe4f | 8aad117f4cb0734d00deaff12fb90383aedcd164 | 100644 |
| v2plan/PR211_V2_DELIVERY_OPERANDS_READER_RU.md | новый файл | этот документ | 100644 |

Proposed reader SHA-256:
`838655234a8e7ad1053f6a093de22ae35d9a11544356d3517641e76d1f094686`.
Code review root и независимого peer: **APPROVE**.
Добавлены три чистые функции summarization, приоритетная последовательность
records и один признак already-bounded. Нет новых test functions, CI jobs,
dependencies, product calls, scorer changes или mutation credit.
Gate по-прежнему читает результаты существующего CI; сам reader ничего
не переисполняет. Runtime нового reader и required CI на конечном SHA — **PENDING**.
