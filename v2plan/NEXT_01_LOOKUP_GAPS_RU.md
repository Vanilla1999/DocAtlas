# 01. Поиск только недостающей части

Статус: TODO. Выполнять первым. Это проверка existing lookup, не новый механизм.

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

Пока не выполнено. Здесь записать команды, артефакты, итог и статус DONE/BLOCKED.
