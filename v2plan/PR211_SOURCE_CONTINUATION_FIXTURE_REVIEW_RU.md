# PR #211: current transaction для одного source-continuation fixture

Дата: 2026-10-08. База `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Изменён только setup node
`tests/docs/test_source_continuation.py::test_public_handler_binds_reader_to_real_active_sqlite_snapshot`.

SHA256 файла:
`7d7ed1eb76dfbf4edf351e81011124a46422519ede31a8130ce97e12e9deded7`.

Фактический первый barrier в core JUnit CI 37824782946 — PermissionError
legacy `sync_project_docs(..., with_vectors=False)` без explicit mutation grant.
Это подготовка одного authored документа перед read/continuation проверкой,
а не требование восстановить automatic discovery/sync или lifecycle deletion.
Fixture уже имел finite catalog с единственным `docs/jobs.md`; его содержимое,
роль runbook, scope, authority и status сохранены. Catalog не создаётся из glob,
вопроса, oracle или найденных результатов.

Прежний eager service/config внутри project заменён существующим
`indexed_fixture_member_service(tmp_path, monkeypatch, project, ('docs/jobs.md',))`.
Проект теперь находится в `tmp_path/project`, host-selected store — в sibling
`tmp_path/home`, вне project. В оба прежних MCP запроса передаётся тот же новый
project root; question, lookup_queries и scope не изменены. Добавлен только
стандартный `monkeypatch` fixture для временного DOCATLAS_HOME.

Helper не изменён: `tests/_fixture_member_transaction.py`, SHA256
`87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe`.
Он создаёт cold LocalMemberService и выполняет настоящий member transaction:
explicit confirm, host storage path, catalog SHA256, content SHA256 и entry hash
ровно выбранного authored path, explicit cold CAS `expected_generation_id=None`.
Проверяются отсутствие eager materialization/home до записи, успешный
member_upsert, lexical/no-vector режим, точное число новых members, нулевые
changed/deleted, активная generation, policy.validate, точные committed
sources/content/hash/catalog binding/project identity и тот же store после
materialize. Нет retry с обновлённым CAS, direct DB insertion или подавления
PermissionError. Существующие negative consent/hash/CAS/store controls helper
остаются в named-document integration tests.

Прежний setup status-success guard сохранён как `assert sync.status == 'success'`.
Весь AST начиная с первого `payload = call_docs_tool_payload(...)` до конца
node byte-for-byte эквивалентен AST базы. SHA256 этого AST dump без locations:
`0c63a559c9f6addcc994f6925e2e2ccf72d74e58244745d9d6ea220130e8c093`.
В частности, сохранены original-query coverage, actual snapshot attribution,
snippet tampering rejection, forged source_uri rejection, continuation range,
polling text, отдельный read bound <=600 и отказ `source_changed` без snippet
после изменения источника. Runtime/retrieval/source-read production код и
публичные expectations не менялись. Следующий semantic failure, если он есть,
не скрывается этим setup slice.

Статические проверки: только одна function изменена; все остальные bodies и
все decorators/parameter inventories сохранены. Assert inventory 48 → 48;
47 прежних Assert AST-identical, заменён только setup call с тем же ожидаемым
success. Все expressions содержимого записываемых fixture files совпадают.
13 base test nodes сохраняют inventory hash
`0cd1903746caec80f4afd218bd0d22fc51e6d8c9fafa4ebebb9ecc63d77b403e`,
совпадающий с неизменённым `tests/diagnostic_labels.source_continuation.json`.
`ast.parse`, compile без исполнения и `git diff --check` для этого testfile — PASS.

Локальные repository imports, pytest, subprocess runtime, provider/client runs
и installations не выполнялись. Нужны независимый review и обычный CI на
опубликованном SHA; runtime PASS этого node пока не утверждается.
