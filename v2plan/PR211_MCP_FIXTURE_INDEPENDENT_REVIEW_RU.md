# PR #211: независимый review четырёх MCP fixture migrations

Дата: 2026-10-08. Reviewer: `footprint_audit`; автор slice: `acceptance_audit`.

## Verdict и версии

**APPROVED для четырёх разрешённых fixture migrations.** Блокирующих замечаний
по frozen diff нет. Это verdict по тестовым изменениям; runtime PASS четырёх
nodes и готовность PR к merge не объявляются.

| Файл | Проверенный SHA-256 |
|---|---|
| `tests/test_mcp_patch_plan_context_tool.py` | `430c3e0fde5c48e3b791a35120b01f9223347505d8bd440e541e141f74bc9dd2` |
| `tests/test_mcp_patch_plan_context_output_contract.py` | `b0baf7c63851cfeb2eb25f9e58a3141b0202316ed7f0ef3eea0c999b72e5e997` |
| `tests/test_mcp_patch_constraints_tool.py` | `1ade00e62d47f508b3c36a3f4e34d01dafdfb1815da143941dafc267c17f6cd2` |
| `v2plan/PR211_MCP_FIXTURE_MIGRATION_REVIEW_RU.md` | `26c56e7192b250901aa89c22044188252c882d7d147ceafc5fdc5ff8c06a27cf` |

Независимый diff/AST review выполнен относительно
`b68759e65f52317928ba22166248e679098024ae`. Реальный предыдущий CI и merge SHA
`964056442f67b0d913310d3f8a295deb3c90263e` описаны в
[авторском rationale](PR211_MCP_FIXTURE_MIGRATION_REVIEW_RU.md); этот run не
является проверкой текущих изменений.

## Обоснование и сохранённый смысл

Первичные producers просмотрены независимо. В
[SourceBoundary](../docmancer/docs/domain/source_boundary.py) источником
допуска служит valid catalog с конечным `code_files`. В
[patch context producer](../docmancer/docs/_patch_plan_context_part02.py)
отсутствие этого допуска приводит к `unresolved_local_code_membership` до
source discovery. [Implementation map](../docmancer/docs/_patch_plan_context_part01.py)
возвращает контекст выбранных источников с hash и `confidence=unknown`; он не
сертифицирует поведение, policy, отсутствие символа или edit plan.

Поэтому декларация уже существующих fixture files исправляет недостающую
предпосылку трёх положительных source tests. Она не возвращает обход repository
или dependency cache и не подменяет прежние ожидания пустым результатом.

| Изменённая проверка | Оценка миграции |
|---|---|
| `test_get_patch_plan_context_normalizes_snake_case_and_pascal_case` | Два literal members сохраняют исходные question/symbol queries и порядок обоих результатов. `Path.open` spy должен увидеть оба выбранных source file и отвергнуть другие fixture files или внешние Dart sources. Допустимые control files перечислены отдельно. |
| `test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded` | Тот же запрос сначала должен вернуть все пять явно объявленных файлов при max_files=12, затем прежние три при max_files=3 в том же порядке. Исходный JSON UTF-8 cap `<32000` сохранён. Ограничение действительно проверяется на более широком положительном результате. |
| `test_patch_plan_context_output_contract_shapes` | Прежний NBO fixture копируется в tmp_path, где объявляется один существующий menu_line.dart. Общий committed fixture не меняется. Все прежние shape assertions сохранены; дополнительно требуется ровно этот файл и непустой source context. |
| `test_mcp_tool_respects_max_constraints_and_max_tokens` | Explicit generated/lockfile paths дают advisory candidates через настоящий producer. Wide 12/1200 должен превысить оба narrow bounds без truncation; тот же запрос затем проверяется на прежних 2/180, warning и typed truncated flag. |

Source helpers сравнивают ответ с bytes, захваченными **до** вызова handler:
membership, уникальность файлов, read action, непустые refs, line bounds и literal
patterns, а также отдельные bounds/literal evidence, unknown confidence и hash
для current_behavior. После вызова сохраняется именно отображение path→bytes.

Budget positive не приписывает generated path существование или право чтения,
а lockfile path не становится version/policy proof. Это соответствует текущим
[advisory producers](../docmancer/docs/application/_patch_constraints_service_part02.py).
[MCP boundary](../docmancer/docs/interfaces/mcp/project_tools.py) принудительно
оставляет policy unresolved. Новый тест проверяет это для обоих пакетов вместе
с `answer_available`, `answer_supported`, `mutation_authorized`, `edit_ready=False`.
Пустой narrow constraints list допускается: final clamp может потратить бюджет
на обязательные warnings. Содержательный wide control предотвращает пустую
проверку truncation.

## Граница изменения и независимая проверка

- Во всех трёх modules сохранены 25 test names: 18 + 1 + 6. Изменены только
  четыре согласованные функции, остальные 21 test и общие source/workspace
  fixtures совпадают по AST с `b68759e`. Не изменены decorators, markers или
  selections. Добавленные `monkeypatch` и `tmp_path` обслуживают только
  изолированную проверку чтений и копию fixture; node IDs сохраняются.
- Все 12 исходных assert AST четырёх nodes найдены в candidate без изменения:
  2 + 2 + 5 + 3. Два private helpers не изменяют общие fixtures и используются
  только тремя разрешёнными plan tests.
- Frozen hashes, `ast.parse` и `git diff --check`: PASS.
- Из AST извлечён только чистый `_assert_selected_source_evidence`. На отдельном
  literal payload один положительный и 11 отрицательных controls: PASS.
  Отвергаются чужой member, дубликаты, нулевые/выходящие за файл bounds обоих
  видов evidence, выдуманный literal, ложный hash и повышенная confidence.
  Это проверка assertion helper, не запуск MCP handler или pytest.

Repository imports, service constructors, настоящий source discovery, budget
producer, `Path.open` spy в runtime, pytest, subprocesses и installed/client
проверки локально **NOT RUN**. Следующий шаг — четыре настоящих nodes в штатной
offline CI-среде, затем joint acceptance на общем конечном SHA.

Остальные 15 MCP failures из авторского inventory остаются неизменёнными и не
считаются закрытыми: dependency membership, absence/alternative certificates,
policy и mutation plans требуют отдельного contract review. Production,
retrieval, golden cases, 800-token gate, catalog ceiling и required/downstream
gates этим slice не меняются. Статическое одобрение не превращает эти блокеры
в PASS.
