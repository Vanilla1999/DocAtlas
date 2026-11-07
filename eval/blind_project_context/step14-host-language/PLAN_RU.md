# Step14: язык до первого запроса к отвечающей модели

Дата: 2026-11-08. База: `main` после обычного merge PR #249,
`ea045e19a4b1ce452e26b9b85c2d118b4369acc6`.

## Задача и граница

Убрать отдельный шаг отвечающей модели, который только выбирал
`docs_status(action="project", include_language=true)`. Сам публичный read-only
MCP-вызов сохраняется: его выполняет клиент до первого provider request каждого
нового user prompt, через настоящий executor подключённого сервера и его
обычную permission-проверку. Не появляется другой MCP-процесс, поиск по файлам
в обход сервера, автоиндексация или inference для определения языка.

Источник языка — существующие declarations в `docatlas.project-docs.yaml`.
Новых словарей, aliases, таблиц вопрос→файл, классификаторов и translation maps нет.
Сравниваются все поля trusted project binding и scope; в модель попадает только
ограниченная нормализованная подсказка. `unknown`, `mixed`, `partial` не становятся
English. Hash в этом API относится к текущему inspected набору/declarations,
а не к active-index version и не доказывает полноту инспекции. Проверки actual
evidence freshness/authority остаются на существующем retrieval-пути.

Новый режим включается явно: `--language-preflight host-v1` для MCP-профиля.
Отсутствие флага оставляет прежний model preflight; существующие конфигурации и
политики MiniLM/Qwen не переключаются. Shared source-to-draft инструкция,
schemas/constraints, allowlist, source text, выдаваемые capabilities и guards
не меняются.

## Единственный запланированный локальный прогон

Переиспользуется `integrations/opencode-v2-compact/check_profile_client.py`,
настоящий OpenCode **2.2.5**, установленный пакет и ограниченный launcher Step13.
Scripted только внешний provider — это проверка client/transport/permissions,
не запуск Qwen, MiniLM, Terra, не quality/billing эксперимент.

Исходный вопрос и оба документа существующего сценария неизменны:
`Who signs the hand-off record, and may a courier sign it?`
Новые blind/gold вопросы не читаются и не запускаются.

| Сценарий | Максимум provider requests | Настоящие MCP вызовы |
|---|---:|---|
| Прежний concise/model-preflight control | 4 | status, context, issued source read |
| Concise + host-v1 | 3 | host status, context, issued source read |
| Прежний files control | 2 | 0; native in-scope read и отклонённый out-of-scope read |
| Host-v1 + заранее отсутствующие Qwen assets | 2 | host status, context с техническим отказом; без inference/retry |
| Host-v1, declarations отсутствуют | 1 | host status |
| Host-v1, declarations mixed | 1 | host status |
| Host-v1, declarations изменены после создания config: partial | 1 | host status |
| Host-v1, несовпадающий workspace binding | 0 | реальный status из того же проекта, отказ до provider |

Итого: **8 отдельных клиентских сессий, максимум 14 scripted provider requests,
0 model inference**. До них один public `prepare_docs` и один canonical
`get_docs_context` для исходных документов. В клиентских сессиях максимум
12 MCP операций: 7 status, 3 context (включая отказ), 2 source reads.
Client-denied jobs/out-of-scope запросы учитываются отдельно и не должны
дойти до MCP. Прежний concise control нужен для проверки неизменности default
пути после правки builder/plugin и парного сравнения; standard/full legacy
suite повторно не запускается.

Для unknown/mixed/partial меняется только явно объявленная metadata одного
подготовленного fixture-каталога; document bytes, entries и DB остаются теми же.
После каждого сценария восстанавливаются исходные байты каталога; эти изменения
не скрываются под формулировкой «все файлы всё время неизменны».
Отдельной подготовки для language declarations не требуется.
Binding-negative использует тот же подготовленный project/project_id, но
другой реальный workspace_path: это проверяет всю тройку binding без второго
store и без доступа к посторонним документам.

## PASS и ограничения

- Реальный matching status **response** завершён до первого HTTP provider request;
  фиксируются request/response monotonic timestamps, не только начало status.
- Первый model request уже содержит правильный hint и исходный вопрос;
  host status не подделывается под assistant/tool transcript.
- Host-positive требует 3 вместо 4 scripted requests, но тот же реальный набор
  чтений, исходные facts/text/refs/source URI и прежний jobs denial.
- Unknown/mixed/partial переданы как эти состояния; stale generated config не
  хранит старый язык. Это не тест качества определения языка по тексту.
- Несовпадающий binding останавливает prompt до provider; технический retrieval
  failure остаётся error, не превращается в ответ «фактов нет» и не повторяется.
- Applicable project instruction, source-to-draft, исходные schema constraints,
  read-only guards, исходные source bytes и DB сохранены. Все принадлежащие
  прогону процессы остановлены с проверенной identity, без общего `pkill`.
- Фиксируются actual provider/tool counts и отдельно local-tokenizer размеры
  каждого запроса/суммы. Это не provider usage, цена, latency live-модели или
  доказательство превосходства над обычным поиском.

Изменение declarations после config generation проверяет отсутствие build-time
кэша. Оно **не** является доказательством refresh внутри двух prompt одной живой
сессии; такое доказательство не подменяется перезапуском процесса. Реализация
должна привязывать in-memory hint к текущим session ID и user message ID, не
доверять импортированным metadata и не брать прошлый hint при отсутствии текущего.

Первый неуспешный прогон, если случится, сохраняется с реальными counts. Повтор
возможен только после установленной причины и конкретной правки; никакого
подбора вопросов, expected facts или критериев для получения PASS.

## Первая попытка и основание ограниченного повтора

`step14-client.UQbSTF/run-01`: harness FAIL после исполнения всех восьми cases,
**14 scripted provider requests, 0 inference**. Positive client cases уже
проверили исходные документы, инструкции, разрешённые/запрещённые операции и
доставку declared/unknown/mixed/partial. Workspace-negative действительно
получил ответ правильного проекта с чужим workspace binding и не сделал ни
одного provider request. Все owned процессы завершены.

Причина FAIL — наблюдение отказа: CLI OpenCode 2.2.5 выдаёт только
`UnexpectedStatus: 500`; точный `DocumentationLanguagePreflightError` с причиной
`documentation_language_preflight_binding_or_envelope_mismatch` находится в
native журнале `client-data/opencode/log/opencode.log`, в строке с endpoint
того же session ID и `http.status=500`. Harness ошибочно ожидал эту подробность
в CLI stdout/stderr. Это не успешный итог первого harness-запуска и не
необнаруженный product binding failure.

Исправление ограничено instrumentation: потребовать ту же точную причину в
native журнале с matching session/prompt endpoint, наряду с прежними
проверками реального status response, несовпадающего binding, нулевых provider
calls и cleanup. Generic startup failure не принимается. Источники, вопросы,
критерии полноты и product-код не меняются.

После этой правки разрешён один повтор того же bounded roster в новом
`run-02`: максимум14 scripted provider requests, prepare1/canonical1,
те же12 клиентских MCP операций,0 inference. Первый raw run и его input hashes
сохраняются. Это проверка исправленного acceptance до его публикации, не
повторный подбор retrieval или отвечающей модели.
