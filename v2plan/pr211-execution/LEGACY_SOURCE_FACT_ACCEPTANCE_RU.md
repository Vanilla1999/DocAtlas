# PR211: независимый Legacy oracle по исходным фактам

## Решение и граница

Рабочая база: `eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a`, tree
`6d75a3b5f019e94c11810364a7214b442b5829fa`.

ADR 0003 прямо разделяет полезность возвращённых фактов и producer query credit:
`docs/adr/0003-context-first-project-reads.md`, blob
`9ec7ca998294b171ea3e0e52972ffbdd673116dc`, строки 17–20 и 37–42.
Оригинальный вопрос и явные host lookups сохраняются. Lookup не даёт credit
оригиналу. Независимый evaluator проверяет неизменные вопросы и требуемые факты
по видимым источникам.

Это явная **версионированная смена acceptance-метрики** в рамках принятого ADR,
а не сохранение прежнего producer coverage-критерия под другим именем.
Новый blocking критерий — `verified_original_case_fact_count >= 12` из **15**
положительных исходных случаев. Случай засчитывается, только если **все полные
замороженные fact fragments** видны в содержательной части источника на точных
допустимых путях. Источник совпадает с validator snapshot того же вызова, hash
независимо пересчитан, project identity выведен из host-selected request root,
scope совпадает с project request, а полный snippet присутствует в заявленном
диапазоне строк текущего файла. Это оценка замороженного корпуса; она не означает
серверную сертификацию ответа или полноты смысла свободного вопроса.

`original_query_covered_count` остаётся исходной telemetry. Для неё остаются
отдельные проверки: literal original trace относится к этому же вопросу и
публичному источнику; host lookup, admission-only trace, изменённый origin или
унаследованный parent не могут дать original credit. Честное
`covered_query_ids=["query-lookup-1"]`,
`missing_query_ids=["query-original"]` совместимо с полезным source-bound фактом.

Число **12** не снижено. Оба frozen корпуса, protocol lock, original gold,
исторический подробный Legacy verdict и шесть hard-zero метрик сохраняются.
V2 thresholds и output-cost policy не меняются. Новый versioned crosswalk и его
SHA256 добавлены только в секцию Legacy acceptance lock.

## Наблюдение и независимая перепроверка

`run_project_docs_self_host_gate._call_with_snapshot` остаётся побайтно прежним.
Он уже наблюдает реальный вызов и сохраняет actual validator snapshot; возвращает
snapshot только при ровно одном retrieval и одном validation.
Новая запись не повторяет retrieval, validator, qualifier или scorer.

В `legacy_fact_evidence` копируются исходные question/scope/lookups/project_path,
наблюдённые call counts, точная `projected_source`, hash material из исходного
snapshot source и необходимые literal query trace поля. Пустые или отсутствующие
observations не заменяются успешными значениями.

Текущий hash-контракт определён в
`docmancer/docs/application/_model_visible_docs_support.py`, blob
`dd6795d83c8d863b12dd5e7d9ebe0712a19b2549`: SHA256 канонических
`path, section, content, snippet, version`.
Его JSON-формат — UTF-8, `ensure_ascii=False`, сортированные ключи и separators
`(",", ":")`; production helper `canonical_projection_bytes` остаётся прежним.
Oracle самостоятельно хеширует сохранённые материалы и проверяет source path,
section/version, полную публичную строку и текущий source text. Полный видимый
snippet не нормализуется для source-byte проверки. Сопоставление frozen fact
fragments сохраняет прежний case-insensitive substring контракт.

Новый oracle отдельно проверяет метаданные, которые не входят в пятиключевой
content hash. Expected owner не берётся из candidate или projected snapshot:
`local:` + SHA256 UTF-8 `str(Path(captured_request.project_path))` вычисляется
из host-selected абсолютного root без `..`. Это точный текущий контракт
`docmancer/docs/application/project_docs_member_transaction.py`, blob
`18e979c12769662c3a69376ed1c52a5f06cb6378`, строки 92–96. Mirror после запуска
может быть удалён: identity связывается с captured host root, а body bytes —
с исходным checkout. Эти два root намеренно не приравниваются.
Public `scope` должен быть `project`, как frozen case и реальный request.

Public `line_start`/`line_end` должны быть строгими int, без принятия bool или
числовых строк, и попадать внутрь текущего UTF-8 файла. Конец равен началу плюс
точное число переводов строки в snippet; полный snippet обязан содержаться в соответствующем
line window. Расширение диапазона, сдвиг на другую строку или текст в другой
части того же файла не дают credit. Char spans отсутствуют в текущем public DTO
и не выдумываются. Пустой negative source inventory не требует координат.

Сам факт ищется только в substantive body. ATX/Setext headings, standalone
link/image/reference, URL/link destination и table headers исключены именно в
месте факта; соседняя содержательная фраза не легализует заголовок или image alt.
Метаданные маскируются без склейки соседних букв, чтобы обработка не создала новый
fact substring. Native fenced code, команды в обычном тексте и data rows таблицы
остаются полезным body. Raw visible snippet и hash material при этом сохраняются
полностью. Это независимый oracle по frozen фактам, не вызов production qualifier.

`eval.project_context_quality_protocol.run_live` добавляет отдельный summary
только для Legacy `question_with_lookups`, перед итоговым report digest.
Natural/paraphrases/question-only ветки не меняются. Checker повторно читает frozen
corpus, проверяет точные 16 IDs/вопросы/lookups, пересчитывает 15 положительных
случаев из receipts и источников и сравнивает оба заявленных агрегата с результатом.
Готовые `fact_checks`, `passed`, рейтинги и raw original count не заменяют эту
проверку.

JSON receipt — наблюдение evaluator в том же CI, а не подписанная удалённая
аттестация. Проверка файлов использует текущий checkout. Proof runtime должен
относиться к этому же дереву; старые отчёты без новых receipts не получают
искусственно восстановленные поля. Installed/client/MCP transport acceptance
по-прежнему требует отдельного реального evidence.

## Сохранённые исходные данные

| Файл | Git blob | SHA256 исходных байтов |
| --- | --- | --- |
| `eval/project_context_quality/cases.json` | `43962d4d03f2bc6b0ceed498ef904730f113d2fb` | `b77ae44e8fb41bc53a6aa6cf584d886ee884ba337302285e4de9af2e4a5d829a` |
| `eval/project_context_quality/cases.legacy.json` | `43962d4d03f2bc6b0ceed498ef904730f113d2fb` | `b77ae44e8fb41bc53a6aa6cf584d886ee884ba337302285e4de9af2e4a5d829a` |
| `eval/project_context_quality/protocol.lock.json` | `71cc9674d2dd0d94d1fb29db7302003800043d19` | `58322c3af9cea3ebb74b76f7438d0abf677a4f98e94bd483550086bf4ac83516` |

Текущий acceptance-lock формат V2 v3 остаётся прежним; новая локальная секция
Legacy имеет `schema_version="legacy-source-fact-acceptance-v2"`.
Её crosswalk имеет собственную версию и SHA256
`07a0baf63be159d1ba8dc6c8595d3b01bc1d2bb209fff781bb635223b5a74cec`.
Checker сверяет числовой floor с неизменным `original_query_coverage_min=12`
из frozen protocol; это явная миграция смысла acceptance, не переименование
raw telemetry.

## Компактные controls

Новые ordinary test functions не добавлены. В acceptance-модуле остаются
**5 definitions / 5 cases**. Один прежний Legacy test содержит здоровые
независимо заданные конфигурации:

- 12 полных source-bound случаев, context-only результат и raw original=0;
- те же 12 случаев плюс отдельный literal original trace с собственным raw credit;
- captured mirror root, которого уже нет на диске и который отличается от root
  проверяемых исходных файлов;
- три полных source/hash/line-bound окна с фактом: statement с inline command,
  native fenced command и содержательная data row таблицы.

Это авторские временные файлы для проверки evaluator. Они не участвуют в live
retrieval и не изменяют настоящий gold или документацию проекта. Hash первого
источника независимо зафиксирован как
`0180c2e1aea9e5c3960e140171879049dac9507516f299c7e75d532da7ee7c9f`.

Из здорового baseline в том же существующем test проверяются: честная потеря
одного полного факта при неизменной source fidelity; корректно перепривязанный
путь `wiki/Commands.md.shadow`; forged hash при одинаковых public/snapshot rows;
подмена видимого snippet; lookup-to-original transfer; admission-only/origin/parent
подмены; два forged rollups; неправильный call count; изменённый original request;
неполный roster; ложная answer authority; неверная negative abstention и каждая
из шести прежних hard-zero метрик. Проверки требуют конкретные named причины,
чтобы случайный другой отказ не считался доказательством нужного guard.

После peer/root review добавлены два независимых класса counterfactuals:
**11** metadata-only окон с полными согласованными source/hash/line bindings,
соседними unrelated body и `metadata_only_evidence_count=0`; **10** согласованных
public/snapshot подмен владельца, scope и line coordinates при прежнем content hash
и всех hard-zero rollups=0. Первые обязаны терять fact credit и достигать
`legacy_fact_floor`; вторые — конкретного owner/scope/line guard. Отдельно проверены
относительный host root и root с `..`. Эти controls закрывают обнаруженные review
пробелы; ранее согласованный source digest сам по себе их не покрывал.

В protocol-модуле сохраняются **14 definitions / 21 expanded cases**, включая
прежние три compound-fact snippets. В том же test дополнительно проверяется
точный copied request и отсутствие выдуманных counts/source bindings при пустом
наблюдении.

Shared critical mutation runner и его corpus не меняются. Эти counterfactual
report faults не объявляются новыми production mutation kills. Actual выполнение
existing tests и нового live oracle требуется после публикации.

## Предыдущий actual evidence и ожидаемый честный статус

Run [38008532239, advanced job 114082885405](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114082885405):

- PR head `f7b9253c8e477babf276ae8dd2cb18905451cd15`;
- checkout merge `011e808a0dcd2ec8104611a2257d17b5f20e327a`;
- checkout tree `cfe816a4e295961b2b529b612bbc63c39ff99ccf`, равен tree PR head;
- raw original coverage **0/15**; полный frozen факт с прежней citation integrity
  наблюдается в **8/15** исходных положительных случаев;
- все положительные checks проходят **7/15**, общий исторический результат **8/16**;
- все шесть сохранённых hard-zero метрик равны **0**.

**8/15 меньше 12/15: это остаётся FAIL.** Указанный старый report не содержит новых
persisted validator receipts, поэтому не является runtime PASS нового oracle.
В этом slice не исправляются retrieval, ru-clean, отсутствующий Configuration
catalog member или устаревшие source facts. Вопросы и ожидания этих случаев
сохраняются.

## Exact manifest

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `eval/project_context_quality/legacy_fact_acceptance.py` | `100644` | `NEW` | `a384c46c1fafd5fd59a8ad20ad0da5e7b38a59e0` |
| `eval/project_context_quality/legacy_fact_acceptance_crosswalk.json` | `100644` | `NEW` | `567811cb42e0550bb2699a7edeccb02f46f4f918` |
| `eval/project_context_quality_v2/acceptance.lock.json` | `100644` | `3174cf3fd95c478a180ffe7e258a06982308e13a` | `3e4c7b5bbefbf5da72643c882af9d4c8b8577061` |
| `scripts/check_legacy_project_context_lineage.py` | `100755` | `c9e28f9b2045faffcac3b71ce0a570d664339664` | `82ed3990e7a1ec30c76db06fcec3940495f90435` |
| `scripts/run_project_docs_self_host_gate.py` | `100644` | `fa68a5a4ea147960321dcaa02950398f14146f2d` | `3e044b27c4d1809c869329e4241ac68e3c28b70c` |
| `eval/project_context_quality_protocol.py` | `100644` | `5f5cb5223dddf3265650d6c139e02aeb3acb8df0` | `63f0657ab238a4e326be3a83e930ab6a8a93c5da` |
| `tests/test_project_context_quality_acceptance.py` | `100644` | `607a37c0dbe5ddda6188ff7671df8833ac8cd0de` | `23ee4085a974f09414504714676e46480e69347c` |
| `tests/test_project_context_quality_protocol.py` | `100644` | `6285f69b5f14b3819650fffa9d868579409bc2b9` | `bc7c613a206ebf72cddd077f35c53627241e5e2f` |

## Статическая проверка и inverse

Git tree базы прочитан напрямую: все шесть изменяемых путей и modes совпадают,
два новых code/data пути отсутствуют; этот execution note — третий новый путь. Все body changes выполнены через уникальные text
anchors; локальные Python/import/pytest или иной runtime не выполнялись.

- Runner: пять bounded hunks; inverse восстанавливает base побайтно. Число,
  arguments и порядок реальных вызовов, observer implementation, старые checks,
  metrics, thresholds и digest logic сохраняются.
- Protocol: один hunk из пяти добавленных строк перед digest; inverse побайтный.
- Protocol test: один hunk из трёх asserts/receipt строк; inverse побайтный.
- Acceptance test: один прежний body заменён плюс локальный fixture helper;
  остальные четыре test bodies/imports сохранены побайтно.
- Acceptance lock: удаление шести добавленных Legacy metadata keys и разделяющей
  запятой полностью восстанавливает исходные байты, включая все V2 settings.
- Acceptance module node hash остаётся
  `ca44afff50d4dee0cd4d04ca51d5c531ba4dd4bab755b616fc867b2d386e4a23`;
  protocol definition-roster hash остаётся
  `8f62404e0fc3319bfc9a971d93c412acecd9aa457b26a0aa6f2cb52037b8ca28`.
  Оба hash вычислены по отсортированным полным `path::function` IDs, соединённым
  `\n` без завершающего newline; второй hash описывает definitions, не expanded IDs.
  Диагностические labels/rosters и selector paths не меняются.

Contracts reviewer выдал итоговый static APPROVE всем восьми code/data blobs,
включая оба исправленных пробела. Root выполняет собственное review перед
публикацией. Все восемь
code/data blobs проверены roundtrip, а inverse checks выполнены без локального
runtime. После публикации обязательны actual existing controls и same-tree live
receipt. Новый runtime PASS или готовность PR к merge этим slice не заявляются.

Для focused JUnit evidence используются существующие nodes:
`tests/test_project_context_quality_acceptance.py::test_legacy_compatibility_floor_keeps_original_threshold_and_hard_safety`
и три прежних параметра
`tests/test_project_context_quality_protocol.py::test_runner_forwards_scope_and_requires_each_fact_group`.
