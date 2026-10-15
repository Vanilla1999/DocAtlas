# PR #211: stdio harness и явный advanced surface

Дата: 2026-10-08. Harness/test-only slice; не runtime/merge/release approval.
Исходный checkpoint HEAD: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Контракт compact default surface введён commit `4ed1abd`; production/retrieval,
authored corpus, запросы полной матрицы и числовые acceptance thresholds не меняются.

## Дефект harness

`scripts/docs_mcp_stdio_smoke.py` запускал default server, но передавал
`context_format="patch_context"` и ожидал execution-level `permission_denied`.
После compact-surface change это поле отсутствует в default input schema,
включая значение `null`. MCP SDK может отвергнуть запрос до application callback
и вернуть обычный `Input validation error: ...` TextContent. Общий JSON decoder
в таком случае выдавал `JSONDecodeError` до проверки нужного контракта.

Точная SDK форма проверена read-only по первичному коду
[MCP Python SDK v1.29.0 — lowlevel/server.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.29.0/src/mcp/server/lowlevel/server.py),
версия совпадает с `uv.lock`. `call_tool(validate_input=True)` валидирует
`tool.inputSchema` до callback; `_make_error_result` возвращает один TextContent
и `isError=True`, без structured content. Runtime этой версии здесь не запускался.

Prepared matrix также отправляла patch/null в default session. Миграция
направляет существующие проверки в явно включённый подходящий surface.

## Разделение sessions

Для structured и text transport используются отдельные private fixtures,
как и раньше. Внутри каждого transport sessions теперь разделены:

| Session | Условие и проверка |
|---|---|
| Cold advanced | Startup `DOCATLAS_MCP_ADVANCED_TOOLS=1`; ровно 9 ожидаемых tools, advanced format/schema; omitted/null/patch сохраняют cold storage denial |
| Cold default | Startup advanced=0 и admin=0; ровно 3 tools; поле format отсутствует; null/patch/docs_answer/unknown отвергаются validation boundary |
| Confirmed default preparation | Прежний explicit member grant, пустой store до approval, положительный docs result с цитатами после success |
| Restart default | Прежний generation/CAS/repeat/no-derived-write contract; положительные docs и повторная format rejection на подготовленном store |
| Restart advanced | Та же полная prepared patch matrix, после отдельной inventory/schema проверки |

Cold advanced исполняется первым, чтобы не подготавливать store до cold negative
проверок; confirmed preparation остаётся в default session. `--read-only`
заканчивается после cold sessions и сохраняет явное NOT RUN для lifecycle,
partial/complete, большого evidence, scope/version acceptance.

Default `TOOLS` остаётся literal set из трёх имён: его AST читает
`scripts/release_request.py`. CLI, установленный console script, запрет source
`PYTHONPATH` в installed smoke и import-origin assertions сохраняются.
Source test использует свой явный checkout `PYTHONPATH` и проверяет origin;
это не installed evidence. Patch-only source trace требует явный patch argument
и использует explicit advanced surface без изменения retrieval arguments.

## Error handling и сохранённые guards

`payload`/`text_payload` остаются строгими JSON decoders с прежним structured/text
контрактом. Новый rejection validator применяется только к запросу, который
предварительно отвергнут доставленной input schema по `additionalProperties`.
Он требует `isError=True` и принимает ровно две формы:

- точное `Input validation error: <message>` сообщение для этой schema error;
- JSON `status=failed`, `reason_code=validation_error`, `phase=validation`,
  `tool=get_docs_context`, без sources и положительных authority/answer flags.

`permission_denied`, execution failure, другое сообщение, произвольный non-JSON,
успешный wire или delivered sources не считаются правильным validation rejection.
`wire_form` в отчёте описывает наблюдение, а не подменяет returned docs payload.

Не ослаблены nonempty/cited-content проверки, точные hashes/spans, immutable
fixture member state, initial/repeated grant/CAS, library lineage/version/root
отказы и full patch validator. Матрица сохраняет original complete/partial/scope/
version/large запросы, строгий `>32768` unique nonoverlap bytes gate и BLOCKED
при upstream failure. Deferred retrieval не исправлен и не waived.

Старые report prefixes и ключи сохранены; добавлены `surface_mode` и
`default_format_rejections`. `docs_null` в prepared matrix теперь относится
только к явно advanced session. Byte measurements по-прежнему не объявляются
model token counts или автоматической сертификацией client visibility.

## Проверка и пределы

В `tests/test_docs_mcp_stdio_delivery.py` расширены существующие nodes:
environment isolation, строгие negative decoder controls и source stdio
default/advanced sessions с положительной patch delivery после preparation.
Остальные source/lineage/span/library/large fidelity guards сохранены.

Выполнены AST parse, `git diff --check`, static сверка diagnostic roster
(20 base nodes, hash MATCH), проверка literal трёх-tool release contract и
лимита 1000 строк. Новых pytest nodes нет, manifest не менялся.

Pytest, project imports, Git/server subprocesses и installed smoke в этой среде
не выполнялись: полные runtime dependencies отсутствуют. Runtime dependencies
не скачивались/не устанавливались, permissions не обходились. Живое подтверждение wire error form, source/installed
delivery и обязательных CI/downstream gates требуется на конечном SHA в
подготовленной fixture-only среде. Этот slice не объявляет эти gates пройденными.
