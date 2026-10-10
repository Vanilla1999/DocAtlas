# PR #211: confirmed preparation для двух indexed MCP fixtures

Дата: 2026-10-08. База `40032f7be3c6d0822e8c25a2e2c53acf9a46aeea`.
Runtime новой версии: NOT RUN; требуется обычный совместный CI.

Изменены только `tests/test_dictionary_exit_indexed_mcp.py` и
`tests/test_dictionary_exit_literal_needs_mcp.py`. В последнем полном CI на f0ed956
шесть concrete cases (2 + 4) останавливаются на legacy sync без mutation grant.
Это подготовка authored README перед настоящим MCP handler, а не проверка
разрешённости старого implicit indexing API.

Обе fixture объявляют конечный catalog с одним literal README.md: overview,
project scope, supporting authority, active, search_only. Нет source_of_truth,
новых source bytes, inferred queries, directory scan или selection из prose.
Используется уже проверенный `indexed_fixture_member_service`: отдельный
host-selected temporary home, cold expected_generation_id=None, confirm=True,
catalog/entry/content hashes, реальный member transaction и SQLite; materialize
выполняется после commit. Helper и его hash/CAS/rejection controls не меняются.

Оригинальные README bytes, вопросы, lookup_queries, public handler и snapshot
не изменены. Все 14 assertions результата сохранены AST-exact: непустой source,
точный command fragment, no answer/edit authority, существующий <=800 token
criterion, citation integrity, qualification rejection и literal recovery guards.
Две setup assertions получили единственную замену: `sync.status == "success"`
теперь относится к результату настоящего confirmed transaction.

Оба прежних module имеют те же 7 и 9 Assert nodes. Имена всех трёх test functions,
их signatures и parameter decorators AST-identical; concrete roster остаётся
2 + 4 + 3 cases. Последние три recovery cases не меняются. Пустой результат
не может дать PASS: исходные положительные content assertions сохранены.

Production, retrieval, frozen gold, текущие gates/thresholds и CI selectors
не меняются. Новых runtime/import/provider/client запусков локально нет.
Проверены AST и `git diff --check`; это не заявление о runtime PASS.

Reviewed source SHA256:

| Файл | SHA256 |
|---|---|
| tests/test_dictionary_exit_indexed_mcp.py | e558282c12c84da03f4d570a80992d5da9f67c7353424aa058f57c213c1270be |
| tests/test_dictionary_exit_literal_needs_mcp.py | 0d69667639693fd285e1ce869c01dd13f4a3820d5efd57e07b119c193ea6aa43 |
