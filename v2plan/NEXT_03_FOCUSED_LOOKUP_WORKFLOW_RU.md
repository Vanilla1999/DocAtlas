# 03. Довести использование focused lookup

Статус: ЗАВЕРШЕНО. Инструкция уточнена; runtime gates не менялись.

## Решение

- План 01 завершён: existing lookup доставляет missing/partial facts в четырёх controls.
- План 02 законсервирован: простое удаление `no_new_direction` отклонено,
  frozen supported claims 49 → 45. Это не доказательство необходимости gate навсегда.
- Read/proof separation сохраняем. Admission/selection research не продолжаем
  в этом плане. Цель — понятная инструкция агенту, а не новый поисковый механизм.

## 1. Одна инструкция в существующем workflow

Проверить действующие agent instructions и публичное описание `lookup_queries`:
`docmancer/mcp/_docs_server_resources.py`, `_docs_server_shared.py`,
`_docs_server_tool_data.py`, `agent_workflow_contract.py`.
Сначала записать конкретный пробел инструкции и где этот текст получает агент.
Если правило уже полностью есть — закрыть этап без правки и без дублирования.
Иначе изменить источник действующего текста и только необходимые связанные
описания. Не создавать ещё одну competing policy или новый API.

Правило:
1. По полученному тексту отделить известное от конкретного пробела.
2. Если нужен дополнительный поиск — сохранить original question, а lookup
   направить только на missing part. Сохранить subject, environment, version,
   negation и условия; не подставлять предполагаемый ответ.
3. Самостоятельный вопрос отправлять отдельным вызовом.
4. Агент сохраняет известный факт с источником и условиями применимости между
   вызовами. Новая выдача не обязана повторять его. Отсутствие факта в ней
   не опровергает его; конфликтующие сведения не склеивать.
5. Если focused поиск не добавил сведений — сообщить partial/unknown. Не повторять
   тот же запрос; продолжать только при новой формулировке с конкретным основанием
   или новом источнике. Если нужны пользовательские данные — запросить их.
   «Не нашли в доступном контексте» не означает «данных не существует».

Пример: known — default timeout; missing lookup —
`OrbitClient timeout configured in production`.
Наличие context и query coverage не означает supported answer или edit permission.

**DONE:** правило находится в реально выдаваемых агенту instructions; публичные
описания согласованы. Если оно уже полностью есть — записать это без новой правки.

## 2. Проверить один follow-up цикл

Использовать четыре fixtures плана 01: both, absent, wrong, partial.
Первый native call — original question. Второй — тот же question + один focused
lookup. Expected lookup задаётся вручную, генератор/модель не добавляется.
Переиспользовать `lookup_gap_probe.py` и existing tests, не создавать новый benchmark.

Проверить final bytes: both получает production fact, wrong
не получает чужой факт, absent не получает выдуманное значение, partial получает
owner fact без численного ответа. Proof/edit flags не повышаются из-за lookup.
В existing fixtures known также сохраняется во второй выдаче — оставить эту
regression expectation, но не делать её общим требованием API. Сохранение знаний
самим агентом ручной replay не проверяет.
Проверить relevant instruction/schema tests и отсутствие противоречий в тексте.

**DONE:** четыре сценария и relevant tests проходят; опубликованная инструкция
содержит правило missing-part lookup и остановки. Manual lookup replay проверяет
механизм, но не доказывает, что любая нейросеть сама правильно выделит пробел.
Это regression, не измерение эффекта новой инструкции. Если правок нет и проверки
на том же коде уже пройдены, сослаться на результаты вместо повторного запуска.

## 3. Закрыть работу

Записать сюда изменённые файлы, команды, результаты и ограничения. Один итоговый
коммит после проверки. Не возобновлять план 02 автоматически.

**ЗАВЕРШЕНО:** инструкция согласована и доступна агенту, existing механизм проходит
regression, результаты сохранены, изменения закоммичены при их наличии.
Улучшение поведения нейросети, прирост общего recall и unseen validation не заявлены.
Для таких выводов нужны реальные вызовы агента; отдельное исследование не входит
в этот план и не блокирует его завершение.
**BLOCKED/STOP:** для выполнения потребовались runtime gate changes, compiler,
retry engine или tuning. Записать конкретную причину и остановиться.

## Результат

### Пробел и замена обязанности

Quickstart уже содержал targeted same-need query и stop on no progress,
а `agent_workflow_contract.py` — immutable root, partial answer и bounded limits.
Но не было явного правила сохранения sourced facts между пакетами, запрета
склеивания конфликтов и различения «не найдено» / «не существует». Публичное
описание инструмента не объясняло missing-part lookup. Поэтому этап не закрыт
как no-op: уточнена существующая gap-directed инструкция, не добавлен recovery path.

### Изменения и доставка

- `_docs_server_tool_data.py`: единый `FOCUSED_LOOKUP_GUIDANCE`, включённый
  в действующее `PUBLIC_ADVERTISED_DESCRIPTIONS["get_docs_context"]`.
- `_docs_server_resources.py`: тот же текст включён в выдаваемый агенту ресурс
  `docmancer://agent/quickstart`, раздел Gap-directed follow-up.
- `_docs_server_shared.py`: реально advertised schema `lookup_queries` уточняет
  missing part, subject/environment и existing call/recovery limits.
- `tests/docs/test_agent_question_planning_contract.py`: расширена существующая
  проверка runtime description/schema и quickstart; новых test nodes нет.
- Этот план: статус и результаты. `agent_workflow_contract.py` проверен,
  не изменён: существующие policy limits и guards остаются действующими.

### Проверки

- `uv run pytest tests/docs/test_agent_question_planning_contract.py tests/docs/test_lookup_gap_probe.py tests/test_unified_docs_context_mcp.py -q`:
  **28 passed, 1 failed**. Единственный failure — `test_get_docs_context_schema`:
  ожидает отсутствие `request_intent` / `lifecycle_intent`. Отдельное исполнение
  `_docs_server_tool_data.py` из HEAD и сравнение с runtime подтвердило одинаковый
  набор property keys; эти два поля уже есть в HEAD. Несвязанный тест не исправлялся.
- Та же команда с `-k 'not test_get_docs_context_schema'`:
  **28 passed, 1 deselected**.
- Existing native probe исполнен через `test_lookup_gap_probe.py`: 8 calls,
  four controls both/absent/wrong/partial. Final snippets сохраняют known fact,
  focused доставляет production/owner только в both/partial; чужой или выдуманный
  факт не появляется. `answer_supported=false`, `edit_ready=false`,
  `support_status=retrieval_only` во всех восьми пакетах.
- Первый запуск остановлен diagnostic inventory из-за нового test node;
  assertions перенесены в existing test, manifest не менялся.
- `git diff --check` перед итоговым коммитом.

### Границы результата

Это manual expected-lookup regression, не unseen validation и не измерение
поведения модели. Сохранение знаний самим агентом не проверено. Recall gain,
эффект новой инструкции и улучшение любых нейросетей не заявлены. Лимиты
coding first-call/recovery не расширены; новый текст действует только внутри
них. Admission/selection/compiler/retrieval и production defaults не менялись.
Ранее существовавшие незакоммиченные изменения плана 02, probe и его tests
не включаются в коммит этого плана.
