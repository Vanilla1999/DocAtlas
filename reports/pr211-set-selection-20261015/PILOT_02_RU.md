# Повтор с исправленным transport: subset работает, полнота — FAIL

Владелец разрешил продолжить после transport failure. Запущена одна новая
попытка на том же установленном wheel и неизменном product/prompt. Runner
передал оригинальное host environment, а не HOME/XDG из data fixture.

| Вопрос | Покрытие A/D | Полный DTO A/D, o200k_base | Сокращение | Selector | Статус |
|---|---|---|---|---|---|
| P03 |515/515 →442/515|47784 →1057|97.79%|input≈21227/output≈14;9.69s;1 completion|FAIL: потеря frozen witness|
| E01 |не запускался|—|—|0|STOP после P03|

Фактически:1 cold prepare,2 public context calls,1 stateless host attempt,
1 JSON completion,0 retries,0 V40. Полный A call1.667s, D10.637s.
167 checked windows →3 selected/delivered windows. Input/output оценки не
включают неизвестные internal framing/reasoning/billing tokens. Это не оценка
полной стоимости и не измерение сгенерированного ответа.

## Где потеряли контекст

Ответ модели: `{"selected_ids":["w9","w44","w76"]}`.

- `w9`: configuration.md:102–111, правило POETRY_/uppercase/dot-dash replacement;
  текст заканчивается `here is an example:`, самого примера в этом окне нет.
- `w44`: repositories.<name>.url, другой пример environment setting.
- `w76`: http-basic credentials, другой пример environment settings.
- `w73` был во входе, но не выбран. Он содержит исходный пример
  `export POETRY_VIRTUALENVS_PATH=/path/to/virtualenvs/directory` и credentials
  example из того же раздела. Raw witness требует строки102–114;
  именно73 символа fenced example (raw offsets3247–3320) не доставлены.

Одинаковые pool/excluded/complete_candidates в A/D, checked windows модели
совпали с baseline sources. Сервер доставил ровно selected evidence IDs;
delivered rows в точности равны исходным baseline rows. Ошибок source/immutable
oracle checks0, состояние SQLite/проекта не изменилось, corpus hashes неизменны.
Сборка DTO и последующий validator не потеряли выбранный текст.

Таким образом, это уже не transport или first-fit failure: subset selector
сам исключил отдельное окно с продолжением. Правило для буквального вопроса
присутствует, но существующий критерий full witness не выполнен. Не подменяем
его семантической оценкой «этого достаточно», не меняем gold ради PASS.

## Вывод и дальнейшая граница

Opt-in pipeline технически выполнен: модель получила весь пул и вернула
валидное подмножество, источники сохранены, токенов существенно меньше.
Однако цель задачи «меньше при сохранённой полноте» НЕ достигнута.
Эксперимент остановлен по условию владельца. Prompt не ретюнился, правильные
IDs модели не подсказывались, E01/V40 не запускались. Default по-прежнему
возвращает полный checked pool; изменений PR remote/main нет.

Разумная следующая гипотеза для отдельного согласованного изменения:
явные связи продолжения между разрезанными окнами одного структурного блока,
чтобы selector выбирал целостную единицу правило+пример. Это НЕ реализовано
в этом пилоте и не означает разрешение скрытого добавления соседей после
selected_ids (оно нарушило бы текущее точное соответствие выбор/выдача).
Нужен общий source-structural контракт, не специальная обработка P03/w73.

Доказательства: `pilot-02/RESULTS.json`, `V40-P03/{A,D}-dto.json`,
`{A,D}-assessment.json`, `selector-receipts.json`, `host-request.json`,
`host-stdout.bin`, `MANIFEST.json`, `ledger.jsonl`, `executed-runner.py`.
Исходный transport FAIL сохранён отдельно в `pilot/` и описан в `RESULT_RU.md`.
