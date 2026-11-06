# Final candidate evaluation: all 16 sessions

**16/46 required facts; 17/46 supporting fact citations; 5/16 fully answered cases.** Eight L2 sessions censored at 900 seconds count as failed answers, not exclusions. Two completed L0 sessions returned an emergency stop and no sources.

## Recorded accounting

```json
{
  "sessions": 16,
  "final_answers_emitted": 8,
  "censored": 8,
  "facts_pass": 16,
  "facts_total": 46,
  "facts_partial": 1,
  "citations_supported": 17,
  "answers_pass": 5,
  "usage": {
    "input": 372326,
    "output": 4043,
    "reasoning": 0,
    "cache_read": 28032,
    "cache_write": 0,
    "input_with_cache": 400358,
    "steps": 35,
    "top_level_tool_calls": 27,
    "top_level_tool_errors": 0,
    "reported_nested_tool_calls": 19
  },
  "usage_is_lower_bound": true,
  "seconds_sum": 8024.91,
  "seconds_min": 72.34,
  "seconds_max": 900.25
}
```

Persisted session metadata supplies the most complete recorded usage on censored runs. Their event streams omit a final step, so totals are lower bounds; both ledgers remain in JSON. Input, cache-read, output and reasoning are separately reported.

## Per-case outcomes

| Corpus/case | Facts | Citation support | Input + cache | Censored | Exact question |
|---|---:|---:|---:|---|---|
| L0/T01-en | 3/3 | 3/3 | 60803 | False | True |
| L0/T01-ru | 3/3 | 3/3 | 61429 | False | False |
| L0/T02-ru | 0/3 | 0/3 | 8433 | False | False |
| L0/T05-ru | 2/2 | 2/2 | 57235 | False | True |
| L0/T10-ru | 3/3 | 3/3 | 44511 | False | False |
| L0/T12-ru | 0/3 | 0/3 | 8417 | False | False |
| L0/T15-en | 1/2 | 2/2 | 55702 | False | False |
| L0/T19-ru | 4/4 | 4/4 | 58078 | False | False |
| L2/T01-en | 0/3 | 0/3 | 5339 | True | None |
| L2/T01-ru | 0/3 | 0/3 | 8323 | True | None |
| L2/T02-ru | 0/3 | 0/3 | 5347 | True | None |
| L2/T05-ru | 0/2 | 0/2 | 5363 | True | None |
| L2/T10-ru | 0/3 | 0/3 | 5359 | True | None |
| L2/T12-ru | 0/3 | 0/3 | 5339 | True | None |
| L2/T15-en | 0/2 | 0/2 | 5345 | True | None |
| L2/T19-ru | 0/4 | 0/4 | 5335 | True | None |

## L0/T01-en

What is expected of me when I submit a pull request to DocAtlas?

DocAtlas’s contribution guide asks you to:

1. **Name your branch** `feat/<topic>` or `fix/<description>`.
2. **Run the full test suite before opening the PR.**
3. **Include tests for new connectors or fetchers where practical.** [CONTRIBUTING.md:59–63, ev-dc2112ec2f32298ae05568ea]

The documented test commands are `pytest tests/ -v` on Linux/CI and `arch -arm64 .venv/bin/python -m pytest tests/ -v` on macOS to avoid Rosetta architecture issues. [CONTRIBUTING.md:45–57, ev-0e149b0aa2447c7ccb879804]

For new contributors, the guide also recommends reading `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md`, and `docs/PROJECT_MAP.md` first. [CONTRIBUTING.md:7–11, ev-9784550caf26f12213696e05]

If your change affects documentation, note that the PR summary includes an **advisory** documentation-impact report; any documentation edit remains a separate, reviewable change. If you add an architecture document, runbook, ADR, workflow document, or user-facing reference, update `docs/INDEX.md`. [README.md:176–188, ev-e894fd0d45b0e2eee145231f; docs/INDEX.md:53–57, ev-9ffd33738f2220fa5018de84]

Question contract: {"frozen_question": "What is expected of me when I submit a pull request to DocAtlas?", "actual_question": "What is expected of me when I submit a pull request to DocAtlas?", "original_question_exact": true, "deviation": null, "frozen_search_question": null, "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention.
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing.
- **T01.F3: PASS; citation PASS.** Explicitly requires tests for new connectors/fetchers where practical.

## L0/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

При отправке PR в DocAtlas руководство участника просит:

1. **Назвать ветку** в формате `feat/<topic>` или `fix/<description>`.
2. **До открытия PR запустить полный набор тестов.**
3. Для новых коннекторов или fetcher-компонентов **добавить тесты, где это практически возможно**. [CONTRIBUTING.md, строки 59–63; ev-dc2112ec2f32298ae05568ea]

Команда для Linux / CI — `pytest tests/ -v`; для macOS руководство рекомендует `arch -arm64 .venv/bin/python -m pytest tests/ -v`, чтобы избежать проблем arm64/x86_64 Rosetta. [CONTRIBUTING.md, строки 45–57; ev-0e149b0aa2447c7ccb879804]

Если вы новый участник, сначала рекомендуется прочитать `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md`. [CONTRIBUTING.md, строки 7–11; ev-9784550caf26f12213696e05]

**Для отдельных изменений:**

- При изменении документации проверьте, нужно ли обновить её индекс; в частности, его следует обновлять при добавлении архитектурной документации, runbook, ADR, описания рабочего процесса или пользовательского справочника. [docs/INDEX.md, строки 53–57; ev-9ffd33738f2220fa5018de84]
- Если меняете границу публичного Docs MCP, сначала прочитайте канонический справочник и сохраните описанные в руководстве ограничения интерфейса. [CONTRIBUTING.md, строки 34–38; ev-7fdd74125bd26e0d1292cb85]

В найденном разделе об отправке PR дополнительных требований к шаблону описания или процессу ревью не указано.

Question contract: {"frozen_question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?", "actual_question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": "What is expected of me when I submit a pull request to DocAtlas?", "actual_search_question": "What is expected of me when I submit a pull request to DocAtlas?", "supplied_translation_exact": true, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T01.F1: PASS; citation PASS.** States both feat/ and fix/ branch patterns; translated placeholders preserve the convention.
- **T01.F2: PASS; citation PASS.** Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing.
- **T01.F3: PASS; citation PASS.** Explicitly requires tests for new connectors/fetchers where practical.

## L0/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

Не могу безопасно рекомендовать команду очистки: извлечение документации DocAtlas остановилось из-за превышения аварийного лимита контекста, поэтому у меня нет подтверждённых сведений о том, какие данные удаляются и как их сохранить.

**До проверки документации не запускайте очистку индекса.**

Question contract: {"frozen_question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "actual_question": "\"Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": "How can I safely clean up the DocAtlas index without deleting data I still need?", "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T02.F1: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: `doc-atlas clear-index` previews a bounded cleanup plan before removing derived
- **T02.F2: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: for all local indexes while preserving configuration
- **T02.F3: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: can be bound to its `plan_digest`

## L0/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

**Верификация проверяет установленный MCP-маршрут, а не полноценную работу агента OpenCode.** Сценарий `eval/project_binding/installed_stdio.py` с вариантами `unbound`, `black` и `mixed` задействует установленный wheel, реальный установщик проекта, MCP через stdio, SQLite и MiniLM. [docs/PROJECT_BINDING.md:72–79, ev-3a519fcbfb7616ce6bd0f390]

В привязанных вариантах проверяются:

- чтение по одному вопросу без явного пути и паритет с запросом, где указан корень проекта;
- отклонение попытки использовать подкаталог как привязанный проект;
- текст и координаты источников, а также неизменность исходных файлов и индекса.

В варианте `unbound` отдельно проверяется регрессия для отсутствующей цели запроса. [docs/PROJECT_BINDING.md:72–79, ev-3a519fcbfb7616ce6bd0f390]

**Чего это не доказывает:**

- Это детерминированные сценарии установленного MCP, **не автономные запуски OpenCode с моделью** и не бенчмарки токенов. Работу реального клиента и production smoke нужно подтверждать отдельно. [docs/PROJECT_BINDING.md:72–79, ev-3a519fcbfb7616ce6bd0f390; docs/main-flow-evaluation.md:39–41, ev-4ad9c3634855b91b5b620d8b]
- Настроенный каталог MiniLM сам по себе не доказывает, что модель загрузилась или участвовала в конкретном запросе. [docs/PROJECT_BINDING.md:60–69, ev-5586663a246b891203064c1f]
- Успех сервера или сохранённый полный ответ сам по себе не доказывает полезную доставку в сообщение OpenCode: нужно проверять в нём текст, ссылки и диапазоны строк. Качество ответов клиента и оплаченные токены требуют отдельного измерения. [docs/opencode-compact-text.md:115–127, ev-677b7a6440957e8f45e566fd]
- Сама установка привязки не индексирует документы и не подтверждает завершение подготовки проекта. [docs/PROJECT_BINDING.md:16–29, ev-8fdcfd9e14e65203de681d99]

Question contract: {"frozen_question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?", "actual_question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?", "original_question_exact": true, "deviation": null, "frozen_search_question": "What does verification of the project-bound OpenCode integration cover, and what does it not prove?", "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T05.F1: PASS; citation PASS.** Explicitly lists installed wheel, actual installer, stdio MCP, SQLite and MiniLM.
- **T05.F2: PASS; citation PASS.** Explicitly excludes autonomous OpenCode/model execution and token benchmarking from the verification claim.

## L0/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

Предлагается расширить существующий интеграционный сценарий и провести **две независимые сопоставимые попытки** одного и того же исходного вопроса — с подробным логированием off и on. Вопрос должен проходить через настоящий публичный API, CLI или MCP, желательно установленного пакета, на изолированных данных и с реальными retrieval, selection, storage и validation. [docs/main-flow-evaluation.md:17–21, ev-1d1d4d4953794fbbc3282feb]

1. **Заранее подготовить независимый эталон:** зафиксировать вопрос, корпус и версии, обязательные факты и дословные фрагменты, допустимые источники и их hash/span, scope и ожидаемые изменения состояния. Эталон берётся из документов и требований, а не из результатов проверяемого кода.
2. **Запустить оба режима из одинаковых состояний**, включая индекс, кеш, права и consent. Результат первого запуска нельзя использовать как ожидаемый ответ второго.
3. **Проверить каждый запуск отдельно, затем паритет:** сверить факты, исходный текст и цитаты с документами, а между режимами — источники, scope/version, результат и изменения состояния. Совпадение двух неверных ответов не считается PASS. Логирование не должно менять права, выбор источников, побочные действия или число продуктовых вызовов; timestamps и trace ID исключаются только по заранее заданному правилу.
4. **Проверить диагностику:** при on трасса должна связывать этапы вопроса и помогать локализовать сбой, явно показывая пропуски; при off подробная трасса отключена. В MCP диагностика отделена от protocol stdout. Само событие или `exit 0` не заменяет проверку результата и состояния. [docs/main-flow-evaluation.md:21–25, ev-1d1d4d4953794fbbc3282feb]

Внутренние mocks использовать не предлагается; если подменяется внешний транспорт, эту границу нужно обозначить: такой запуск не проверяет живого провайдера. Записка описывает **предложение, а не полученный PASS**; одна пара off/on также не доказывает общую надёжность недетерминированного агента. [docs/main-flow-evaluation.md:3–5, 27, 39–41, ev-97f6b6e6fdc7cf4b65a0569c, ev-1d1d4d4953794fbbc3282feb, ev-4ad9c3634855b91b5b620d8b]

Question contract: {"frozen_question": "Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?", "actual_question": "\"Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": "What public scenario is proposed for comparing runs with logging turned off and on?", "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T10.F1: PASS; citation PASS.** Reproduces one original user question through real public API/CLI/MCP, with real components.
- **T10.F2: PASS; citation PASS.** Requires log-off/on runs from identical initial index/cache/permissions/consent states.
- **T10.F3: PASS; citation PASS.** Requires independent checking of both outcomes and parity; explicitly rejects two identical wrong answers as PASS.

## L0/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

Не удалось получить документацию проекта: объём выбранного контекста превысил аварийный предел — 50 297 токенов при лимите 50 000. Поэтому я не могу достоверно описать, как MCP-сервер работает с собственной документацией проекта.

Question contract: {"frozen_question": "Как MCP-сервер документации работает с собственной документацией проекта?", "actual_question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": "How does the docs MCP server handle a project's own documentation?", "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T12.F1: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: Reads never reconcile
an index or write to the repository.
- **T12.F2: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: Project documentation must belong to a
finite explicit `docatlas.project-docs.yaml` catalog
- **T12.F3: FAIL; citation FAIL.** Final answer abstains after the explicit emergency stop; it does not state the required fact: `prepare_docs(action="sync_project_docs", project_path=...)` without a `mutation`
performs no writes.

## L0/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

**Because that mode depends on metadata ordinary OpenCode does not preserve.** `DOCATLAS_MCP_MODEL_VIEW=1` puts a concise view in `content[].text` but keeps the complete source packet in MCP `_meta`. In the documented stock OpenCode **v2.1.2** adapter, `_meta` is dropped; the original source packet is therefore lost and the response’s short source references cannot be resolved. The documentation does not establish whether other OpenCode versions behave differently. [docs/opencode-compact-text.md:36–45, ev-8ed9b9e1a3fd964b5c046518]

**Use the self-contained compact-text route instead:** re-run `doc-atlas install opencode` for an existing registration, adding `--project` for a project-owned config. It sets both `DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`; leave `DOCATLAS_MCP_MODEL_VIEW` absent or off. Updating the package alone does not rewrite an existing registration. The two compact modes are mutually exclusive. [docs/opencode-compact-text.md:3–10, 53–58, 101–110, ev-b4af38aadfa329bc288aed51, ev-8ed9b9e1a3fd964b5c046518, ev-677b7a6440957e8f45e566fd]

The alternative keeps source excerpts, evidence IDs, URIs, paths and line ranges in the model-visible text, without depending on `_meta`. It is still a view, **not a completeness or answer-authority guarantee**. The documented token savings are an offline text-token proxy, not measured paid-provider savings. [docs/opencode-compact-text.md:46–71, 128–140, ev-8ed9b9e1a3fd964b5c046518, ev-f33b444d20f363a6713d75a8]

Question contract: {"frozen_question": "Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?", "actual_question": "\"Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": null, "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T15.F1: PARTIAL; citation PASS.** PARTIAL: correctly states response _meta is dropped, but does not state that structuredContent AND content are retained. Citation availability cannot fill omitted final-answer facts.
- **T15.F2: PASS; citation PASS.** Explicitly connects losing the original source packet to unresolvable response-local short references.

## L0/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

Для управления **локальным процессом Qdrant, принадлежащим DocAtlas**, используется группа команд `doc-atlas qdrant`:

| Команда | Назначение |
|---|---|
| `doc-atlas qdrant up` | Запускает Qdrant в фоне, при необходимости загружая закреплённую версию. `--port` задаёт порт; `--docker` выводит фрагмент Docker Compose вместо запуска управляемого бинарного файла. |
| `doc-atlas qdrant down` | Останавливает управляемый процесс; отказывается использовать чужой PID-файл. |
| `doc-atlas qdrant status` | Показывает PID, порт, URL, состояние процесса, принадлежность DocAtlas, работоспособность и версию. `--json` возвращает JSON. |
| `doc-atlas qdrant upgrade` | Обновляет управляемый бинарный файл с сохранением хранилища. Для работающего управляемого процесса требуется `--force`; миграция хранилища между версиями не автоматизирована. |
| `doc-atlas qdrant logs` | Показывает журнал stdout; с `--stderr` — stderr. |

Источник: `wiki/Commands.md`, строки 104–114, evidence ID `ev-5d1a7e5547416bdd471a9e6f`.

При заданном `DOCATLAS_QDRANT_URL` DocAtlas использует существующий сервер и пропускает управление локальным процессом. Администрирование Qdrant относится к поверхности **только для сопровождения**. [`wiki/Commands.md:116–124`, `ev-5d1a7e5547416bdd471a9e6f`; `README.md:211–217`, `ev-29302886b2fd5587d74f6d38`]

Question contract: {"frozen_question": "Какие команды DocAtlas используются для управления Qdrant?", "actual_question": "\"Какие команды DocAtlas используются для управления Qdrant?\"", "original_question_exact": false, "deviation": "Extra surrounding quote characters; exact original-question contract violated. Not normalized or excused.", "frozen_search_question": "Which DocAtlas commands are used to manage Qdrant?", "actual_search_question": null, "supplied_translation_exact": null, "translation_note": "Translation is optional; omission is recorded, not counted as an original-question mutation."}

- **T19.F1: PASS; citation PASS.** Identifies the local doc-atlas qdrant lifecycle group and the managed-process boundary in the surrounding bullets.
- **T19.F2: PASS; citation PASS.** Identifies qdrant up as downloading the pinned binary and starting the managed process.
- **T19.F3: PASS; citation PASS.** Identifies qdrant down as stopping the managed process.
- **T19.F4: PASS; citation PASS.** Identifies qdrant status and its PID/port/URL/process-state reporting.

## L2/T01-en

What is expected of me when I submit a pull request to DocAtlas?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "What is expected of me when I submit a pull request to DocAtlas?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions."}

- **T01.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Branch name: `feat/<topic>` or `fix/<description>`
- **T01.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Run the full test suite before opening the PR
- **T01.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: New connectors or fetchers should include tests where practical

## L2/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions."}

- **T01.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Branch name: `feat/<topic>` or `fix/<description>`
- **T01.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Run the full test suite before opening the PR
- **T01.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: New connectors or fetchers should include tests where practical

## L2/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions."}

- **T02.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: `doc-atlas clear-index` previews a bounded cleanup plan before removing derived
- **T02.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: for all local indexes while preserving configuration
- **T02.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: can be bound to its `plan_digest`

## L2/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions."}

- **T05.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: the installed wheel, actual project installer, stdio MCP, SQLite and MiniLM
- **T05.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: not autonomous OpenCode/model runs or token benchmarks

## L2/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: in-flight get_docs_context arguments are not present in the saved completed-tool event stream. Do not infer exact preservation or extra quotes from other sessions."}

- **T10.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Воспроизвести один исходный пользовательский вопрос через настоящий публичный API/CLI/MCP
- **T10.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: **Две сопоставимые попытки.** Запустить поток с подробными логами off и on из двух одинаковых исходных состояний
- **T10.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: **Два независимых PASS и паритет.**

## L2/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Как MCP-сервер документации работает с собственной документацией проекта?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: no in-flight get_docs_context arguments in saved completed-tool events. Exact preservation is not established."}

- **T12.F1: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: Reads never reconcile
an index or write to the repository.
- **T12.F2: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: Project documentation must belong to a
finite explicit `docatlas.project-docs.yaml` catalog
- **T12.F3: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: `prepare_docs(action="sync_project_docs", project_path=...)` without a `mutation`
performs no writes.

## L2/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: no in-flight get_docs_context arguments in saved completed-tool events. Exact preservation is not established."}

- **T15.F1: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: retains `structuredContent` and `content`, but drops response `_meta`.
- **T15.F2: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: would lose the original `source-packet` and make its
response-local short references non-resolvable.

## L2/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

**No final answer: censored at 900 seconds.**

Question contract: {"frozen_question": "Какие команды DocAtlas используются для управления Qdrant?", "actual_question": null, "original_question_exact": null, "deviation": "Unknown: no in-flight get_docs_context arguments in saved completed-tool events. Exact preservation is not established."}

- **T19.F1: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: The `doc-atlas qdrant` group manages a DocAtlas-owned local Qdrant process.
- **T19.F2: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: `doc-atlas qdrant up` | Download the pinned Qdrant binary
- **T19.F3: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: `doc-atlas qdrant down` | Stop a docmancer-managed process.
- **T19.F4: FAIL; citation FAIL.** Censored at 900 seconds with no final answer. Required fact not answered: `doc-atlas qdrant status` | Report pid, port, url, alive

## Boundaries and limitations

All 16 assigned cases remain in the denominator, including eight censored failures. No survivor-only quality score.
Censored session metadata records more provider tokens than interrupted step_finish streams. Use persisted session totals and preserve both ledgers; unfinished work may add unrecorded cost. Emitted tool counts also omit in-flight operations.
Six observed L0 questions have additional surrounding quotes, violating exact original-question preservation. Two L0 questions are exact. Eight L2 in-flight arguments are unavailable in saved completed-tool events, so exact preservation is unobservable.
The L0 comparison is a matched completed-trajectory operational comparison, not a clean exact-question-compliant experiment for all cases. Quote deviations are not normalized away.
The full input ratio is a recorded lower bound, not a cost-saving claim. L2 has no final answers and its shorter recorded provider traffic is not successful context compression.
Many whole source documents were delivered through semantic selection and structural closure, not token-budget filling. Two L0 emergency stops blocked the selected context before source delivery.
Source bodies were independently checked against frozen bytes/spans. content_sha256 is a canonical projection-material digest, not sha256(snippet). Presence/syntax was checked; projection-digest reconstruction is not claimed.
Required fact and supporting citation grades do not exhaustively grade extra advice. All material qualifiers are required; partial facts count as zero. The same final-answer rule is used in both fresh arms.
No new agent/model/product calls, no completion polling, no wheel/input/policy/threshold changes. Historical and invalid setup attempts are separate.

`candidate.json` preserves actual final answers, traces, source/witness excerpts, per-fact reasons, question comparisons and usage ledgers. No source digest is equated with a raw-snippet hash.
