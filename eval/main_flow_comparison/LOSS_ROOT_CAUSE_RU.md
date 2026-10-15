# Причины потери контекста: квалификация источников и ранний запрет выдачи

## Вывод и границы анализа

Для семи неуспешных вопросов **1, 4, 6, 7, 8, 9, 10** сохранённая трасса показывает отказ квалификации всех записанных кандидатов и последующий `delivery_blocked=true`. Русский текст распознаётся токенизатором, но квалификация требует буквального совпадения словоформ и не менее **50%** терминов вопроса. Поэтому окна с фактическим ответом могут не пройти допуск.

Это **не только проблема русской морфологии**: в артефактах также видны различия формулировок, отсутствие нужных окон среди записанных кандидатов вопросов 1/9 и фрагментация источника для вопроса 10.

Анализ выполнен без изменения продукта и без повторного запуска MCP, retrieval, qualification или тестов. Использованы исходники, сохранённые JSON/JSONL и чтение изолированной SQLite через stdlib `sqlite3` с `mode=ro`. Отдельный stdlib-скрипт сопоставил сохранённые строки буквальным регулярным выражением; production-функции не импортировались и не вызывались.

**Числа совпадений и списки терминов ниже реконструированы из исходников и сохранённых байтов, а не извлечены из runtime-операндов трассы.** Их машиночитаемая запись: `root-cause-reconstructed-matches.json`. Она не является результатом повторного выполнения квалификатора и не доказывает качество ответа.

Пути исходников далее относительны корню репозитория. Номера строк относятся к исследованному checkout. В `docatlas-results.json:2–7` записаны source-checkout transport, SHA `2f729efee5e6d55dd1867fc00c90e363970a2cd4` и hash корпуса. Проверенный diff этого SHA для `evidence_qualification.py`, `context_query_probes.py`, `query_reference_binding.py` и `_project_docs_diagnostics.py` был пустым.

## 1. Непосредственно записанные наблюдения: семь строк

Вопросы зафиксированы в `questions.json:2,5,7–11`; порядок вызовов следует `run_docatlas.py:83–91`. Соответствующие события находятся в `docatlas-trace.jsonl`:

| ID | Исходный вопрос | Строка JSONL | Записанные исходы квалификации |
|---|---|---:|---|
| 1 | Как включить и выключить подробные логи основного потока DocAtlas через CLI? | 4 | 6 × `insufficient_visible_match` |
| 4 | Куда DocAtlas выводит трассу и как она отделяется от ответов CLI и протокола MCP? | 13 | 6 × `insufficient_visible_match` |
| 6 | Какие публичные пути DocAtlas покрывает lifecycle-логирование и покрывает ли оно ошибки разбора аргументов CLI? | 19 | 4 × `insufficient_visible_match`, 2 × `metadata_only_evidence` |
| 7 | Означает ли status=success в трассе DocAtlas, что найденных доказательств достаточно для ответа? | 22 | 6 × `insufficient_visible_match` |
| 8 | Как DocAtlas ведёт себя при ошибке записи диагностики и как сообщает о пропусках трассы? | 25 | 4 × `insufficient_visible_match`, 2 × `metadata_only_evidence` |
| 9 | Какие новые тесты разрешены в DocAtlas и чем нужно проверять корректность результата помимо логов? | 28 | 6 × `insufficient_visible_match` |
| 10 | Доказывает ли статья Countdown-Code, что unit-тесты хуже интеграционных тестов? | 31 | 6 × `insufficient_visible_match` |

Для каждого запроса записаны три различных chunk ID дважды: всего 42 наблюдения, из них 38 лексических отказов и 4 metadata-only. Это не 42 уникальных документа или окна. Код отдельно выполняет исходный и `source_of_truth` acquisition: `docmancer/docs/application/_project_docs_service_part03.py:232–269`. Диагностика снимается до дедупликации: `:335–367`.

Все семь итоговых наблюдений имеют `delivery_blocked=true`, `context_available=false` и отсутствующие `sources`; ответы в `docatlas-results.json` содержат `required_evidence_missing`, `requires_confirmation=false`, `operational_status=not_found`.

## 2. Точный путь квалификации

### 2.1. Какая часть кандидата проверяется

`_tag_retrieval_query()` создаёт probe и передаёт **`chunk.text` как `evidence_text`**: `docmancer/docs/application/reference_query_tagging.py:84–106`. Путь, title и heading metadata входят в `visible_text`, однако обычная проверка тела использует `evidence_text`: `docmancer/docs/domain/evidence_qualification.py:269–276`.

Поэтому наличие `DocAtlas` в catalog description или retrieval prefix не превращается в совпадение этого слова в теле. Для сравнений выбираются substantive lines, а не весь индексируемый retrieval text.

### 2.2. Важная замена токенизации на production-пути

Первоначальный `literal_query_probe()` берёт слова длиной от четырёх символов: `docmancer/docs/application/context_query_probes.py:39–46`. Но считать итоговый порог только по этим словам было бы ошибкой.

1. Для исходного вопроса создаётся reference plan: `docmancer/docs/application/source_reference_evidence.py:78–79`.
2. При подготовке кандидата прикладываются `_reference_root_plan` и `_reference_plans`: `:130–141`.
3. `qualify_evidence()` вызывает `prepare_reference_probe()`: `docmancer/docs/domain/evidence_qualification.py:269–276`.
4. Подготовленный plan заменяет `query_terms` результатом `documentation_query_terms(body_question)`: `docmancer/docs/domain/query_reference_binding.py:437–462`.
5. `reference_body_question()` сохраняет исходный текст вопроса: `:289–291`.
6. Итоговый tokenizer берёт все различные буквальные токены через `[\w.:/+-]+`, выполняет `casefold`, сохраняет короткие слова и связки, ограничивает список 32 элементами: `docmancer/docs/domain/query_terms.py:93–100`.

В рассматриваемых вопросах учитываются, например, `ли`, `и`, `в`, `что`, `как`, `для`; повторное `покрывает` в ID 6 дедуплицируется.

### 2.3. Правила совпадения и порог

- Markdown-тело разбирается на substantive lines и headings: `docmancer/docs/domain/evidence_qualification.py:277–321`.
- Слова проверяются в casefolded теле: `:342–363`.
- Заголовки могут помогать только после двух совпадений в теле: `:364,395–407`; метаданные heading path не равнозначны строкам заголовка в самом body.
- `_visible_term_present()` вызывает общее регулярное выражение: `:493–495`.
- Даже `exact=False` требует буквальное написание, а не склонение, stemming или синоним: `docmancer/docs/domain/technical_tokens.py:7–16`.
- Порог: 1.0 для одного термина, 0.4 при hard exact terms, иначе **0.5**. При недостижении возвращается `insufficient_visible_match`: `docmancer/docs/domain/evidence_qualification.py:418–425`.

У этих семи вопросов нет hard exact terms по правилам `docmancer/docs/domain/query_terms.py:103–135,146–150`. В частности, bare `DocAtlas`, `CLI`, `MCP` и `status=success` не создают здесь hard exact constraint. Технический anchor и hard exact term — разные сущности.

## 3. Проверка по сохранённым окнам SQLite

База: `/home/viadmin/.docatlas-main-flow-comparison-20261011/docatlas-home/mcp-members/members.db`, таблица `retrieval_children`.

Chunk ID из трассы сопоставлены с `display_text`, `char_start`, `char_end`, `line_start`, `line_end`. Для всех исследованных окон проверено равенство `display_text` соответствующему character slice `corpus.md`.

В таблице ниже ID сокращены до первых восьми символов после `child-`. Полные ID и уже полученные списки терминов/совпадений записаны в `root-cause-reconstructed-matches.json`. Дроби — **реконструкция буквальных body matches**, не сохранённые runtime `match_ratio`.

| ID | Окна и реконструированные совпадения | Конкретная причина и граница вывода |
|---|---|---|
| 1 | `8120800d` — 4/11: `как, и, через, cli`; `29ab9d83` — 3/11: `и, через, cli`; `21dbda0a` — 1/11: `как` | Записаны `corpus.md:29–45,78–79` и хвост строки 81. Нужные CLI-инструкции находятся в `:5–25` и среди этих кандидатов отсутствуют. Есть acquisition miss; нельзя утверждать, что именно qualification отбросила нужные инструкции этого запроса. |
| 4 | `8120800d` — 4/13: `и, как, cli, mcp`; `6e9a9936` — 4/13: `и, от, cli, mcp`; `d79731df` — 1/13: `трассу` | `6e9a9936`, строки 19–26, содержит прямое указание stderr отдельно от CLI/MCP output. Вопрос: `выводит, отделяется, ответов, протокола`; источник: `идёт, отдельно, ответа, stdout`. Морфология и перефразирование дают недостаточный literal overlap. |
| 6 | `8120800d` — 4/13: `и, ошибки, разбора, cli`; `6e9a9936` — 3/13: `и, ошибки, cli`; `14351b36` — только заголовок | Прямой ответ есть в строках 32–34 окна `8120800d`. `публичные` ≠ `публичный`, `покрывает` ≠ `Покрыты`, `lifecycle-логирование` ≠ `lifecycle-событий`. Третье окно закономерно metadata-only. |
| 7 | `8120800d` — 6/13: `означает, status, success, в, найденных, доказательств`; `6e9a9936` — 3/13: `в, для, ответа`; `e6256df7` — 1/13: `ответа` | Строки 38–40 прямо различают завершение вызова и достаточность доказательств. 6/13 ниже 0.5. `достаточно` ≠ `достаточность`; `ответа` отличается от `результат`; `docatlas` не совпадает с префиксом `docatlas_request_start`. |
| 8 | `8120800d` — 6/13: `как, при, записи, диагностики, и, о`; `9a8cb20e` — 4/13: `записи, диагностики, и, о`; `14351b36` — только заголовок | Строки 41–44 содержат поведение при отказе записи диагностики. `ошибке` ≠ `Ошибка`, `пропусках` ≠ `пропуске`, `сообщает` ≠ `сообщение`. Прямой ответ остаётся ниже порога. |
| 9 | `55bd80c5` — 3/14: `и, корректность, результата`; `8120800d` — 3/14: `новые, в, и`; `8a9d5db5` — 2/14: `и, проверять` | Записаны фрагменты строки 71 и строки 29–45; нет явного integration-only решения строки 74 и основного критерия независимой оценки строки 64. Причина не сводится к qualification: нужные окна не представлены в записанном acquisition. |
| 10 | `a2ed086f` — 3/9: `доказывает, что, тестов`; `8a60f814` — 2/9: `countdown-code, тестов`; `e734e802` — 2/9: `статья, unit-тесты` | Строка 69 разрезана: `8a60f814` содержит Countdown-Code и границу сравнения, `a2ed086f` — `не доказывает`. Каждый фрагмент квалифицируется отдельно. `интеграционных` ≠ `интеграционный`; `unit-тесты` ≠ `unit- и integration-тестов`. Третий кандидат относится к Anthropic, строка 70. |

Токен `тестов` в ID 10 может совпасть с суффиксом `integration-тестов`: для нетехнического термина при `exact=False` используются границы `(?<!\w)` / `(?!\w)`, допускающие соседний дефис. Это следует из `technical_tokens.py:13–16` и не означает семантическую квалификацию сравнения.

## 4. Конкретный источник `metadata_only_evidence`

В ID 6 и ID 8 повторяется `child-14351b36d269548aa21f155f66ef89f5e020417c`:

```markdown
## События и границы

```

Это `corpus.md:27–28`, character span `[1002,1024)`.

Код исключает Markdown heading из substantive lines: `docmancer/docs/domain/evidence_qualification.py:296–298`. При отсутствии substantive lines немедленно возвращается `metadata_only_evidence`: `:316–317`.

Отказ полностью объясняется сохранёнными байтами; он не связан с распознаванием кириллицы.

## 5. Ловушка fallback: unresolved technical mention `DocAtlas`

После отказа исходного вопроса `_tag_retrieval_query()` пробует literal-context admission: `docmancer/docs/application/reference_query_tagging.py:107–113`.

`admit_original_literal_context()`:

- допускает fallback только после `insufficient_visible_match`, а не после metadata-only: `docmancer/docs/domain/literal_context_admission.py:293–297`;
- ищет explicit symbol identity и body witness либо закрытые формы запроса: `:298–342`;
- содержит закрытые формы на английском (`what does`, `what is`, `how does … differ from`, `explain`, `how many`): `:20–57,99–121,155–167`;
- при отсутствии witnesses вызывает ordinary-body fallback: `:365–370`.

Для ID 1/4/6/7/8/9 `DocAtlas` распознаётся как технический anchor по CamelCase (`docmancer/docs/domain/query_terms.py:19–29,75–90`), но получает **`unresolved`, `explicit=False`**, а не explicit symbol identity: `docmancer/docs/domain/query_reference_binding.py:87–93`.

Получается конкретная развилка: bare `DocAtlas` недостаточен для explicit-symbol admission, русская фраза не проходит закрытые английские формы, а наличие любого query mention / technical anchor **запрещает ordinary-body admission**: `docmancer/docs/domain/ordinary_body_context.py:80–84`. Это ограничение области fallback, а не доказательство отсутствия фактов в документе.

Для ID 10 ordinary-body маршрут требует как минимум два различных content words из непрерывной последовательности исходного вопроса, в исходном порядке, внутри одной source clause: `ordinary_body_context.py:93–109`. В сохранённых фрагментах такой пары нет. Английские function-word категории заданы в `:19–34`; русские `ли` и `что` не исключаются из последовательности. Изменение этого правила не проверялось и не объявляется достаточным исправлением.

## 6. От квалификации до `required_evidence_missing`

### 6.1. Где отбрасываются кандидаты

Project-context service вызывает reranking на `docmancer/docs/application/_project_context_service_part01.py:159–175`. В `docmancer/docs/domain/project_doc_ranking.py:204–225` проверяются qualified query matches и заново вычисляется literal context. При отсутствии qualification, literal admission и explicit context-candidate retention кандидат исключается.

Есть дополнительные каналы сохранения контекста: `_project_context_service_part01.py:130–155`. Сохранённая трасса не содержит всех промежуточных результатов этих проверок; конкретную последовательность опустошения каждого context pack по runtime-операндам восстановить нельзя.

### 6.2. Откуда берётся строка причины

1. Каноническая selection вызывается в `_project_context_service_part01.py:478–484`.
2. Её project-docs config использует `result_kind="docs_answer"`: `docmancer/docs/application/_evidence_selection_part01.py:438–450`.
3. Для `docs_answer` selector безусловно запрещает полноценную answer authorization, добавляя `unsupported_answer_authorization:context_only`: `docmancer/docs/application/_evidence_selection_part03.py:385–390`.
4. При непустом `missing` выбирается `required_evidence_missing`, если более приоритетные причины не применились: `:422–427`.
5. При этом пригодный read context разрешён независимо от отсутствия answer proof: `_project_context_service_part01.py:879–909`. Следовательно, одна только политика `context_only` не объясняет потерю контекста этих семи запросов.
6. Unified service вычисляет `context_available = bool(context_pack)`: `docmancer/docs/application/_unified_context_service_part01.py:318`. Он берёт canonical support payload и разрешает доставку supported answer либо eligible read context. При отказе копирует support reason в delivery decision: `:405–469`.
7. `operational_status=not_found` формируется агрегированием статусов/числа источников: `docmancer/docs/application/_unified_context_service_part02.py:558–584`. Это не доказательство отсутствия документа в индексе.

### 6.3. Ранний veto, а не доказанная потеря при упаковке ответа

MCP handler проверяет delivery veto **до обычной projection/recovery**: `docmancer/docs/interfaces/mcp/context_tools.py:358–384`. При блокировке он валидирует отказ, записывает observation с `delivery_blocked=True` и сразу возвращает его.

`_explicit_delivery_block()` формирует наблюдаемый отказ с `context_available=false`, `answer_supported=false`, `delivery_decision.deliverable=false`, выбранным reason и operational status: `docmancer/docs/application/model_visible_projection.py:466–494`.

Поэтому для этих семи ответов **нельзя приписывать исчезновение источников финальному token budget/packing проекции**: нормальная проекция не была достигнута. Это также не доказывает отсутствие влияния более ранних acquisition/stage budgets. Сохранённые события не позволяют измерить их вклад или восстановить все невыбранные окна.

## 7. Что доказано, а что остаётся реконструкцией или гипотезой

**Непосредственно подтверждено артефактами:**

- перечисленные qualification outcomes и финальный ранний delivery veto;
- конкретные сохранённые body windows и их равенство фрагментам корпуса;
- наличие прямых фактов в полученных окнах ID 4/6/7/8;
- отсутствие нужных окон среди записанных кандидатов ID 1/9;
- разрезание строки 69 между двумя полученными окнами ID 10;
- heading-only содержание metadata-only кандидата.

**Подтверждено исходниками и реконструкцией, но не записанными runtime-операндами:**

- замена исходного ≥4-character probe полным literal token list на подготовленном пути;
- приведённые match lists/ratios и порог 0.5;
- ограничения fallback для unresolved `DocAtlas`;
- путь передачи canonical support reason в early delivery veto.

**Не доказано этим анализом:**

- точное состояние каждого промежуточного context pack, fallback/retention результата и selector missing set в сохранённом вызове;
- все producer-level omissions или самая первая потеря до записанного candidate preview;
- полная причина retrieval misses ID 1/9, в том числе относительный вклад ranking, limit и budget;
- что stemming, перевод запроса, меньший порог, увеличение лимита или объединение фрагментов исправит все семь задач без новых дефектов.

Observation adapter сохраняет только ID/outcome/reason, опуская query terms, ratios, reference plans и fallback operands: `docmancer/docs/application/projection_decision_trace.py:188–192`. Его собственная граница доказательства прямо запрещает считать неизвестные upstream omissions доказанным отсутствием ранней потери: `:197–200`.

Для устранения этих пробелов нужен отдельно разрешённый сбор наблюдений или сценарий. В данном анализе таких запусков не было; приведённые числа не следует маркировать как runtime telemetry или PASS исправления.
