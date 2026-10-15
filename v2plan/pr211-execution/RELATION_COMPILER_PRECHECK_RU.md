# PR211: precheck 25 ожиданий отменённого relation compiler

## Граница решения

Этот срез готовит отдельное сокращение ровно двух test functions из
`tests/docs/test_admission_relation_witnesses.py`:

| Function | Cases | Старое ожидание |
| --- | ---: | --- |
| `test_local_relation_not_question_word_overlap` | 20 | Generated `retrieval_need`, успешный `typed_local`, непустые source spans для EN/RU и обоих ответов |
| `test_new_lexical_family_and_markdown_layout` | 5 | Generated `retrieval_need` и успешный `typed_local` для новых prose/Markdown layouts |

**Все 25 cases этим precheck остаются collected.** Исходный module, его
`CASES`, `probe`, `qualify`, остальные functions и diagnostic registration
не меняются. В будущем допустимо удалить только эти две functions после
собственного зелёного proof и отдельного review.

Это versioned retirement ожиданий отменённой генерации. Он не доказывает
execution-equivalence старых и новых тестов, не считает 25 source questions
решёнными и не заменяет исходные body/condition/native quality obligations.

## Действующий source contract

`docs/adr/0003-context-first-project-reads.md`
(`9ec7ca998294b171ea3e0e52972ffbdd673116dc`) сохраняет исходный вопрос и
явные host lookups, отменяет generated queries и перенос lookup credit на original.

`build_documentation_query_plan`
(`docmancer/docs/domain/documentation_query_plan.py`,
`0cd20b1138f1a3a2740729677d9588414f2dcf32`, строки 85–109)
строит literal original и только явно переданные host slots.
Он не создаёт `origin=retrieval_need`.
Отдельный `question_retrieval_needs` сохраняет unresolved полный original;
это не generated semantic lane и не доказательство requested relation.
`admission_grammar.parse_admission_frame` возвращает `None`, а compatibility
`relation_local_witness` не удостоверяет relation из переданного frame.

В двух выбранных tests общий `probe` вызывает
`next(q for q in plan.queries if q.origin == "retrieval_need")`.
По текущим исходникам эта предпосылка отсутствует до проверки source body.
Новый precheck проверяет действующий запрет генерации через live DQP builder;
он не мутирует отключённый grammar shim и не выдаёт его отказ за entailment proof.

## Actual 113 и остающаяся работа

PR HEAD `441cdefd2b251d63f716bfa75b053413bbe09c76`;
merge checkout `ceea2571e9847a71515feda4e1e1441fafdede44`.

[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263)
показал:

| Module | PASS | FAIL | Первый показанный отказ |
| --- | ---: | ---: | --- |
| admission_relation_witnesses | 23 | 49 | `test_local_relation_not_question_word_overlap`, `StopIteration` |
| admission_relation_safety | 8 | 18 | lane isolation test, `StopIteration` |

Decoded log SHA-256:
`ad44754505bf41a660a8312924380d8989915f6cf776a0579ae84f45edbf0f59`,
569005 UTF-8 bytes. В crosswalk сохранены точные две `JUNIT_MODULE` строки
и номера строк reader. Непоказанные individual outcomes не объявляются
прочитанными; source-derived объяснение выбранных functions отделено от summary.

Ни весь witness module, ни safety module не объявлены legacy:

| Unselected группа | Cases | Что сохраняется |
| --- | ---: | --- |
| keyword/body negatives | 24 | Все 12 original-body rows и 12 старых retrieval_need-origin rows |
| source policy | 15 | Действующие independent foreign/stale/risk controls |
| conditional questions | 3 | Исходные вопросы, оба negative bodies и positive body |
| native public reads | 5 | Original discovery, реальные source bytes и false answer/edit flags |

Итого **47 cases** остаются вне этого сокращения.
Дополнительные 12 старых-origin rows требуют отдельного разбора; этот срез
не удаляет их вместе с original-body negatives. Safety module со всеми
26 cases и импортами `CASES/qualify/probe` остаётся прежним.
Его текущие crop/no-I/O и source-policy faults в critical runner не меняются.

## Два representatives и точный учёт исполнения

1. Из `CASES[1][1]` сохранён русский original:
   `Когда выполняется QueueTasks относительно response delivery?`.
2. Из последнего literal decorator row второй function сохранён original:
   `How do input fields correspond to output fields?`.

Каждый input вызывает настоящий `build_documentation_query_plan` ровно один раз.
Проверяются raw query rows, полный original, отсутствие parent/need/policy fields,
component incompleteness и полный public payload по независимым literal JSON
expected values. Gold не конструируется вторым production DTO с теми же defaults.

Добавлены **2 plan calls**, **0 alias calls**, **0 qualification calls**,
**0 ordinary test functions**. В control остаётся одно pytest-имя.
Ни 20 EN/RU/answer combinations, ни пять layout bodies не запускаются циклом
через старый `qualify`, новый qualifier, retrieval или MCP.

Все 25 question/body/operator/historical-assertion records сохранены в crosswalk.
Они заново извлекаются только как данные: literal `CASES`, literal decorators,
точный произведённый порядок answer/language/family и пять layout rows.
Выполнение old helper или test body отсутствует.

## Один направленный generation fault

Mutation `relation_question_does_not_generate_typed_retrieval_need`
меняет live `build_documentation_query_plan`: для temporal surface
` relative to ` или ` относительно ` добавляет один настоящий
`DocumentationLookup("query-need-1", question, "retrieval_need", relation="direct",
need_relation="temporal_order")`.

Этот DTO допустим текущему constructor: parent отсутствует, relation входит
в разрешённый enum. Ошибка должна возникнуть на independent row assertion
`critical_relation_original_does_not_generate_need_queries`, а не на
ValueError, collection, StopIteration или произвольном earlier guard.

Новые два inputs исполняются после всех прежних checks control.
В 24 prior originals, трёх DQP3 originals и двух DQP30 representatives нет
обеих temporal surfaces; прежние lookups тоже не создают этот original.
Первый новый русский input достигает fault; второй mapping input остаётся
обычным healthy original.

Все 29 прежних Mutant blocks, их target order, expected failures, guards,
import roster и executor сохранены побайтно. Новый block добавлен последним.
Уникальный source anchor и before/after SHA-256 закреплены в crosswalk.
Один mutant child добавляется; измеренного ускорения CI здесь нет.

## Сохранение source и future retirement

Полный archive — точный исходный blob
`f230beaa41ebb0b999f97493007fe253c629ef78`.
Control требует одну из двух **полных** последовательностей AST:

- все исходные nodes: 6 test functions / 72 cases;
- удалены только выбранные две functions: 4 test functions / 47 cases.

Неполное удаление, изменение imports, `CASES`, helpers, соседнего test body
или decorator не соответствует ни одной последовательности.
Whitespace не объявляется отдельным runtime AST proof; будущий source removal
потребует своего exact inverse и review.

| Binding | SHA-256 |
| --- | --- |
| Полный source/archive | `34620c11c83e58dad640b4ee56711830de9ab3ba18ca0c64e88e6f26ffea2809` |
| Selected 2-function roster | `8f70e346a0c0cb4ba2e4580d715637895d10ebe1b11ccd4e6ebafdd7fc9ffbae` |
| 25 raw archived records | `c75cba6725098b2ca036a47634091f015a5917c3c5b10bed88a001f57b1b474b` |
| 2 representatives и literal expected values | `5943d52139a599c91cebfe3eddb1eab73fde67287d509fc3af9524c359ef57b7` |
| 6 исходных test node IDs | `a005ffa9039aa28ec770ad4fac6aa32c1f6e1ed0e7502b42b4dd20557794fe7f` |
| 4 future test node IDs | `a7b826ebf07b3eacaaf91d6543517619f1291c2b98fdf6e6d95a0aa75105d37d` |

JSON digests: UTF-8, sorted keys, ensure_ascii=False, compact separators.
Node hashes: sorted полные path::function IDs, newline без trailing newline.
Owning shard проверен отдельно: `tests/diagnostic_labels.admission_contract.json`,
base `5714aa323a983c9f070559088a0499fa863a7d4e`; его текущий witness hash
совпадает с шестью nodes. Сейчас shard не меняется.

## Phase 1: конкретный manifest для review

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| tests/docs/test_project_retrieval_alias_contract.py | 100644 | b691088f84e48599512fe7126463c4679a98de23 | 49903acefdaf9960870801ab93bb968748ef6678 |
| scripts/run_critical_mutation_gate.py | 100755 | d6e04f2459e5407c335d55964c9404e3ac871e1a | 015135ccd27685ba888b4a74250f08c252907ed3 |
| eval/task_level/contract_history/admission_relation_compiler_inputs.py.txt | 100644 | NEW | f230beaa41ebb0b999f97493007fe253c629ef78 |
| eval/task_level/contract_history/admission_relation_compiler_inputs.json | 100644 | NEW | 1a3a104a097e533dddc1e54fb8757027f2828ea3 |
| v2plan/pr211-execution/RELATION_COMPILER_PRECHECK_RU.md | 100644 | NEW | этот документ |

Code bases включают предыдущий DQP30 precheck; его собственный runtime ещё
не заменяется этим source review. Четыре code/data roundtrips совпали.
Control 420→539 lines: только constants, один data-only helper и финальный
двух-input block. Их удаление восстанавливает base побайтно.
Runner 857→866 lines: удаление одного нового Mutant block восстанавливает
весь base, включая executor, побайтно.
Одна existing pytest function и её diagnostic node hash остаются прежними.

Phase 2 пока не создана. Она потребует actual healthy proof, свежего consumer
и selector audit, отдельного удаления двух functions, изменения только owning
module hash, real runtime receipt в crosswalk и note. Никаких заранее
одобренных production, gold, scorer или source-policy изменений нет.

## Runtime

Целевой joint critical proof: **54 PASS / 0 FAIL / 0 ERROR / 0 SKIP** и
**30 intended kills**, включая новый один FAIL с точным guard, нулём errors/skips
и совпадающими source/import identities. Предыдущие DQP3/DQP30 runtime guards
сохраняют свои обязательства.

На момент подготовки все 25 old cases ещё collected.
Новый baseline и mutant не запускались локально или отдельно от обычного CI.
После root/peer source review результат остаётся **PENDING** до исполнения
на конечном опубликованном SHA; сохранённый blob не является runtime PASS.
