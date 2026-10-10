# PR211: независимый review диагностики guard fixtures

Дата: 2026-10-08. Base `03583656617336a746e9192249467017d6131f29`.
**Вердикт: APPROVE** для окончательных bytes:

- `tests/docs/test_context_completion_guards.py`: SHA-256
  `1d52c712f23b5c50745315cf49df6bf5eee96d3007ddb3d03b6e6ecce6373b29`.
- `tests/docs/test_query_block_guards.py`: SHA-256
  `a737f1c8fc3af21a623c99d135cd45f70f5830d5b9be351ea6589d8fbb7c872f`.

Это diagnostic-only изменение, не исправление 47 setup errors и не утверждение
о работоспособности их downstream guards. В actual `4320a68` JUnit остаются
24 ERROR и 23 ERROR соответственно: index_project завершился, но обращение
к отсутствующему projector stage дало IndexError. В XML нет ни одного
system-out/system-err block; возвращённый public payload там не показан.
Конкретная upstream причина по этим данным неизвестна.

Прочитаны весь diff и авторский report, `observe_call`, MCP dispatcher,
`build_mcp_error_payload` и соответствующий producer flow. Observer возвращает
dict payload и stages с list values; он действительно оборачивает используемый
`context_tools.project_docs_context`. Пустая trace может означать выход раньше
этой точки; добавленные assertions не объявляют конкретную гипотезу фактом.

В первую версию review внесён один finding: стандартный MCP failure помещает
reason/message в `payload.error`, а не в top-level поля. Окончательный diff
исправляет это узким whitelist `error.reason_code`, `error.message`,
`error.exception_type` только при dict error. Он не выводит whole error,
traceback, hints, sources или snapshot. Иначе типизированный early error снова
оставил бы настоящий reason невидимым.

В каждой fixture добавлен ровно один assertion перед прежним `[0]`. При
присутствующем stage первоначальный return и дальнейшие действия прежние;
при отсутствии setup по-прежнему завершается ошибкой до test body, теперь с
публичными status/kind/reason/message/operational reason, confirmation/hard-stop,
whitelisted error и числами sources/stages. Нет PASS/skip/xfail fallback,
retry, дополнительного запроса, source read или синтезированного projector input.

Stdlib AST сравнение против base подтвердило: удаление только нового diagnostic
assertion и возврат имени `_` вместо `payload` у первого observer call делает
обе fixtures AST-exact исходным. Все остальные module AST nodes совпадают.
Исходные test bodies, collection names/decorators, вопросы, corpus/gold,
catalog preparation, scope, существующие patches, return values и guard
assertions не меняются. Hashes выше независимо сверены после исправления
nested-error finding; `git diff --check` чист.

Public error message здесь — уже возвращённое диагностическое поле; новая
проверка не добавляет чтения исходных документов и не предоставляет consent
или authority. Причина следующего actual failure должна анализироваться
отдельно: эти assertions не разрешают менять deferred retrieval, thresholds,
gold, gates или semantic expectations ради PASS.

Repository modules не импортировались; pytest, services/providers/clients,
локальные runtime pilots и installations не запускались. Runtime финальных
bytes **NOT RUN**. Следующий обычный CI опубликованного SHA должен показать
фактический upstream reason; результаты предыдущего HEAD на него не переносятся.
