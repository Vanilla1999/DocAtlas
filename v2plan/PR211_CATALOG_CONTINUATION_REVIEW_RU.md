# PR #211: продолжение сокращения catalog без смены контракта

Дата: 2026-10-08. База: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.
Это отчёт автора для независимого review. Локально выполнены только AST/stdlib
проверки; pytest, validators, MCP subprocess и clients автор не запускал.

## Результат и открытый gate

Advertised catalog: **7066 → 6918 UTF-8 bytes**, экономия **148 bytes**.
От исходной независимой базы `21fe472d` это **7602 → 6918**, экономия 684 bytes.
Действующий ceiling **≤6144** не изменён: **FAIL, превышение 774 bytes**.
Output schema **860 <1000 bytes**, буквально прежняя. Она уже входит в catalog.

| Инструмент | Весь tool до | Весь tool после | Input после | Output после | Tool description после |
|---|---:|---:|---:|---:|---:|
| get_docs_context | 2414 | 2342 | 490 | 860 | 917 |
| prepare_docs | 4007 | 3950 | 3600 | — | 295 |
| docs_status | 641 | 622 | 415 | — | 153 |

Input prepare уменьшился только на 38 bytes описаний mutation/storage_path.
Остальные input constraints, значения defaults, nullable fields, enums, bounds,
required fields, unknown-field closure и conditional branches буквально прежние.
Ни одного runtime handler, sanitizer, loader/registry, internal/advanced schema или
retrieval producer этот slice не меняет. Числовое предложение 7168 не одобрено и
не реализовано. Bytes не являются измерением model tokens.

## Сохранённый смысл каждой сокращённой части

| Было | Стало | Сохранённый контракт |
|---|---|---|
| One concrete original question unchanged | One unchanged concrete original question | Один конкретный исходный вопрос без переписывания |
| benchmark/evaluation or documentation-governance meta-questions | benchmark/evaluation/docs-governance meta-questions | Ни один из трёх видов meta-question не заменяет вопрос |
| never infer rewrites, translations, subquestions, expected answers or source names; never batch independent questions | never infer rewrites/translations/subquestions/expected answers/source names or batch independent questions | Явные lookups того же вопроса; весь список запретов и independent-question batching сохранены |
| Keep exact literals. Preserve explicit project/library/version/scope/path | Keep exact literals and explicit project/library/version/scope/path | Сохранить literals и все пять явно заданных bindings |
| all=repo+modules in the same repository without module filters | all=repo+modules, same repository, no module filters | Тот же repository и отсутствие module filters обязательны |
| module_path always implies module scope | module_path implies module scope | Безусловная импликация именно от module_path, не от другого поля |
| set only explicit exact/historical versions | exact/historical versions only if explicit | Версия только по явному запросу; omit для current project и requery после lockfile изменений прежние |
| certify neither answer completeness, proof nor edit readiness | certify no answer completeness/proof/edit readiness | Context/flags не удостоверяют ни одно из этих трёх свойств |
| separate explicit target and authorization | separate explicit target+authorization | Для edit нужны отдельные explicit target и authorization; hard_stop=true/false guards прежние |
| freshness, provenance, network consent and budgets | freshness/provenance/network consent/budgets | Все четыре guard categories остаются обязательными |
| Use only ... or an explicit docs lifecycle request | Only ... or explicit docs lifecycle request | Preparation только из returned get_docs_context action или explicit lifecycle request |
| missing/stale docs or network approval alone ... | missing/stale docs/network approval alone ... | Missing/stale и network approval сами по себе preparation не разрешают |
| source bindings, confirmation and network consent | source bindings/confirmation/network consent | Сохранены все три prerequisites; poll returned job_id и один unchanged retry после verified readiness прежние |
| explicit health, freshness, indexing, or job-progress requests | explicit health/freshness/indexing/job-progress requests | Read-only status для тех же явных запросов; no discovery прежний |
| a returned job_id from prepare_docs | returned prepare_docs job_id | Job ID должен быть выдан prepare_docs, не угадан |
| Confirmed lexical member upserts; omitted/null grants no writes | Confirmed lexical member upserts only; omitted/null: no writes | Только подтверждённые lexical member upserts, отсутствие/null не дают write |
| Bind exact catalog, document hashes and generation | Bind exact catalog/document hashes/generation | Привязки catalog, document hashes и generation точные; null generation только для absent store |
| POSIX no-follow reads required; unsupported platforms fail closed | POSIX no-follow reads or fail closed | Без этих reads операция обязана fail closed, включая unsupported platform |
| caller/project cannot redirect | no caller/project redirects | Тот же exact absolute host-selected private DB вне project; ни caller, ни project его не перенаправляют |

Guidance не требует предварительно загружать skill/reference для обычного
get_docs_context. Source-as-data/no-instructions, lookup coverage non-transfer,
separate edit authorization, hard_stop, source/version bindings и consent
остаются видимыми в обычном catalog.

## Meaning helper и отрицательные controls

`tests/docs/_scope_guidance_contract.py` принимает только прежние clauses и
перечисленные эквивалентные варианты. Это не проверка присутствия разрозненных
ключевых слов. В частности, compact запрет independent-question batching обязан
быть частью того же `never infer ... or batch ...` clause. Отдельный отрицательный
control сохраняет запрет inference и разрешает batching; он должен падать именно
на `lookup.batch`, а не на соседнем inference guard.

Scope clauses по-прежнему разбираются отдельно для project/module/all. Required
`same repository` и отсутствие filters проверяются внутри **all** clause;
module scope связывается именно с `module_path` или с description этого поля.
Version omit связывается с current project/version. Дополнительный `type` у scope,
если он объявлен, обязан сохранять nullable string. Сам exact enum уже задаёт
те же JSON types. Любой default, включая null, отвергается helper.

Два существующих pytest nodes сохранены с теми же IDs:

- `tests/docs/test_agent_question_planning_contract.py::test_runtime_tool_teaches_one_concrete_question_per_call`
- `tests/docs/test_agent_recovery_version_guidance.py::test_advertised_tool_guidance_matches_installed_recovery_and_question_rules`

Их прежние 4+6 controls сохранены как явные successors новых формулировок; добавлены
соседние semantic negatives. Всего внутри двух nodes **38 mutations**: 20 question/
scope/authority prose, 5 scope schema/default, 13 recovery/version/lifecycle.
Это 38 iterations внутри двух nodes, не 38 дополнительных pytest cases.

Каждая mutation сначала доказывает, что реально изменила current guidance/schema.
Затем ожидается `AssertionError` с конкретным guard label. Поэтому обновление
needle не может молча превратиться в no-op, а случайный отказ другого guard не
считается успешной проверкой. Покрыты wrong project/module meanings, cross-repo all,
implicit module filters, подмена module_path на project_path, inferred bindings,
scope widening, extra enum value, исключение null, default project/module/null,
current-library вместо current-project version, inferred versions, guessed job ID,
speculative preparation, source bindings, confirmation/network consent и authority.

У question module осталось 8 top-level test nodes, у recovery module — 3; все
прочие AST nodes этих файлов, включая policy expectations, imports, decorators и
остальные test bodies, равны базе. Inventory и selectors не менялись.
`test_pr211_catalog_equivalence.py` и frozen 7602-byte fixture не менялись:
5 schema nodes и 417 ранее подготовленных boundary cases остаются прежними.

## Почему остальные рассмотренные сокращения не включены

Гипотетический catalog **без всех descriptions** занимает 5108 bytes. При ceiling
6144 на все description texts вместе с их JSON keys осталось бы 1036 bytes.
В candidate эти annotations занимают 1810 bytes, из них сам текст — 1708 bytes.
Это объясняет оставшиеся 774 bytes; удалить annotations целиком означало бы
потерять самостоятельную guidance обычных вызовов. Это не доказательство того,
что 6144 математически недостижимо при любом другом представлении.

Из оставшегося prepare input особенно существенны открытые advertised parameters,
member mutation structure и conditional action guards. Mutation structure без
descriptions занимает 920 bytes; все три conditional branches — 723 bytes без
обрамляющего ключа allOf. Их ограничения действуют до service I/O и не заменены
проверкой в handler.

Проверены следующие варианты, но production patch их не содержит:

1. Удаление двух nullable-string types, подразумеваемых enum, экономило бы 50 bytes
   в буквальной schema. Однако текущий `_strip_null_enum_values` при отсутствующем
   type удаляет null из enum. Реальный advertised surface тогда **теряет null**.
   Такой patch не эквивалентен без отдельного изменения sanitizer. Оно не внесено
   ради этих 50 bytes. Это найденная зависимость producer, не объявленная новая
   runtime regression текущего schema.
2. Вынос общего required/nonempty project_path трёх actions в отдельный conditional
   добавляет 18 bytes: повторный action discriminator съедает экономию. Перенос
   первого if/then/else на верхний уровень сохраняет только 2 bytes и перестраивает
   нормализацию ради ничтожной экономии. Оба варианта отклонены.
3. Prefix regex вместо полных action discriminators, группировка полей через
   patternProperties и ссылки на короткие scalar definitions ухудшают прозрачность
   advertised fields или связывают validation с именами/prefixes. Они не использованы.
4. Digest/generation maxLength остаются явными: `$` допускает terminal newline в
   применяемом regex engine. Замена lengths строгим lookahead и объединение path
   negative lookaheads дают единичные bytes ценой менее очевидного schema. Эти
   перестановки не нужны для сохранения текущего контракта и не закрывают 774 bytes.

Никакой из этих вариантов не оправдывает silent ceiling increase, generic object,
удаление source/consent guards или перенос validation исключительно в service.

## Локальное evidence и его предел

Выполнено без импорта DocAtlas, без pytest/jsonschema и без сторонних downloads:

- `ast.literal_eval` трёх PUBLIC_ADVERTISED constants текущего файла и `git show`
  точной базы; canonical JSON: `ensure_ascii=False`, `sort_keys=True`,
  `separators=(',', ':')`, UTF-8 без newline.
- Полное AST равенство всех остальных source nodes; input равенство после удаления
  только description annotations; буквальное output равенство.
- Положительный вызов actual meaning helper на frozen 21fe catalog, базе df9b и
  candidate: все три проходят.
- Два изменённых test bodies исполнены из AST в stdlib harness с extracted literal
  catalog и assertion-only `raises` adapter: все 38 mutations реально меняют свой
  input и отвергаются с ожидаемым конкретным guard. Это **не pytest/SDK/runtime PASS**.
- AST parse всех четырёх изменённых Python files, прежний test roster и `git diff --check`.

Normal CI после интеграции должен подтвердить helper callers, 5 equivalence nodes,
boundary validation, реальный advertised catalog и installed MCP. Этот локальный
отчёт не подменяет эти проверки, required CI/downstream gates или client acceptance.

## Hashes для независимого review

Это content SHA256, не tested commit SHA.

| Файл/артефакт | SHA256 |
|---|---|
| `_docs_server_tool_data.py` | `24e968fd533ca5e4a876af6c8544de7c93cfdbe8a18381351b9a7863e576a2d7` |
| `_scope_guidance_contract.py` | `7bbaf01953a09205cd219b67cd66cce93c12561531606e5bd183f1139f397dac` |
| `test_agent_question_planning_contract.py` | `fdc7116561eaa3a36f6b98f53e7bb21fc06a137df58443c72a5e345d14103ad7` |
| `test_agent_recovery_version_guidance.py` | `9cbecd07e83b532d2d442873d97cda867acaca76a528ea3b299eb561f7acba75` |
| Candidate canonical catalog, 6918 bytes | `10160389f0052bc464c6af49b67187d48baa6e0e99f27bdbdfbff559740aa9af` |
| Неизменный `test_pr211_catalog_equivalence.py` | `3475753adf1f043b13c9d4b325fc4341bd6bab6129d2de502d88cf6446e78473` |
| Frozen catalog fixture, 7602 bytes | `ad63f367601a18fe04ec715800be2a935a7496c16beb71df4d1818d258bc06db` |

**Итог автора:** узкое prose/test изменение готово к независимому review.
Footprint acceptance остаётся открытым: **6918 >6144**. Retrieval не менялся.
