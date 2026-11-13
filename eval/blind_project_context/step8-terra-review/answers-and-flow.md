## L0 clarified T01-ru
Evidence 3/3; input 120593; tools 34079; steps 7
Согласно руководству для участников DocAtlas, перед отправкой pull request от вас ожидается:

- Назвать ветку `feat/<topic>` для новой функциональности или `fix/<description>` для исправления.
- Запустить **весь набор тестов** до открытия PR.
- Для новых коннекторов или загрузчиков данных (*fetchers*) по возможности добавить тесты.  
  [CONTRIBUTING.md, строки 59–63, `ev-4e12ab8c2f646242`]

Также стоит проверить, затрагивает ли изменение документацию. Для этого можно использовать `doc-atlas docs-impact --base origin/main`. Отчёт носит рекомендательный характер: он указывает, какую документацию нужно проверить, но не редактирует её автоматически. Такой отчёт публикуется и в сводке PR. [README.md, строки 176–189, `ev-79f531095e3ccd5b`, `ev-83b31a79fcb790f1`]

### Trace
{"tool": "execute", "input": {"code": "return await tools.opencode.list_mcp_resources({});"}, "status": "completed", "output_tokens": 569, "nested_calls": [{"tool": "opencode.list_mcp_resources", "status": "completed"}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',search_question:'What is expected of me when I submit a pull request to DocAtlas?'});"}, "status": "completed", "output_tokens": 11787, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "search_question": "What is expected of me when I submit a pull request to DocAtlas?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "4e56321601ed56cf0efdc088940d822d0d917faa0f922c9849ee68b4b540614e", "next_portion": 2, "portion": 1, "remaining_rows": 221}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',search_question:'What is expected of me when I submit a pull request to DocAtlas?',portion:2,continuation_token:'4e56321601ed56cf0efdc088940d822d0d917faa0f922c9849ee68b4b540614e'});"}, "status": "completed", "output_tokens": 9332, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "search_question": "What is expected of me when I submit a pull request to DocAtlas?", "portion": 2, "continuation_token": "4e56321601ed56cf0efdc088940d822d0d917faa0f922c9849ee68b4b540614e"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "4e56321601ed56cf0efdc088940d822d0d917faa0f922c9849ee68b4b540614e", "next_portion": 3, "portion": 2, "remaining_rows": 162}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',search_question:'What is expected of me when I submit a pull request to DocAtlas?',lookup_queries:['What are the contributor expectations when submitting a pull request to DocAtlas?','DocAtlas pull request contributor expectations']});"}, "status": "completed", "output_tokens": 11942, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "search_question": "What is expected of me when I submit a pull request to DocAtlas?", "lookup_queries": ["What are the contributor expectations when submitting a pull request to DocAtlas?", "DocAtlas pull request contributor expectations"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "f64fb885f7738b562dbf8d1e41c9d494ca0633b27e60405d56d9e2bccee6c14a", "next_portion": 2, "portion": 1, "remaining_rows": 235}}
{"tool": "execute", "input": {"code": "return await tools.opencode.read_mcp_resource({server:'docatlas',uri:'docatlas://source/96139b756c0caffd32f41847'});"}, "status": "completed", "output_tokens": 102, "nested_calls": [{"tool": "opencode.read_mcp_resource", "status": "completed", "input": {"server": "docatlas", "uri": "docatlas://source/96139b756c0caffd32f41847"}}], "code_error": false, "truncated": false}

## L0 clarified T12-ru
Evidence 0/3; input 22636; tools 12621; steps 4
MCP-сервер DocAtlas работает с собственной документацией проекта как с **ограниченным набором проверяемых источников**, а не как с готовым ответом:

1. **Определяет проект и источники.** Сервер можно привязать к конкретному корню проекта. Для поиска он использует только явно включённые и актуальные документы из каталога проекта; имя файла, ссылка из README или имя модуля сами по себе не разрешают обнаруживать другие файлы. [docs/PROJECT_BINDING.md:16–24, ev-74003835177b5002; docs/project-docs-mcp-workflow.md:1–6, ev-1ed7ba2f75cd093b]
2. **Подготавливает индекс по отдельному разрешению.** Если документация ещё не подготовлена, сервер рекомендует подготовку. `prepare_docs(action="sync_project_docs")` без подтверждённой мутации ничего не записывает; подтверждённая синхронизация обновляет индекс выбранных документов с привязкой к каталогу и хешам файлов. Изменённые, удалённые или исключённые из каталога источники не выдаются как актуальные. [docs/PROJECT_BINDING.md:25–32, ev-247e068b32b20c3a; README.md:142–143, ev-132f47d276e2ccaa]
3. **Ищет контекст по вопросу.** Основной вызов — `get_docs_context`. Можно ограничить поиск документацией уровня проекта или выбрать область `all` для обзора проекта и модулей; `module_path` выбирает существующий модуль из каталога. [README.md:166–175, ev-232f696ea354011a, ev-787ffdef0998eca1; docs/PROJECT_BINDING.md:53–59, ev-9b02282e9ee9e85d]
4. **Возвращает доказательства, а отвечает агент.** Результат `docs_context` содержит фрагменты с идентификаторами источников и координатами. Выборка ограничена и не считается гарантированно полной: агент должен опираться на найденное и явно отмечать пробелы. Сервер не удостоверяет готовый ответ и не предоставляет разрешение на редактирование. [docs/modules/project-context-retrieval.md:72–82, ev-cd8708f17f496138; docs/adr/0003-context-first-project-reads.md:9–16, ev-21cd4c55f2ec3951]

Для проверки состояния и свежести предусмотрен `docs_status`; `prepare_docs` предназначен для операций подготовки и обновления, а не для обычного чтения. [README.md:120–125, ev-7d5f6a15cccbd7b6]

### Trace
{"tool": "execute", "input": {"code": "return await tools.opencode.list_mcp_resources({});"}, "status": "completed", "output_tokens": 569, "nested_calls": [{"tool": "opencode.list_mcp_resources", "status": "completed"}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Как MCP-сервер документации работает с собственной документацией проекта?\"',search_question:'How does the documentation MCP server work with the project’s own documentation?'});"}, "status": "completed", "output_tokens": 11705, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\"", "search_question": "How does the documentation MCP server work with the project’s own documentation?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "dff400a8e979862239942bc7d9d42142354dbeb626eb5c4bca56cd2fa57d9d34", "next_portion": 2, "portion": 1, "remaining_rows": 215}}

## L0 docatlas T01-en
Evidence 3/3; input 45061; tools 24297; steps 4
DocAtlas’s contribution guide asks you to:

- **Name your branch** `feat/<topic>` or `fix/<description>`.
- **Run the full test suite before opening the PR.**
- **Include tests for new connectors or fetchers where practical.** [CONTRIBUTING.md:59–63, ev-5adef38c969b3425]

The documented test commands are `pytest tests/ -v` on Linux/CI, or `arch -arm64 .venv/bin/python -m pytest tests/ -v` on macOS to avoid Rosetta issues. [CONTRIBUTING.md:45–58, ev-b1d5b59bb1adcb68]

For documentation impact, the PR summary includes an **advisory** report highlighting module docs that need review or are missing. Documentation edits remain explicit, reviewable changes. [README.md:176–189, ev-75f0cae70602887c, ev-fa52a902a1196387]

The retrieved guidance does not specify a required PR description format, approval count, or merge policy.

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"What is expected of me when I submit a pull request to DocAtlas?\"'});"}, "status": "completed", "output_tokens": 11969, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"What is expected of me when I submit a pull request to DocAtlas?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "158e301c8e5c53d193bb545e2185d66b6d298c4ae67f15b284b9f843538215e9", "next_portion": 2, "portion": 1, "remaining_rows": 195}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"What is expected of me when I submit a pull request to DocAtlas?\"',lookup_queries:['pull request contribution guidelines tests checklist review','contributing pull requests development tests lint']});"}, "status": "completed", "output_tokens": 11981, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"What is expected of me when I submit a pull request to DocAtlas?\"", "lookup_queries": ["pull request contribution guidelines tests checklist review", "contributing pull requests development tests lint"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "e13a8e6143793a0c9ada5eb2ce078db521064722071d755419bca7f9e7760fac", "next_portion": 2, "portion": 1, "remaining_rows": 198}}

## L0 docatlas T01-ru
Evidence 3/3; input 44972; tools 20706; steps 6
Согласно руководству для участников, перед отправкой pull request нужно:

- Назвать ветку `feat/<topic>` или `fix/<description>`.
- Запустить **полный набор тестов** до открытия PR.
- Для новых коннекторов или загрузчиков добавить тесты, где это практически возможно.  
  Источник: `CONTRIBUTING.md:59–63` (ev-4e12ab8c2f646242).

Также стоит проверить влияние изменений на документацию. Команда `doc-atlas docs-impact --base origin/main` показывает, какие поддерживаемые документы затронуты. В сводке каждого PR GitHub Actions публикует рекомендательный отчёт; документация автоматически не редактируется, поэтому необходимые правки нужно внести отдельным проверяемым изменением. Источник: `README.md:176–189` (ev-79f531095e3ccd5b, ev-83b31a79fcb790f1).

Новым участникам рекомендуют сначала прочитать `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md` (`CONTRIBUTING.md:7–12`, ev-996ea467889e3fce).

В найденном разделе о PR не указаны требования к шаблону описания, числу одобрений или форматированию кода.

### Trace
{"tool": "execute", "input": {"code": "return await tools.opencode.list_mcp_resources({});"}, "status": "completed", "output_tokens": 569, "nested_calls": [{"tool": "opencode.list_mcp_resources", "status": "completed"}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"'});"}, "status": "completed", "output_tokens": 814, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "c8fd9da59e5369184b755afc5c8136a159951d1d855f5ad756a8ad5b03381c5f", "next_portion": 2, "portion": 1, "remaining_rows": 141}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',lookup_queries:['pull request contribution guidelines checklist tests code review contributing']});"}, "status": "completed", "output_tokens": 7301, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "lookup_queries": ["pull request contribution guidelines checklist tests code review contributing"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "b8c8d5ac36b99c615d8bd42dbc487787a9f8166b123285ab13548bfb87ff80a3", "next_portion": 2, "portion": 1, "remaining_rows": 131}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',lookup_queries:['CONTRIBUTING.md pull request checklist before submitting tests lint formatting changes documentation'],});"}, "status": "completed", "output_tokens": 11675, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "lookup_queries": ["CONTRIBUTING.md pull request checklist before submitting tests lint formatting changes documentation"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "78affccbc2bb8b1ac697e6cf2d8aa2e7dac7dcde07a70ef38e2b500373759c27", "next_portion": 2, "portion": 1, "remaining_rows": 198}}

## L0 docatlas T02-ru
Evidence 3/3; input 38028; tools 15961; steps 5
Используйте **`doc-atlas clear-index` сначала без `--apply`**: по умолчанию команда только показывает план. Она удаляет производное состояние индекса, но сохраняет исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы. [docs/index-cleanup.md:1–16, ev-4695cd8634f4a35a, ev-3f99cafb0c9b7972]

### Безопасный порядок

1. **Выберите минимальную область.** Для одного проекта запустите предварительный просмотр:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --format json
   ```

   Это работает, если `docatlas.yaml` проекта указывает на его отдельный каталог `.docatlas`. Если проект использует общий индекс, `project-local` откажет: глобальная очистка затронет общий локальный индекс, а не только один проект. [docs/index-cleanup.md:17–28, 57–63, ev-25614a2d7c71e22b, ev-eee349d5abb7a614]

2. **Проверьте план целиком:** цели удаления, предупреждения и блокировки, а также `plan_digest`. В план могут входить SQLite и его служебные файлы, извлечённые документы, кэши и проверенное локальное векторное состояние. Убедитесь, что эти производные данные больше не нужны или их можно восстановить. [docs/index-cleanup.md:29–52, ev-6e108c4604f95add, ev-d267c77457907084]

3. **Остановите Docs MCP и процессы синхронизации**, использующие то же хранилище. Затем примените именно проверенный план:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --plan-digest <digest-из-предпросмотра> \
     --apply \
     --format json
   ```

   Устаревший digest или изменившиеся цели блокируют применение. Активные процессы и записи также блокируют очистку; `--allow-incomplete` не обходит эту защиту. [docs/index-cleanup.md:29–42, 89–105, ev-6e108c4604f95add, ev-77aab8d3cdf7d51e, ev-70b6dddcf682f677]

**Важно:** удалённые коллекции Qdrant команда не удаляет; непроверенное локальное векторное состояние сохраняется. `--allow-incomplete` лишь подтверждает, что указанное непроверенное состояние векторов или кэша останется. Индекс проектной документации впоследствии можно восстановить из файлов проекта через `prepare_docs(action="sync_project_docs")`. [docs/index-cleanup.md:53–56, 89–101, ev-52a22c6803d4f19a, ev-77aab8d3cdf7d51e]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?'});"}, "status": "completed", "output_tokens": 1617, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "492fa49c74ff763b4ef7600b199ea42deba761ff9b4554e142d9cc9eddbbe32c", "next_portion": 2, "portion": 1, "remaining_rows": 120}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?',lookup_queries:['index cleanup prune garbage collection dry-run retention','очистка индекса удаление garbage collection dry run']});"}, "status": "completed", "output_tokens": 7411, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "lookup_queries": ["index cleanup prune garbage collection dry-run retention", "очистка индекса удаление garbage collection dry run"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "90d2a88196ff9778e834632a2d6f4cb08d490f7dafd32afa4e8b300efd9b776d", "next_portion": 2, "portion": 1, "remaining_rows": 142}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?',lookup_queries:['index cleanup prune garbage collection dry-run retention','очистка индекса удаление garbage collection dry run'],portion:2,continuation_token:'90d2a88196ff9778e834632a2d6f4cb08d490f7dafd32afa4e8b300efd9b776d'});"}, "status": "completed", "output_tokens": 6586, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "lookup_queries": ["index cleanup prune garbage collection dry-run retention", "очистка индекса удаление garbage collection dry run"], "portion": 2, "continuation_token": "90d2a88196ff9778e834632a2d6f4cb08d490f7dafd32afa4e8b300efd9b776d"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "90d2a88196ff9778e834632a2d6f4cb08d490f7dafd32afa4e8b300efd9b776d", "next_portion": 3, "portion": 2, "remaining_rows": 102}}

## L0 docatlas T05-ru
Evidence 2/2; input 30734; tools 16229; steps 4
Верификация здесь — это **детерминированные сценарии установленного MCP**, а не полноценный прогон автономного агента OpenCode.

**Что проверяют:** `eval/project_binding/installed_stdio.py` запускает сценарии `unbound`, `black` и `mixed` с установленным wheel, настоящим установщиком проекта, MCP через stdio, SQLite и MiniLM. Для привязанных конфигураций проверяются:

- чтение с одним вопросом и эквивалентность вызову с явно указанным корнем;
- отклонение привязки к подпапке;
- текст и координаты источников;
- неизменность исходных файлов и индекса.

Сценарий `unbound` дополнительно проверяет регрессию при отсутствии целевого проекта. [docs/PROJECT_BINDING.md:72–79, ev-54e04a63f116e343]

**Чего это не доказывает:**

- успешную автономную работу OpenCode или модели и результаты измерения токенов; это отдельные проверки [docs/PROJECT_BINDING.md:74–79, ev-54e04a63f116e343];
- успех реального клиента или production smoke: installed stdio проверяет упаковку и протокол лишь в пределах протестированных сценариев и данных [docs/main-flow-evaluation.md:39–41, ev-82e3226a7a58cbac];
- что указанная директория модели означает её загрузку или участие в конкретном вызове [docs/PROJECT_BINDING.md:60–66, ev-0d4340c58eec1d88].

Кроме того, сама установка **привязывает соединение**, но не индексирует документы и не подтверждает завершение подготовки проекта [docs/PROJECT_BINDING.md:16–24, ev-510ba37e13473d71].

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?'});"}, "status": "completed", "output_tokens": 5628, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "43d2df5b01e3486f9a5bcfdd7e3e311d3ef606781f8e77f56777b1a451985087", "next_portion": 2, "portion": 1, "remaining_rows": 44}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?',lookup_queries:['OpenCode project-bound integration verification smoke checks limitations','OpenCode привязка к проекту проверка верификация']});"}, "status": "completed", "output_tokens": 10254, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?", "lookup_queries": ["OpenCode project-bound integration verification smoke checks limitations", "OpenCode привязка к проекту проверка верификация"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "e037482a8fc65d3f2c76616539707c8a06106393fc89eed3d02ccd806bed6550", "next_portion": 2, "portion": 1, "remaining_rows": 190}}

## L0 docatlas T10-ru
Evidence 3/3; input 12007; tools 5642; steps 3
Предлагается **расширить существующий интеграционный сценарий**: провести один и тот же исходный вопрос через настоящий публичный API, CLI или MCP — предпочтительно установленного пакета — на изолированных данных, с реальными retrieval, selection, storage и validation. Это предложение проверки, а не отчёт о полученном PASS. [docs/main-flow-evaluation.md:1–4, 17–20; ev-e17923ec2225793c, ev-bfb4f07197ce3145]

1. **Заранее задать независимый эталон** по исходным документам и требованиям: вопрос, версии корпуса, обязательные факты и опорные фрагменты, допустимые источники, scope и ожидаемые изменения состояния. Эталон нельзя брать из выдачи проверяемого кода. [docs/main-flow-evaluation.md:21; ev-8595aedfc4a23a53, ev-0bcffe70c51743a1]
2. **Запустить два раза — с подробными логами off и on** — из одинаковых исходных состояний, включая индекс, cache, права и consent. Результат первого запуска не становится ожидаемым ответом для второго. [docs/main-flow-evaluation.md:22; ev-e6134a01f1977e40, ev-3eeeefb6b9f534d2]
3. **Проверить корректность каждого запуска независимо, затем паритет:** факты, текст и цитаты, выбранные источники, scope/version, результат и состояние. Два одинаковых неверных ответа — не PASS. Логирование не должно менять права, выбор источников, побочные действия или число продуктовых вызовов; технические timestamps и trace IDs исключаются только по заранее заданному правилу. [docs/main-flow-evaluation.md:23; ev-6f00782ce1a4dbce, ev-53c6b7245db73091, ev-b782cf344facd786]
4. **Проверить диагностику:** при on трасса связывает этапы вопроса и помогает локализовать сбой, явно отмечая пропуски; при off подробная трасса отключена. В MCP диагностика отделена от protocol stdout. Само наличие события или exit 0 не заменяет проверки результата и состояния. [docs/main-flow-evaluation.md:24–25; ev-6584e706a2ceecfe, ev-2d31b9fe8ebaafab]

Внутренние mocks не предлагается использовать. Если для воспроизводимости подменён внешний транспорт, это нужно указать: такой запуск не доказывает работу живого провайдера. Дополнительно предлагаются отрицательные случаи: неверные версия/scope, недостаточность данных, отсутствие доступа или consent и отказ зависимости либо записи логов. [docs/main-flow-evaluation.md:26–36; ev-619df3053a1c1e0b, ev-2730173eddf81cd0]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?'});"}, "status": "completed", "output_tokens": 5295, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "7a5bd57866c15a439823e15b0f75443e4e79b02a02c9317a4db77eb727765af1", "next_portion": 2, "portion": 1, "remaining_rows": 2}}

## L0 docatlas T12-ru
Evidence 0/3; input 25573; tools 13894; steps 4
MCP-сервер DocAtlas работает с документацией проекта как с **источником фактов для клиента**, а не как с текстом, который он сам пишет или заверяет готовым ответом.

1. **Источники.** Документация хранится и проверяется в репозитории. Сервер извлекает только актуальные документы, явно включённые в каталог `docatlas.project-docs.yaml`: одно лишь привычное имя файла, ссылка из README или имя модуля не разрешают автоматически искать другие файлы. Файлы репозитория остаются источником истины; сервер не должен незаметно создавать документацию или делать коммиты. [docs/project-docs-mcp-workflow.md:1–6, `ev-1ed7ba2f75cd093b`; CONTRIBUTING.md:34–37, `ev-629b05ff6b0cc446`]

2. **Подготовка и актуальность.** Индексация выполняется отдельно через `prepare_docs(action="sync_project_docs")` и требует явного подтверждения изменения. Она привязана к выбранным элементам каталога, хешам файлов, хранилищу и ожидаемому поколению индекса. Изменённые, удалённые или исключённые из каталога документы не выдаются как актуальные; синхронизация не генерирует официальную документацию. [README.md:142–143, `ev-132f47d276e2ccaa`]

3. **Запрос и ответ.** Клиент передаёт исходный вопрос в `get_docs_context`. Сервер возвращает ограниченный контекст с указанием источников, а ответ формулирует сам клиент, отмечая пробелы. При нехватке безопасных подтверждений возвращается `insufficient_evidence`; для чтения проектной документации сервер не обещает заверенный им ответ. [README.md:126–137, `ev-339110a914bbf960`, `ev-551a62e246c38d49`; docs/adr/0003-context-first-project-reads.md:9–16, `ev-21cd4c55f2ec3951`]

4. **Рабочий цикл.** Если контекст указывает, что нужна подготовка, клиент выполняет предложенное действие `prepare_docs` с необходимыми разрешениями и повторяет вопрос. `docs_status` предназначен для явной проверки состояния, а не для обязательного поиска перед каждым запросом. Сервер запускается командой `doc-atlas mcp docs-serve`. [README.md:110–125, `ev-20e3297819aad7e1`, `ev-7d5f6a15cccbd7b6`; README.md:126–135, `ev-339110a914bbf960`]

При привязке к проекту выбор цели не выводится из текущего рабочего каталога процесса; сама привязка также **не означает**, что документы уже проиндексированы. [docs/PROJECT_BINDING.md:16–24, `ev-74003835177b5002`]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true})"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Как MCP-сервер документации работает с собственной документацией проекта?\"'})"}, "status": "completed", "output_tokens": 2873, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "e87606ce8aa012b6d5dfbd77fbe890029a0888d85078bf5fab084d24343eb9ea", "next_portion": 2, "portion": 1, "remaining_rows": 127}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Как MCP-сервер документации работает с собственной документацией проекта?\"',lookup_queries:['project documentation MCP server indexing catalog get_docs_context project sources local documentation preparation','документация самого проекта MCP сервер индексация каталог поиск источники']})"}, "status": "completed", "output_tokens": 10674, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\"", "lookup_queries": ["project documentation MCP server indexing catalog get_docs_context project sources local documentation preparation", "документация самого проекта MCP сервер индексация каталог поиск источники"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "e7386d8212b98d460bb3f52d0f5fdcca984ea1befe00eeee100eb52fd8c7c794", "next_portion": 2, "portion": 1, "remaining_rows": 224}}

## L0 docatlas T15-en
Evidence 2/2; input 9447; tools 3105; steps 3
**Because stock OpenCode can lose the evidence needed to resolve the response’s references.** The older `DOCATLAS_MCP_MODEL_VIEW=1` mode puts concise text in `content` but the complete source packet in MCP `_meta`. The documented stock OpenCode v2.1.2 adapter drops response `_meta`, so the original source packet is lost and the response’s short references cannot be resolved. The mode requires a host that preserves `_meta` out of band. [docs/opencode-compact-text.md:38–46, ev-ed36168c4eddf605; docs/mcp-docs-server.md:135–139, ev-dc8bdcddc647b08d]

For OpenCode, use **`DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`**, with `DOCATLAS_MCP_MODEL_VIEW` absent or `off`. Compact text carries the selected excerpts, evidence IDs, source URIs, paths and line ranges in the text itself; the two modes are mutually exclusive. [docs/opencode-compact-text.md:47–58, ev-3e833eb1d23824c5; docs/opencode-compact-text.md:101–106, ev-31ec2f05769c697c]

For an existing registration, rerun `doc-atlas install opencode`: upgrading the package alone does not rewrite OpenCode settings. The documented compatibility finding is specifically for stock OpenCode v2.1.2. [docs/mcp-docs-server.md:135–140, ev-dc8bdcddc647b08d]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Why shouldn\\'t OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?\"'});"}, "status": "completed", "output_tokens": 2758, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "fd75f34022683b7e1a5f7cca79f36c113eb18f841c6422fdfcb2da35346f34c5", "next_portion": 2, "portion": 1, "remaining_rows": 58}}

## L0 docatlas T19-ru
Evidence 4/4; input 13609; tools 7292; steps 3
Для управления **локальным процессом Qdrant, принадлежащим DocAtlas**, используется группа команд `doc-atlas qdrant`:

| Команда | Назначение |
|---|---|
| `doc-atlas qdrant up` | Скачать закреплённый бинарный файл при необходимости и запустить Qdrant в фоне. `--port` задаёт порт, а `--docker` выводит фрагмент Docker Compose вместо запуска управляемого бинарного файла. |
| `doc-atlas qdrant down` | Остановить управляемый процесс; команда не использует PID-файл, который не был создан DocAtlas. |
| `doc-atlas qdrant status` | Показать PID, порт, URL, состояние процесса и проверки работоспособности, принадлежность DocAtlas и версию. `--json` выводит результат в JSON. |
| `doc-atlas qdrant upgrade` | Заменить управляемый бинарный файл, сохранив хранилище на диске. Для работающего процесса требуется `--force`; межверсионная миграция хранилища не автоматизирована. |
| `doc-atlas qdrant logs` | Просмотреть вывод процесса; `--stderr` выбирает поток ошибок. |

Источник: `wiki/Commands.md`, строки 104–115, evidence ID `ev-14d1cb95bf206e1c`, `ev-42465a2e6fd42f82`.

При указании `DOCATLAS_QDRANT_URL` DocAtlas подключается к существующему серверу и пропускает управление локальным жизненным циклом (`wiki/Commands.md`, строки 116–122, `ev-2466206b07eae211`). Администрирование Qdrant относится к возможностям, поддерживаемым только для сопровождения (*maintenance-only*): `README.md`, строки 217–218, `ev-2f3bd8aeff4ba76c`.

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 347, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Какие команды DocAtlas используются для управления Qdrant?'});"}, "status": "completed", "output_tokens": 6945, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Какие команды DocAtlas используются для управления Qdrant?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "cf80f87af8fff51c4cfd29cfd86043de9b52e79f0159f89e8d582b4a4a51e63a", "next_portion": 2, "portion": 1, "remaining_rows": 89}}

## L0 search T01-en
Evidence 3/3; input 6097; tools 2887; steps 3
Before opening a PR, DocAtlas asks you to:

- Name your branch `feat/<topic>` or `fix/<description>`.
- Run the full test suite.
- Include tests for new connectors or fetchers where practical. [CONTRIBUTING.md:59–63](CONTRIBUTING.md#L59-L63)

The documented full-suite command is `pytest tests/ -v` on Linux/CI, or `arch -arm64 .venv/bin/python -m pytest tests/ -v` on macOS to avoid Rosetta architecture issues. [CONTRIBUTING.md:45–57](CONTRIBUTING.md#L45-L57)

The bundled GitHub Actions workflow also publishes an **advisory documentation-impact report** in each PR summary. Check it for documentation that needs review; any resulting documentation edit should be an explicit, reviewable change. [README.md:176–188](README.md#L176-L188)

For new contributors, the project recommends starting with the README, contributing guide, documentation index, and project map. [CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "**/*CONTRIBUT*", "hidden": true}, "status": "completed", "output_tokens": 23, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "pull request|pull requests|Pull Request", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 76, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/CONTRIBUTING.md"}, "status": "completed", "output_tokens": 790, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/README.md", "offset": 145, "limit": 65}, "status": "completed", "output_tokens": 1501, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "**/*", "hidden": true, "limit": 100}, "status": "completed", "output_tokens": 497, "nested_calls": [], "code_error": false, "truncated": false}

## L0 search T01-ru
Evidence 3/3; input 6014; tools 2795; steps 3
При отправке PR в DocAtlas от вас ожидается следующее:

- Назовите ветку `feat/<topic>` или `fix/<description>`.
- **До открытия PR запустите полный набор тестов.** Для Linux/CI указана команда `pytest tests/ -v`; для macOS — `arch -arm64 .venv/bin/python -m pytest tests/ -v`.
- Для новых коннекторов или источников данных (*fetchers*) добавьте тесты там, где это практически возможно. [CONTRIBUTING.md:45–63](CONTRIBUTING.md#L45-L63)

Также новым участникам рекомендуют сначала прочитать `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md`. [CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)

Если изменение затрагивает документацию, учтите отчёт в сводке PR: он указывает, какие документы модулей стоит проверить и для каких изменённых модулей поддерживаемой документации нет. Отчёт носит рекомендательный характер; правки документации вносятся отдельно, в виде явного изменения для ревью. [README.md:176–188](README.md#L176-L188)

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "**/*CONTRIBUT*", "hidden": true}, "status": "completed", "output_tokens": 23, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "pull request|Pull Request|pull-request", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 76, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/CONTRIBUTING.md"}, "status": "completed", "output_tokens": 790, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/README.md", "offset": 150, "limit": 60}, "status": "completed", "output_tokens": 1409, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "**/*", "hidden": true, "limit": 150}, "status": "completed", "output_tokens": 497, "nested_calls": [], "code_error": false, "truncated": false}

## L0 search T02-ru
Evidence 0/3; input 6352; tools 2425; steps 3
Безопасный способ — использовать **`doc-atlas clear-index`**: без `--apply` команда только показывает план. Она удаляет производное состояние индекса, сохраняя исходные файлы проекта, `docatlas.yaml`, конфигурацию и посторонние файлы. Не путайте её с более разрушительной командой `doc-atlas clear`, которая может удалить конфигурацию и кеши моделей. [docs/index-cleanup.md:3–15, 83–85]

### Очистка одного проекта

1. Убедитесь, что `docatlas.yaml` проекта указывает на его собственный каталог `.docatlas`. Для общего индекса выборочное удаление строк одного проекта не поддерживается: `project-local` откажется работать с общим хранилищем. [docs/index-cleanup.md:19–20, 57–62]

2. Получите план и проверьте список целей, предупреждения и блокирующие условия:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --format json
   ```

3. Остановите Docs MCP и процессы синхронизации, использующие это хранилище. Затем примените **именно просмотренный план**, передав его `plan_digest`:

   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --plan-digest <digest-from-preview> \
     --apply \
     --format json
   ```

   Если план или состояние целей изменились, применение будет отклонено. Живые процессы и активные записи также блокируют очистку. [docs/index-cleanup.md:29–41, 89–91, 102–106]

План может включать базу SQLite и её вспомогательные файлы, извлечённые документы, кеши и локальный managed-Qdrant с подтверждённым владением. Исходники не удаляются; позднее индекс можно восстановить через `prepare_docs(action="sync_project_docs")`. [docs/index-cleanup.md:43–55]

Если действительно нужно очистить **все локальные индексы** в DocAtlas home, используйте тот же порядок с `--scope global`; этот вариант не ограничен одним проектом. [docs/index-cleanup.md:64–81]

**Важно:** удалённые коллекции Qdrant не удаляются; локальное векторное состояние без маркера владения сохраняется и отмечается как неполное. Флаг `--allow-incomplete` лишь подтверждает, что указанное непроверенное состояние останется: он не обходит блокировку живыми процессами и не разрешает удаление удалённых данных. [docs/index-cleanup.md:91, 96–100]

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "очист|cleanup|prune|garbage|garbage.collect|delete index|удалени", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 1029, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/index-cleanup.md"}, "status": "completed", "output_tokens": 1396, "nested_calls": [], "code_error": false, "truncated": false}

## L0 search T05-ru
Evidence 2/2; input 13585; tools 3309; steps 5
Верификация привязанной интеграции проверяет **работу установленного MCP на детерминированных сценариях**, а не полноценный диалог агента:

- `eval/project_binding/installed_stdio.py` запускает сценарии `unbound`, `black` и `mixed` с установленным wheel, настоящим установщиком проекта, stdio MCP, SQLite и MiniLM. Для привязанных вариантов проверяются запросы только с вопросом, совпадение результата с явным корнем, отклонение привязки к подкаталогу, текст источников и координаты, а также неизменность исходников и индекса. Для непривязанного варианта проверяется регрессия с отсутствующей целью. [docs/PROJECT_BINDING.md:72–79]
- Отдельно `docs_status(action="project")` показывает привязку, эффективную конфигурацию доставки и фактическую готовность проекта. При этом сама установка привязывает цель, но **не индексирует документы и не подтверждает завершение подготовки**. [docs/PROJECT_BINDING.md:16–23, 60–65]

**Чего это не доказывает:** такие тесты не являются автономным запуском OpenCode с моделью и не измеряют расход токенов. Указанная директория MiniLM сама по себе не доказывает, что модель загрузилась или участвовала в работе. [docs/PROJECT_BINDING.md:62–65, 72–79]

Для подтверждения полезной доставки нужно отдельно проверить текст источника, публичные ссылки и диапазоны строк в фактическом сообщении инструмента OpenCode: сохранённого полного ответа, статуса `ok`, числа источников или `truncated=false` недостаточно. Качество у клиента/провайдера и оплаченные токены требуют отдельного измерения на реальном клиенте. [docs/opencode-compact-text.md:123–126]

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "верификац|verification|verify", "limit": 100}, "status": "completed", "output_tokens": 562, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "OpenCode", "limit": 100}, "status": "completed", "output_tokens": 1255, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/PROJECT_BINDING.md"}, "status": "completed", "output_tokens": 987, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/opencode-compact-text.md", "offset": 114, "limit": 30}, "status": "completed", "output_tokens": 505, "nested_calls": [], "code_error": false, "truncated": true}

## L0 search T10-ru
Evidence 3/3; input 8368; tools 5235; steps 3
Предлагается расширить существующий интеграционный сценарий и провести **один и тот же пользовательский вопрос через настоящий публичный API, CLI или MCP**, предпочтительно установленного пакета. Данные должны быть изолированы, а retrieval, selection, storage и validation — реальными. Это предложение проверки, а не отчёт о полученном PASS. [docs/main-flow-evaluation.md:3–5, 17–19](docs/main-flow-evaluation.md#L3-L19)

1. **Заранее подготовить независимый эталон:** вопрос, версии корпуса, обязательные факты и дословные фрагменты, допустимые источники и диапазоны, scope и ожидаемые изменения состояния. Эталон берётся из документов и требований, а не из ответа проверяемого кода. [docs/main-flow-evaluation.md:21](docs/main-flow-evaluation.md#L21)
2. **Выполнить две попытки — logging off и on** — из одинаковых исходных состояний, включая индекс, cache, права и consent. Результат первого запуска не использовать как эталон второго. [docs/main-flow-evaluation.md:22](docs/main-flow-evaluation.md#L22)
3. **Независимо проверить оба результата**, включая факты и соответствие цитат документам, затем сравнить источники, scope/version, продуктовый результат и состояние. Два одинаковых неверных ответа не дают PASS; переключение логов не должно менять права, источники, побочные действия или число продуктовых вызовов. [docs/main-flow-evaluation.md:23](docs/main-flow-evaluation.md#L23)
4. **Проверить диагностику:** при on трасса связывает этапы вопроса и помогает локализовать сбой, при off подробная трасса отключена; в MCP диагностика отделена от protocol stdout. Событие или exit 0 не заменяют проверку результата и состояния. [docs/main-flow-evaluation.md:24](docs/main-flow-evaluation.md#L24)

Внутренние mocks использовать не предлагается; подмена внешнего транспорта должна быть явно оговорена и не доказывает работу живого провайдера. Одна пара запусков также не доказывает общую надёжность недетерминированного агента. [docs/main-flow-evaluation.md:26, 39–41](docs/main-flow-evaluation.md#L26)

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "логирован|logging", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 146, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/main-flow-evaluation.md"}, "status": "completed", "output_tokens": 1739, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/main-flow-logging.md"}, "status": "completed", "output_tokens": 1596, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docatlas.project-docs.yaml"}, "status": "completed", "output_tokens": 1754, "nested_calls": [], "code_error": false, "truncated": false}

## L0 search T12-ru
Evidence 3/3; input 18843; tools 11457; steps 3
MCP-сервер DocAtlas работает с документацией проекта по принципу **«сначала найти подтверждённые источниками сведения, затем предоставить их клиенту»**. Он не создаёт официальный ответ или документацию самостоятельно.

- **Источники задаются явно.** Сервер читает только файлы, перечисленные буквальными относительными путями в `docatlas.project-docs.yaml`; наличие README, ссылки или каталога `docs/` само по себе не даёт права читать другие файлы. В собственном каталоге DocAtlas, например, перечислены `README.md`, описание MCP-сервера и руководство по работе с документацией проекта. [docs/project-docs-mcp-workflow.md:3–5, 23–28](docs/project-docs-mcp-workflow.md#L3-L5), [docatlas.project-docs.yaml:65–72, 113–120, 129–136](docatlas.project-docs.yaml#L65-L72)

- **Запрос начинается с `get_docs_context`.** Клиент передаёт вопрос и путь к проекту; при необходимости он также ограничивает поиск уровнем проекта или точным путём модуля. Чтение не обновляет индекс и не изменяет репозиторий. [docs/mcp-docs-server.md:26–40, 82–87](docs/mcp-docs-server.md#L26-L40), [docs/project-docs-mcp-workflow.md:96–108](docs/project-docs-mcp-workflow.md#L96-L108)

- **Результат — данные для ответа, а не готовый ответ.** Сервер возвращает `docs_context` с привязкой к источникам: в частности, с путями, хешами, дословными фрагментами и координатами. Ответ формулирует клиентская модель, опираясь на найденное и указывая пробелы; при недостатке безопасных данных возвращается `insufficient_evidence`. Найденный фрагмент не считается доказательством полноты ответа. [docs/mcp-docs-server.md:48–71](docs/mcp-docs-server.md#L48-L71)

- **Подготовка индекса отделена от чтения.** Если сервер вернул необходимое действие, клиент выполняет именно его через `prepare_docs`, соблюдая подтверждения и привязки к источникам; затем, после проверки успеха и готовности, повторяет исходный вопрос без изменений. `docs_status` предназначен для состояния, свежести или задания, а не для первоначального поиска. [docs/mcp-docs-server.md:26–40](docs/mcp-docs-server.md#L26-L40)

- **Синхронизация не редактирует документацию.** Для записи выбранных документов в индекс требуется явно подтверждённая операция с хешами каталога и документов, ожидаемым поколением и выбранным клиентом приватным хранилищем вне проекта. Изменённые, удалённые или исключённые из каталога документы не выдаются как актуальные свидетельства. Сама операция не создаёт документацию и не удаляет физически все старые записи. [docs/project-docs-mcp-workflow.md:61–89](docs/project-docs-mcp-workflow.md#L61-L89)

При запросе на изменение документации агент может подготовить обычный проверяемый Git-патч, но найденный контекст сам по себе **не является разрешением на редактирование**. [docs/mcp-docs-server.md:103–105](docs/mcp-docs-server.md#L103-L105)

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "**/*MCP*"}, "status": "completed", "output_tokens": 3, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "MCP", "limit": 100}, "status": "completed", "output_tokens": 4255, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/README.md", "offset": 110, "limit": 53}, "status": "completed", "output_tokens": 1601, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/project-docs-mcp-workflow.md"}, "status": "completed", "output_tokens": 1695, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/mcp-docs-server.md", "limit": 200}, "status": "completed", "output_tokens": 2447, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docatlas.project-docs.yaml", "limit": 145}, "status": "completed", "output_tokens": 1456, "nested_calls": [], "code_error": false, "truncated": true}

## L0 search T15-en
Evidence 2/2; input 6613; tools 3512; steps 3
OpenCode users shouldn’t simply enable `DOCATLAS_MCP_MODEL_VIEW=1` because **the older mode depends on metadata that stock OpenCode drops**. It puts concise text in `content[].text` but keeps the complete source packet in MCP `_meta`. The pinned OpenCode v2.1.2 adapter retains `content` and `structuredContent`, but drops response `_meta`; consequently, the original source packet is lost and the response-local short references cannot be resolved. [docs/opencode-compact-text.md:36–45](docs/opencode-compact-text.md#L36-L45)

**Use the self-contained compact-text route instead:** rerun `doc-atlas install opencode` for an existing registration, adding `--project` for a project-owned config, then restart OpenCode. The registration sets `DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`; leave `DOCATLAS_MCP_MODEL_VIEW` absent or off. Updating the package alone does not rewrite an existing registration. The two modes are mutually exclusive. [docs/opencode-compact-text.md:3–11, 47–58, 101–106](docs/opencode-compact-text.md#L3-L11)

Compact text retains selected source text and its original evidence IDs, URIs, paths and line ranges in the model-visible text, rather than relying on private `_meta`. It is still a model-facing view, not a replacement for the full machine packet. [docs/opencode-compact-text.md:47–50, 60–63](docs/opencode-compact-text.md#L47-L50)

The documented offline projection found a **25.7%** text-token reduction for compact text, versus **38.4%** for the incompatible private-metadata view. That is a transport measurement, not proof of paid-model accuracy or billing savings; no paid GPT/OpenCode conversation or billing was measured. [docs/opencode-compact-text.md:128–140](docs/opencode-compact-text.md#L128-L140)

### Trace
{"tool": "grep", "input": {"pattern": "DOCATLAS_MCP_MODEL_VIEW", "path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "limit": 100}, "status": "completed", "output_tokens": 173, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/opencode-compact-text.md"}, "status": "completed", "output_tokens": 2287, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs/mcp-docs-server.md", "offset": 95, "limit": 75}, "status": "completed", "output_tokens": 1052, "nested_calls": [], "code_error": false, "truncated": true}

## L0 search T19-ru
Evidence 4/4; input 8575; tools 3423; steps 3
Для управления локальным процессом Qdrant используется группа команд `doc-atlas qdrant`:

- **`up`** — запускает Qdrant в фоне, при необходимости скачивая закреплённый бинарный файл. Опция `--port` задаёт порт, а `--docker` выводит фрагмент Docker Compose вместо запуска.
- **`down`** — останавливает процесс, управляемый DocAtlas; не использует чужой PID-файл.
- **`status`** — показывает PID, порт, URL, состояние процесса, принадлежность DocAtlas, работоспособность и версию. `--json` выводит данные в JSON.
- **`upgrade`** — заменяет управляемый бинарный файл, сохраняя хранилище. Для обновления при работающем процессе нужен `--force`; миграция хранилища между версиями не автоматизирована.
- **`logs`** — показывает вывод процесса; `--stderr` выбирает стандартный поток ошибок. [wiki/Commands.md:104–114](wiki/Commands.md#L104-L114)

Администрирование Qdrant относится к возможностям **только для обслуживания**. Если задан `DOCATLAS_QDRANT_URL`, DocAtlas использует существующий сервер и пропускает управление локальным процессом. [README.md:211–217](README.md#L211-L217); [wiki/Commands.md:116–120](wiki/Commands.md#L116-L120)

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project", "pattern": "Qdrant", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 2180, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/wiki/Commands.md", "offset": 104, "limit": 21}, "status": "completed", "output_tokens": 643, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/README.md", "offset": 208, "limit": 14}, "status": "completed", "output_tokens": 421, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L0-0/project/docs", "pattern": "qdrant", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 179, "nested_calls": [], "code_error": false, "truncated": false}

## L2 clarified T01-ru
Evidence 3/3; input 90305; tools 37024; steps 6
Согласно руководству для контрибьюторов, при отправке PR ожидается следующее:

1. Назовите ветку `feat/<topic>` или `fix/<description>`.
2. **До открытия PR запустите полный набор тестов.**
3. Если добавляете коннектор или fetcher, включите тесты там, где это практически возможно. [CONTRIBUTING.md:59–63, ev-1451334086980703]

Также проверьте влияние изменений на документацию: в сводке PR публикуется отчёт `docs-impact`, который показывает документацию модулей, требующую проверки, и изменения без поддерживаемой документации. По умолчанию отчёт информационный; сами правки документации вносятся отдельно как изменения, доступные для ревью. [README.md:188–189, ev-25bb7a3681793cf2; docs/change-aware-docs.md:30–31, ev-1c5ab3858c921879]

В найденном разделе о подаче PR не указаны требования к шаблону описания, числу ревьюеров или конкретной команде запуска тестов.

### Trace
{"tool": "execute", "input": {"code": "return await tools.opencode.list_mcp_resources({});"}, "status": "completed", "output_tokens": 569, "nested_calls": [{"tool": "opencode.list_mcp_resources", "status": "completed"}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что от меня ожидается, когда я отправляю pull request в DocAtlas?',search_question:'What is expected of me when I submit a pull request to DocAtlas?'});"}, "status": "completed", "output_tokens": 12437, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?", "search_question": "What is expected of me when I submit a pull request to DocAtlas?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "7a5e86fd8348ad344b215e4ac188c076c3f6658ca6c56d2fb6695a85850d908d", "next_portion": 2, "portion": 1, "remaining_rows": 402}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что от меня ожидается, когда я отправляю pull request в DocAtlas?',search_question:'What is expected of me when I submit a pull request to DocAtlas?',portion:2,continuation_token:'7a5e86fd8348ad344b215e4ac188c076c3f6658ca6c56d2fb6695a85850d908d'});"}, "status": "completed", "output_tokens": 11496, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?", "search_question": "What is expected of me when I submit a pull request to DocAtlas?", "portion": 2, "continuation_token": "7a5e86fd8348ad344b215e4ac188c076c3f6658ca6c56d2fb6695a85850d908d"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "7a5e86fd8348ad344b215e4ac188c076c3f6658ca6c56d2fb6695a85850d908d", "next_portion": 3, "portion": 2, "remaining_rows": 344}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что от меня ожидается, когда я отправляю pull request в DocAtlas?',search_question:'What is expected of me when I submit a pull request to DocAtlas?',lookup_queries:['What are the contributor expectations when submitting a pull request to DocAtlas?','contributing pull request contributor guidelines checklist tests']});"}, "status": "completed", "output_tokens": 12186, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?", "search_question": "What is expected of me when I submit a pull request to DocAtlas?", "lookup_queries": ["What are the contributor expectations when submitting a pull request to DocAtlas?", "contributing pull request contributor guidelines checklist tests"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "7c57dae0fbd1ce50411f5fe3b5d47c0f303a1efd38fea2574526237e578e7403", "next_portion": 2, "portion": 1, "remaining_rows": 638}}

## L2 clarified T12-ru
Evidence 0/3; input 44650; tools 23506; steps 4
MCP-сервер DocAtlas работает не только с документацией внешних библиотек: он умеет находить **собственную документацию репозитория** и передавать её агенту как контекст с указанием источников. Ответ формирует агент, а не сервер. [README.md:17–28, ev-dfd6cf329b378e5a; docs/adr/0003-context-first-project-reads.md:9–15, ev-96eefe92741ad96f]

Как устроен процесс:

1. **Подключение проекта.** Сервер запускается командой `doc-atlas mcp docs-serve`. В привязанной к проекту конфигурации цель задаётся при подключении; сама привязка ещё не означает, что документы проиндексированы. [docs/mcp-docs-server.md:1–9, ev-f7ef5ecbfbb6cb39; docs/PROJECT_BINDING.md:16–24, ev-9d8ef207c31250fa]
2. **Подготовка документов.** Агент сначала вызывает `get_docs_context`. Если требуется подготовка, он следует возвращённой рекомендации для `prepare_docs` и повторяет исходный вопрос. Для синхронизации после изменений предусмотрено `prepare_docs(action="sync_project_docs")`. Сервер ищет только явно включённые актуальные элементы каталога: имя README или ссылка на файл сами по себе не дают разрешения обнаруживать другие файлы. [docs/DOCMANCER_PRODUCT_BRIEF.md:13–26, ev-1f679a7959bbe47f, ev-5313bbebf30816c7; README.md:166–173, ev-f6064d85308a996d; docs/project-docs-mcp-workflow.md:1–6, ev-36c004a6b087d563]
3. **Поиск в нужной области.** `scope="project"` ограничивает запрос документацией уровня репозитория; `scope="all"` включает также документацию модулей. Точный `module_path` выбирает существующий модуль, а не произвольную папку. [docs/mcp-quickstart-example.md:8–22, ev-07f379f2fc054c17; docs/PROJECT_BINDING.md:53–59, ev-c1b2c7a92cbe82b3]
4. **Ответ с оговорками.** Сервер возвращает ограниченные выдержки с происхождением; агент использует их для ответа и отмечает пробелы. Наличие фрагмента не удостоверяет полноту ответа и не разрешает редактирование. [README.md:29–35, ev-3d0ea8c70f3d27d2; docs/adr/0003-context-first-project-reads.md:9–15, ev-96eefe92741ad96f]

Документация зависимостей обрабатывается отдельно: её предварительная загрузка читает манифесты и lock-файлы, но **не индексирует** собственные README, docs или wiki проекта. [docs/project-docs-demo.md:56–61, ev-cdb514f98df63d79]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Как MCP-сервер документации работает с собственной документацией проекта?\"',search_question:'How does the documentation MCP server work with the project’s own documentation?'});"}, "status": "completed", "output_tokens": 11351, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\"", "search_question": "How does the documentation MCP server work with the project’s own documentation?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "8766ca199a4ff7b0da833d7cdeace29ac76342d5865a60e230bccc22ca22066e", "next_portion": 2, "portion": 1, "remaining_rows": 447}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Как MCP-сервер документации работает с собственной документацией проекта?\"',search_question:'How does the documentation MCP server work with the project’s own documentation?',portion:2,continuation_token:'8766ca199a4ff7b0da833d7cdeace29ac76342d5865a60e230bccc22ca22066e'});"}, "status": "completed", "output_tokens": 11819, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Как MCP-сервер документации работает с собственной документацией проекта?\"", "search_question": "How does the documentation MCP server work with the project’s own documentation?", "portion": 2, "continuation_token": "8766ca199a4ff7b0da833d7cdeace29ac76342d5865a60e230bccc22ca22066e"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "8766ca199a4ff7b0da833d7cdeace29ac76342d5865a60e230bccc22ca22066e", "next_portion": 3, "portion": 2, "remaining_rows": 389}}

## L2 docatlas T01-en
Evidence 3/3; input 69914; tools 32077; steps 5
DocAtlas’s contribution guide asks you to:

- Name your branch `feat/<topic>` or `fix/<description>`.
- Run the **full test suite before opening** the pull request.
- Include tests for new connectors or fetchers where practical.  
  [CONTRIBUTING.md:59–63, ev-5452c2e03b2abb73]

Also check the PR’s **docs-impact report** for documentation that needs review or is missing. The report is advisory by default; any documentation edit is an explicit, reviewable change. [README.md:188–189, ev-e31d889d5beaf70e; docs/change-aware-docs.md:30–31, ev-6e1828f9c60f63bb]

For orientation, the guide recommends that new contributors read the README, contributing guide, documentation index, and project map. [CONTRIBUTING.md:7–12, ev-003ed175728213ac]

I did not find a documented general requirement for a particular PR description, review process, or test command in the retrieved guidance.

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"What is expected of me when I submit a pull request to DocAtlas?\"'});"}, "status": "completed", "output_tokens": 7170, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"What is expected of me when I submit a pull request to DocAtlas?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "d0943d39d7069044fe694c72a0f381013ce032559a20179b301418729b2040df", "next_portion": 2, "portion": 1, "remaining_rows": 204}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"What is expected of me when I submit a pull request to DocAtlas?\"',lookup_queries:['CONTRIBUTING pull request guidelines tests description checklist review','pull request template contributor requirements']});"}, "status": "completed", "output_tokens": 12191, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"What is expected of me when I submit a pull request to DocAtlas?\"", "lookup_queries": ["CONTRIBUTING pull request guidelines tests description checklist review", "pull request template contributor requirements"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "70e16cde0f2e7bfaca4e46f8510fc0c4ac91a5dd2decd045c1fc639a05f68402", "next_portion": 2, "portion": 1, "remaining_rows": 571}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"What is expected of me when I submit a pull request to DocAtlas?\"',lookup_queries:['CONTRIBUTING.md pull requests submitting changes tests lint formatting checklist']});"}, "status": "completed", "output_tokens": 12380, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"What is expected of me when I submit a pull request to DocAtlas?\"", "lookup_queries": ["CONTRIBUTING.md pull requests submitting changes tests lint formatting checklist"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "3798bff70105c3c88f0da231e8b559573860fec7d2547fb1d54dc44ff8f0ff35", "next_portion": 2, "portion": 1, "remaining_rows": 382}}

## L2 docatlas T01-ru
Evidence 0/3; input 86922; tools 36413; steps 6
По найденной документации от нового участника ожидается следующее:

- **Ознакомиться с проектом:** начать с `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md` — они описывают продукт, структуру репозитория и процесс участия. [CONTRIBUTING.md:7–12, ev-779b53944eb75e7f]
- **Проверить влияние изменений на документацию.** В сводке PR GitHub Actions публикует рекомендательный отчёт: он показывает документацию модулей, которую стоит проверить, и изменения модулей без поддерживаемой документации. Исправления документации вносятся отдельным явным изменением, пригодным для ревью. По умолчанию проверка `docs-impact` информационная, а не блокирующая. [README.md:188–189, ev-44cfe0eb9f9a28bc; docs/change-aware-docs.md:30–31, ev-bb3570b9652f029c]

**Ограничение:** в полученных фрагментах не нашлось общего чек-листа PR с обязательными командами тестирования, требованиями к описанию или правилами ревью. Поэтому подтвердить их по доступным свидетельствам я не могу.

### Trace
{"tool": "execute", "input": {"code": "return await tools.opencode.list_mcp_resources({});"}, "status": "completed", "output_tokens": 569, "nested_calls": [{"tool": "opencode.list_mcp_resources", "status": "completed"}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',lookup_queries:['pull request contributing guidelines checklist tests review','contributing pull request requirements']});"}, "status": "completed", "output_tokens": 11672, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "lookup_queries": ["pull request contributing guidelines checklist tests review", "contributing pull request requirements"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "979b3c78c2c2baf55046dd898132eb671f5fc49b934190d421122df0266d8819", "next_portion": 2, "portion": 1, "remaining_rows": 509}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',lookup_queries:['pull request contributing guidelines checklist tests review','contributing pull request requirements'],portion:2,continuation_token:'979b3c78c2c2baf55046dd898132eb671f5fc49b934190d421122df0266d8819'});"}, "status": "completed", "output_tokens": 11708, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "lookup_queries": ["pull request contributing guidelines checklist tests review", "contributing pull request requirements"], "portion": 2, "continuation_token": "979b3c78c2c2baf55046dd898132eb671f5fc49b934190d421122df0266d8819"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "979b3c78c2c2baf55046dd898132eb671f5fc49b934190d421122df0266d8819", "next_portion": 3, "portion": 2, "remaining_rows": 455}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"',lookup_queries:['CONTRIBUTING.md \"Pull requests\" tests checklist','\"pull request\" \"tests\" \"documentation\" contributing']});"}, "status": "completed", "output_tokens": 12128, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Что от меня ожидается, когда я отправляю pull request в DocAtlas?\"", "lookup_queries": ["CONTRIBUTING.md \"Pull requests\" tests checklist", "\"pull request\" \"tests\" \"documentation\" contributing"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "6a0656e788ada11c8bb919c5b45553a389bcd8034d3f1cd106a94703cbb57089", "next_portion": 2, "portion": 1, "remaining_rows": 592}}

## L2 docatlas T02-ru
Evidence 3/3; input 42409; tools 22697; steps 4
Самый безопасный подход — сначала получить **план очистки без применения**, проверить все его цели и только затем подтверждать удаление. Если в плане есть данные, которые ещё нужны, не применяйте его.

### Очистка индекса одного проекта

Этот вариант работает только для отдельного хранилища проекта `.docatlas`, определённого через его `docatlas.yaml`:

```bash
doc-atlas clear-index \
  --scope project-local \
  --project-path /absolute/path/to/project \
  --format json
```

Команда без `--apply` показывает цели, блокировки и `plan_digest`. Проверьте план, затем остановите Docs MCP и процессы синхронизации, использующие то же хранилище. Если всё в плане можно удалить, примените **именно проверенный** план: [docs/index-cleanup.md:17–42, ev-a8cde0b524e60d4f, ev-b334c5cfcfd8ded3].

```bash
doc-atlas clear-index \
  --scope project-local \
  --project-path /absolute/path/to/project \
  --plan-digest <digest-from-preview> \
  --apply \
  --format json
```

В план могут попасть SQLite-база и её служебные файлы, извлечённые документы, кэши и подтверждённое локальное хранилище Qdrant. Исходники проекта и `docatlas.yaml` не являются целями очистки; индекс документации проекта позднее можно восстановить через `prepare_docs(action="sync_project_docs")` [docs/index-cleanup.md:43–56, ev-74b84d1ef3fab3fc, ev-4159dc0e258186c2].

### Важные ограничения

- Если проект использует **общий индекс**, `project-local` откажет в очистке: DocAtlas не угадывает принадлежность строк в общей базе. `--scope global` очищает все локальные индексы в DocAtlas home, поэтому не используйте его, если другие индексы ещё нужны. Для независимой очистки проекту требуется отдельная локальная конфигурация [docs/index-cleanup.md:57–74, ev-d18345dc5493a4cd, ev-ffc2773f8455a0da].
- Не заменяйте `clear-index` командой `doc-atlas clear`: последняя шире и может удалить конфигурацию и кэши моделей [docs/index-cleanup.md:75–86, ev-fd64164c2bb7bcde].
- Устаревший план или активный процесс блокируют применение. Удалённые коллекции Qdrant не удаляются; локальное векторное состояние без подтверждённого владельца сохраняется и отмечается как неполное. `--allow-incomplete` не снимает блокировку активного процесса и не разрешает непроверенное удаление [docs/index-cleanup.md:89–101, ev-547955e61e47ac1e].

Если задача лишь в том, чтобы устаревшие документы не попадали в результаты, физическая очистка может не понадобиться: изменённые, удалённые или исключённые из каталога источники отфильтровываются при чтении, хотя их старые строки физически не удаляются [docs/project-docs-mcp-workflow.md:83–90, ev-69de5fb835f9f8e8].

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?',lookup_queries:['index cleanup prune dry run retention delete safety','очистка индекса удаление dry-run сохранение данных']});"}, "status": "completed", "output_tokens": 10845, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "lookup_queries": ["index cleanup prune dry run retention delete safety", "очистка индекса удаление dry-run сохранение данных"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "ca1767a73358923126ce6ae3418210376045f5491d5b4df0ce11b2100777eb8c", "next_portion": 2, "portion": 1, "remaining_rows": 661}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?',search_question:'docs/index-cleanup.md clear-index dry-run scope global project-local library prune commands confirmation',lookup_queries:['docs/index-cleanup.md preview apply clear-index commands scopes','prune library versions dry_run keep latest remove data']});"}, "status": "completed", "output_tokens": 11516, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?", "search_question": "docs/index-cleanup.md clear-index dry-run scope global project-local library prune commands confirmation", "lookup_queries": ["docs/index-cleanup.md preview apply clear-index commands scopes", "prune library versions dry_run keep latest remove data"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "553edad331d7e9bc99ea5f8f553f4b28e71e06792d98d6542e69b284d1045615", "next_portion": 2, "portion": 1, "remaining_rows": 797}}

## L2 docatlas T05-ru
Evidence 2/2; input 42559; tools 18184; steps 5
Верификация — это **детерминированные сценарии установленного MCP**, а не проверка поведения модели в OpenCode.

Она запускает установленный wheel, настоящий project installer, MCP через stdio, SQLite и MiniLM. В вариантах с привязкой к проекту проверяются:

- чтение по одному вопросу без указания корня и совпадение результата с запросом, где корень указан явно;
- отклонение привязки к подкаталогу;
- текст и координаты источников, а также неизменность исходников и индекса.

В варианте без привязки отдельно проверяется регрессия отсутствующей цели запроса. [ev-493823027f9075ae, `docs/PROJECT_BINDING.md:74–79`]

**Чего это не доказывает:** что автономная сессия OpenCode или модель примет правильные решения, качественно ответит на вопрос или обеспечит определённый расход токенов. Для полезной доставки в самом OpenCode документация рекомендует отдельно проверить текст выбранного источника, публичные ссылки и диапазоны строк в фактическом сообщении инструмента; одного `ok`, числа источников или `truncated=false` недостаточно. [ev-493823027f9075ae, `docs/PROJECT_BINDING.md:74–79`; ev-d271ca082523e51b, `docs/opencode-compact-text.md:123–127`]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true})"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?'})"}, "status": "completed", "output_tokens": 6465, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "ebd85f50c198702d840b88387856185aff8514097731a2b8d53331b40aaf1a72", "next_portion": 2, "portion": 1, "remaining_rows": 222}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?',lookup_queries:['OpenCode project-bound integration verification verify what checks limitations','OpenCode verify project binding verification smoke'])"}, "status": "completed", "output_tokens": 27, "nested_calls": [], "code_error": true, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?',lookup_queries:['OpenCode project-bound integration verification verify checks limitations','OpenCode verify project binding verification smoke']})"}, "status": "completed", "output_tokens": 11356, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?", "lookup_queries": ["OpenCode project-bound integration verification verify checks limitations", "OpenCode verify project binding verification smoke"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "3d42ccbaaa532d587ad3abc514fcb145e5c6bcfdd130a750550037b6ce36d646", "next_portion": 2, "portion": 1, "remaining_rows": 523}}

## L2 docatlas T10-ru
Evidence 3/3; input 16446; tools 10092; steps 3
Предлагается **расширить существующий интеграционный сценарий**: провести один исходный пользовательский вопрос через настоящий публичный API, CLI или MCP — предпочтительно установленного пакета — на изолированных данных, с реальными retrieval, selection, storage и validation. Это именно предложение сценария, а не утверждение, что такая проверка уже выполнена. [ev-60db148c110217c7, `docs/main-flow-evaluation.md:17–20`]

1. **Заранее подготовить независимый эталон:** вопрос, версии корпуса, обязательные факты и дословные фрагменты, допустимые источники и их hash/span, scope и ожидаемые изменения состояния. Эталон выводится из документов и требований, а не из ответа проверяемого кода. [ev-506bfd050e9ed072, ev-0e3e7aa14846865f, `docs/main-flow-evaluation.md:21`]
2. **Выполнить две попытки** — с подробными логами off и on — из одинаковых исходных состояний, включая индекс, cache, права и consent. Результат первой попытки не становится ожидаемым ответом второй. [ev-110efe4cc04ad362, ev-0de03c600ce6bdd1, `docs/main-flow-evaluation.md:22`]
3. **Независимо проверить обе попытки**, затем сравнить источники, scope/version, результат, изменения состояния и число продуктовых вызовов. Одинаковые неправильные ответы не считаются PASS; timestamps и trace IDs исключаются только по заранее заданному правилу. [ev-2ff0d9936b727278, ev-8ff7101e69fc1621, ev-0501065089e7f557, `docs/main-flow-evaluation.md:23`]
4. **Проверить диагностику:** при on трасса связывает этапы вопроса и помогает локализовать сбой, её пропуски явные; при off подробная трасса отключена. В MCP диагностический канал отделён от protocol stdout. [ev-9c253164a54bb94f, ev-b90095986fdec0fa, `docs/main-flow-evaluation.md:24–25`]

Внутренние mocks не используются. Если для воспроизводимости подменён внешний транспорт, эту границу нужно указать: такой тест не доказывает работу живого провайдера. [ev-27a6c616df956a37, `docs/main-flow-evaluation.md:26–27`]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?'});"}, "status": "completed", "output_tokens": 9756, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "c439e1b2ce0774208f0387ca32eba0dbe9b2fae00972537aff52835491ab8fc0", "next_portion": 2, "portion": 1, "remaining_rows": 199}}

## L2 docatlas T12-ru
Evidence 0/3; input 33948; tools 18500; steps 4
MCP-сервер DocAtlas работает с документацией проекта как с **проверяемыми файлами репозитория**, а не как с произвольным набором найденных файлов.

1. **Определяет допустимые источники.** Файл `docatlas.project-docs.yaml` задаёт каталог проектной документации. Сервер извлекает сведения только из явно включённых актуальных файлов: привычное имя, ссылка из README или название модуля сами по себе не разрешают поиск других файлов. [docs/project-docs-mcp-workflow.md:1–5, ev-97b6f7f3c1b187ba; wiki/Configuration.md:7–11, ev-b47069e207aa2833]

2. **Готовит индекс отдельно от чтения.** Для вопросов используется `get_docs_context`; подготовка и синхронизация выполняются через `prepare_docs`, когда это явно запрошено или рекомендовано сервером и соблюдены требования подтверждения. При подтверждённой синхронизации обновляются индексированные разделы выбранных файлов. Изменившиеся хеши исключают устаревшие разделы из текущего поиска; удалённые или исключённые из каталога документы также не выдаются. Синхронизация сама не создаёт официальную документацию. [README.md:120–125, ev-396b48f2a75644f2; README.md:142–143, ev-58e5db01261a9c80]

3. **Возвращает контекст с источниками.** Перед выдачей проверяются принадлежность к каталогу, область проекта или модуля, идентичность и актуальность источника. Результат содержит дословные выдержки с путём и координатами; отвечающая модель использует их для ответа со ссылками. Документация зависимостей обрабатывается отдельно от собственных README/docs/wiki проекта. [docs/mcp-docs-server.md:63–74, ev-0e4293f680364f9c, ev-7eb1037fb91fab7f; README.md:17–28, ev-568acfd181bd9bb9; docs/project-docs-demo.md:56–61, ev-efb13472650d0e32]

4. **Не подменяет проверку ответа или разрешение на правку.** Проектный результат — `docs_context` с политикой `cite_only`; найденный фрагмент не доказывает полноту ответа и не разрешает менять файлы. Если безопасных подтверждений нет, сервер возвращает `insufficient_evidence`. Файлы репозитория остаются источником истины; DocAtlas не должен незаметно писать или коммитить документацию. [docs/mcp-docs-server.md:48–62, ev-b1e3c59ec4329a9c, ev-b3d29996124ef24f; CONTRIBUTING.md:34–37, ev-e5f4db7716736e5e]

Сервер запускается командой `doc-atlas mcp docs-serve`; третий основной инструмент, `docs_status`, предназначен для явной проверки состояния и актуальности, а не для обнаружения документации. [README.md:110–125, ev-883c8116c03232fc, ev-396b48f2a75644f2]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true})"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как MCP-сервер документации работает с собственной документацией проекта?'})"}, "status": "completed", "output_tokens": 6680, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как MCP-сервер документации работает с собственной документацией проекта?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "6df13e50f2080d990f24d847085549ae0a802aa3a74d20d50624e8047dc4b9cb", "next_portion": 2, "portion": 1, "remaining_rows": 227}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Как MCP-сервер документации работает с собственной документацией проекта?',lookup_queries:['docs/mcp-docs-server.md project documentation indexing discovery tools','docs project documentation configuration catalog freshness indexing project reads']})"}, "status": "completed", "output_tokens": 11484, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Как MCP-сервер документации работает с собственной документацией проекта?", "lookup_queries": ["docs/mcp-docs-server.md project documentation indexing discovery tools", "docs project documentation configuration catalog freshness indexing project reads"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "54a1d0f2db37329e878848c97c939e1443d007abd87433dc65853aadb789bb3b", "next_portion": 2, "portion": 1, "remaining_rows": 624}}

## L2 docatlas T15-en
Evidence 2/2; input 10095; tools 3767; steps 3
`DOCATLAS_MCP_MODEL_VIEW=1` relies on the host preserving the complete source packet in MCP response `_meta`, separately from the text shown to the model. The documented stock OpenCode v2.1.2 adapter drops response `_meta`. Enabling the mode there would therefore lose the original source packet and leave its short references unresolvable. [ev-949ac367b27547a5, `docs/opencode-compact-text.md:38-46`]

The mode is intended **only for a verified compatible host**: a host that retains `_meta` for auditing but keeps it out of the model transcript. Forwarding `_meta` to the model saves nothing; discarding it loses the machine audit. [ev-38b6c83446bbdcae, `docs/model-context-delivery.md:17-26`]

For ordinary OpenCode, use the self-contained text route instead:

```sh
DOCATLAS_MCP_TEXT_FALLBACK=1
DOCATLAS_MCP_COMPACT_TEXT=1
```

Leave `DOCATLAS_MCP_MODEL_VIEW` unset or off: the two compact modes are mutually exclusive. The OpenCode route keeps source excerpts, evidence IDs, URIs, paths and line ranges in the text without relying on private `_meta`. New and re-registered installations set both recommended flags; to upgrade an existing registration, rerun `doc-atlas install opencode`—upgrading the package alone does not rewrite the settings. [ev-acf111f413ccc1e1, `docs/mcp-docs-server.md:123-134`; ev-2a5621d34fd423c0, `docs/mcp-docs-server.md:135-142`; ev-784391083a99e015, `docs/opencode-compact-text.md:47-59`]

The compatibility finding is specifically documented for **stock OpenCode v2.1.2**; the cited evidence does not establish the behavior of other versions or custom adapters.

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true})"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'Why shouldn\\'t OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?'})"}, "status": "completed", "output_tokens": 3431, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?"}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "475d6dbf3e9d5daae04c384554c98646dad2b2b349ebbbb71497a05f47e5d3e8", "next_portion": 2, "portion": 1, "remaining_rows": 232}}

## L2 docatlas T19-ru
Evidence 4/4; input 42686; tools 23223; steps 4
Для управления локальным процессом Qdrant используется группа **`doc-atlas qdrant`**:

- `doc-atlas qdrant up` — загрузить при необходимости и запустить Qdrant в фоне. `--port` задаёт порт, а `--docker` выводит фрагмент Docker Compose вместо запуска управляемого бинарника.
- `doc-atlas qdrant down` — остановить процесс, управляемый DocAtlas.
- `doc-atlas qdrant status` — показать состояние процесса, порт, URL и версию; `--json` выводит результат в JSON.
- `doc-atlas qdrant upgrade` — заменить управляемый бинарник, сохранив хранилище. Для работающего управляемого процесса требуется `--force`; миграция хранилища между версиями не автоматизирована.
- `doc-atlas qdrant logs` — показать журнал stdout; `--stderr` выбирает stderr.  
  [wiki/Commands.md:104–115, ev-a1242d1c71f6725b, ev-6ccd6a722c6d3b33]

Если задан `DOCATLAS_QDRANT_URL`, DocAtlas подключается к существующему Qdrant и не управляет его локальным жизненным циклом. [wiki/Commands.md:116–120, ev-fa3a823d49b2e822]

### Trace
{"tool": "execute", "input": {"code": "return await tools.docatlas.docs_status({action:'project',include_language:true});"}, "status": "completed", "output_tokens": 336, "nested_calls": [{"tool": "docatlas.docs_status", "status": "completed", "input": {"action": "project", "include_language": true}}], "code_error": false, "truncated": false}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Какие команды DocAtlas используются для управления Qdrant?\"'});"}, "status": "completed", "output_tokens": 10703, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Какие команды DocAtlas используются для управления Qdrant?\""}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "2f919e18cedd5c7d59acf2f6e2c138e67625302c4be448f1285465788bd8d89d", "next_portion": 2, "portion": 1, "remaining_rows": 196}}
{"tool": "execute", "input": {"code": "return await tools.docatlas.get_docs_context({question:'\"Какие команды DocAtlas используются для управления Qdrant?\"',lookup_queries:['Qdrant CLI commands start stop status docatlas','docatlas qdrant up down status']});"}, "status": "completed", "output_tokens": 12184, "nested_calls": [{"tool": "docatlas.get_docs_context", "status": "completed", "input": {"question": "\"Какие команды DocAtlas используются для управления Qdrant?\"", "lookup_queries": ["Qdrant CLI commands start stop status docatlas", "docatlas qdrant up down status"]}}], "code_error": false, "truncated": false, "more_context": {"continuation_token": "e8857b876b68f70de4daccb74871e8ae8b6636e8afba496cad11a44bfb3a0128", "next_portion": 2, "portion": 1, "remaining_rows": 557}}

## L2 search T01-en
Evidence 3/3; input 7950; tools 4243; steps 3
DocAtlas’s contribution guide asks you to:

- **Name your branch** `feat/<topic>` or `fix/<description>`.
- **Run the full test suite before opening the PR.** The documented commands are `pytest tests/ -v` on Linux/CI and `arch -arm64 .venv/bin/python -m pytest tests/ -v` on macOS.
- **Include tests for new connectors or fetchers where practical.**  
  [CONTRIBUTING.md:45–63](CONTRIBUTING.md#L45-L63)

If you’re new to the project, the guide also recommends reading the README, contribution guide, documentation index, and project map first ([CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)). For Docs MCP changes, it specifies additional interface and evidence boundaries and asks contributors to read the canonical reference ([CONTRIBUTING.md:34–38](CONTRIBUTING.md#L34-L38)).

The README says the bundled GitHub Actions workflow adds an advisory documentation-impact report to PR summaries; any resulting documentation edit remains an explicit, reviewable change ([README.md:188](README.md#L188)).

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "**/*CONTRIBUT*", "hidden": true}, "status": "completed", "output_tokens": 23, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "**/*pull*", "hidden": true}, "status": "completed", "output_tokens": 3, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "pull request", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 469, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/CONTRIBUTING.md"}, "status": "completed", "output_tokens": 790, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": ".github/**/*", "hidden": true}, "status": "completed", "output_tokens": 3, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "contribut|PRs| PR |reviewer", "caseSensitive": false, "include": "*.md", "limit": 70}, "status": "completed", "output_tokens": 2955, "nested_calls": [], "code_error": false, "truncated": true}

## L2 search T01-ru
Evidence 3/3; input 16388; tools 7728; steps 3
Согласно руководству для участников, перед отправкой PR от вас ожидается:

1. **Назвать ветку** в формате `feat/<topic>` или `fix/<description>`.
2. **Запустить полный набор тестов** до открытия PR.
3. Если добавляете **коннектор или fetcher**, включить тесты там, где это практически возможно. [CONTRIBUTING.md:59–63](CONTRIBUTING.md#L59-L63)

Команда для Linux/CI — `pytest tests/ -v`; для macOS руководство рекомендует `arch -arm64 .venv/bin/python -m pytest tests/ -v`. [CONTRIBUTING.md:45–57](CONTRIBUTING.md#L45-L57)

Новым участникам также предлагают сначала прочитать `README.md`, `CONTRIBUTING.md`, `docs/INDEX.md` и `docs/PROJECT_MAP.md`. [CONTRIBUTING.md:7–11](CONTRIBUTING.md#L7-L11)

В разделе об отправке PR **не указаны** требования к описанию PR, количеству ревьюеров или формату коммитов. [CONTRIBUTING.md:59–63](CONTRIBUTING.md#L59-L63)

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "**/*", "hidden": true}, "status": "completed", "output_tokens": 2774, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "pull request|Pull Request|pull requests|PR", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 2778, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/CONTRIBUTING.md"}, "status": "completed", "output_tokens": 790, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/testing.md", "limit": 180}, "status": "completed", "output_tokens": 167, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/documentation-language.md", "limit": 100}, "status": "completed", "output_tokens": 1219, "nested_calls": [], "code_error": false, "truncated": true}

## L2 search T02-ru
Evidence 0/3; input 9812; tools 4177; steps 3
Чтобы очистить **производный индекс**, а не нужные исходные данные, используйте `doc-atlas clear-index`: без `--apply` команда только показывает план. Она сохраняет исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы. Не путайте её с `doc-atlas clear` — более широкой разрушительной командой, которая может удалить конфигурацию и кэши моделей. [docs/index-cleanup.md:3–15, 83–85]

### Безопасный порядок

1. **Выберите область.** Для отдельного проекта используйте `project-local`; он работает только с выделенным каталогом проекта `.docatlas`. Если проект использует общий индекс, команда откажет, а `global` очистит общие локальные индексы, затрагивая и другие проекты. [docs/index-cleanup.md:17–20, 57–67]

2. **Посмотрите план и проверьте все цели и предупреждения:**
   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --format json
   ```
   В ответе будут цели, блокирующие и неполные состояния и `plan_digest`. В план могут входить SQLite и его вспомогательные файлы, извлечённые документы, кэши и проверенное локальное состояние Qdrant. [docs/index-cleanup.md:22–30, 43–51]

3. **Остановите Docs MCP-сервер и процессы синхронизации**, использующие это хранилище. Затем примените именно проверенный план:
   ```bash
   doc-atlas clear-index \
     --scope project-local \
     --project-path /absolute/path/to/project \
     --plan-digest <digest-from-preview> \
     --apply \
     --format json
   ```
   Устаревший digest или изменившиеся цели не будут применены; живые процессы и активные writer lease блокируют очистку. [docs/index-cleanup.md:29–41, 89–91, 102–106]

4. **Не используйте `--allow-incomplete` как способ принудительного удаления.** Он лишь подтверждает, что указанное непроверенное состояние векторов или кэша останется. Удалённые коллекции Qdrant не удаляются; локальное векторное состояние без маркера владения сохраняется. [docs/index-cleanup.md:96–100]

Цели сначала перемещаются в карантин на той же файловой системе; при ошибке *этапа перемещения* уже перемещённые цели восстанавливаются. После очистки индекс проектной документации можно перестроить из файлов репозитория через `prepare_docs(action="sync_project_docs")`. [docs/index-cleanup.md:53–55, 92–93]

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "**/*", "hidden": true, "limit": 100}, "status": "completed", "output_tokens": 2781, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/index-cleanup.md"}, "status": "completed", "output_tokens": 1396, "nested_calls": [], "code_error": false, "truncated": false}

## L2 search T05-ru
Evidence 2/2; input 19237; tools 10424; steps 3
Верификация привязанной к проекту интеграции — это **детерминированная проверка установленного MCP-пути**, а не полноценный запуск агента OpenCode.

Она проверяет:

- установленный wheel, реальный установщик проекта, обмен с MCP по stdio, SQLite и MiniLM;
- в вариантах с привязкой к проекту — запрос только с вопросом, совпадение результата с запросом, явно указывающим корень проекта, отклонение привязки к подкаталогу, исходный текст и его координаты, а также отсутствие изменений в источниках и индексе;
- в варианте без привязки — регрессию на отсутствие указанной цели. Сценарии запускаются через `eval/project_binding/installed_stdio.py --layout unbound|black|mixed`. [docs/PROJECT_BINDING.md:72–79]

**Чего она не доказывает:** работу автономной сессии OpenCode или модели и результаты токенных бенчмарков. Кроме того, наличие настроенного каталога MiniLM само по себе не доказывает, что модель загрузилась или участвовала в обработке. [docs/PROJECT_BINDING.md:60–65, 72–79]

Отдельно: сама установка создаёт привязку, но **не индексирует документы и не подтверждает завершение подготовки**. Готовность проекта и действующие настройки показывает `docs_status(action="project")`. [docs/PROJECT_BINDING.md:16–23, 60–65]

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "верификац|verification|verify", "caseSensitive": false, "limit": 100}, "status": "completed", "output_tokens": 5846, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/PROJECT_BINDING.md"}, "status": "completed", "output_tokens": 987, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "OpenCode", "include": "*.md", "limit": 100}, "status": "completed", "output_tokens": 3591, "nested_calls": [], "code_error": false, "truncated": false}

## L2 search T10-ru
Evidence 3/3; input 26440; tools 22429; steps 3
Предлагается расширить существующий интеграционный сценарий и **дважды воспроизвести один пользовательский вопрос** через настоящий публичный API, CLI или MCP, предпочтительно установленного пакета. Данные должны быть изолированы, а поиск, отбор, хранение и валидация — реальными. Это предложение проверки, а не отчёт о полученном PASS. [docs/main-flow-evaluation.md:1–3, 17–19](docs/main-flow-evaluation.md#L1-L19)

1. **Заранее задать независимый эталон:** вопрос, версии корпуса, обязательные факты и дословные фрагменты, допустимые источники и диапазоны, scope и ожидаемые изменения состояния. Эталон берётся из исходных документов и требований, а не из ответа проверяемой системы. [docs/main-flow-evaluation.md:21](docs/main-flow-evaluation.md#L21)
2. **Запустить off и on из одинаковых исходных состояний**, включая индекс, кеш, права и consent. Ответ первого запуска нельзя использовать как эталон для второго. В CLI глобальные `--no-trace` и `--trace` ставятся перед подкомандой. [docs/main-flow-evaluation.md:22](docs/main-flow-evaluation.md#L22); [docs/main-flow-logging.md:12–15](docs/main-flow-logging.md#L12-L15)
3. **Независимо проверить оба результата**, затем сравнить источники, scope/версию, продуктовый результат и изменения состояния. Два одинаковых неправильных ответа не означают PASS; переключение логов не должно менять права, побочные действия или число продуктовых вызовов. [docs/main-flow-evaluation.md:23](docs/main-flow-evaluation.md#L23)
4. **Проверить диагностику:** при on трасса должна связывать этапы вопроса и помогать локализовать сбой, явно показывая пропуски; при off подробная трасса отключена. В MCP диагностика отделена от protocol stdout. [docs/main-flow-evaluation.md:24](docs/main-flow-evaluation.md#L24)

Внутренние mocks не предлагается использовать; если подменён внешний транспорт, это нужно обозначить: такой запуск не проверяет живого провайдера. Дополнительно предлагаются отрицательные случаи: неверные версия или scope, недостаток данных, отсутствие доступа или consent, а также отказ зависимости или записи логов. [docs/main-flow-evaluation.md:26–37](docs/main-flow-evaluation.md#L26-L37)

**Граница вывода:** одна пара запусков не доказывает общую надёжность агента. В документации также описаны интеграционные сценарии OFF/ON/OFF с реальными документами и SQLite, но их выполнение ожидает разрешённого CI; они не проверяют установленный MCP stdio или production-клиента. [docs/main-flow-evaluation.md:39–41](docs/main-flow-evaluation.md#L39-L41); [docs/main-flow-logging.md:89–96](docs/main-flow-logging.md#L89-L96)

### Trace
{"tool": "grep", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "логирован|logging", "limit": 100}, "status": "completed", "output_tokens": 1034, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/main-flow-evaluation.md"}, "status": "completed", "output_tokens": 1739, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/main-flow-logging.md"}, "status": "completed", "output_tokens": 1596, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docatlas.project-docs.yaml"}, "status": "completed", "output_tokens": 18060, "nested_calls": [], "code_error": false, "truncated": true}

## L2 search T12-ru
Evidence 3/3; input 31679; tools 25917; steps 3
MCP-сервер DocAtlas работает с документацией репозитория как с **явно выбранными источниками для поиска**, а не как с разрешением автоматически просматривать или изменять проект.

1. **Что доступно.** Документы должны быть перечислены относительными путями в `docatlas.project-docs.yaml`. Само наличие `README.md`, папки `docs/` или ссылки на файл не делает их доступными автоматически. Например, каталог самого DocAtlas явно включает `README.md` и описание MCP-сервера. [docs/project-docs-mcp-workflow.md:3–5, 23–28](docs/project-docs-mcp-workflow.md#L3-L28); [docatlas.project-docs.yaml:83–90, 132–140](docatlas.project-docs.yaml#L83-L140)

2. **Как задаётся вопрос.** Клиент начинает с `get_docs_context(project_path=..., question=..., scope=...)`. Можно выбрать документы всего репозитория, только уровня проекта или конкретного модуля; для модуля нужен точный `module_path`. Чтение не синхронизирует индекс и не изменяет репозиторий. [docs/mcp-docs-server.md:26–40, 82–87](docs/mcp-docs-server.md#L26-L40); [docs/project-docs-mcp-workflow.md:96–108](docs/project-docs-mcp-workflow.md#L96-L108)

3. **Если нужна подготовка.** Клиент выполняет возвращённое сервером действие `prepare_docs`, соблюдая необходимые подтверждения и привязки, при наличии задания проверяет его через `docs_status`, затем повторяет исходный вопрос без изменений. Синхронизация без `mutation` ничего не записывает; подтверждённая запись требует, в частности, точных хешей каталога и документов, поколения индекса и выбранного хостом приватного хранилища вне проекта. [docs/mcp-docs-server.md:32–40](docs/mcp-docs-server.md#L32-L40); [docs/project-docs-mcp-workflow.md:61–81](docs/project-docs-mcp-workflow.md#L61-L81)

4. **Что возвращается.** Для проектной документации сервер выдаёт `docs_context` с привязкой к источникам: фрагментами, путями, хешами и координатами. Клиент может объяснить подтверждённые фактами сведения и указать пробелы, но выдача не гарантирует полноты ответа. При недостатке безопасных свидетельств возвращается `insufficient_evidence`. Текст источников считается данными, а не инструкциями. [docs/mcp-docs-server.md:48–71](docs/mcp-docs-server.md#L48-L71); [docs/project-docs-mcp-workflow.md:52–54](docs/project-docs-mcp-workflow.md#L52-L54)

5. **Актуальность и изменения.** Изменённые, удалённые или исключённые из каталога документы не должны использоваться как актуальные свидетельства даже до повторной синхронизации. Синхронизация выбранных документов сама по себе не очищает все старые записи индекса. DocAtlas также не генерирует и не коммитит официальную документацию: разрешённое пользователем изменение оформляется обычным проверяемым Git-патчем. [docs/project-docs-mcp-workflow.md:83–94, 124–128](docs/project-docs-mcp-workflow.md#L83-L94)

Локальный сервер запускается командой `doc-atlas mcp docs-serve`. Документация внешних зависимостей обрабатывается отдельно и не становится доступной по сети лишь потому, что она упомянута в репозитории. [docs/mcp-docs-server.md:5–9](docs/mcp-docs-server.md#L5-L9); [docs/project-docs-mcp-workflow.md:143–148](docs/project-docs-mcp-workflow.md#L143-L148)

### Trace
{"tool": "glob", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "pattern": "**/*", "limit": 100}, "status": "completed", "output_tokens": 2775, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/project-docs-mcp-workflow.md"}, "status": "completed", "output_tokens": 1695, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docatlas.project-docs.yaml"}, "status": "completed", "output_tokens": 18060, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/mcp-docs-server.md"}, "status": "completed", "output_tokens": 2447, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/project-docs-demo.md"}, "status": "completed", "output_tokens": 940, "nested_calls": [], "code_error": false, "truncated": false}

## L2 search T15-en
Evidence 2/2; input 14015; tools 7593; steps 3
**Because stock OpenCode drops the metadata that makes that mode’s references usable.** `DOCATLAS_MCP_MODEL_VIEW=1` puts concise text in the model-visible response but keeps the complete original source packet in MCP `_meta`. The documented stock OpenCode v2.1.2 adapter drops response `_meta`, so the original packet is lost and the short, response-local references cannot be resolved. The mode is intended for hosts that retain `_meta` out of band without forwarding it to the model. [docs/opencode-compact-text.md:36–45](docs/opencode-compact-text.md#L36-L45); [docs/model-context-delivery.md:9–25](docs/model-context-delivery.md#L9-L25)

For ordinary OpenCode, use the **self-contained compact-text route** instead. It keeps selected source text, original evidence IDs, URIs, paths, line ranges and other provenance in the text OpenCode sees, without depending on private metadata. The two modes are mutually exclusive. [docs/opencode-compact-text.md:47–58](docs/opencode-compact-text.md#L47-L58)

The documented default installation sets `DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`. For an existing registration, rerun `doc-atlas install opencode` (add `--project` for a project-owned configuration), then restart OpenCode; a package update alone does not change the registration. Leave `DOCATLAS_MCP_MODEL_VIEW` absent or off. [docs/opencode-compact-text.md:3–10](docs/opencode-compact-text.md#L3-L10); [docs/opencode-compact-text.md:101–105](docs/opencode-compact-text.md#L101-L105)

The self-contained route is less compact in the documented offline projection—25.7% versus 38.4% for the incompatible private-metadata view—but the project did **not** measure a paid OpenCode conversation or billing savings. [docs/opencode-compact-text.md:128–140](docs/opencode-compact-text.md#L128-L140)

### Trace
{"tool": "glob", "input": {"pattern": "**/*", "path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "limit": 100}, "status": "completed", "output_tokens": 2842, "nested_calls": [], "code_error": false, "truncated": true}
{"tool": "grep", "input": {"pattern": "DOCATLAS_MCP_MODEL_VIEW", "path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "limit": 100}, "status": "completed", "output_tokens": 482, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/opencode-compact-text.md"}, "status": "completed", "output_tokens": 2287, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/model-context-delivery.md"}, "status": "completed", "output_tokens": 1096, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/docs/mcp-docs-server.md", "offset": 100, "limit": 65}, "status": "completed", "output_tokens": 886, "nested_calls": [], "code_error": false, "truncated": true}

## L2 search T19-ru
Evidence 4/4; input 19052; tools 8361; steps 3
Для управления локальным Qdrant, принадлежащим DocAtlas, используется группа **`doc-atlas qdrant`**:

- `doc-atlas qdrant up` — запускает Qdrant в фоне, при необходимости скачивая закреплённую версию. `--port` задаёт порт, а `--docker` выводит фрагмент Docker Compose вместо запуска бинарного файла.
- `doc-atlas qdrant down` — останавливает управляемый процесс; чужой PID-файл не используется.
- `doc-atlas qdrant status` — показывает PID, порт, URL, состояние, принадлежность DocAtlas, работоспособность и версию. `--json` выводит результат в JSON.
- `doc-atlas qdrant upgrade` — заменяет управляемый бинарный файл, сохраняя хранилище. Для работающего процесса требуется `--force`; миграция хранилища между версиями не автоматизирована.
- `doc-atlas qdrant logs` — показывает конец журнала стандартного вывода; `--stderr` выбирает стандартный поток ошибок. [wiki/Commands.md:104–114](wiki/Commands.md#L104-L114)

Справка по группе: `doc-atlas qdrant --help`. [docs/capabilities.md:53](docs/capabilities.md#L53)

При указании `DOCATLAS_QDRANT_URL` используется существующий Qdrant, а управление локальным процессом обходится. [wiki/Commands.md:116–120](wiki/Commands.md#L116-L120)

### Trace
{"tool": "grep", "input": {"pattern": "Qdrant", "path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "limit": 100}, "status": "completed", "output_tokens": 5861, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "grep", "input": {"pattern": "qdrant", "path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project", "limit": 100}, "status": "completed", "output_tokens": 1857, "nested_calls": [], "code_error": false, "truncated": false}
{"tool": "read", "input": {"path": "/home/viadmin/.cache/docatlas-step8-review-work/L2-0/project/wiki/Commands.md", "offset": 104, "limit": 21}, "status": "completed", "output_tokens": 643, "nested_calls": [], "code_error": false, "truncated": true}
