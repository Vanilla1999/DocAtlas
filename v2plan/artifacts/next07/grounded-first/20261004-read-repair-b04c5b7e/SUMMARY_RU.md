# Исправление research read-кандидата после b04c5b7e

Дата: 2026-10-04. Ветка: `next07-feasibility-audit`.
База: `b04c5b7ea1bfbdbbe9f439cefee2bab206c513e2`.
Статус: **код локальной правки подготовлен; native I.3 / C НЕ ПРОВЕРЕНЫ**.
Это новая research-версия по просьбе пользователя «ты что-то сделай» после
предыдущего содержательного REJECTED, не переименование старого результата.

## Что изменено

Только существующая read-ответственность в `v2plan/next07_grounded_candidate.py`.
Retrieval, splitter, ranking, production/defaults, guards и исходный test harness
не менялись. R1 и R2 — отдельные поправки внутри одного read-слоя; их отдельные
patch-файлы сохранены в приложенном в чате архиве проверки.

**R1 — выбор существующего matcher для wrong-state.** Для уже распознанного
`default` применяется штатный `default_local_witness`, а не не поддерживающий
этот оператор `relation_local_witness`. Для проверки исходного утверждения
меняется только occurrence state в локальном proof-probe по offsets parser.
Original question, retrieval queries, source bytes и public flags не меняются.
Другие operators сохраняют прежний matcher. Только `witnessed is True` может
установить mismatch; False/None не становятся доказательством противоречия.
Ни новых productions, ни словаря событий, ни правила под LeaseClient нет.

**R2 — сохранение parser-owned source section.** Прежняя проверка только edges
заменена проверкой полноты каждого пересечённого Markdown owner плюс прежних
явных dependency edges. Whole greedy chunk не считается целым owner, когда
его хвост находится в другом chunk. Такой вариант получает существующий отказ
`hidden_structural_dependency`. Окно не расширяется; parent rescue, новые reads,
clipping и повышение бюджета не добавлены.

Это консервативная структурная граница: она закрывает выявленный дефект с поздней
restriction в том же разделе без её языкового распознавания. Она НЕ доказывает
сохранность любых смысловых связей между произвольными разделами. Длинные или
разрезанные owners могут не пройти; влияние на полезные partial facts и 49 IDs
ещё не измерено. Это риск кандидата, а не разрешение снижать retention acceptance.

## Что проверено здесь

22 **новых узких** теста прошли на извлечённых неизменённых определениях:
выбор matcher, сохранение request/offsets, False/None, геометрия source owners,
Unicode, соседние разделы, headings внутри fence и явные dependency edges.
В dispatch tests используются spies; они проверяют маршрутизацию вызова,
не поведение настоящего proof matcher.

Исполнены exact helper definitions из нового candidate (AST extraction), полный
pinned `admission_grammar.py` (blob `310284a936913bfccf0db9713166a357025d43ea`) и
чистые определения `parse_markdown_parents` с зависимостями из source blob
`89528de2cb78820ca244924d5be39a94164355de`. Полный DocAtlas не импортировался.
Не выдавать эти 22 PASS за прежние 22 PASS I.3 или за 24/24 acceptance.

Дополнительно: Python compile, тождественность AST retrieval functions, побайтовое
сохранение source/exact guard блока и завершающей read/echo логики. Исходный
`v2plan/test_next07_grounded_first.py` не изменён (blob
`c8ce3ea1a0b2a37c490bbe3cb116acc03e5a5c7e`); прежние 24 tests/expectations сохранены.
Новый module содержит 22 pure checks и 7 checks с настоящими native matchers.
Результат и hashes — `result.json`; raw JUnit с полными node IDs — `pure-tests.xml.gz`.

## Что НЕ выполнено

7 native matcher checks, 24 authenticated I.3 tests, остальные mandatory controls,
final C packet, 800/3 final validation, 49-ID/partial retention, gates/full suite,
unseen/reader: **NOT_RUN**. В текущем исполняемом окружении checkout не получен:
`git ls-remote` и DNS lookup к GitHub завершаются ошибкой разрешения имени;
исходники прочитаны и изменения публикуются через GitHub connector.
Никаких имитаций source guards или искусственно разрешённых DTO для приёмки нет.

## Одна команда проверки в существующем окружении проекта

```sh
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q \
  v2plan/test_next07_grounded_first.py \
  v2plan/test_next07_grounded_read_repairs.py
```

Полный expected inventory команды — 53 параметризованных checks; это число
не результат запуска. Сохранить stdout/exit/JUnit в НОВОМ каталоге. Не менять
checks ради PASS. G reference и исправление DTO harness повторять не нужно,
если их source/package hashes не изменились. При содержательном failure текущая
revision отклоняется, без автоматического наращивания правил.

Даже успех этой команды — local I.3, не final delivery: далее остаются прочие
mandatory controls и I.4–I.6 действующего плана. Rollout не разрешён. История
BLOCKED/REJECTED и frozen evidence сохранена без изменений.
