# PR #211 — независимое review finite-membership fixtures

Дата: 2026-10-08. Reviewer: root, не автор slice. База:
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

## Решение

**APPROVE** для указанного test-only slice и обычного совместного CI.
Blocking findings не обнаружены. Это review корректности fixtures и сохранения
проверок; runtime изменённых tests ещё **NOT RUN**. Оно не означает, что все
затронутые failures закрыты или что PR готов к merge.

| Одобренный файл | SHA256 |
|---|---|
| `tests/docs/test_code_graph.py` | `fafe19b4e843573dfb5ea9e2b9bb8fd150c1c7ce2d13af0716259b4afb347332` |
| `tests/docs/test_source_map.py` | `6fd36d40f70f8eb2e7c485112e06875ea21674b9c133bcefb14bf04caa8b003e` |

## Независимая проверка контракта

Прочитаны diff обоих файлов, авторский отчёт, текущие
`SourceBoundary.from_project` / `iter_bounded_source_files`, source facts и
source-evidence producer, graph builder и bounded path traversal.

Finite `code_files` — явная декларация fixture, а не результат обхода проекта
или вывода из вопроса. `source_roots` только ограничивает эту декларацию.
Helpers записывают конкретные созданные исходники в test-owned project catalog;
25 имён в cap fixture получаются из того же конечного authored range, которым
создаются файлы. Production membership, source boundary и retrieval не меняются.

Positive controls сначала доказывают отсутствие source reads без membership,
затем проверяют реальные reads только объявленных файлов. Наблюдатель вызывает
исходный `Path.read_text`, сохраняет hash возвращённого UTF-8 текста и не меняет
его. Hash сопоставляется с заранее созданными bytes. Matching unlisted decoy
существует, но не читается. Пути, line bounds, полный однострочный snippet,
file metadata и graph references проверены против исходников, а не только
против другого поля того же DTO.

Negative controls не заменены отсутствием membership. Для generated, ignored,
excluded, runtime-artifact, outside-root и symlink members декларация содержит
реально запрещённый путь. Смешанная декларация отвергается целиком; representative
source observers доказывают отсутствие частичного read. Literal generated opt-in
проверен вместе с отказом строке `"true"`. Count, depth, file/scanned bytes и deadline
проверяются на существующих, явно объявленных исходниках.

Два дополнительных невакуозных assertion проверены по текущему producer:

- `absent_in_source` создаётся после разрешённого scan, если literal term не найден;
  оно сохраняет `confidence="unknown"` и не доказывает несуществование символа.
- Positive path на depth 2 опирается на настоящий string literal и import/reference
  edges. `_file_strings` читает `string_literals` независимо от пустого compatibility
  поля `status_like_tokens`; это не возвращение semantic status inference.

## Сохранение тестов и ограничений

Независимый stdlib AST audit сопоставил frozen df9 files с рабочими файлами:

| Проверка | code_graph | source_map |
|---|---:|---:|
| Старые test names, тот же порядок | 35/35 | 29/29 |
| Старые assert AST сохранены | 144/144 | 74/74 |
| Assert AST после slice | 160 | 103 |
| Удалённые assertions / test names | 0 / 0 | 0 / 0 |

Параметризация, skip/xfail и selectors не изменены; новые test nodes не добавлены.
`ast.parse`, компиляция AST без исполнения и `git diff --check`: PASS.
Замена runtime functions результата на stub не обнаружена.

Из сохранённого df9 Python 3.12 JUnit ledger независимо получены исходные totals:
code_graph — 13 PASS / 22 FAIL; source_map — 11 PASS / 18 FAIL. Эти числа относятся
к исходному выполненному CI. Они не являются прогнозом результата данного slice.

Сохранены спорные assertions и отдельные tests на Dart self-package identity,
prose generated opt-in, `status_like_tokens` и ranking/order. Их дальнейшее
расхождение должно остаться видимым в CI. Ни package identity, ни semantic status,
ни authority не выводятся из новой декларации. Deferred retrieval, frozen gold
и числовые ceilings не изменены.

Локально не запускались pytest, repository imports, providers, package installs
или client/runtime subprocesses. Следующий обязательный шаг — общий CI на одном
опубликованном SHA, сравнение полного node roster и прежних PASS cases.
