# PR211: текущая граница «evidence is data» в P1.6

## Что меняется и почему

Исторический evaluator вызывал только select_evidence, ожидал старое
expected_supported=true для project_rule и записывал tool/lifecycle/authority/
credentials как постоянные False. Это не доказывало текущее поведение публичной
выдачи. Миграция вводит отдельный current report; исторические результаты и
ожидания остаются доступны для сравнения.

Неизменны:

- evidence_is_data_protocol.json, Git blob 9f05de62916edff051e5d6814ff17a81f2e5e978;
- исторический results/evidence-is-data.json, blob c43a53aa91357fee3f76e3604f91123d54065689;
- все шесть исходных вопросов, candidate_text, source, authority, source_class,
  public_requirements и исторические expected_supported/assignment_sources;
- шесть существующих имён самостоятельных oracle self-tests.

Эти две frozen blob identities проверяются до каждого current derive/verify.
Новый crosswalk связывает каждый исходный case с текущим read-only контрактом.
Полный положительный факт — первые 32 символа неизменного положительного окна —
должен сохраниться в public payload, structuredContent и JSON text fallback.
Этот факт не добавляется в вопрос или public_requirements.

## Слой измерения

Fixture подменяет только retrieval boundary исходным _candidate(case). Дальше
вызываются реальные call_docs_tool_payload, handle_context_tool,
project_docs_answer, validate_model_visible_projection и серверный
_mcp_tool_result с установленными mcp.types.TextContent/CallToolResult.
JSON сериализуется реальной моделью MCP и затем разбирается обратно.

Наблюдаются фактические:

- dispatcher calls и все аргументы facade get_docs_context;
- projector question, исходные candidates/requirements/trust, текущая
  document_content_policy и наличие typed control fields;
- validation payload, полный same-call snapshot и ошибки;
- public payload, оба доставленных payload, envelope metadata, SHA256 и bytes.

Это public-delivery contract fixture. Он не доказывает indexed retrieval,
stdio/client session или автономный ответ модели. Production-код этот slice
не изменяет; protocol/report утверждают только эту границу измерения.

## Независимый oracle

Oracle строит ожидаемые source/child/parent/display hashes и public-source hash
из frozen protocol, отдельно от production candidate builder. Каждый из шести
source windows сохраняется целиком. Историческое metadata authority связывается
с исходным candidate, но не считается доказанным project_rule или разрешением
на действия.

Текущая выдача обязана иметь cite_only/retrieval_only, не давать answer/edit/
proof coverage, не менять исходный вопрос, не вызывать дополнительный tool,
не включать network/preparation/refresh flags. Проверяется реальная
cited_untrusted_document_data policy; это не пять заранее заполненных False.

Весь report сохраняется без raw hostile document bodies. Строки из source body
заменяются ссылками на проверяемые диапазоны frozen case и SHA256. Полный payload
и snapshot восстанавливаются в памяти. Отдельный ledger порядка ключей сохраняет
реальный порядок JSON fallback даже после sort_keys=True при сохранении report.
Verifier пересчитывает наблюдения, source bindings и обе MCP wire receipts.
Скрытый/добавленный ledger, подмена диапазона/hash или потеря ключей не проходят.
Неизвестный свободный текст остаётся opaque digest и делает observation
неподтверждённым; исключения также сохраняются только как тип и SHA256.

Фальшивый credential marker может присутствовать внутри точной untrusted
цитаты. Его перенос в answer/control field отклоняется; raw marker не
появляется в persisted report или console diagnostics.

## Усиление тех же шести self-tests

Контроли меняют фактические captures, затем повторно вызывают реальный validator
и MCP serializer. Проверяется независимый oracle над тем же форматом report:

- корректный по production schema always-empty результат не проходит полный факт;
- легитимный факт удалён, исходный hostile tail сохранён: self-consistent
  snapshot проходит production validator, frozen full-fact oracle отклоняет;
- поддельный source path с пересчитанным hash и snapshot проходит проверку
  внутренней согласованности, но не frozen provenance; отдельный неверный hash
  также отклоняется;
- additional prepare_docs dispatch, network/preparation/refresh flags,
  answer/edit, lifecycle/action/authority fields и credential вне цитаты;
- скрытые source-window/call/key-order ledgers, raw marker, private path,
  завышенные claims и подменённые imported-runtime/proof manifests;
- сохранение и чтение sorted JSON не меняет оригинальные wire receipts.

Положительный baseline и каждый directed control печатаются по существующим
именам. До фактического CI ни один из них не объявляется PASS.

## CI и оставшаяся acceptance

Runner всегда пишет новый current report до проверки verdict. По умолчанию это
results/evidence-is-data.current.json; перезапись frozen historical report
отклоняется. CI сохраняет report в RUNNER_TEMP и загружает artifact при любом
verdict. Quality, oracle/report integrity, два прежних Agent Developer
adversarial gates и syntax/formatting имеют отдельные шаги; прежние gates не
удалены и их FAIL не маскируется.

Никакого output ceiling 800/6144 или нового token cap нет. Bytes, reported tokens
и обе wire costs измеряются; fidelity/authority/source guards остаются обязательны.

p1_closure.py пока читает старые committed v1 отчёты P14/P15/P16.
Его исторический green не заменяет проверку новых current reports. Подключение
current evidence к финальному closure/acceptance требуется отдельным согласованным
slice; здесь старые факты и history не перезаписываются.

## Проверка этого изменения

Подготовлены GitHub source blobs для независимого review. Выполнены удалённое
чтение текущих producer contracts, сверка frozen identities и точного roster
шести self-test имён. Локальные импорты, Python/pytest/AST, установка пакетов,
серверы, модели и provider calls не запускались. Runtime verdict ожидается
только от CI на опубликованном конечном SHA.
