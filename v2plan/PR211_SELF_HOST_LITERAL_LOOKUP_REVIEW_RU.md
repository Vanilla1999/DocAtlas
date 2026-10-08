# PR211: явный lookup в новом синтетическом self-host positive

Дата: 2026-10-08. База: `991638f28ecff659c320b45738edfaa8b9fd375e`.

Изменён только prepared public call и его диагностические/дополнительные assertions в
`tests/test_project_docs_self_host_fixture.py::test_self_host_confirmed_prepare_binds_one_host_store_and_copied_project`.
Это проверка lifecycle и связи mirror → host-selected store → публичное чтение.
Она не удостоверяет качество ответа на исходный вопрос без явного lookup.

## Наблюдение CI и установленный текущий контракт

На 991638f новый node прошёл cold-read, explicit preparation, generation, config,
private-store и отсутствие project-local DB, затем упал на `status == 'ok'`:
фактически вернулся `insufficient_evidence`. Прежний assertion не напечатал полный
payload; первый фактический operational/qualification reason того CI неизвестен.
Ни CRLF, ни конкретный reason code не объявляются доказанной причиной этого прогона.

Независимое чтение текущего source устанавливает несовместимость запроса с буквальной
квалификацией его исходного документа:

- `application/context_query_probes.py::literal_query_probe` берёт слова длиной от
  четырёх символов без удаления вопросительных слов: исходный вопрос
  `What does \`MirrorNeedle\` require?` даёт `what`, `does`, `mirrorneedle`, `require`.
- `domain/technical_tokens.py::technical_term_pattern` требует буквальное слово и
  явно не приравнивает его к склонённой форме. `require` не совпадает с `requires`.
- `domain/evidence_qualification.py::qualify_evidence` при exact term требует
  отношение совпавших слов не менее 0.4. В прежнем RULES совпадает только
  `mirrorneedle`: 1/4 = 0.25. Это конкретный blocker исходной qualification,
  без вывода о первом reason code завершённого CI.
- `application/_docs_context_payload.py` сохраняет отдельные `covered_query_ids`
  и `missing_query_ids`; `application/context_selection.py` вычисляет их из
  действительно атрибутируемых источникам публичных запросов.

## Узкий successor

К прежнему prepared вызову добавлен только явно заданный host lookup:
`lookup_queries=['\`MirrorNeedle\` explicit preparation']`.
Все три буквальных слова есть в неизменном теле RULES. Это публичный запрос хоста,
а не автоматически выведенное требование или скрытое изменение qualification.
Исходный question остаётся дословно прежним; cold call тоже остаётся прежним.

Все 24 прежних assertion expressions внутри node сохранены. Дополнительно проверяются:

1. `context_available is True` и непустой same-call snapshot.
2. `answer_available is False` и `support_status == 'retrieval_only'`.
3. `query-lookup-1` находится в `covered_query_ids`.
4. `query-original` отсутствует в `covered_query_ids`.
5. `query-original` находится в текущем публичном `missing_query_ids`.

Проверка `status == 'ok'` / `kind == 'docs_context'` сохранена. Для неё и пяти
новых assertions добавлен полный JSON payload вместе с ключами snapshot при отказе.
Исходные `answer_supported is False`, `edit_ready is False`, непустой источник
`docs/rules.md`, snippet-in-source, project identity, полное содержание источника,
content hash, generation, catalog hash, единственный private host store,
`project_docs_ready`, честный `not_git`, запрет auto-sync, отсутствие stale/ignored
и отказ повторного prepare сохраняются.

## Байты, инвентарь и статическое доказательство

RULES остаётся **88 байт**, включая три CRLF; SHA-256:
`867b29312611d6aeda55a87adf26b18cfe96631b26440a722d0de81c52082ee1`.
Membership, catalog authority, все остальные fixture файлы и configuration
не изменены. Сохранён точный assertion `source['content'] == RULES.decode()` и
`source['display_content_hash'] == hashlib.sha256(RULES).hexdigest()`.

Файл теста: SHA-256
`098c51af40c4ad37e7ddc07a4fd64abf6f2f4caaa7a8eced02cb41754e9a0569`,
18465 байт, 307 строк. В изменённом node assertions **24 → 29**.

Stdlib AST-проверка установила:

- Весь AST вне единственного node точно совпадает с базой, включая RULES,
  `_checkout`, `_cold_read`, imports и остальные пять tests.
- После удаления ровно нового lookup, diagnostic assignment и пяти новых
  assertions, а также diagnostic message у прежнего status assertion,
  AST изменённого node точно совпадает с базой.
- Сохранены все шесть прежних test IDs и decorators; новых nodes нет.
- Diagnostic labels не изменены; SHA-256 файла
  `tests/diagnostic_labels.project_docs_self_host_fixture.json`:
  `bc653faa03300249877061c2d5953fe882e528af4f66b487e4a28b6bd82246eb`.
- `git diff --check` PASS; Python source синтаксически разобран через stdlib AST.

Машиночитаемое статическое доказательство сохранено отдельно как
`pr211-acceptance-artifacts/self-host-literal-lookup-static-proof.json`.

## Границы

Production/retrieval, mirror implementation, старые существовавшие до этого slice
questions, downstream corpora, scoring, gold, floors, workflows и labels не менялись.
Нет monkeypatch квалификации, поддельных flags или принятия пустого результата.
Новый positive по-прежнему обязан получить настоящий source-bound read packet;
исходный вопрос остаётся явно непокрытым.

Локальные imports DocAtlas, runtime, pytest, installs, providers и client calls:
**NOT RUN**. Positive результат successor ещё не доказан исполнением. Нужны
независимый review и следующий обычный общий CI на опубликованном SHA.
