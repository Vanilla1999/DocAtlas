# Fresh valid file baseline: independent final-answer review

Source: `/tmp/opencode/terra-step10-prepared/{L0,L2}/file-current`. All 16 completed sessions used real permitted file reads/search. Historical denied-access baseline remains separate.

## Result

{
  "sessions": 16,
  "completed_trajectories": 16,
  "usage": {
    "input": 138621,
    "output": 9315,
    "reasoning": 0,
    "cache_read": 31232,
    "cache_write": 0,
    "input_with_cache": 169853,
    "steps": 48,
    "top_level_tool_calls": 50,
    "top_level_tool_errors": 0,
    "reported_nested_tool_calls": 0
  },
  "facts_pass": 42,
  "facts_total": 46,
  "facts_partial": 4,
  "citations_supported": 45,
  "answers_pass": 12,
  "sessions_with_retrieval": 16,
  "comparison_valid": true,
  "seconds_sum": 295.57
}

Semantic paraphrases count, but all material qualifiers in each frozen required fact must appear in the final answer for binary PASS. PARTIAL counts as zero, with exact omitted qualifier recorded. A citation to complete source text does not repair omitted answer content. Citation support is graded separately and can PASS for a partial answer. Alternative independently checked source passages may support the same fact.

Four partial facts: both T15 answers omit retention of structuredContent/content; L2 T12 omits the no-reconcile/no-repository-write read guarantee; L0 T19 omits the pinned-binary qualifier. These are final-answer omissions even where the relevant source was retrieved and cited.

| Corpus/case | Facts | Supported fact citations | Input | Cache read | Output | Reasoning | Tools |
|---|---:|---:|---:|---:|---:|---:|---:|
| L0/T01-en | 3/3 | 3/3 | 4863 | 0 | 379 | 0 | 4 |
| L0/T01-ru | 3/3 | 3/3 | 3967 | 1280 | 402 | 0 | 4 |
| L0/T02-ru | 3/3 | 3/3 | 10415 | 0 | 842 | 0 | 2 |
| L0/T05-ru | 2/2 | 2/2 | 3653 | 1536 | 400 | 0 | 2 |
| L0/T10-ru | 3/3 | 3/3 | 5519 | 1024 | 622 | 0 | 3 |
| L0/T12-ru | 3/3 | 3/3 | 9765 | 1280 | 944 | 0 | 5 |
| L0/T15-en | 1/2 | 2/2 | 6412 | 0 | 458 | 0 | 3 |
| L0/T19-ru | 3/4 | 4/4 | 4864 | 2944 | 407 | 0 | 2 |
| L2/T01-en | 3/3 | 3/3 | 9470 | 0 | 265 | 0 | 2 |
| L2/T01-ru | 3/3 | 3/3 | 6870 | 3584 | 476 | 0 | 4 |
| L2/T02-ru | 3/3 | 3/3 | 9377 | 0 | 835 | 0 | 2 |
| L2/T05-ru | 2/2 | 2/2 | 11318 | 16512 | 564 | 0 | 3 |
| L2/T10-ru | 3/3 | 3/3 | 7495 | 1792 | 719 | 0 | 4 |
| L2/T12-ru | 2/3 | 2/3 | 29729 | 0 | 970 | 0 | 5 |
| L2/T15-en | 1/2 | 2/2 | 6681 | 1280 | 583 | 0 | 4 |
| L2/T19-ru | 4/4 | 4/4 | 8223 | 0 | 449 | 0 | 1 |

## L0/T01-en

What is expected of me when I submit a pull request to DocAtlas?

### Actual final answer

When submitting a PR to DocAtlas:

- Name your branch `feat/<topic>` or `fix/<description>`.
- Run the full test suite before opening the PR: `pytest tests/ -v` on Linux/CI, or `arch -arm64 .venv/bin/python -m pytest tests/ -v` on macOS.
- Include tests for new connectors or fetchers where practical.  
  [CONTRIBUTING.md:45–63](CONTRIBUTING.md#L45-L63)

New contributors are also encouraged to read the README, contribution guide, documentation index, and project map. [CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)

If your change affects documentation, note that the PR’s GitHub Actions summary includes an advisory report highlighting module docs needing review or missing maintained documentation; documentation edits are left to an explicit, reviewable change. [README.md:188](README.md#L188)

### Required facts and citations

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention. Answer excerpt: `feat/<topic>` or `fix/<description>`
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing. Answer excerpt: Run the full test suite before opening the PR
- **T01.F3: PASS; citation PASS.** Requires tests for new connectors/fetchers where practical; Russian L0 source-provider wording is a faithful contextual paraphrase. Answer excerpt: Include tests for new connectors or fetchers where practical.

## L0/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

### Actual final answer

При отправке pull request в DocAtlas от вас ожидается следующее:

- Назовите ветку `feat/<тема>` или `fix/<описание>`.
- **До открытия PR запустите полный набор тестов**: на Linux/CI — `pytest tests/ -v`; на macOS в руководстве приведена команда `arch -arm64 .venv/bin/python -m pytest tests/ -v`.
- Для новых коннекторов или источников данных добавьте тесты там, где это практически возможно. [CONTRIBUTING.md, строки 45–63](CONTRIBUTING.md#L45-L63)

Новым участникам также рекомендуют сначала прочитать `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md`. [CONTRIBUTING.md, строки 7–11](CONTRIBUTING.md#L7-L11)

В просмотренном руководстве не указаны требования к шаблону или описанию PR и к числу одобрений.

### Required facts and citations

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention. Answer excerpt: `feat/<тема>` или `fix/<описание>`
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing. Answer excerpt: До открытия PR запустите полный набор тестов
- **T01.F3: PASS; citation PASS.** Requires tests for new connectors/fetchers where practical; Russian L0 source-provider wording is a faithful contextual paraphrase. Answer excerpt: Для новых коннекторов или источников данных добавьте тесты там, где это практически возможно.

## L0/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

### Actual final answer

Безопаснее использовать **`doc-atlas clear-index`**, а не более широкую команду `doc-atlas clear`: первая удаляет производное состояние индекса, сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы. Без `--apply` она только показывает план. [`docs/index-cleanup.md:3–15, 83–85`](docs/index-cleanup.md#L3-L15)

### Очистка индекса одного проекта

1. Убедитесь, что `docatlas.yaml` указывает на отдельный каталог `.docatlas` этого проекта. Если проект использует общий индекс, `project-local` откажется удалять из него строки: определять их принадлежность догадкой небезопасно. [`docs/index-cleanup.md:17–20, 57–62`](docs/index-cleanup.md#L17-L20)

2. Получите и изучите предварительный план:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --format json
   ```

   Проверьте перечисленные объекты, предупреждения и блокировки; сохраните `plan_digest`. Остановите Docs MCP-сервер и процессы синхронизации, использующие то же хранилище. [`docs/index-cleanup.md:22–32`](docs/index-cleanup.md#L22-L32)

3. Примените именно проверенный план:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --plan-digest <digest-from-preview> \
     --apply \
     --format json
   ```

   Если план или характеристики целей изменились, применение будет отклонено до разрушительных перемещений — тогда нужно заново получить и проверить план. [`docs/index-cleanup.md:34–41, 87–90`](docs/index-cleanup.md#L34-L41)

В план могут входить SQLite и его служебные файлы, извлечённые документы, принадлежащие проекту кэши и подтверждённо управляемый DocAtlas локальный каталог Qdrant. Исходники и `docatlas.yaml` не являются целями очистки; индекс проектных документов можно позже восстановить через `prepare_docs(action="sync_project_docs")`. [`docs/index-cleanup.md:43–55`](docs/index-cleanup.md#L43-L55)

### Если индекс общий

`--scope global` сбрасывает производные индексы под разрешённым DocAtlas home, **не только индекс одного проекта**. Сначала проверьте план командой `doc-atlas clear-index --scope global --format json`, затем при согласии примените его с `--plan-digest <digest-from-preview> --apply --format json`. Для независимой очистки проектов документация предлагает отдельные project-local конфигурации. [`docs/index-cleanup.md:57–80`](docs/index-cleanup.md#L57-L80)

**Не обходите предупреждения вслепую:** `--allow-incomplete` лишь подтверждает, что указанное непроверенное состояние векторов или кэша останется; удаление удалённых коллекций Qdrant оно не разрешает и блокировку живым процессом не снимает. Перед окончательным удалением объекты перемещаются в карантин на той же файловой системе; при ошибке перемещения уже перемещённые объекты восстанавливаются. [`docs/index-cleanup.md:90–100`](docs/index-cleanup.md#L90-L100)

### Required facts and citations

- **T02.F1: PASS; citation PASS.** Names clear-index, distinguishes preview from --apply, and tells the user to review a bounded explicit plan before deletion. Answer excerpt: Без `--apply` она только показывает план.
- **T02.F2: PASS; citation PASS.** Explains the global/shared local-index scope and expressly preserves configuration, contrasting clear-index with broader clear. Answer excerpt: сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы.
- **T02.F3: PASS; citation PASS.** Binds execution to the reviewed plan_digest, including a --plan-digest example and stale-plan refusal. Answer excerpt: Примените именно проверенный план:

Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.

## L0/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

### Actual final answer

Верификация проверяет **установленную интеграцию и её MCP-поведение**, но не весь пользовательский сценарий работы модели.

- Скрипт `eval/project_binding/installed_stdio.py --layout unbound|black|mixed` задействует установленный wheel, реальный project-installer, stdio MCP, SQLite и MiniLM. В привязанных конфигурациях он проверяет запрос только с вопросом, совпадение результата с запросом с явным корнем, отклонение привязок к подпапкам, исходный текст и его координаты, а также неизменность источников и индекса. Конфигурация `unbound` проверяет регрессию отсутствующей цели. [docs/PROJECT_BINDING.md:72–79]
- Это **детерминированные сценарии установленного MCP**, а не автономные запуски OpenCode с моделью и не тесты расхода токенов. Поэтому их успех сам по себе не доказывает, как автономный агент выполнит задачу или сколько токенов потратит. [docs/PROJECT_BINDING.md:74–79]
- Отдельно: сама установка лишь привязывает цель; она не индексирует документы и не подтверждает готовность проекта. А указанный каталог модели MiniLM сам по себе не доказывает, что модель загрузилась или участвовала в работе. [docs/PROJECT_BINDING.md:16–23, 60–65]

### Required facts and citations

- **T05.F1: PASS; citation PASS.** Explicitly lists installed wheel, actual installer, stdio MCP, SQLite and MiniLM. Answer excerpt: установленный wheel, реальный project-installer, stdio MCP, SQLite и MiniLM
- **T05.F2: PASS; citation PASS.** Explicitly excludes autonomous OpenCode/model execution and token benchmarking from the verification claim. Answer excerpt: не автономные запуски OpenCode с моделью и не тесты расхода токенов

## L0/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

### Actual final answer

Предлагается **расширить существующий интеграционный сценарий** и дважды провести один и тот же исходный пользовательский вопрос через настоящий публичный API, CLI или MCP — предпочтительно установленного пакета. Данные должны быть изолированы, а retrieval, selection, storage и validation — реальными. Это предложение проверки, а не отчёт о её успешном прохождении. [`docs/main-flow-evaluation.md:3–5, 17–19`]

1. **До запуска подготовить независимый эталон:** вопрос, версии корпуса, обязательные факты и дословные фрагменты, допустимые источники и их hash/span, scope и ожидаемые изменения состояния. Эталон берётся из документов и требований, а не из ответа проверяемого кода. [`docs/main-flow-evaluation.md:21`]
2. **Выполнить две попытки — logging off и on** — из одинаковых исходных состояний, включая индекс, cache, права и consent. Ответ первого запуска не используется как эталон для второго. [`docs/main-flow-evaluation.md:22`]
3. **Проверить каждую попытку независимо, затем сравнить их:** факты и цитаты с документами, выбранные источники, scope/version, результат и изменения состояния. Два одинаковых неверных ответа не означают PASS; переключение логов не должно менять права, источники, побочные действия или число продуктовых вызовов. [`docs/main-flow-evaluation.md:23`]
4. **Проверить диагностику:** при on трасса должна связывать этапы вопроса и помогать локализовать сбой, явно отмечая пропуски; при off подробная трасса отключена. В MCP диагностика отделяется от protocol stdout. Событие или `exit 0` не заменяют проверку результата и состояния. [`docs/main-flow-evaluation.md:24`]

Внутренние mocks применять не предлагается; если подменён внешний транспорт, это нужно указать, поскольку такой запуск не доказывает работу живого провайдера. Одна пара off/on также не доказывает общую надёжность недетерминированного агента. [`docs/main-flow-evaluation.md:26, 39–41`]

### Required facts and citations

- **T10.F1: PASS; citation PASS.** Reproduces one original user question through real public API/CLI/MCP, with real components. Answer excerpt: один и тот же исходный пользовательский вопрос через настоящий публичный API, CLI или MCP
- **T10.F2: PASS; citation PASS.** Requires log-off/on runs from identical initial index/cache/permissions/consent states. Answer excerpt: logging off и on
- **T10.F3: PASS; citation PASS.** Requires independent checking of both outcomes and parity; explicitly rejects two identical wrong answers as PASS. Answer excerpt: Два одинаковых неверных ответа не означают PASS

## L0/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

### Actual final answer

MCP-сервер DocAtlas работает с документацией собственного репозитория как с **явно разрешёнными источниками для поиска**, а не как с файлами, которые он может свободно обходить или изменять.

1. **Состав источников задаётся каталогом.** В `docatlas.project-docs.yaml` документы перечисляются по буквальным относительным путям. Наличие `README`, каталога `docs/` или ссылки на файл само по себе не разрешает его читать. Например, в каталоге самого DocAtlas перечислены и описание MCP-сервера, и руководство по работе с документацией проекта. Невалидный каталог блокирует поиск и синхронизацию, не очищая существующий индекс. [docs/project-docs-mcp-workflow.md:23–28, 52–59; docatlas.project-docs.yaml:113–120, 129–136]

2. **Запрос начинается с контекста.** Клиент вызывает `get_docs_context` с вопросом и путём проекта. Можно ограничить поиск документацией всего проекта, конкретного модуля или обоих уровней через `scope`; для модуля нужен точный `module_path`. Чтение само по себе не обновляет индекс и не меняет репозиторий. [docs/mcp-docs-server.md:26–40, 82–87; docs/project-docs-mcp-workflow.md:96–108]

3. **Результат — источники, а не готовый удостоверенный ответ.** Сервер возвращает `docs_context` с выдержками, путями, хешами и координатами; клиент формулирует ответ по этим данным. Если безопасных свидетельств нет, возвращается `insufficient_evidence`. Найденный фрагмент не гарантирует полноты ответа и не даёт разрешения на редактирование. [docs/mcp-docs-server.md:48–71; docs/modules/project-context-retrieval.md:3–7, 98–103]

4. **Индекс обновляется отдельно и с подтверждением.** Если запрос вернул необходимое действие подготовки, клиент выполняет именно его и после успешной подготовки повторяет исходный вопрос без изменений. Вызов `prepare_docs(action="sync_project_docs")` без `mutation` ничего не записывает. Подтверждённая синхронизация привязывается к хранилищу вне проекта, хешам каталога и документов и ожидаемому поколению индекса; устаревшие привязки отклоняются. [docs/mcp-docs-server.md:32–40, 89–94; docs/project-docs-mcp-workflow.md:61–81]

5. **Актуальность проверяется и до следующей синхронизации.** Изменённые, удалённые или исключённые из каталога документы не должны служить текущими свидетельствами. При этом синхронизация выбранных документов не означает физического удаления всех старых записей. DocAtlas также не генерирует и не коммитит официальную документацию: разрешённые пользователем изменения оформляются обычным Git-патчем. [docs/project-docs-mcp-workflow.md:83–94, 124–128]

Локальный сервер запускается командой `doc-atlas mcp docs-serve`; его основные инструменты — `get_docs_context`, `prepare_docs` и `docs_status`. [docs/mcp-docs-server.md:5–9, 18–30]

### Required facts and citations

- **T12.F1: PASS; citation PASS.** Explicitly states reads do not update/reconcile the index or change the repository. Answer excerpt: Чтение само по себе не обновляет индекс и не меняет репозиторий.
- **T12.F2: PASS; citation PASS.** Requires explicit literal-path catalog membership and rejects implicit discovery by filenames/directories/links. Answer excerpt: В `docatlas.project-docs.yaml` документы перечисляются по буквальным относительным путям.
- **T12.F3: PASS; citation PASS.** States that bare sync_project_docs does not write; confirmed mutation/source bindings are required. Answer excerpt: без `mutation` ничего не записывает

## L0/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

### Actual final answer

**Because ordinary OpenCode cannot retain the evidence that this mode puts in private metadata.** The older model-view mode sends concise text but places the complete source packet in MCP `_meta`. The documented stock OpenCode v2.1.2 adapter drops response `_meta`, so the original source packet would be lost and the response’s short references would no longer resolve. The mode requires a host that retains `_meta` out of band. [docs/opencode-compact-text.md:36–45](docs/opencode-compact-text.md#L36-L45); [docs/mcp-docs-server.md:135–139](docs/mcp-docs-server.md#L135-L139)

For OpenCode, use the **self-contained compact-text route** instead: it keeps the selected source text, original evidence IDs, URIs, paths and line ranges in the text visible to the model. Run `doc-atlas install opencode` again to upgrade an existing registration, then restart OpenCode; updating the package alone does not change the registration. The model-view and compact-text flags are mutually exclusive. [docs/opencode-compact-text.md:5–11, 47–58](docs/opencode-compact-text.md#L5-L11)

This compact view is not a substitute for the full machine packet, and the documentation says paid-model reading accuracy remains unverified. [docs/opencode-compact-text.md:13–21, 60–70](docs/opencode-compact-text.md#L13-L21)

### Required facts and citations

- **T15.F1: PARTIAL; citation PASS.** PARTIAL: correctly states response _meta is dropped, but does not state that structuredContent AND content are retained. Citation availability cannot fill omitted final-answer facts. Answer excerpt: adapter drops response `_meta`
- **T15.F2: PASS; citation PASS.** Explicitly connects losing the original source packet to unresolvable response-local short references. Answer excerpt: the original source packet would be lost and the response’s short references would no longer resolve

Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.

## L0/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

### Actual final answer

Для управления локальным процессом Qdrant используется группа **`doc-atlas qdrant`**:

- `doc-atlas qdrant up` — скачать при необходимости и запустить Qdrant в фоне. `--port` задаёт порт; `--docker` выводит фрагмент Docker Compose вместо запуска локального бинарного файла.
- `doc-atlas qdrant down` — остановить управляемый процесс.
- `doc-atlas qdrant status` — показать состояние, включая PID, порт, URL, работоспособность и версию; `--json` выводит результат в JSON.
- `doc-atlas qdrant upgrade` — заменить управляемый бинарный файл, сохранив хранилище. Для работающего управляемого процесса требуется `--force`; миграция хранилища между версиями не автоматизирована.
- `doc-atlas qdrant logs` — просмотреть вывод процесса; `--stderr` показывает ошибки вместо стандартного вывода. [wiki/Commands.md:104–114](wiki/Commands.md#L104-L114)

При использовании существующего Qdrant можно задать `DOCATLAS_QDRANT_URL`: тогда управление локальным жизненным циклом пропускается. [wiki/Commands.md:116–120](wiki/Commands.md#L116-L120) Администрирование Qdrant относится к функциям, предназначенным только для сопровождения. [README.md:217](README.md#L217)

### Required facts and citations

- **T19.F1: PASS; citation PASS.** Identifies the local doc-atlas qdrant lifecycle group and the managed-process boundary in the surrounding bullets. Answer excerpt: группа **`doc-atlas qdrant`**
- **T19.F2: PARTIAL; citation PASS.** PARTIAL: gives qdrant up download/start behavior but omits that the downloaded binary is pinned; the cited source includes this qualifier. Answer excerpt: `doc-atlas qdrant up` — скачать при необходимости и запустить Qdrant в фоне.
- **T19.F3: PASS; citation PASS.** Identifies qdrant down as stopping the managed process. Answer excerpt: `doc-atlas qdrant down` — остановить управляемый процесс.
- **T19.F4: PASS; citation PASS.** Identifies qdrant status and its PID/port/URL/process-state reporting. Answer excerpt: `doc-atlas qdrant status` — показать состояние, включая PID, порт, URL, работоспособность и версию

## L2/T01-en

What is expected of me when I submit a pull request to DocAtlas?

### Actual final answer

Before opening a pull request to DocAtlas:

- Name your branch `feat/<topic>` or `fix/<description>`.
- Run the full test suite.
- If you add a connector or fetcher, include tests where practical. [CONTRIBUTING.md:59–63](CONTRIBUTING.md#L59-L63)

The documented test command for Linux/CI is `pytest tests/ -v`. On macOS, the guide recommends `arch -arm64 .venv/bin/python -m pytest tests/ -v` to avoid Rosetta architecture issues. [CONTRIBUTING.md:45–57](CONTRIBUTING.md#L45-L57)

New contributors are also asked to start with the README, contributing guide, documentation index, and project map. [CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)

### Required facts and citations

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention. Answer excerpt: `feat/<topic>` or `fix/<description>`
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing. Answer excerpt: Run the full test suite.
- **T01.F3: PASS; citation PASS.** Requires tests for new connectors/fetchers where practical; Russian L0 source-provider wording is a faithful contextual paraphrase. Answer excerpt: If you add a connector or fetcher, include tests where practical.

## L2/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

### Actual final answer

При отправке PR в DocAtlas от вас ожидается:

- Назвать ветку `feat/<topic>` или `fix/<description>`.
- До открытия PR запустить полный набор тестов.
- Для новых коннекторов или fetcher’ов добавить тесты там, где это практически возможно. [CONTRIBUTING.md, строки 59–63](CONTRIBUTING.md#L59-L63)

В руководстве приведены команды для полного запуска тестов: [CONTRIBUTING.md, строки 45–57](CONTRIBUTING.md#L45-L57)

```bash
# Linux / CI
pytest tests/ -v

# macOS — во избежание проблем arm64/x86_64 Rosetta
arch -arm64 .venv/bin/python -m pytest tests/ -v
```

Если PR меняет **Documentation MCP**, дополнительно нужно сохранить публичный набор инструментов (`get_docs_context`, `prepare_docs`, `docs_status`) и описанные в руководстве границы поведения; перед изменениями предлагается прочитать канонический справочник Docs MCP. [CONTRIBUTING.md, строки 34–38](CONTRIBUTING.md#L34-L38)

Руководство также рекомендует новым участникам начать с `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md`. [CONTRIBUTING.md, строки 7–11](CONTRIBUTING.md#L7-L11)

### Required facts and citations

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention. Answer excerpt: `feat/<topic>` или `fix/<description>`
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing. Answer excerpt: До открытия PR запустить полный набор тестов.
- **T01.F3: PASS; citation PASS.** Requires tests for new connectors/fetchers where practical; Russian L0 source-provider wording is a faithful contextual paraphrase. Answer excerpt: Для новых коннекторов или fetcher’ов добавить тесты там, где это практически возможно.

## L2/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

### Actual final answer

Самый безопасный путь — использовать **`clear-index` с предварительным просмотром**, а не более широкую команду `doc-atlas clear`. По умолчанию `clear-index` ничего не удаляет: применение требует `--apply`. Она удаляет производное состояние индекса, сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы. [`docs/index-cleanup.md:3–15`](docs/index-cleanup.md#L3-L15)

### Для одного проекта

1. Убедитесь, что `docatlas.yaml` проекта указывает на его собственный каталог `.docatlas`. Затем получите план:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --format json
   ```

2. Проверьте все цели, предупреждения и блокирующие условия в ответе. Остановите Docs MCP server и процессы синхронизации, использующие то же хранилище. Примените **именно просмотренный план**, передав его `plan_digest`:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --plan-digest <digest-from-preview> \
     --apply \
     --format json
   ```

   Если план или характеристики целей изменились, применение будет отклонено; получите и проверьте новый план. [`docs/index-cleanup.md:17–41, 87–91`](docs/index-cleanup.md#L17-L41)

Локальный план может включать SQLite и его служебные файлы, извлечённые документы, принадлежащие проекту кэши и локальные данные Qdrant с подтверждённым маркером владения. Исходники и `docatlas.yaml` не удаляются; индекс впоследствии можно восстановить через `prepare_docs(action="sync_project_docs")`. [`docs/index-cleanup.md:43–55`](docs/index-cleanup.md#L43-L55)

### Важные ограничения

- Если проект использует **общий индекс**, `project-local` откажется его очищать: выборочное удаление строк проекта из общей базы не выполняется. `--scope global` сбрасывает общие локальные индексы, поэтому используйте его только если они больше не нужны или могут быть восстановлены. Сначала выполните `doc-atlas clear-index --scope global --format json`, проверьте план и лишь затем примените его с digest и `--apply`. В отличие от этого, `doc-atlas clear` может удалить также конфигурацию и кэши моделей. [`docs/index-cleanup.md:57–85`](docs/index-cleanup.md#L57-L85)
- Активные процессы и действующие блокировки записи препятствуют очистке. `--allow-incomplete` их **не обходит**: он лишь подтверждает, что обнаруженные непроверенные данные векторов или кэша останутся. Удалённые коллекции Qdrant не удаляются; локальные векторные данные без маркера владения сохраняются. [`docs/index-cleanup.md:90–106`](docs/index-cleanup.md#L90-L106)
- Перед окончательным удалением цели перемещаются в карантин на той же файловой системе; если этап перемещения завершится ошибкой, уже перемещённые цели восстанавливаются. Документ не обещает восстановления после окончательного удаления. [`docs/index-cleanup.md:92–93`](docs/index-cleanup.md#L92-L93)

### Required facts and citations

- **T02.F1: PASS; citation PASS.** Names clear-index, distinguishes preview from --apply, and tells the user to review a bounded explicit plan before deletion. Answer excerpt: По умолчанию `clear-index` ничего не удаляет: применение требует `--apply`.
- **T02.F2: PASS; citation PASS.** Explains the global/shared local-index scope and expressly preserves configuration, contrasting clear-index with broader clear. Answer excerpt: сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы.
- **T02.F3: PASS; citation PASS.** Binds execution to the reviewed plan_digest, including a --plan-digest example and stale-plan refusal. Answer excerpt: передав его `plan_digest`

Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.

## L2/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

### Actual final answer

Верификация проверяет **работу установленной интеграции и её границы**, а не поведение модели в реальном диалоге.

- Сценарии `eval/project_binding/installed_stdio.py --layout unbound|black|mixed` проходят через установленный wheel, настоящий проектный установщик, stdio MCP, SQLite и MiniLM. Для привязанных вариантов они проверяют запрос с одним вопросом, сопоставимость с запросом с явным корнем, отклонение привязки к подпапке, текст и координаты источников, а также неизменность исходников и индекса. Вариант без привязки проверяет регрессию отсутствующей цели. [docs/PROJECT_BINDING.md:72–79](docs/PROJECT_BINDING.md#L72-L79)
- Сама привязка хранит канонический путь проекта, его локальный `project_id` и путь рабочего пространства; она не является идентификатором сессии или учётными данными. Привязка **не индексирует документы и не подтверждает готовность проекта**. [docs/PROJECT_BINDING.md:16–23](docs/PROJECT_BINDING.md#L16-L23)
- Для проверки фактической готовности и настроек предусмотрен `docs_status(action="project")`. Однако даже наличие настроенного каталога MiniLM само по себе не доказывает, что модель загрузилась или участвовала в обработке. [docs/PROJECT_BINDING.md:60–65](docs/PROJECT_BINDING.md#L60-L65)

**Чего это не доказывает:** описанные проверки — детерминированные сценарии установленного MCP, а не автономные запуски OpenCode с моделью и не бенчмарки расхода токенов. Поэтому по ним нельзя утверждать, как модель поведёт себя в реальной сессии или сколько токенов она израсходует. [docs/PROJECT_BINDING.md:72–79](docs/PROJECT_BINDING.md#L72-L79)

### Required facts and citations

- **T05.F1: PASS; citation PASS.** Explicitly lists installed wheel, actual installer, stdio MCP, SQLite and MiniLM. Answer excerpt: установленный wheel, настоящий проектный установщик, stdio MCP, SQLite и MiniLM
- **T05.F2: PASS; citation PASS.** Explicitly excludes autonomous OpenCode/model execution and token benchmarking from the verification claim. Answer excerpt: не автономные запуски OpenCode с моделью и не бенчмарки расхода токенов

## L2/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

### Actual final answer

Предлагается **расширить существующий интеграционный сценарий** и провести один и тот же пользовательский вопрос через настоящий публичный API, CLI или MCP — предпочтительно установленного пакета. Данные должны быть изолированы, а retrieval, selection, storage и validation — реальными. Это предложение проверки, а не отчёт о полученном PASS. [docs/main-flow-evaluation.md:3–5, 17–19]

1. **Заранее создать независимый эталон:** зафиксировать вопрос, корпус и версии, обязательные факты и дословные фрагменты, допустимые источники и их hash/span, scope и ожидаемые изменения состояния. Эталон берётся из документов и требований, а не из ответа проверяемого кода. [docs/main-flow-evaluation.md:21]
2. **Провести две попытки — logging off и on** — из одинаковых начальных состояний, включая индекс, cache, права и consent. Результат первого запуска не использовать как эталон для второго. [docs/main-flow-evaluation.md:22]
3. **Независимо проверить оба результата и их паритет:** факты и цитаты должны соответствовать документам; затем сравниваются источники, scope/version, продуктовый результат и изменения состояния. Два одинаковых неверных ответа не считаются PASS. Логирование не должно менять права, источники, побочные действия или число продуктовых вызовов; технические timestamps и trace IDs исключаются только по заранее заданному правилу. [docs/main-flow-evaluation.md:23]
4. **Проверить диагностику:** при on трасса связывает этапы вопроса и помогает локализовать сбой, явно показывая пропуски; при off подробная трасса отключена. В MCP диагностика отделена от protocol stdout. Само наличие события или `exit 0` не заменяет проверки результата и состояния. [docs/main-flow-evaluation.md:24]

Внутренние mocks использовать не предлагается; если подменён внешний транспорт, нужно указать границу: такой запуск не доказывает работу живого провайдера. Одна пара запусков также не доказывает общую надёжность недетерминированного агента. [docs/main-flow-evaluation.md:26, 39–41]

Для практического переключения CLI поддерживает глобальные `--trace` и `--no-trace` **перед подкомандой**; диагностика выводится в stderr. [docs/main-flow-logging.md:3–15, 21–23]

### Required facts and citations

- **T10.F1: PASS; citation PASS.** Reproduces one original user question through real public API/CLI/MCP, with real components. Answer excerpt: один и тот же пользовательский вопрос через настоящий публичный API, CLI или MCP
- **T10.F2: PASS; citation PASS.** Requires log-off/on runs from identical initial index/cache/permissions/consent states. Answer excerpt: logging off и on
- **T10.F3: PASS; citation PASS.** Requires independent checking of both outcomes and parity; explicitly rejects two identical wrong answers as PASS. Answer excerpt: Два одинаковых неверных ответа не считаются PASS

## L2/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

### Actual final answer

MCP-сервер DocAtlas работает с документацией проекта как с **проверяемыми источниками для поиска**, а не как с материалом, который он вправе самостоятельно создавать или редактировать.

- **Что доступно.** Сервер извлекает только актуальные документы, явно перечисленные относительными путями в `docatlas.project-docs.yaml`. Ссылки из README, привычные имена файлов и расположение в `docs/` сами по себе не добавляют файлы в поиск. В каталоге самого DocAtlas, например, перечислены README, описание MCP-сервера и руководство по работе с документацией проекта. [`docs/project-docs-mcp-workflow.md:3–5, 23–28`](docs/project-docs-mcp-workflow.md#L3-L28); [`docatlas.project-docs.yaml:83–89, 132–156`](docatlas.project-docs.yaml#L83-L156)
- **Как задают вопрос.** Основной вызов — `get_docs_context(project_path=..., question=..., scope=...)`. Можно искать по документации всего репозитория (`all`), только проекта (`project`) или конкретного модуля (`module` с точным `module_path`). Сервер возвращает фрагменты с атрибуцией источника, хешами и координатами; итоговый ответ формирует клиентская модель. Если безопасных данных нет, возвращается `insufficient_evidence`; частичный контекст не гарантирует полноты. [`docs/project-docs-mcp-workflow.md:7–21, 96–108`](docs/project-docs-mcp-workflow.md#L7-L21); [`docs/modules/project-context-retrieval.md:70–79, 88–101`](docs/modules/project-context-retrieval.md#L70-L101)
- **Как обновляется индекс.** Если запрос возвращает необходимое действие подготовки, его выполняют с требуемым подтверждением и привязками к источникам, затем повторяют исходный вопрос без изменений. Сам по себе `prepare_docs(action="sync_project_docs")` ничего не записывает: подтверждённая синхронизация требует, в частности, точных хешей каталога и документов, ожидаемого поколения и выбранного хостом хранилища вне проекта. Она заменяет индексированные разделы выбранных документов. [`docs/project-docs-mcp-workflow.md:7–14, 61–81`](docs/project-docs-mcp-workflow.md#L7-L14)
- **Актуальность и границы.** Изменённые, удалённые или исключённые из каталога документы не выдаются как текущие свидетельства даже до повторной синхронизации; физическая очистка старых записей — отдельная операция. Содержимое документов считается недоверенными данными, а получение контекста не даёт разрешения на изменение файлов. Сервер не генерирует и не коммитит официальную документацию проекта. [`docs/project-docs-mcp-workflow.md:52–59, 83–89, 124–128`](docs/project-docs-mcp-workflow.md#L52-L59)

Документация внешних зависимостей обрабатывается отдельно: она привязана к конкретной библиотеке, версии и одобренному источнику; включение файла в каталог проекта не разрешает сетевую загрузку. [`docs/project-docs-mcp-workflow.md:143–148`](docs/project-docs-mcp-workflow.md#L143-L148)

### Required facts and citations

- **T12.F1: PARTIAL; citation FAIL.** PARTIAL: forbids generating/committing documentation, but does not state that reads never reconcile the index and never write to the repository. Readiness/mutation discussion does not supply this read-path guarantee. Answer excerpt: Сервер не генерирует и не коммитит официальную документацию проекта.
- **T12.F2: PASS; citation PASS.** Requires explicit literal-path catalog membership and rejects implicit discovery by filenames/directories/links. Answer excerpt: явно перечисленные относительными путями в `docatlas.project-docs.yaml`
- **T12.F3: PASS; citation PASS.** States that bare sync_project_docs does not write; confirmed mutation/source bindings are required. Answer excerpt: Сам по себе `prepare_docs(action="sync_project_docs")` ничего не записывает

Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.

## L2/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

### Actual final answer

**Because stock OpenCode drops the metadata that model view needs to preserve citations.** `DOCATLAS_MCP_MODEL_VIEW=1` puts concise text in the response but keeps the complete original source packet in MCP `_meta`. The documented OpenCode v2.1.2 adapter drops response `_meta`, so the original packet is lost and the short references in the response cannot be resolved. [docs/opencode-compact-text.md:36–45](docs/opencode-compact-text.md#L36-L45)

That older mode is intended only for a host that retains `_meta` out of band without forwarding it to the model. A host that discards it loses the machine audit; one that forwards it to the model gains no model-input savings. [docs/model-context-delivery.md:7–25](docs/model-context-delivery.md#L7-L25)

**For OpenCode, use the self-contained compact-text route instead.** New and re-registered installations set `DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`, keeping source text and original evidence references, URIs, paths and line ranges in the model-visible text. Re-run `doc-atlas install opencode` for an existing registration, then restart OpenCode; updating the package alone does not change its configuration. The model-view and compact-text flags are mutually exclusive. [docs/opencode-compact-text.md:3–10, 47–58](docs/opencode-compact-text.md#L3-L10)

The trade-off is that self-contained text saved less in an **offline projected** comparison—25.7% versus 38.4% for the incompatible private-metadata view. No paid GPT/OpenCode conversation or billing was measured, so those figures are not guaranteed invoice savings. [docs/opencode-compact-text.md:128–140](docs/opencode-compact-text.md#L128-L140)

### Required facts and citations

- **T15.F1: PARTIAL; citation PASS.** PARTIAL: correctly states response _meta is dropped, but does not state that structuredContent AND content are retained. Citation availability cannot fill omitted final-answer facts. Answer excerpt: adapter drops response `_meta`
- **T15.F2: PASS; citation PASS.** Explicitly connects losing the original source packet to unresolvable response-local short references. Answer excerpt: the original packet is lost and the short references in the response cannot be resolved

Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.

## L2/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

### Actual final answer

Для управления локальным Qdrant используется группа команд **`doc-atlas qdrant`**:

- `doc-atlas qdrant up` — скачать закреплённый бинарный файл при необходимости и запустить процесс в фоне. `--port` задаёт порт; `--docker` выводит пример `docker compose` вместо запуска.
- `doc-atlas qdrant down` — остановить управляемый процесс; чужой PID-файл команда не затрагивает.
- `doc-atlas qdrant status` — показать PID, порт, URL, состояние процесса, принадлежность DocAtlas, работоспособность и версию. `--json` выводит данные в JSON.
- `doc-atlas qdrant upgrade` — заменить управляемый бинарный файл, сохранив хранилище. Для работающего управляемого процесса требуется `--force`; перенос хранилища между версиями не автоматизирован.
- `doc-atlas qdrant logs` — показать последние строки stdout; `--stderr` переключает на stderr.

Источник: [wiki/Commands.md, строки 104–114](/tmp/opencode/step8-corpora2/L2-0/project/wiki/Commands.md#L104-L114).

По умолчанию `doc-atlas ingest` может автоматически скачать и запустить локальный Qdrant; `ingest --no-vectors` отключает векторную обработку. Для диагностики состояния Qdrant и эмбеддингов можно использовать `doc-atlas doctor` ([wiki/Commands.md, строки 104–106](/tmp/opencode/step8-corpora2/L2-0/project/wiki/Commands.md#L104-L106); [wiki/Troubleshooting.md, строки 153–165](/tmp/opencode/step8-corpora2/L2-0/project/wiki/Troubleshooting.md#L153-L165)).

### Required facts and citations

- **T19.F1: PASS; citation PASS.** Identifies the local doc-atlas qdrant lifecycle group and the managed-process boundary in the surrounding bullets. Answer excerpt: группа команд **`doc-atlas qdrant`**
- **T19.F2: PASS; citation PASS.** Identifies qdrant up as downloading the pinned binary and starting the managed process. Answer excerpt: `doc-atlas qdrant up` — скачать закреплённый бинарный файл при необходимости
- **T19.F3: PASS; citation PASS.** Identifies qdrant down as stopping the managed process. Answer excerpt: `doc-atlas qdrant down` — остановить управляемый процесс
- **T19.F4: PASS; citation PASS.** Identifies qdrant status and its PID/port/URL/process-state reporting. Answer excerpt: `doc-atlas qdrant status` — показать PID, порт, URL, состояние процесса

## Accounting and evidence boundary

Step input/cache/output/reasoning totals reconcile exactly with session metadata. Input-with-cache is input plus cache-read, consistent with the previous analyzer. Output and reasoning are not added as a new billing metric. Tool calls are actual recorded top-level invocations. Completion and exit 0 were not used as answer grades.
The JSON includes final answers, exact tool traces, all step usage, input-artifact hashes, inspected supporting source excerpts/coordinates/hashes, frozen witness excerpts, and per-fact reasons. Only the authorized dev cases were reviewed. No questions, sources, labels, policy, production code or agent runner changed. No extra agent/model calls were made for grading.
Source-output checks verify actual numbered read/grep lines against frozen files rather than assuming a requested read range was delivered. Required facts may be supported by independently verified equivalent source passages rather than only the original oracle location. Additional non-required advice is not exhaustively graded.
