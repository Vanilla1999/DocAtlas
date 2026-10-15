# PR211: independent review indexed MCP fixture migration

Дата: 2026-10-08. База: `40032f7be3c6d0822e8c25a2e2c53acf9a46aeea`.
Решение: **APPROVE — узкая миграция fixture setup**. Runtime нового patch: **NOT RUN**; требуется совместный CI на опубликованном SHA.

Независимо прочитаны actual diff двух test modules, existing helper `tests/_fixture_member_transaction.py`, cold `LocalMemberService`, member executor и catalog validation. Сравнение выполнено с Git source базы, а не только с author report. Production, helper, evaluator, questions и frozen gold этим review не изменены.

## Проверенный контракт

Обе fixture по-прежнему авторски записывают тот же один README с теми же bytes. Добавленный catalog — конечный literal `README.md`, role overview, project scope, **supporting**, active, **search_only**. Нет `source_of_truth`, code_files, roots, directory scan, inferred query или source selection по ожидаемому answer. Такой catalog не даёт edit/answer authority; исходные assertions продолжают явно требовать `answer_supported is answer_available is edit_ready is False`.

Fixture author отдельно передаёт `("README.md",)` существующему helper. Helper строит полный explicit mutation: confirm true, operation sync_project_docs, exact host storage, catalog/content/entry hashes, cold expected_generation_id None. Он вызывает настоящий member route; не подменяет retrieval, grants, registry, storage validation или результаты.

Storage выбран до создания DB: `<tmp>/home/mcp/members.db`, с настоящим `MemberStoragePolicy`, вне `<tmp>/project`. Cold service не материализован до commit. Helper проверяет mode member_upsert, vectors not requested, exact source count/bytes/content hashes/catalog bindings/project identity, zero deletes/changes и тот же generation/store после materialization. Legacy eager DB, который нельзя усыновить current storage policy, удалён только из fixture setup.

`tests/_fixture_member_transaction.py` побайтно совпадает с базой; helper не обновляет CAS и не повторяет отказавшую запись. Existing explicit member negative/CAS tests не изменены. В обоих тестах отсутствие или подмена источника всё ещё приводит к assertion failure; пустой результат не может считаться PASS.

## Независимая статическая проверка

Стандартной библиотекой `ast` и read-only `git show` проверено:

- Имена, signatures и parameter decorators всех трёх tests совпадают с базой. Concrete roster остаётся **2 + 4 + 3**.
- Оригинальные README write_text calls AST-identical.
- В двух migrated tests всё от `payload, snapshot = gate._call_with_snapshot(...)` до конца тела AST-identical: questions/lookup_queries/handler/snapshot, content checks, запрет answer/edit authority, <=800, citation integrity, qualification rejection.
- Единственные заменённые setup assertions теперь проверяют `sync.status == "success"` реального confirmed member transaction.
- Третий recovery test целиком AST-identical, включая forbidden semantic clause parser и три assertions.
- Assert inventory: первый module **7**, второй **9**; из них **14** исходных result/recovery assertions AST-identical, **2** setup assertions мигрированы.
- `git diff --check` чист для обоих reviewed files.

Уточнение формулировки: у двух fixture test functions изменён setup body; идентичны их names/signatures/decorators и вся result tail. Целый function AST идентичен только у третьего recovery test. Это не влияет на одобрение кода.

## Frozen reviewed hashes

| Path | SHA256 |
| --- | --- |
| tests/test_dictionary_exit_indexed_mcp.py | e558282c12c84da03f4d570a80992d5da9f67c7353424aa058f57c213c1270be |
| tests/test_dictionary_exit_literal_needs_mcp.py | 0d69667639693fd285e1ce869c01dd13f4a3820d5efd57e07b119c193ea6aa43 |
| tests/_fixture_member_transaction.py, unchanged | 87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe |

Blocking findings нет. Этот review подтверждает корректность scope и current-contract setup, но не заменяет фактический PASS шести ранее блокированных cases на новом SHA. Локально runtime/import/provider/client calls не выполнялись.
