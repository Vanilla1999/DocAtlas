# PR211: явная подготовка пяти fixtures чтения

## Причина и граница изменения

На опубликованном `80c8fbbb3e8c379467a9075f93f7165d080f8432`
`tests/test_docs_service_part03.py` имеет **18 FAIL / 6 PASS**.
Это фактический отчёт [acceptance diagnostics](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114077935805), а не результат предлагаемой миграции.

Пять проверок чтения ещё готовили индекс через
`service.ingest_project_docs(..., with_vectors=False)` без mutation.
Текущий production-контракт отклоняет такой вызов до чтения проекта
и до записи: наличие файла или каталога само по себе не разрешает ingestion.
Миграция меняет только подготовку данных в этих пяти существующих функциях.

## Явно выбранные данные

| Существующая проверка | Members |
| --- | --- |
| `test_get_project_docs_can_filter_by_module_path` | `README.md`, `packages/backend/README.md`, `packages/frontend/README.md` |
| `test_get_project_docs_can_filter_by_module_name_exact_match` | те же три явно перечисленных пути |
| `test_get_project_docs_project_scope_preserves_backward_compatibility` | `README.md`, `packages/backend/README.md` |
| `test_get_project_context_low_signal_single_token_query_returns_no_results` | `README.md` |
| `test_get_project_docs_distinguishes_indexed_no_results_from_not_indexed` | `README.md` |

Каждая функция записывает конечный catalog: `roots: []`, `code_files: []`.
Для корневого README fixture явно задаёт `overview/project`; для двух
модулей — `other/module` и соответствующий `module_path`.
Authority во всех случаях `supporting`, status `active`, impact `track`.
Эти значения заданы тестом; они не извлекаются из вопроса, prose или discovery.

Подготовку выполняет существующий `indexed_fixture_member_service`
из `tests/_fixture_member_transaction.py` без изменения helper.
Он выбирает отдельное host storage, задаёт `confirm: True`, точные
catalog/content/entry hashes и первоначальный generation CAS,
вызывает реальную member transaction и сверяет сохранённые bytes,
membership, project identity и поколение. Vector sync и extraction
не запрашиваются.

## Что сохраняет проверку

Все **24 существующих имени** в модуле сохранены; новых обычных tests нет.
Исходные тела документов, вопросы, параметры запросов и assertions
сохранены побайтно. Обратная замена ровно пяти блоков подготовки
восстанавливает исходный blob `0f0e079ec28707bf6015df8162d94c92c2f5fa2b`.

Общие `_service_with_real_agent` / `_service`, member helper,
production и остальные модули не меняются.
Orphan/invalid-catalog, identity, lifecycle, auto sync/prune/vector
и семантические DTO-миграции остаются отдельными задачами.

## Acceptance

Новый runtime **PENDING**. Код локально не исполнялся: нет запуска
pytest, imports, AST, subprocess или установки зависимостей.
Нужен обычный PR CI на опубликованном конечном SHA, включая этот модуль
на всех поддерживаемых Python. Устранение первого setup barrier
не объявляется заранее успешным прохождением пяти проверок
или исправлением других прежних failures модуля.

## Независимый review

Alias и root: **APPROVE** exact code blob
`7fba205d8324b1c84564b44b0cda130986a4cd78`.
Проверены opt-in подготовка, конечные scopes, неизменные исходные assertions,
общая фабрика и остальные tests. Это static review, не новый runtime PASS.
