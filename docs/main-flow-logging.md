# Логи основного потока

Подробная диагностика по умолчанию выключена. Включение не меняет формат
ответа, источники или число продуктовых запросов.

```sh
doc-atlas --trace query "OAuth tokens" --mode lexical --format json 2>trace.jsonl
doc-atlas --trace context --help
doc-atlas --trace mcp docs-serve 2>trace.jsonl
```

Глобальные `--trace` / `--no-trace` указываются **перед подкомандой**.
Они переопределяют `DOCATLAS_TRACE` на время вызова. Без флага используется
существующая настройка: только `DOCATLAS_TRACE=1` включает трассу; значение
окружения читается при загрузке модуля, поэтому задайте его до запуска процесса.

```sh
DOCATLAS_TRACE=1 doc-atlas --no-trace query "OAuth tokens" --mode lexical
```

Для MCP-клиента можно задать `DOCATLAS_TRACE=1` в окружении серверного процесса.
Диагностика идёт в **stderr**, отдельно от JSON/текстового ответа CLI и MCP stdout.
Обычные ошибки и сторонние сообщения stderr не отключаются флагом `--no-trace`.

## События и границы

- `docatlas_request_start` и `docatlas_request_end` связываются через `request_id`.
  Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms`
  и `trace_incomplete`.
- Покрыты CLI `query`, `context` и публичный диспетчер Docs MCP
  (`operation=call_docs_tool_payload`). Ошибки разбора CLI до входа в callback
  не имеют lifecycle-событий.
- Существующий `docatlas_query_trace` содержит подробную диагностику проекции
  MCP и использует тот же `request_id`. Его previews могут включать данные
  документов; новые lifecycle-события не содержат текст вопроса или документов.
- `success` означает завершение границы вызова, а не достаточность найденных
  доказательств. Возвращённые статусы `error`/`failed` и исключения отмечаются
  как `error`; результат запроса остаётся источником продуктового статуса.
- Ошибка записи диагностики не должна менять ответ. Пропущенное начало
  отмечается `trace_incomplete`; при сбое завершения предпринимается запись
  `docatlas_trace_gap`. Полностью недоступный stderr не позволяет доставить
  даже сообщение о пропуске.

## Проверка

Интеграционные сценарии находятся в
`tests/test_project_context_quality_v2_protocol.py` и
`tests/test_main_flow_logging_integration.py`: реальные документы и SQLite,
публичный MCP-dispatcher и CLI subprocess, OFF/ON/OFF, независимый исходный факт,
сохранение выдачи и корреляция событий. Это не проверка установленного MCP stdio
или production-клиента. Выполнение новых проверок ожидает разрешённого CI.

Обоснование стратегии: [результат, источники и трасса](main-flow-evaluation.md).
