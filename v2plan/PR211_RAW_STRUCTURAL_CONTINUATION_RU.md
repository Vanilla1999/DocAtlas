# PR211: точные байты структурного контекста и `read_next`

## Подтверждённое наблюдение 136

Опубликованный HEAD: `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07`.
Checkout существующего CI: `32765e44d2e85d3f638ac9d22a2fa6f4f46f6aee` — merge этого HEAD.
[Reader job 114141422568](https://github.com/Vanilla1999/DocAtlas/actions/runs/38026891736/job/114141422568)
прочитан как готовый текстовый результат; новый job, replay либо локальное исполнение не запускались.

| Наблюдение | Значение |
|---|---|
| UTF-8 размер прочитанного reader log | 674211 байт |
| SHA-256 reader log | `fdf815da3d3a2f0c301b4b36740aac2c29c3de79f0c50fe536281d7aac8bd7f0` |
| Модуль | `tests/docs/test_docs_context_read_next.py` |
| Python 3.11 / 3.12 / 3.13 | на каждом 31 collected: 23 PASS, 8 FAIL, 0 ERROR, 0 SKIP |
| Предыдущий 130 | на каждом 31 PASS, 0 FAIL, 0 ERROR, 0 SKIP |
| Первый guard всех восьми | строка 184: `len(payload["read_next"]) == 1`; фактически 0 |
| Новое исполнение этой поправки | PENDING |
| Настоящие клиентские проверки | NOT_RUN |

Предыдущее наблюдение прочитано отдельно из
[reader 114135542071](https://github.com/Vanilla1999/DocAtlas/actions/runs/38024963940/job/114135542071):
642613 байт, SHA-256 `db7554f76f20570a38c61035d9af43bf85cdb45792f1dd048fe85278b8211a8c`.

Точные XML hashes 136:

| Python | SHA-256 |
|---|---|
| 3.11 | `9b3b5b0ca35eb314f59c10ba0d990ec432e286af3472ffb7c0ad46f50152a155` |
| 3.12 | `e62d11191cde8d6b9e77932a5aa5adcb4a94bf4a1f827dd781f17b63f9386d92` |
| 3.13 | `d4e572cd644f1414147a18238db14c2ebe0d4d368ac79f801182f66364a0a8a0` |

Падают все сочетания `legacy_scope = control / absent / True / False`
и `authorized / revoked`. Ветка `control` не добавляет legacy proof metadata.
До падения проходит точное ожидание
`{"status": "unverified", "reasons": ["coverage_unverified"]}`.
Поэтому legacy-инъекция не объясняет все восемь случаев.
В существующем коде отказ регистрации диапазона добавляет
`source_unavailable` в quality reasons; такого результата здесь не наблюдали.

Фактический trace не содержит финальных source/snapshot rows и выбранного
структурного варианта. Следующий раздел описывает подтверждённую несовместимость
исходников и возможную цепочку потери компактного варианта; он не выдаёт
неполученные промежуточные операнды за наблюдение runtime.

## Причинная граница в исходниках

В 133 буквальный admission начал сохранять полный исходный фрагмент вместе с
LF/CRLF: `_docs_context_projection_core.py` 136 blob
`3dc9c8f19b4431503a073730e1c6f330cd583634`, строки 280–308.
Его raw span проверяется `literal_context_admission.py`
`2a25313955f125e79666eb386f108e8e94eac7cf`, `_checked_raw_body_window`.

Структурный генератор использовал другой формат:

1. `joint_context_candidates._context_row` (base `cc2b2a88…`)
   отрезал завершающий whitespace у запрошенного `raw[start:end]`.
2. Затем `_docs_source` (`dd6795d83c8d863b12dd5e7d9ebe0712a19b2549`,
   строка 28) повторно вызывал `strip()`.
3. `joint_seed_envelopes.py` (`1a1847809623f909c6d212bf2dbcad694b2fef5a`)
   строит компактный общий диапазон из точных исходных вхождений.
4. `retained_seed_mapping` (`e7761bc3b5b1a38d5cbaebed98a7c0eadbcdccfe`)
   справедливо требует полного координатного включения каждого исходного
   вхождения в том же immutable source. Обёрнутый диапазон, обрезавший последний
   LF исходного фрагмента, этот guard не проходит.
5. Более широкий `containing_section` иногда может сохранить оба фрагмента,
   хотя компактный вариант потерял завершающие байты. Если широкий вариант уже
   показывает весь документ, диапазона для продолжения не остаётся.

Исправление сохраняет исходное правило полного включения. `_context_row`
берёт точный `raw[start:end]`, вычисляет inclusive `line_end` по `end - 1`
и возвращает те же байты в public snippet после построения стандартной
identity/hash row. Пустой текст по-прежнему отклоняет `_docs_source`.
Owner, current source, catalog, generation, scope, lifecycle, policy и
source digest проверяются прежними вызовами. Генератор не читает файлы,
не регистрирует URI и не создаёт query/answer/edit credit.

Одинаковый алгоритм диапазона сохраняет LF и CRLF. Существующая регрессионная
native fixture использует исходный LF-документ; отдельный новый CRLF runtime
этим slice не заявляется.

## Сохранённый native контроль

Меняется только тело существующей функции
`test_final_public_handler_continuation_preserves_quality_and_usable_reference`.
Все 7 pytest function names, параметры и 31 collected cases модуля сохранены;
восемь выбранных native сценариев остаются прежними.

Оригинальный вопрос остаётся
`How does docs_status polling progress work?`.
Полное тело `_continuation_document` не изменено:
SHA-256 его исходного definition block —
`ef28f7df07632e0c17e86252310bc6fdeb691b0214c96021f73de5e9ff1e3f5d`
(3762 UTF-8 байта).

Observer перехватывает уже существующий вызов `seed_envelopes`, вызывает
исходную функцию ровно один раз на каждое перехваченное обращение и возвращает
тот же объект. Сохранённая копия используется только для проверки после
исходного public call. Для каждого компактного варианта проверяются исходный
`raw[start:end]`, точные line coordinates, наличие каждого первоначального
snippet и полный same-source `retained_seed_mapping`.
Диапазон обязан заканчиваться раньше конца исходного документа.

`read_next == 1` остаётся обязательным. При падении выводятся только число
sources, первые четыре identity/range/hash rows, число перехваченных обращений
и первые четыре количества вариантов. Тексты источников туда не копируются.
Whole-prefix oracle теперь сравнивает public snippet с точным
`b"".join(raw.splitlines(keepends=True)[:line_end])`.

Все прежние проверки сохраняются: source path/identity/hash; точный исходный
snapshot; отсутствие answer/edit authority и inferred component proof; полный
непрочитанный suffix; пропуск только пустых разделительных строк; один resource
read; отказ после отзыва права; прежняя форма resource response и его действующий
операционный бюджет 600. Resource reader/URI issuer/authorization здесь не меняются.

## Узкая поправка общего fixture oracle

В `tests/docs/_current_source_guard_fixtures.py` меняется одна строка:
line-window containment использует `splitlines(keepends=True)` и `"".join`.
Предыдущее выражение удаляло конечный LF и нормализовало CRLF. Например,
истинная цитата `Rule.\n` не находится в старом диапазоне `Rule.`.
Новый oracle требует точного существования цитаты внутри заявленного raw
диапазона; он не превращает containment в доказательство full-window fidelity.

Непосредственные потребители этого helper, прочитанные в точном source inventory:

| Путь | Blob |
|---|---|
| `tests/docs/test_admission_pipeline_invariants.py` | `0d31455894392e878b696603e9e5bfe88578a176` |
| `tests/docs/test_context_completion_guards.py` | `d63d0bbf593da38ab0d4ae8cd472a3f6c3a5fc73` |
| `tests/docs/test_evidence_set_source_preparation.py` | `40925708ddff6992907d6b5b14a7509ba48fb42d` |
| `tests/docs/test_query_block_guards.py` | `5100517fdb6635ad3bd2f5304b49fdf553ee3533` |

В helper также определён `canonical_range`, непосредственно вызывающий
`_context_row`. Вызовы, авторские documents/questions, строгие координаты,
nonempty snippet, source matching и validator не меняются.
Этот перечень описывает проверенных прямых потребителей и не заявляет
отсутствие произвольных динамических import.

## Точный manifest

Все файлы сохраняют mode `100644`. Три base path/blob отдельно перечитаны
на опубликованном 136 и совпали побайтно.

| Путь | Base blob | Новый blob |
|---|---|---|
| `docmancer/docs/application/joint_context_candidates.py` | `cc2b2a880824b22170723f69b49a490dfe5b47d5` | `cd7feb12aa0dac17a5ee0d418691a8c19bcf3761` |
| `tests/docs/test_docs_context_read_next.py` | `9826ba4b27bfe203dffa05917fcdf0d6345ef536` | `14df87db48fc684783fa1d0dbd05ca5bad7b833c` |
| `tests/docs/_current_source_guard_fixtures.py` | `4d06fbdcbee5e7db31ad0b2e1b58c6fd97de4d5e` | `d548e04faf68a8e471af8050164edb9d0eecc265` |

Новые UTF-8 SHA-256 в порядке таблицы:
`20177340d9ba59986ffda88b0889a0bc5048f16274c0dbbc021748a4ac5a5b56`,
`6837d1391eef15ebf8e5a62a7418b52f5a2adff2026c80390aac57f937a95614`,
`460b047e27b2315484ef275d2b83390f467aad1a16f3c7bc4ca44787bc23fe8c`.

Три roundtrip совпали побайтно. Обратная замена 3 producer hunks,
6 test hunks и одной строки общего oracle восстанавливает каждый base целиком.
Новые pytest names, native acquisition calls, gold/scorer/quality thresholds,
runtime grants и changes к refs отсутствуют. Независимый static review выполняется
до публикации; фактический новый PASS остаётся PENDING.
