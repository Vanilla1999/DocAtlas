# PR #211: сначала конкретные critical/recovery operands, затем большие ledgers

## Статус и actual основание

Это diagnostic-only изменение чтения уже сохранённых artifacts. Оно не запускает
pytest, продукт, providers, новые jobs или повторный evaluator и не меняет gate verdict.

Проверяемая база — опубликованный пакет 118:

- PR HEAD: `cadeef515ea78c78338821f38b15fed3bde7c993`.
- Merge checkout: `9f25f147c522d84f61a57abb1d731d2b6e792c9a`.
- Tree: `62d727c3ffbb35e77f0301d0e961e6f60ed4ebe2`.
- [CI run 38019193867](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867).
- [Advanced job 114116175443](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867/job/114116175443):
  actual step 15 `Run critical mutation gate` завершился SUCCESS.
- [Acceptance reader 114118025694](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867/job/114118025694):
  root прочитал healthy critical baseline 54/0/0/0, но console omitted 77 из 128
  выбранных artifact records. Индивидуальные 29 mutant operands в этом
  ограниченном выводе не были получены.

Metadata run/head/event и actual step SUCCESS дополнительно проверены GitHub API.
Счётчики 54 и 77/128 выше — результаты чтения root, не запуск этой правки.
Прямой SUCCESS старого producer подтверждает aggregate gate; он не заменяет
непрочитанные индивидуальные before/after/import hashes в retirement crosswalk.
DQP33 остаётся pending до четырёх собственных actual named mutation receipts.

## Что меняется

| Вывод | Содержимое и источник |
| --- | --- |
| `CRITICAL_OPERANDS` | Исходный artifact path/SHA/bytes; run, validated, returncode; JUnit counts/roster; actual nonpassing cases и первые строки их сообщений; mutation name/path/anchor/before/after/killer/expected failures/guard. |
| `import_origin` внутри critical | Соседний уже сохранённый `import-origin.stdout.log`: SHA/bytes, число parsed rows, module/path/hash. Для baseline — весь список; для mutant — ровно строка его объявленного production module. |
| `RECOVERY_OPERANDS` | Report path/SHA/bytes, counts, case id/outcome/guard/error type и первая строка сообщения. Большая повторяемая таблица `modules` остаётся только в исходном full record. |
| `JUNIT_TRACKED` | Один существующий lossless module и точные outcomes двух его controls: API case + три parametrized list/table/code cases. |

Порядок: critical operands → recovery operands → существующие компактные V2
operands → все прежние полные selected records. Старые records не удалены,
не пересчитаны и не заменены summary. Полный diagnostic artifact сохраняет
оба представления; исходные uploaded reports остаются неизменными.

Число evidence receipts не захардкожено: на базе 118 это normal baseline + 29
mutants; после relation25 precheck ожидается baseline + 30, если новый gate
фактически пройдёт. Это ожидаемая конфигурация, не новый runtime PASS.
Так же читаются реально существующие recovery reports без обещания числа kills.

## Точная граница import receipt

Producer `scripts/run_critical_mutation_gate.py`, blob
`d6e04f2459e5407c335d55964c9404e3ac871e1a`, вызывает
`_assert_import_origins` отдельным subprocess до pytest. Его JSON содержит
реальные module/path/SHA rows; `_save_evidence` копирует этот stdout рядом с
`evidence.json`.

Поэтому вывод явно помечен
`separate_process_import_probe_not_pytest_same_process`.
Он не объявлен pytest same-process attestation и не доказывает live client delivery.

Текущий source roster содержит 42 module entries. Новый reader сохраняет все
полученные baseline rows, без прежнего общего list bound 32; число 42 не
навязывается будущим artifacts. Для mutant сохраняются actual selected row и
число не выбранных остальных rows, а SHA всего stdout связывает полный файл.
Все 29 текущих mutation paths присутствуют в прочитанном module roster.

Reader читает только literal sibling artifact file. Он не открывает production
paths из JSON, не импортирует найденные modules и не исполняет stdout.
Пустой, отсутствующий или malformed JSON, invalid row/hash, duplicate module
и отсутствующий/неоднозначный mutated module создают diagnostic issue. Они не
превращаются в успешную пустую проверку. Прежний exit 2 при issues сохранён.

## Сохранность и ограничения вывода

- Existing transport budget 384000 bytes и reserve 512 bytes сохранены.
  Это ограничение диагностической консоли, не потолок product output.
- В priority records не копируются source bodies, tracebacks или mutation
  `old/new` code. Собственная первая строка failure message сохраняется;
  длинная строка получает prefix, число characters и SHA через существующий
  bound 512.
- Все реальные baseline module rows и failure/case rows сохраняются в summary.
  Summary уже ограничивает scalar values и не проходит повторное list32
  преобразование. При нехватке общего console budget final receipt сообщает
  и общий omitted count, и отдельные critical/recovery omitted counts.
- Existing V2 focused functions, full-record extraction, quality scorers,
  corpus, thresholds, runtime calls, required CI wiring и historical reports
  не меняются.

## JUnit successor scope

В `tests/docs/test_docs_lossless_context_projection.py`
`d2f12bbed978a4efe2fb5ff83718880f8137aa91` сохраняются:

- `test_context_budget_uses_explicit_optional_output_limits`: 1 case.
- `test_four_distinct_qualified_lanes_survive_without_source_fit_gate`:
  3 cases, list/table/code.

Reader добавляет только module name и эти два имени в существующий node filter.
Он читает уже готовый XML каждой Python lane, сохраняя artifact file/XML SHA,
не запускает эти tests и не выводит четыре PASS из module aggregate.
Это получение baseline operands; необходимые directed cap faults остаются
отдельным обязательством перед условным budget retirement.

## Exact manifest и static validation

| Путь | Mode | Base blob | Reviewed blob |
| --- | --- | --- | --- |
| scripts/summarize_acceptance_artifacts.py | 100644 | 8aad117f4cb0734d00deaff12fb90383aedcd164 | 2378d40b543ebdc1835dfc9b9654850203bbdbdb |
| scripts/summarize_pytest_acceptance.py | 100644 | 5b98d9d29364413966c334f43383d44a0f0f20aa | 66f3951b16b906995e82e60432b921b2125f0c03 |

SHA-256:

- Acceptance reader: `5c45470648b1d95a3bdb9863daf7671a5b0bb7220c8fabdcf02cbcff1aa3ae97`; 31316 UTF-8 bytes.
- JUnit reader: `c90d67f4f903a2d50aedf93fd3f6f167368cbdfed52adcc5163c9d3f08a5a7fa`; 10018 UTF-8 bytes.

Оба blob roundtrip побайтно exact. Inverse ровно внесённых helper/read/order/
counter изменений восстанавливает полный acceptance reader 8aad117f;
удаление трёх добавленных JUnit строк восстанавливает полный 5b98d9d.
Все старые focused helper bodies и исходные full records сохранены.

Root независимо прочитал оба exact source blobs и дал static APPROVE.
Новый Python syntax/runtime здесь не запускался; новые output records и
будущие individual mutant receipts ещё pending обычного следующего CI.
