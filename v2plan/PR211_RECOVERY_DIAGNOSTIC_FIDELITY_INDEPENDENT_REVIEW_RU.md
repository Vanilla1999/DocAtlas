# PR211: independent review recovery diagnostic fidelity

Дата: 2026-10-08. База: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Решение: **APPROVE**. Это узкая test-only миграция representation cap; runtime нового slice **NOT RUN** до совместного CI.

Независимо прочитаны actual diff, current `recovery._problem_spans`, оба его diagnostic callers, `NEXT_PARALLEL_IMPLEMENTATION_PROMPT_RU.md` (общее разрешение representation/output cap migrations и раздел B) и `V4_PRODUCT_DECISIONS_RU.md` (этап 1, явная миграция cap tests с сохранением fidelity/guards).

Producer сохраняет исходный вопрос после удаления внешнего whitespace, возвращая один diagnostic fragment либо пустой список для пустого input. Его callers помещают fragment в recovery diagnostics; это не новое retrieval направление, не acquisition, не semantic proof и не разрешение на действие. Прежний `<=220` проверял длину представления, поэтому его замена входит в разрешённую cap migration. Ожидание `[question * 30]` следует из контракта сохранения исходного запроса; все три параметра не имеют внешнего whitespace, поэтому оно не конфликтует с действующим `.strip()`.

Проверены read-only Git source базы, AST и точная текстовая замена:

- Весь file diff — ровно одна assertion: `len(...[0]) <= 220` заменено на точное равенство полному списку `[question * 30]`.
- Все **8 остальных assertions** и остальной source file побайтно неизменны после подстановки этой одной строки. В частности, indexed MCP contents, citations, отсутствие answer/edit authority и существующий **<=800** не меняются.
- Все **3 recovery node IDs**, EN/RU параметры, signatures и decorators сохранены.
- Запрещающий semantic clause parser monkeypatch, exact short-question guard, empty-input negative и stale `query_requirement_spans=(("old", ...),)` остаются на месте.
- Длины трёх long inputs — **1920 / 1770 / 1110 символов**. Новый equality отвергает truncation до 220, пропущенные повторы, добавленный текст, дополнительные/разделённые fragments и унаследованный `old` span. Проверяется весь список, а не только его первый элемент.
- `docmancer/docs/application/recovery.py` побайтно совпадает с базой; production/retrieval, fixtures, gold, thresholds, inventory и skip/xfail не изменены.
- `git diff --check` чист для reviewed test file.

Frozen reviewed hashes:

| Path | SHA256 |
| --- | --- |
| tests/test_dictionary_exit_literal_needs_mcp.py | 3fd5357109a722359d9d631982fc29f380a280738327dfc6df37085c3dc8b828 |
| v2plan/PR211_RECOVERY_DIAGNOSTIC_FIDELITY_REVIEW_RU.md | 37fab8131276c5dd452c6428639f2917be0e4078bd3b28f61b86c8dfd3c33808 |
| docmancer/docs/application/recovery.py, unchanged | aacede21bc010ed4e21967f94ecb6bc3bb53663b17582633864a41f222f67552 |

Blocking findings нет. Одобрение относится к контракту и границам этой единственной test migration, а не к PASS полного recovery/downstream gate. Локальные production imports, runtime, установки, provider/client calls не выполнялись; фактический результат трёх cases устанавливается следующим совместным CI.
