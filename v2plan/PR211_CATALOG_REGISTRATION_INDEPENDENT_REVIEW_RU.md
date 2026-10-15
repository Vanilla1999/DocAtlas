# PR #211 — independent review registration companion

Дата: 2026-10-08. Решение: **APPROVE** для указанного узкого изменения.
Baseline: `f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`.
Review проведён независимо от автора; локальный runtime/pytest не запускался.

## Проверенный diff и точные hashes

В `tests/docs/test_mcp_docs_tools_registration.py` изменён только node
`test_agent_templates_include_three_tool_selection_guidance`:
literal assertion для runtime advertised description заменён на
`assert_public_context_guidance(runtime_tools["get_docs_context"])`.

| Файл | SHA-256 |
| --- | --- |
| `tests/docs/test_mcp_docs_tools_registration.py` | `d120db1dc0d82f733dc46ff0d5ece7221d414a9ab082f8bff6d816681414fa44` |
| `tests/docs/_scope_guidance_contract.py` | `7bbaf01953a09205cd219b67cd66cce93c12561531606e5bd183f1139f397dac` |
| `tests/docs/test_agent_question_planning_contract.py` | `fdc7116561eaa3a36f6b98f53e7bb21fc06a137df58443c72a5e345d14103ad7` |
| `docmancer/mcp/_docs_server_tool_data.py` | `24e968fd533ca5e4a876af6c8544de7c93cfdbe8a18381351b9a7863e576a2d7` |
| `docmancer/mcp/agent_workflow_contract.py` | `273992d92a73a23da2034db28c11dcbe617b92ba5318d17e8f349cfcd8529678` |
| `docmancer/templates/references/troubleshooting.md` | `ffdc2bf8264fe94ff6621c886cc76370f05662b9b50855621db377be4daa0a0c` |
| `v2plan/PR211_CATALOG_REGISTRATION_FOLLOWUP_RU.md` | `b5700820ca34ff32670ad697fb309f1f66685c2efea3d764e51e5ec24dde1ccc` |

Helper, companion, production tool data, workflow-contract producer и installed
troubleshooting reference побайтно равны baseline f0ed956.

## Почему successor сохраняет контракт

`runtime_public_tool_dicts()` получает tools из настоящего `build_docs_surface`,
проверяет public tool order и возвращает их копии. Новый вызов проверяет именно
этот runtime tool; тест не подставляет отдельную ожидаемую копию описания.

Helper читает advertised `description` fields и проверяет отдельный guard
`question.meta`. Допускаются две заранее reviewed полные отрицательные clauses:
`no benchmark/evaluation or documentation-governance meta-question` и
`no benchmark/evaluation/docs-governance meta-question`. Текущий plural
`meta-questions` сохраняет запрет. Проверка не сводится к наличию слова `question`
или к числу байт. Смена разрешённой формулировки не разрешает benchmark,
evaluation или docs-governance подменять исходный конкретный вопрос.

Существующий `test_runtime_tool_teaches_one_concrete_question_per_call`
подменяет этот запрет на `use a meta-question`, требует изменения advertised
guidance и ожидает `AssertionError` именно с `question.meta`.
Статически проверено: текущая clause встречается в string constants production
tool data ровно один раз; указанная замена не является NOOP и не оставляет ни
одну принятую `question.meta` clause. Соседние mutations и guard checks не менялись.
Это source-level проверка negative control, не заявление о новом runtime PASS.

Вызов helper также сохраняет проверки исходного вопроса, explicit lookups,
непереноса coverage, scope, version, source trust, consent, budgets и отсутствия
автоматической edit authority. Installed reference по-прежнему проверяется
прежним literal assertion `documentation-governance meta-question`, поскольку
его текст не сокращался.

## AST, inventory и ограничения доказательства

Сравнение через stdlib AST подтвердило ровно одну изменённую statement в одной
test function. После обратной подстановки прежнего assertion весь AST модуля
равен baseline, включая imports, decorators, fixtures и остальные test bodies.
Число literal `ast.Assert` меняется 195 → 194 из-за замены одного assertion
вызовом существующего assert helper; другие 194 assertions сохранены.

Сохранены все 34 base node IDs. Их hash по действующему diagnostic-inventory
алгоритму — `126c1abf598b97742534288958ef58a76bcaf0371968fcd4c017e97dd730f4e6`;
он совпадает с неизменённым `tests/diagnostic_labels.json`. Ничего не исключено,
не перемаркировано, не превращено в skip или xfail.

`ast.parse`, compile без исполнения и `git diff --check`: PASS.
Production code, schemas, limits, retrieval и CI workflow в этом followup
не изменены. Известный failure f0ed956 остаётся в acceptance evidence;
подтвердить исправление docs/platform jobs должен обычный CI на следующем SHA.
