# 01. Поиск только недостающей части

Статус: DONE (ограниченная диагностика четырёх synthetic scenarios). Это проверка
existing lookup, не новый механизм; не unseen validation.

## Цель

Выяснить, помогает ли focused lookup найти недостающее и доходит ли найденное
до final context. Уже известную часть не повторять, но сохранять subject,
environment, version и условия. Найденный контекст не считать supported автоматически.

## Этап 1 — зафиксировать 4 сценария до запуска

1. В документах есть обе части; первая уже известна, вторая требует поиска.
2. Недостающего факта в доступных документах нет.
3. Есть похожий факт для другого subject/environment — его принимать нельзя.
4. Есть только частичный ответ — известный факт сохраняется, unknown остаётся unknown.

Использовать существующий native test/replay harness. Для каждого записать:
исходный вопрос, known fact с source witness, missing fact, focused lookup,
ожидаемые source bytes. Labels не передавать в retrieval/admission.
Не добавлять parser, автоматический генератор вопросов или модель.

**DONE:** четыре сценария и expectations записаны до оценки результатов.

## Этап 2 — одно парное сравнение

- A: original question без lookup.
- B: тот же original question + один focused `lookup_queries` про missing fact.
- Corpus, retrieval configuration, guards и budget одинаковы.
- Проверить existing API: lookup уточняет тот же вопрос. Самостоятельный вопрос
  требует отдельного вызова; не обходить это ограничение.
- По каждому сценарию сохранить: retrieved witness → admission reason → final
  visible witness → claim support/unknown и proof/edit flags.

Пример: «Default timeout и timeout сервиса X в production?» → lookup
«timeout сервиса X в production». Не искать просто «timeout».

**DONE:** для каждого missing fact установлен первый наблюдаемый барьер:
нет в corpus / не найден / admission / selection / дошёл. Выигрыш не обязателен.

## Этап 3 — решение, максимум одна локальная правка

- Lookup нашёл и доставил: механизм достаточен; поправить existing инструкцию
  использования только если она не объясняет поиск missing part.
- Нашёл, но admission отбросил: передать exact-window пример в план 02.
- Не найден: записать retrieval limitation; не менять retrieval в admission trial.
- Данных нет: честный partial/unknown; уточнить у пользователя источник данных,
  а не повторять поиск без новой информации.

**ЗАВЕРШЕНО:** результаты дописаны сюда, выбран один исход; при правке relevant
tests проходят. Нет бесконечного retry. Новый запрос оправдан новым источником
или конкретной новой поисковой формулировкой, а не неудовлетворённостью ответом.
**STOP/BLOCKED:** требуются aliases, fallback, grammar или threshold tuning.
Не расширять четыре сценария в новый benchmark без конкретного обнаруженного дефекта.

## Результат

### Этап 1 — DONE, expectations до запуска

Общий original question: `What is OrbitClient default timeout and what timeout
is configured for OrbitClient in production?`
Known source `defaults.md`: `OrbitClient default timeout is 5 seconds.`
Focused lookup: `OrbitClient timeout configured in production`.
Это уточнение того же вопроса, а не отдельный need вне original question.

Четыре isolated corpora (в каждом также known source):

| Сценарий | Второй source `deployment.md` | Ожидаемые facts |
|---|---|---|
| both | `OrbitClient timeout configured in production is 12 seconds.` | known 5; missing 12 доступен для поиска |
| absent | `Production deployment uses three replicas.` | known 5; production timeout unknown |
| wrong | `NovaClient timeout configured in staging is 12 seconds.` | known 5; нельзя приписать 12 OrbitClient production |
| partial | `OrbitClient timeout configured in production is managed by the deployment owner.` | known 5; owner fact полезен, численное значение unknown |

Sources оформлены Markdown с нейтральным heading `Guide`. Expectations — только
в этом документе/оценке, не в indexed corpus или запросе. Проверяем exact sentences
в delivered snippets и actual flags; delivery предложения не приравниваем к proof.
Обе стороны используют один индекс своего corpus и native defaults.

### Этап 2 — DONE

Команда: `PYTHONPATH=. .venv/bin/python v2plan/lookup_gap_probe.py --output
/tmp/opencode/lookup-gaps-01`. Восемь full-native calls; same index внутри пары,
без runtime patches. Raw payload/trace/request и ingest находятся в output.

| Сценарий | Без lookup | Focused lookup | Первый наблюдаемый барьер |
|---|---|---|---|
| both | только default 5 | default 5 + production 12 | A: после retrieval/query window и qualification, до final packet; B: дошёл |
| absent | только default 5 | только default 5 | нужного численного факта нет в corpus |
| wrong | только default 5 | только default 5 | нужного факта нет; чужой subject/environment не доставлен |
| partial | только default 5 | default 5 + owner fact | A: после retrieval/query window и qualification; B: partial дошёл, число отсутствует в corpus |

Known sentence доставлена во всех 8 calls. `answer_supported=false`,
`edit_ready=false`, `support_status=retrieval_only` во всех calls. Это source
witness delivery, не независимая проверка claim-support evaluator. `query_coverage`
не трактуется как полнота ответа. Численное unknown устанавливается по fixtures,
а не по автоматически составленному runtime списку пробелов.

В both/partial без lookup deployment sentence уже присутствует в retrieved
candidates и query window, `qualification_reason=visible_fields`, а явных
`projection_rejections` нет. Поэтому **не доказан admission refusal**: локализуем
потерю только в дальнейшей projection/selection delivery. Lookup меняет query
lanes/ordering; его результат не доказывает, что admission стал правильнее.

### Этап 3 — DONE: existing lookup оставить, передать delivery conflict в 02

Для этих controls механизм достаточен: focused lookup доставляет missing/partial
fact без потери known и без чужого ответа. Новый follow-up API, retry loop,
compiler/fallback не нужны. Использование: original question остаётся прежним,
lookup спрашивает только missing part с subject/environment/conditions.
Если данных нет — partial/unknown и запрос источника у пользователя.

В план 02 передаём both/partial как **delivery conflict**, не как установленный
locality defect. Следующая диагностика должна назвать конкретную ветку, где
пропадает уже найденный qualified witness; удалять gates по этой таблице нельзя.
Production instructions/defaults не менялись. На этом план 01 остановлен.
Regression control: `tests/docs/test_lookup_gap_probe.py`.
`.venv/bin/python -m pytest -q tests/docs/test_lookup_gap_probe.py
tests/docs/test_unified_read_admission_probe.py`: **34 passed**.
Первый collection остановлен diagnostic inventory guard; добавлен behavioral
manifest для нового test module, guard не отключался.
