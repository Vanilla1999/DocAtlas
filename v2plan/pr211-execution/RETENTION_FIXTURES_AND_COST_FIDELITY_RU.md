# PR #211: ActionPacket retention fixtures и output fidelity

## Причина, подтверждённая CI

На `067dd56044fb1fe292af2d17783154c8a4b7c092` Task33 дал **61 PASS / 3 FAIL**:
[run 37991321112 / job 114025928664](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321112/job/114025928664).

Два SDK-вызова в тестах использовали обычный facade без завершения retention invocation.
Текущий handler возвращает `unsupported_found_window_retention`, когда реальный
`_RetentionCompletion` не завершён producer-ом. Fixture уже владеет всеми исходными
окнами, поэтому теперь явно реализует `retain_found_windows` / `_retention_ack`
и проходит через действующий `_found_window_retention_producer`. Обходов completion
или замены handler/validator нет. Ответ SDK проверяется по `schema_version=4`;
поле `kind=patch_context` не входит в текущий ActionPacket v4.

Оба теста сохраняют исходные вопросы, авторские тексты и пути. Дополнительно проверяются
полные окна, SHA256 каждого текста, untrusted-data boundary и реальный
`validate_action_packet` на исходных evidence items. Формат не выдаёт разрешение на edit.

Третий тест имеет действительно пригодную цитату `src/navigation.py: navigation only`.
Для retrieval-only ответа `ok` означает доступный context; `answer_available`,
`answer_supported` и `edit_ready` остаются false. Теперь проверяется сам точный source,
а не прежнее требование скрывать пригодную навигацию. Legacy facade сохраняет свою
единственную допустимую цитату `src/legacy.py: code` по тому же retrieval-only контракту;
это не доказательство пригодности к изменению кода. Fixture документа со stable child
identity получает недостающий `display_content_hash` от неизменённых авторских bytes:
без этого текущий selector обоснованно отвергал неполный binding. Default и SDK теперь
оба проверяют сохранённый документ без answer/edit grant.
Все остальные negative cases, source-choice producer и 32 consent controls сохранены.

## Стоимость вместо потолка

Первый тест `test_context_completion_followup.py` больше не требует втиснуть ответ
в число на один токен меньше наблюдаемой длины. Тот же реальный FastAPI corpus и
исходный вопрос проходят действующий serializer с отсутствующим и устаревшим
минимальным output hint. Проверяются неизменные тексты и присутствующие поля
identity/hash/lineage/version/trust, binding validator и измеряемая стоимость.
Операционные ограничения не меняются.

Второй тест этого файла про полный priority fact `mkdocs-05` оставлен побайтно прежним:
это остаётся отдельным quality failure, который нельзя закрыть миграцией output cap.

## Проверка

20 имён main ActionPacket tests и два имени completion tests сохранены.
Production не изменён. Выполнен source review и проверка точных replacements;
локальный Python/runtime не запускался. Полный PASS определяется последующим CI.
