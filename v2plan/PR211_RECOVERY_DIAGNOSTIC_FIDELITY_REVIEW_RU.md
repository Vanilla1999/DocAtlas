# PR211: fidelity recovery diagnostics вместо отменённого display cap

Дата: 2026-10-08. Base: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Узкий test-only slice; production, retrieval и evaluator gold не меняются.

## Причина и текущий контракт

В `tests/test_dictionary_exit_literal_needs_mcp.py` три прежних параметра
`test_recovery_diagnostics_do_not_split_or_inherit_clauses` падают исключительно
на проверке длины display fragment `<=220`. Предыдущие assertions в каждом
из трёх cases проходят в core CI 37824782946 на Python 3.11/3.12/3.13.

`recovery._problem_spans` сохраняет исходный вопрос для diagnostics/retry guidance;
это не поисковый запрос, не admission и не generated retrieval lane. Ограничение
числа символов здесь — representation cap. V4_PRODUCT_DECISIONS_RU.md, этап 1,
и NEXT_PARALLEL_IMPLEMENTATION_PROMPT_RU.md, раздел B, явно разрешают миграцию
таких caps на fidelity controls при сохранении действующих guards.

Successor проверяет точный полный список `[question * 30]` вместо проверки
его обрезанной длины. Те же длинные EN/RU вопросы теперь обнаружат truncation,
пропуск повторов, добавленный текст, clause splitting или унаследованные spans.
Ожидание следует из сохранения исходного запроса, а не из текущей длины ответа.

## Сохранённые controls и границы

- Все три исходных concrete node IDs, параметры и имена сохранены.
- Запрещающий monkeypatch semantic clause parser сохранён и действует на все calls.
- Точное равенство короткому исходному вопросу и empty-input negative сохранены.
- Устаревший `query_requirement_spans` остаётся в fixture: его нельзя наследовать.
- Единственная изменённая assertion имеет fidelity successor; остальные восемь
  assertions этого файла, включая indexed MCP citation/authority и `<=800`, прежние.
- Нет новых skip/xfail, исключений inventory, thresholds или source fixtures.
- Frozen retrieval gate 800, output schema gate и read/acquisition guards не меняются.

Independent review и фактический совместный CI этого slice фиксируются отдельно.
PASS исходного SHA не переносится на изменённый файл автоматически.
