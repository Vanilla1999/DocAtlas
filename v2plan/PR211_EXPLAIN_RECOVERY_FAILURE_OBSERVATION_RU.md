# PR211: фактический отказ Explain и диагностика существующего capture

## Подтверждённый результат

На PR HEAD `f7b9253c8e477babf276ae8dd2cb18905451cd15`
[advanced job 114082885405](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114082885405)
recovery baseline завершился **11 PASS / 1 FAIL / 0 ERROR**.
Отказ `closed_literal_context` имеет guard `recovery_explain_literal_source_fact`.
Mutation runner отдельно отверг неполностью успешную baseline; **23 intended kills
на этом SHA не подтверждены**.

Stdout показывает guard, но не capture отказавшего positive. Полный
`ContractFailure.detail` сохраняется в JSON report. Этот report из binary artifact
в данной сессии не прочитан, поэтому конкретный positive index и этап потери
факта пока не объявлены доказанными. Из общего marker нельзя заключить, что
сломался parser, retrieval, literal admission или финальная delivery.

## Узкое изменение

База `scripts/run_recovery_contract_gate.py` —
`342fc84bea32b0ab69219c01155d83931e3d71c4`, mode **100755**.
Новый blob `a8e9c5b0c0588e281eec7532ac5016f3aaaeb6be`.

- Failure detail существующей positive-проверки получает неизменный capture,
  порядковый номер positive/read, ожидаемые path/literal и SHA-256 полного
  уже заданного body. Это данные fixture, не новый runtime или input producer.
- Обработчик того же `ContractFailure` печатает одну строку
  `RECOVERY_FAILURE` из уже имеющихся request/public/projector records.
- Вывод включает статусы и reason codes, actual candidate/projected/snapshot
  IDs, paths и window hashes, original qualification trace, literal admissions
  и projection rejections. Текст snippet, raw document, owner и полный payload
  не печатаются.
- Основные ряды candidates, sources, projection attempts и delivery inputs
  ограничены 16 элементами; fixture/query identifiers сохраняются как записаны.
  Для candidates, public sources и projection attempts сохранены полные количества. Полный
  исходный JSON report остаётся прежним по механизму сохранения.
- Ошибка самого printer явно обозначается `diagnostic_error`, не меняя
  исходный failure, guard, report outcome и ненулевой exit code.

Количество вызовов product/retrieval/projector/validator не увеличивается.
12 case names, все исходные questions/bodies, expected facts, read-only
fingerprints, guards и порядок выполнения сохраняются. Production, corpus,
gold, scoring, mutation list и критерии baseline/kills не меняются.

## Проверка и следующий шаг

Pure text inverse вставки helper, diagnostic call и расширения detail
восстанавливает base побайтно. GitHub blob roundtrip точный; файл 992 строки.
Локальные Python/import/AST/pytest/runtime не исполнялись.

Новый CI должен снова честно проверить все 12 cases и вывести фактический
first-loss capture при отказе. Только по нему выбирается следующая узкая
поправка. Независимый static review readonly и root: APPROVE exact code
`a8e9c5b0c0588e281eec7532ac5016f3aaaeb6be`; нового runtime PASS пока нет.
