# PR #211: точная диагностика recovery read-state failure

Статус: report-only diagnostic slice; read-only guard и production не меняются.
Base `scripts/run_recovery_contract_gate.py`: `31abc4d4d10d91831f714f79a5537a3e67806ac5` на `0855fb491ec388100cce92e57fe64b889c4cd3e0`.

## Actual результат

В обычном [CI run 37996655986 / advanced job 114044351234](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114044351234)
прежние 11 recovery cases прошли; новый `closed_literal_context` завершился failure с guard `recovery_closed_context_is_read_only`.
Итог baseline 11 passed / 1 failure / 0 errors.
Recovery mutation gate правильно отказался считать kills, потому что baseline ещё не полностью зелёный.
Runtime/импорт crash не был причиной этого результата.

Отдельный P1.4 на том же SHA уже показал 9/14, discovery 5/10, complete fact 4/5, errors 0;
две целевые behavior cases прошли, все 14 READ_STATE сравнения совпали.
Эти результаты не заменяют recovery baseline и не доказывают весь путь холодного service materialization.

## Что пока не было видно

Старый recovery log печатает только имя case и guard.
Нельзя восстановить из него номер/вопрос failing read либо поле изменившегося состояния.
Полный capture остаётся в сохранённом report, но сам прежний detail не включал state_before/after.

Статически найдена отдельная возможная причина:
`LocalMemberService.materialize` создаёт `LibraryDocsService`,
который eagerly строит `LibraryRegistry` и `DocsJobTracker` на том же SQLite target.
`LibraryRegistry._ensure_schema` создаёт doc_libraries/index;
`SQLiteDocsJobStore._migrate` создаёт job tables и обновляет schema version,
а tracker выполняет interrupt/prune.
Cold member preparation не создаёт эти registry/job tables.

В P1.4 fixture materialize находится до before-hash; в новом recovery case первый public call находится после before-hash.
Это source-based объяснение возможного расхождения, а не уже наблюдавшийся конкретный SQLite diff.
Нужно увидеть новый diagnostic log. Никакого warming или переноса проверки за initialization этот slice не делает.

## Изменение

Прежняя state tuple представлена именованным dict из тех же четырёх значений:
generation, store_sha256, document_sha256, catalog_sha256.
Порядок фактических чтений сохраняется: generation, SQLite, документ, catalog.
Before и after по-прежнему читаются ровно по одному разу на public call.

Только при неравенстве печатается `RECOVERY_READ_STATE`:
case, ordinal read number, исходный вопрос, selected source path и список реально изменившихся полей с before/after.
В log попадают generation ids и SHA-256; source body/secret values не печатаются.

Исходный `after == before` guard остаётся обязательным с тем же именем.
Public call, fixtures, frozen inputs, case roster, mutable-source steps, report verifier, assertion detail и verdict не меняются.
Ни один failed baseline не объявляется пройденным.

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| scripts/run_recovery_contract_gate.py | 31abc4d4d10d91831f714f79a5537a3e67806ac5 | 20ddd043865ae32b33d02147b11899bde9ffbc5a | 100755 |

После static review нужен обычный recovery job на новом SHA и причинное исправление подтверждённого diff.
Локальные runtime/imports/pytest/subprocesses не выполнялись.
