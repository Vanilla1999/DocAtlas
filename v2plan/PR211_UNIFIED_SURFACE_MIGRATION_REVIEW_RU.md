# PR #211: три stale проверки unified MCP surface

Дата: 2026-10-08. База `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Изменён только `tests/test_unified_docs_context_mcp.py`; production, resources,
schemas, helper, diagnostic manifest, corpus, gold и thresholds не изменены.

SHA256 testfile:
`f78c32606abd857c9040a5d3b84484958882fd1f2663fd995905f50345de0803`.

## Основание и текущий контракт

В фактическом core JUnit CI 37824782946 три nodes остановились на старых
литеральных ожиданиях. Их successor установлен по текущим producers и решениям
`CURRENT_WAVE_DECISIONS_RU.md` / `V4_PRODUCT_DECISIONS_RU.md`, а не по одному
полученному значению.

1. `test_get_docs_context_schema`: старый enum исключал `None`. Producer
   `_docs_server_tool_data.py` явно объявляет nullable scope с тремя значениями
   `project/module/all` и `None`; `_strip_null_enum_values` в
   `_docs_server_shared.py` сохраняет null только при явно nullable type.
   Nullable scope означает отсутствие выбранного scope, а не четвёртый scope
   или право расширить поиск. Проверка использует существующий
   `assert_public_context_guidance`, который сохраняет точный enum/type,
   отсутствие default, repository/module boundaries, original question,
   explicit bindings/lookups, consent и no-edit-authority guards. Прежние
   required/property-set/forbidden-preparation-flags asserts сохранены.
   Добавлены schema positive controls для omitted scope, трёх scopes и null;
   отрицательные controls для `library`, `PROJECT`, пустой строки, числа,
   boolean, list и object. Это не замена enum на слабую subset-проверку.

2. `test_docmancer_agent_quickstart_resource_exists`: прежнее `bounded
   structured` не является текущим требованием output size. Согласованный V4
   сохраняет нужный контекст и attribution, снимает внутренний representation
   cap, оставляет отдельные source/read/work bounds и explicit authorization.
   Из `_docs_server_resources.py` проверяются полные текущие clauses:
   documentation context по умолчанию без обязательного skill read,
   отсутствие answer/edit authority, отдельный explicit target/authorization,
   полные admitted source windows без внутреннего representation cap,
   сохранение text/hash/coordinates и существующие scope/freshness/provenance/
   consent/network/budget bounds. Resource existence, router identity,
   not-a-code-auditor и `get_docs_context` guards сохранены.

3. `test_library_workflow_resource_uses_canonical_three_tool_workflow`:
   публичный producer и static library resource используют unified
   `get_docs_context(question=..., library=..., version=...)`, без `mode`.
   Проверка разбирает AST настоящих inline examples и валидирует подстановки
   по advertised input schema. Не допускаются positional arguments,
   duplicate/unknown keywords или подмена placeholders. Требуется хотя бы
   один library call с точными question/library/version bindings; также
   проверяется project-bound example. Дополнительный отрицательный control
   требует schema rejection для того же call с legacy `mode="library"`.
   Все прежние get_docs_context/prepare_docs/docs_status asserts сохранены.
   Тот же способ проверки реальных examples уже применяется в
   `tests/docs/test_mcp_docs_tools_registration.py`.

Существующий helper не расширялся:
`tests/docs/_scope_guidance_contract.py`, SHA256
`7bbaf01953a09205cd219b67cd66cce93c12561531606e5bd183f1139f397dac`.
Для resource text новый универсальный predicate не вводился: helper относится
к tool schema/descriptions, а resource clauses и calls проверяются напрямую.

## Inventory и границы проверки

AST diff меняет только указанные три functions. Все остальные function bodies,
имена, decorators/parametrization сохранены. Число base nodes — 18; hash
`SHA256("\n".join(sorted(base_nodeids)))` остаётся
`0275c69d4cc904dfef66e7fd7d992c221b349c015aa4b03003b43717d4adc9ad`
и совпадает с неизменённым diagnostic manifest.

Assert inventory: 53 → 64. Сохранены 50 прежних Assert; заменены ровно три
устаревших: scope enum без null, `bounded structured`, `mode="library"`.
Вызов общего guidance helper дополнительно сохраняет его guard-specific
assertions. Четыре остальных failures этого testfile, связанные с публичным
projection/recovery/trust contract, не мигрируются этим slice.

Статические проверки: `ast.parse`, compile AST без исполнения,
body/decorator/assert inventory, соответствие diagnostic hash, чтение literal
resource constants через AST, проверка присутствия всех quickstart clauses и
форм трёх actual inline examples — PASS. `git diff --check` — PASS.

Локальные imports репозитория, test/helper execution, pytest, provider/client
runs и установки не выполнялись. JSON Schema positive/negative controls
добавлены в tests, но локально не исполнялись; фактический результат должен
подтвердить обычный CI на опубликованном SHA. Никакие оставшиеся semantic,
admission, retrieval или missing-catalog failures не объявлены закрытыми.
