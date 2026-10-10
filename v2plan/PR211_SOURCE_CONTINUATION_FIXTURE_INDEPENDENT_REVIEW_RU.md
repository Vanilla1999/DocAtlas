# PR #211: независимый review source-continuation fixture

Дата: 2026-10-08. Verdict: **APPROVE** для узкого setup slice; runtime
этого изменённого node требует совместного CI на опубликованном SHA.
База: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.

Независимо проверены точные SHA256:

- `tests/docs/test_source_continuation.py`:
  `7d7ed1eb76dfbf4edf351e81011124a46422519ede31a8130ce97e12e9deded7`.
- Author report `v2plan/PR211_SOURCE_CONTINUATION_FIXTURE_REVIEW_RU.md`:
  `9afbfc2d57165ceaafb0a9ae8b92f0c5ec353a796fc19c93d6a58440739f0c27`.
- Неизменённый `tests/_fixture_member_transaction.py`:
  `87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe`.

Изменён только setup
`test_public_handler_binds_reader_to_real_active_sqlite_snapshot`: legacy
implicit sync заменён существующим настоящим confirmed member transaction.
`tmp_path/project` и host-selected `tmp_path/home/mcp/members.db` разделены;
временный DOCATLAS_HOME удерживается pytest monkeypatch до завершения всех
запросов и resource reads. Возвращённый materialized service сохраняет тот же
MemberStoragePolicy и store, а текущий MCP dispatcher возвращает именно этот
service после проверки project/store ownership. Поэтому reader/cursor остаются
в той же действующей service lifetime. Новый service между quote и read не
создаётся, mock reader/store или прямой SQL insert не вводится.

Consent и CAS не выводятся из обнаруженных файлов: caller передаёт единственный
authored `('docs/jobs.md',)`, helper составляет explicit confirm, точный host
storage path, catalog/content/entry hashes и cold
`expected_generation_id=None`. Выполняется настоящий sync; helper проверяет
committed generation, точные SQLite source/content/hash/catalog/project-identity
bindings, нулевые changed/deleted и lexical/no-vector режим. Повторного запроса
с обновлённым CAS нет. Существующие отрицательные проверки confirmation,
hashes, storage, отсутствующего/stale CAS и unselected member в
`tests/test_named_document_context_integration.py` остались byte-identical базе.

Все аргументы записи corpus/pyproject/catalog AST-identical базе. Catalog уже
имел `authority: source_of_truth`; slice сохраняет роль runbook, scope project,
active status и тот же текст, не повышает authority и не строит catalog из
результатов поиска. Вопрос, lookup queries, scope и real SQLite route сохранены.

Независимый AST compare подтвердил: изменена ровно одна function; все остальные
module statements и decorators сохранены. 48 assert nodes остаются 48,
47 прежних Assert AST-identical; единственная замена — setup success assertion
после нового transaction. Весь хвост от первого `payload =
call_docs_tool_payload(...)` до конца function AST-identical с SHA256
`0c63a559c9f6addcc994f6925e2e2ccf72d74e58244745d9d6ea220130e8c093`.
Сохранены exact original-query coverage и snapshot attribution, отказ при
snippet tampering и forged source URI, следующий line range, требуемый polling
text, отдельный read bound `<=600`, fresh reference перед изменением файла и
`source_changed` без snippet после изменения. Reader/gateway production
проверяют текущие catalog/active-generation bindings до hydration, digest
прочитанных bytes и повторную авторизацию; эти файлы не менялись.

Остальные controls module не затронуты: одноразовые cursors, неизвестные/forged
URI, TTL/read/range bounds, catalog/index/cross-project revocation, symlink и
delete barriers, отсутствие hydration при отказе, targeted-range boundaries.
13 **base** test IDs (до раскрытия parameterization) сохраняют inventory hash
`0cd1903746caec80f4afd218bd0d22fc51e6d8c9fafa4ebebb9ecc63d77b403e`, независимо
сопоставленный с неизменённым diagnostic manifest. Параметры не менялись.

Проверки review: stdlib hash/AST compare, compile без исполнения,
`git diff --check` — PASS. Repository imports, pytest, server subprocesses,
provider/client calls и installations не выполнялись. Этот review подтверждает
корректность миграции fixture setup и сохранность assertions; он не объявляет
runtime PASS и не скрывает возможный следующий semantic failure общего CI.
Production, retrieval, gold, acceptance thresholds и CI gates не изменены этим
slice. Замечаний, требующих правки до совместного CI, нет.
