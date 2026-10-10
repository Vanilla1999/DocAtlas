# PR #211: независимое review первого test-only slice

Дата: 2026-10-08. База: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Объект review — незакоммиченный diff семи test/helper modules и trust rationale,
зафиксированных SHA256 ниже. Reviewer не изменял production или tests; его
единственный записанный файл — этот отчёт.

## Вердикт

**APPROVE — узкая миграция tests соответствует текущему контракту; открытых
замечаний по прочитанному финальному diff не осталось.** Одно замечание к
anti-vacuity fidelity assertion исправлено координатором и перепроверено по diff.

Это **static review**, а не результат pytest. Runtime, полный CI, пять scope
variants, настоящий MCP stdio, installed/client acceptance в этом review
**NOT RUN**: доступное локальное окружение не содержит требуемых pytest/MCP и
project dependencies. Никаких скачиваний, provider calls, user-index операций,
ослабления permissions/guards или подмены runtime моками ради PASS не выполнялось.
Этот вердикт разрешает интеграцию конкретного test-only slice; merge/release
readiness и результаты старого checkpoint `791/801` им не подтверждаются.

## 1. Unified library call

В `tests/docs/test_mcp_docs_tools_registration.py` старое требование строки
`mode="library"` заменено проверкой фактических inline examples ресурса
`docmancer://workflow/library-docs`.

Проверены текущие producers `_docs_server_resources.py`,
`_docs_server_tool_data.py`, `_docs_server_shared.py` и вызов `current_tools({})`.
Ресурс сейчас содержит два library examples с `question/library/version` и один
project example с `project_path/question`; default schema принимает именно
unified parameters и запрещает дополнительные поля.

Successor парсит Python-call AST, запрещает positional arguments, unpacking,
повтор keywords и значения кроме документированного placeholder `...`, затем
подставляет явные fixture literals и валидирует actual default inputSchema.
Проверка непустого `library_calls` не позволяет пройти при отсутствии примеров.
Для library call закреплён полный набор question/library/version без mode.
Остальные resource, lifecycle, trust-schema, templated-binding, unknown-resource
и WebFetch assertions в существующем node сохранены.

Это проверка advertised API examples; успешный retrieval или stdio delivery
она не доказывает.

## 2. Scope guidance без привязки к одной формулировке

Оба scope modules используют новый shared helper
`tests/docs/_scope_guidance_contract.py`. Он принимает `repo-level plus modules`
и компактное `repo+modules`, сохраняя три раздельных условия:

- project — только repo-level docs;
- module — один module; module_path всегда ограничивает module scope;
- all — repo и modules только внутри того же repository и без module filter.

Сохранены explicit project/library/version/scope/path bindings, запрет widening
из question wording/prose, отсутствие schema default, nullable type и точный enum.
Проверка module_path перенесена к описанию самого поля, где это условие сейчас
рекламируется. Проверены actual compact schema и `WORKFLOW_POLICY.scope_planning`.

Behavioral node `test_public_scope_never_implicitly_widens` со всеми пятью
параметрами не менялся. В нём остались real fixture preparation, source generation,
positive root/foreign reachability до negative isolation, original request
immutability и module/source/non-authority assertions. Эти positive prerequisites
важны: empty retrieval не может выдать ложный scope PASS. Их исполнение остаётся
обязательным runtime acceptance, а не следствием prose helper.

Generated-template checks и literal host example schema validation сохранены.
Helper не является новым pytest node; существующие node names не изменены.

Координатор отдельно сообщил о no-import AST проверке helper на compact/expanded
constants и пяти искажениях boundary guidance. Reviewer не выполнял этот probe
повторно и не считает его pytest или behavioral scope evidence.

## 3. Output cap заменён fidelity и non-authority controls

Проверены `project_insufficient`, `project_docs_answer`,
`validate_model_visible_projection`, canonical projection estimator и
`refresh_action_packet_estimate`. В текущем production `max_tokens` не обрезает
insufficient output; каждый missing detail сохраняется, answer/edit flags ложны.
Оба используемых estimator для JSON fixture считают одинаковые canonical UTF-8
bytes / 4; это оценка, не фактические model tokens.

Successor существующего `test_documents_remain_bounded_and_non_authorizing`:

- сохраняет positive source-bound docs projection и successful validation,
  включая явно маленький legacy max_tokens;
- требует все восемь исходных missing strings с отдельными tail markers без
  переупорядочивания, потери или сокращения;
- требует output estimate >200 при переданном max_tokens=200, чтобы fixture
  действительно пересекал отменённый потолок;
- проверяет status, отсутствие sources/action и три non-authority flags;
- сверяет актуальность estimate и valid complete baseline перед negatives;
- меняет по одному answer_supported/answer_available/edit_ready, обновляет
  estimate и требует отказ validator;
- подменяет hash valid successful source и требует отказ snapshot validation.

### R1 — anti-vacuity замечание, CLOSED

Первый diff сравнивал `failure["missing"]` с тем же mutable input list после
вызова producer. In-place removal/cropping мог изменить сразу output и expected
list; оставшийся длинный элемент всё ещё проходил бы условие >200.

Координатор добавил `expected_missing = tuple(missing)` **до** вызова. Финальный
diff отдельно сравнивает output и input с этим immutable snapshot. Теперь такая
потеря данных или input mutation не может сделать assertion пустой проверкой.
Reviewer прочитал исправление; новых замечаний в нём нет.

## 4. Trust-resource conflict разрешён по security contract

Миграция обоснована не одним observed actual. Reviewer прочитал исходный diff
security commit `6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f`: annotation,
source dimensions, trust-contract builder и JSON resource одновременно заменили
repository-policy instruction grant на cited untrusted data. Этот смысл также
подтверждён root reports `INERT_SECURITY_IMPLEMENTATION_RU.md`,
`INERT_SDK_CLOSURE_RU.md` и последующим
`stage3/pr211-context-admission-checkpoint-2026-10-06/LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md`.
Исторические документы использованы как основание решения, не как runtime PASS
нового SHA.

`scoped_repository_document` означает path attribution policy filename внутри
root. Оно не удостоверяет issuer или consent. `instruction_trust` остаётся
`untrusted_data` для canonical AGENTS/CLAUDE, обычных документов и library lane;
ни source availability, ни отсутствие trusted docs не разрешают WebFetch.

Проверены текущие `annotate_context_pack`, `source_trust_dimensions`,
`_policy_scope` и `build_project_context_trust_contract`. Новые assertions в
существующем resource node связывают advertised resource с actual domain helpers:
in-root AGENTS/CLAUDE, ordinary README, outside-root path, missing root и library
lane. Требуемые positive scoped cases не заменены всеобщим unverified result.
Поддельные caller instruction_trust/executable_policy/scope flags переписываются
в инертные dimensions; original text и caller object сохраняются. Отдельные
selected и empty trust-contract cases проверяют отсутствие network/workflow
grant при обоих исходах; selected case требует ровно один AGENTS source.

Companion `test_trust_contract.py` сохраняет source/risky/rejected classification
и exact unresolved-dependency record; добавляет `no_trusted_context` и required
confirmation для возвращённого prefetch advisory. Resource URI/template inventory,
`trust-contract-1.2`, issued-reference guidance, 600-token/two-read ограничения и
unknown/fabricated reference denial сохранены.

## Проверки reviewer и граница доказательств

Выполнены только чтение working/base diffs и production definitions, `git show`
названного security commit, `git diff --check` (exit 0), чтение diagnostic labels
и SHA256 pinning файлов. Семь test/helper modules не импортировались; pytest,
fixtures, project runtime и test descendants reviewer не запускал.

По diff нет изменений production, retrieval, gold, thresholds, required gates,
conftest или diagnostic manifests. Нельзя переносить этот вывод на последующие
schema/harness slices без отдельного review их deltas. Исполнение совместного
набора на конечном commit SHA, разрешённые fixture Git/server subprocesses и
required CI/downstream/platform/client checks остаются открытыми задачами.

## Reviewed file pins

SHA256 сняты после исправления R1; незакоммиченный diff относится к базе выше.

```text
628b08a888c1074b78a5d985d3607953f85eb67f9d9c10f0c416d0acfa94686f  tests/docs/test_host_scope_contract.py
2e1cd767e29bf398c4073442328e9716271079bb2ca27729a63971dfbfbcab9a  tests/docs/test_host_scope_planning_contract.py
8817577dbe3680da2ac2f667129e82cc4ab010c92e411779d723e65b9d05eb67  tests/docs/_scope_guidance_contract.py
0bff0bb61c883b9da1207793c0745983c227cea3e73597d895b88135c9ae902e  tests/docs/test_mcp_docs_tools_registration.py
dda8365628a9dbbfadecc7894816ad4185f672521c84e48c73b8259b0a2b44ec  tests/test_action_packet_v4_public.py
7757480a60a0e2b45a926fe3ca610907d36df5593ef4eb1c40898a61492d37b9  tests/test_dictionary_exit_delivered_surfaces.py
27132b9df9d537f15a71813d1662ceb0f62e2ceb413543e27a1c8a4f25e48b77  tests/docs/test_trust_contract.py
f14611b42d9363ee638370e7928914961564ccd47a07fdf22866af25cd6e13d5  v2plan/PR211_TRUST_CONTRACT_REVIEW_RU.md
```
