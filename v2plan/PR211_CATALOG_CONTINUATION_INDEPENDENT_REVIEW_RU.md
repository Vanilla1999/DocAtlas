# PR #211: независимый review продолжения catalog compaction

Дата: 2026-10-08. Reviewer не является автором catalog slice.
База: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

**Вердикт: APPROVE частичного сокращения при сохранении открытого footprint gate.**

Этот report оценивает frozen prose/schema slice до отдельного изменения политики
ceiling. Последующее явное решение пользователя убрать hard 6144 реализуется и
проверяется отдельным policy slice; этот исторический результат его не отменяет.

Независимо подтверждено **7066 → 6918 UTF-8 bytes**, экономия **148 bytes**.
Это всё ещё **774 bytes выше действующего ceiling 6144**. Output schema —
буквально прежние **860 bytes <1000**, уже включённые в catalog. Лимит не меняется.
Review не удостоверяет merge readiness, model-token footprint или client acceptance.

## Проверка production changes

Прочитаны полный diff `_docs_server_tool_data.py`, все новые advertised descriptions,
author report и соответствующие meaning helpers/negative controls.

Статическое сравнение с `git show df9b682f:...` подтвердило:

- Изменяются только `PUBLIC_ADVERTISED_DESCRIPTIONS` и две description annotations
  в `PUBLIC_ADVERTISED_INPUT_SCHEMAS`.
- Input trees полностью равны после удаления только ключей `description`.
  Bounds, nullable types, enums/const, defaults, required, closure, if/then/else
  branches и поля mutation object не изменены.
- `PUBLIC_ADVERTISED_OUTPUT_SCHEMAS` равны буквально.
- Все остальные production AST nodes равны базе: handlers, normalization,
  advanced/internal definitions и tool inventory не менялись этим slice.
- Frozen 7602-byte fixture и пять catalog-equivalence nodes не изменены.

Schema-equivalence здесь не выведена из нескольких положительных примеров:
сами validation constraints совпадают целиком. Runtime sanitizer/MCP schema
validation должны дополнительно исполниться в обычном CI.

## Сохранённые advertised instructions

Новая проза сохраняет один unchanged concrete original question и все прежние
запреты на meta-question substitution, inferred translations/rewrites/subquestions,
expected answers/source names и independent-question batching. В compact sentence
`never` относится и к `infer`, и к `batch`; это не отдельный разрешающий batching
clause. Explicit same-question lookups и непереносимость coverage на original
остаются самостоятельными требованиями.

Scope по-прежнему привязан к своим субъектам: project — repo-level docs only,
module — один exact module, all — repo+modules того же repository без module
filters, module_path — module scope. Все explicit project/library/version/scope/path
bindings сохраняются; prose не разрешает расширять scope. Current project требует
omit version, exact/historical version допустима только явно; lockfile changes
требуют повторного запроса.

Source content остаётся untrusted data. Context/flags не удостоверяют answer
completeness/proof/edit readiness. Edit требует отдельного explicit target и
authorization; hard_stop=true запрещает edit, false не даёт permission.
Freshness/provenance/network consent/budgets не удалены.

Preparation остаётся привязанной к returned recommendation или explicit lifecycle
request. Missing/stale docs и network approval по отдельности не дают preparation
grant. Source bindings, confirmation, network consent, poll returned job_id и
единственный unchanged retry после verified success/readiness сохранены.
Status остаётся read-only, без discovery, только для прежних явных status intents,
returned recommendation либо job_id, выданного prepare_docs.

Mutation description по-прежнему требует confirmed lexical member upserts,
exact catalog/document hash/generation bindings, null generation только для
absent store, private host-selected DB вне project и отсутствие caller/project
redirects. Формула `POSIX no-follow reads or fail closed` сохраняет отказ там,
где этот read contract невозможно выполнить. Запреты deletion/vector/artifact
writes не менялись. Skills/references не становятся prerequisite обычного вызова.

## Meaning helper и отрицательные controls

Helper не превращён в проверку несвязанных keywords: retained clauses проверяются
как прежние или конкретные reviewed equivalent варианты. Scope all repository и
filters проверяются внутри all clause; module implication привязана к module_path;
current-version omission — к current project.

Оба изменённых test bodies сохраняют старые node IDs и содержательные прежние
4 + 6 negative controls. Новые controls добавляют соседние semantic failures.
Все остальные companion AST nodes, imports, arguments, decorators и test bodies
равны базе; module inventory остаётся 8 и 3 top-level test functions.

Reviewer независимо извлёк literal catalog через `ast.literal_eval`, pure helper
definitions через AST и literal mutation tuples из двух test bodies. Без импорта
DocAtlas/pytest исполнил isolated stdlib assertion harness:

- frozen 21fe catalog, df9 catalog и candidate проходят meaning helper;
- все **38 mutations** действительно меняют input;
- каждая отклоняется именно ожидаемым guard label;
- batching negative сохраняет inference prohibition и падает на `lookup.batch`;
- source/consent, wrong module/project scope, cross-repository all, implicit
  filters, guessed jobs/versions, scope default/null и unsafe authority controls
  не подменены случайным отказом соседней проверки.

Это **не pytest, SDK или installed runtime PASS**. В harness использован
реальный извлечённый assertion helper, но catalog взят как literal data;
настоящие runtime tool construction и schema validators остаются делом CI.

Новая форма `scope.get('type', ['string', 'null'])` в meaning helper не разрешает
удалять production type: exact enum уже задаёт эти JSON types, но текущий
runtime null-enum sanitizer зависит от literal nullable type. В candidate сам
type **сохранён**. Если его удалить, нормализованный advertised enum и действующие
boundary controls должны обнаружить потерю null. Этот review не одобряет такой
отдельный production patch и не считает raw helper заменой sanitizer acceptance.

## Результат и дальнейшая проверка

Blocking findings в reviewed partial patch нет. Сокращение не маскируется
увеличением ceiling или уменьшением тестового inventory. Catalog всё ещё
**6918 >6144**; необходимые CI/downstream/installed/client проверки остаются
открытыми до их фактического выполнения. Retrieval не менялся.

## Frozen hashes

| Файл/артефакт | SHA256 |
|---|---|
| `docmancer/mcp/_docs_server_tool_data.py` | `24e968fd533ca5e4a876af6c8544de7c93cfdbe8a18381351b9a7863e576a2d7` |
| `tests/docs/_scope_guidance_contract.py` | `7bbaf01953a09205cd219b67cd66cce93c12561531606e5bd183f1139f397dac` |
| `tests/docs/test_agent_question_planning_contract.py` | `fdc7116561eaa3a36f6b98f53e7bb21fc06a137df58443c72a5e345d14103ad7` |
| `tests/docs/test_agent_recovery_version_guidance.py` | `9cbecd07e83b532d2d442873d97cda867acaca76a528ea3b299eb561f7acba75` |
| `v2plan/PR211_CATALOG_CONTINUATION_REVIEW_RU.md` | `c0b450fd0f02834e768bf057ddf893b538681943c72998de0a1c542d2374a496` |
| Candidate canonical catalog, 6918 bytes | `10160389f0052bc464c6af49b67187d48baa6e0e99f27bdbdfbff559740aa9af` |
| `tests/docs/test_pr211_catalog_equivalence.py` | `3475753adf1f043b13c9d4b325fc4341bd6bab6129d2de502d88cf6446e78473` |
| `tests/docs/fixtures/pr211_catalog_21fe472d.json` | `ad63f367601a18fe04ec715800be2a935a7496c16beb71df4d1818d258bc06db` |
