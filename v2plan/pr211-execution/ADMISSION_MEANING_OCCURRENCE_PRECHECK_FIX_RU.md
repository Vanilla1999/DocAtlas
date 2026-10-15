# PR #211: occurrence-aware admission precheck fix

## Фактическая причина

На `c1e058cb51072f02620329000e2d68706a96bd67`, [CI run 37995500411](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411), attempt 1, [normal critical step](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411/job/114040357523) завершился `BASELINE FAILED` с exit 1. Девять normal critical mutants не запускались; успешного proof для retirement нет. Существующий runner сохранил `baseline.junit.xml` и stdout/stderr в артефакте, но вернулся до вывода JUnit evidence.

[Same-run JUnit reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411/job/114043788747) независимо показывает новый `test_current_admission_meaning_preserves_literals_without_inferred_equivalence`: 1 FAIL, сообщение `ValueError: too many values to unpack (expected 1)`. Старый `test_admission_meaning.py` остаётся 30 FAIL / 4 PASS. Все три Python имеют 6013 PASS / 1826 FAIL / 0 ERROR / 10 SKIP; `integrity_issues=[]`, `omitted_rows=0`.

## Контракт и исправление

В замороженном вопросе ``Can a handler for `for` be synchronous?`` два разных вхождения `for`: обычный connective занимает [14, 17), explicit quoted literal — [19, 22). Действующий occurrence-aware `query_mentions` сохраняет оба; quoted literal имеет `symbol_identity`/explicit, обычный connective остаётся unresolved/non-explicit. Это буквальное различие исходных координат, а не semantic grammar.

Precheck ошибочно выбирал reference только по равному text и требовал один результат. Теперь он выбирает quoted occurrence по заранее известным исходным координатам и отдельно проверяет, что обычный connective не стал explicit identity. Ожидаемые source bytes, hard_exact, full original need/unknown demand, все шесть quoted literals, QueueHub/queuehub, finite catalog guards и запрет semantic equivalence не изменены. Production compiler/resolver не меняются.

Техническое объяснение неоднозначности установлено по [current resolver](https://github.com/Vanilla1999/DocAtlas/blob/c1e058cb51072f02620329000e2d68706a96bd67/docmancer/docs/domain/query_reference_binding.py) и замороженному input; компактный reader сообщает тип ошибки, а не строку traceback.

## Диагностика существующего baseline

Отдельная узкая правка runner читает уже созданный JUnit только в существующей ветви `baseline.returncode != 0`. Она печатает counts и первые три неуспешных node/outcome/message, с ограниченными полями и только первой строкой message attribute. Тело failure, traceback, stdout и stderr не печатаются. Если JUnit отсутствует или повреждён, выводится тип ошибки чтения; baseline по-прежнему завершается с exit 1.

Нет нового subprocess, rerun, изменения selectors, expected case counts, production mutants, named guards, mutation credit или literal-comparison режима. Неуспешный baseline не получает `validated` evidence и не разрешает retirement.

## Сохранение и acceptance

- Старые 9 definitions / 34 cases остаются collected; четыре живых guards не меняются.
- Архив `87434b28d5460eae97f7d59ed763e4a8a65aadbf`, frozen crosswalk/roster и diagnostic labels не меняются.
- Новый precheck остаётся одной test definition / одним pytest node. Это исправление oracle, а не сокращение тестов.
- Для retirement по-прежнему нужны фактические 31 PASS / 0 FAIL / 0 ERROR / 0 SKIP normal baseline и девять адресных kills, включая `admission_meaning_no_inferred_equivalence` с guard `critical_admission_meaning_no_inferred_equivalence` и 1 FAIL / 0 ERROR / 0 SKIP.
- Локальное исполнение не выполнялось. Статический review не заменяет следующий CI proof.
