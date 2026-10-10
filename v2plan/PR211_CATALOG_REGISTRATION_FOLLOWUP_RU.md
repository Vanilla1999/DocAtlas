# PR #211 — wording regression, обнаруженная общим CI

Дата: 2026-10-08. Source HEAD:
`f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`, фактический merge checkout:
`417a6544b1f859f7bdad5f40b9729255ec8c1ae2`.

## Причина и исправление

[CI 37819292857](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292857)
обнаружил пропущенный companion assertion после reviewed compaction catalog:
`test_agent_templates_include_three_tool_selection_guidance` всё ещё требует
буквальную строку `documentation-governance meta-question` в advertised description.
Компактная guidance содержит `no benchmark/evaluation/docs-governance meta-questions`.

Это конкретная регрессия данного slice, а не объявленный старый failure:
docs-contract job `113455869668` имеет 1 FAIL / 100 PASS; platform Ubuntu
`113455869646` — 1 FAIL / 76 PASS с той же причиной. Platform package failure
не позволил этим jobs выполнить следующий installed stdio шаг.

Заменён ровно один literal assertion на уже используемый в этом module
`assert_public_context_guidance(runtime_tools["get_docs_context"])`.
Он проверяет всю retained guidance, включая отдельный `question.meta` guard:
запрещено подменять вопрос benchmark/evaluation/docs-governance meta-question.
Этот helper принимает только reviewed equivalent clauses; существующий companion
test содержит non-NOOP mutation этого запрета и ожидает отказ именно `question.meta`.
Соседние source/consent/scope/authority controls остаются действующими.

Проверка прежней полной формулировки в installed troubleshooting reference
не менялась: этот файл не сокращался. Не менялись template rendering, examples
с настоящей schema validation, identity, public tool order, hard-stop assertions,
package/runtime code или число test nodes. Дополнительные tests не нужны: текущий
runtime registration case плюс 38 существующих negative mutations покрывают риск.

## Проверка и границы

Независимый review фиксируется отдельно. Автор выполнил stdlib AST compare:
изменена только указанная test function и только этот assertion; imports,
decorators и roster прежние. `ast.parse` / compile без исполнения и
`git diff --check`: PASS. Локального pytest/runtime запуска не было.

Нужен повторный обычный CI на новом SHA. Исходный f0ed956 CI сохраняется целиком
для сравнения; этот fix не скрывает его регрессию и не отменяет другие failures.
