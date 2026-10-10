# PR #211: независимый review release-resource test migration

Дата: 2026-10-08. Reviewer: `footprint_audit`; автор slice: координатор.

## Verdict и проверенные версии

**APPROVED для узкого test-only изменения.** Замечаний, требующих исправлений,
не найдено. Сравнение выполнено с
`b68759e65f52317928ba22166248e679098024ae`.

| Файл | Проверенный SHA-256 |
|---|---|
| `tests/test_release_gate.py` | `f741478233833600e9e3c10af591f225a46d29b11560f5303cc7e18c8e4104e4` |
| `v2plan/PR211_RELEASE_RESOURCE_REVIEW_RU.md` | `f1ab1f834ca309217639dfa4c23bc31e61d9a17f1a9f40476993195455d61c30` |

Этот verdict относится к корректности миграции assertion. Он не объявляет
required CI/release, настоящий MCP delivery либо PR в целом прошедшими acceptance.

## Почему миграция обоснована

Удалённое ожидание требовало всех result kind/status терминов внутри исходного
`docmancer/mcp/_docs_server_resources.py`. Сам Python-файл не является
публичным result schema. Его короткий quickstart описывает workflow и границы
permission, а типы результатов публикуются через tool schemas.

Независимое сравнение с исходным `21fe472d983f394130849d6fd4e582043d58e9ba`
подтвердило побайтовую неизменность `_docs_server_resources.py`,
`_docs_server_schema.py` и `_docs_server_shared.py`. В `_tool_spec` default
использует advertised docs output, а явный advanced startup добавляет typed
patch branch и `context_format`. В `read_docs_resource` фиксированный quickstart
возвращается из `MCP_RESOURCES`. Эти правила существовали до данной миграции.

Новый тест проверяет через реальные public getters именно эти поверхности:
default kind enum ровно `docs_answer`/`docs_context`, статус
`insufficient_evidence`, отсутствие default `oneOf`/`context_format`, прежний
docs output внутри explicit advanced `oneOf` и отдельный `patch_context` const.
Полученный quickstart должен сохранять lifecycle recommendation, оба hard-stop
состояния, отсутствие permission из `false` и запрет автоматически включать
advanced режим или загружать tools через чтение guide.

## Сохранность действующих gates

Независимое AST-сравнение подтверждает, что все остальные top-level nodes
файла и всё тело изменённого теста до `maintained_contracts` совпадают с `b68759e`.
Все имена функций, аргументы и decorators также совпадают. Поэтому 38
parametrized cases, self-host positive/negative controls, snapshot/citation/
contamination проверки, decoder assertions, gold cases и frozen thresholds,
включая 800-token и 3-source controls, не заменены проверкой доступности ресурса.

Из восьми прежних путей исключён только internal Python source. Семь maintained
user-facing documents продолжают проверяться на все четыре исходных термина.
Production, fixtures, gold corpus, budget ceilings и workflow gates этим slice
не меняются. Остальные retrieval failures остаются отдельной задачей acceptance.

## Выполненная проверка и пределы

- SHA-256, AST parse, структурное сравнение с `b68759e` и `git diff --check`: PASS.
- Read-only stdlib проверки реальных семи Markdown files × четырёх терминов,
  literal default input/output schema и семи guards literal quickstart: PASS.
- Маршруты `current_tools` → `_tool_spec` и `read_docs_resource` просмотрены по
  исходному коду. Настоящие вызовы getters, pytest, renderer, stdio/server и
  installed/client validation локально **NOT RUN**.

[Авторский rationale](PR211_RELEASE_RESOURCE_REVIEW_RU.md) связывает миграцию
с CI failures на HEAD `b68759e` / merge
`964056442f67b0d913310d3f8a295deb3c90263e`. В этом review полный CI повторно не
выполнялся; неизменность предшествующих guards подтверждена сравнением кода.
После публикации требуется общий запуск на конечном SHA. Успех отдельного
required-release workflow не подменяет результат required-ci или installed/client
acceptance.
