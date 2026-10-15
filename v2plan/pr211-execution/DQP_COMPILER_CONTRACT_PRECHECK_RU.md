# PR211: precheck 30 отменённых DQP compiler expectations

## Решение и граница

База: `441cdefd2b251d63f716bfa75b053413bbe09c76` (113).
Исходный `tests/docs/test_documentation_query_plan.py`, blob
`25de8f3898ba60a33a08425d3e045353fa8014f9`, содержит **29 definitions / 70 cases**.
Полный архив этого же blob уже существует:
`eval/task_level/contract_history/documentation_query_plan_explicit_inputs.py.txt`.
Новая копия архива не создаётся; его bytes и прежний DQP3 crosswalk не меняются.

Этот пакет создаёт только **precheck**. Все 30 рассматриваемых cases остаются
collected. Ни один test function, decorator row, исходный question, body,
import, helper или diagnostic registration этим пакетом не удаляется и не меняется.
Retirement допускается отдельным review после здорового собственного runtime proof.

Это версионированный отказ от expectations отменённого compiler, а не доказательство
execution-equivalence старых FAIL-тестов и нового контракта. Source facts,
qualification, source identity/scope/hash и настоящий MCP delivery сохраняют свои
отдельные проверки. Два representatives не считаются выполнением всех архивных inputs.

## Основание текущего контракта

- `docs/adr/0003-context-first-project-reads.md`,
  `9ec7ca998294b171ea3e0e52972ffbdd673116dc`, строки 17–20:
  original и явные host lookups сохраняются; generated questions/translations и
  перенос lookup credit на original отменены. Строки 24–31 сохраняют
  source/scope/fidelity guards и не задают fixed 800/6144 output ceilings.
- `docmancer/docs/domain/documentation_query_plan.py`,
  `0cd20b1138f1a3a2740729677d9588414f2dcf32`, строки 85–109:
  только literal original и до пяти explicit host slots; original required,
  host optional, без inferred policies и public parent. Пять input slots — прежняя
  граница request work; новый output limit не вводится.
- `docmancer/docs/domain/project_retrieval_intent.py`,
  `989e317c45a18fc19d0074a832095ed6a7e7d097`, строки 36–37:
  free-prose alias generation отсутствует.
- `docmancer/docs/domain/project_query_intent.py`,
  `45de711d37bdce2574b9704eaa42e6ecc8278923`, строки 40–41:
  neutral `general` DTO. Его name/flags проверяет отдельный существующий intent
  control, а не alias test.

## Точный subset будущего retirement

| Function | Было cases | Будет выведено | Останется live |
| --- | ---: | ---: | ---: |
| `test_exact_project_facets_and_negative_neighbors` | 10 | 8 | 2 |
| `test_alias_budget_is_fair_across_requested_facets` | 1 | 1 | 0 |
| `test_partial_canonical_facets_cannot_cover_original` | 3 | 3 | 0 |
| `test_only_audited_complete_equivalence_derives_original` | 1 | 1 | 0 |
| `test_operational_facets_have_role_policies` | 4 | 4 | 0 |
| `test_output_budget_wording_gets_requested_facet` | 2 | 2 | 0 |
| `test_audited_installation_equivalence_is_complete_and_bounded` | 4 | 1 | 3 |
| `test_narrow_operational_probes_have_policies` | 3 | 3 | 0 |
| `test_project_query_routing_distinguishes_purpose_from_failure` | 3 | 3 | 0 |
| `test_failure_neighbors_do_not_become_product_purpose` | 2 | 2 | 0 |
| `test_product_definition_host_lookup_without_product_name_can_derive_original` | 1 | 1 | 0 |
| `test_conservative_ru_fallback_cannot_authorize_original_lineage` | 1 | 1 | 0 |
| **Итого** | **35** | **30** | **5** |

В `test_exact_project_facets_and_negative_neighbors` сохраняются ровно rows
6 и 8 (zero-based): «Где находятся модули?» и «Какие инструменты нужны для ремонта?»,
обе с исходным empty-set expectation. В installation function сохраняются ровно
rows 1, 2 и 3: suffixes « и объяснить архитектуру?», « и проверить неизвестный контракт?»,
« с UnknownLedger?» с исходным False. Bodies обеих functions остаются целиком прежними.

Остальные 32 cases после отдельного DQP3 subset не входят в этот retirement:
20 DTO/merge/metadata/normative/MCP/neighbor guards, четыре mixed qualification/body,
четыре disposition/context-access, три host-policy/requirement-hint и один старый
fixed-budget test. Содержательные unknown-tail/no-parent properties остаются в
действующих literal controls; архив сохраняет исходные compound/unknown inputs.

## Два независимых representatives вместо 35 production executions

1. Точный исходный compound question:
   `Explain project purpose, architecture, offline mode and context token budget`.
   Проверяются literal original DTO/payload и отсутствие aliases.
2. Точный исходный canonical text:
   `project architecture overview components indexing retrieval storage`.
   Сначала проверяется original-only plan. Затем этот же текст передаётся
   **явно автором fixture** как host lookup. Оба запроса имеют отдельные IDs;
   равенство bytes не создаёт audited rewrite, parent или required lookup credit.

Новый второй lookup не выдаётся за lookup из старого test, автоматический alias
или изменение original gold. Provenance записана явно в crosswalk.
Expected rows — фиксированные literal JSON values, а не второй production DTO
с теми же mutable defaults. Код проверяет оба original texts через literal AST
существующего frozen source, source/input hashes, query order, IDs, relations,
coverage flags, public serialization, no-parent и пустые policy fields.

В existing control остаётся **одна ordinary test function**.
Добавлены только **2 representative records / 3 plan calls / 2 alias calls**.
35 historical cases читаются как архивные source/roster данные и не перезапускаются
в цикле production API. Это не обещание ускорения полного CI: добавляются два
mutation child runs, а wall-clock эффект пока не измерялся.

## Directed faults и причинный порядок

| Mutation | Decisive input | Named guard |
| --- | --- | --- |
| `documentation_compound_topic_does_not_generate_aliases` | Compound architecture + token budget | `critical_compound_request_has_no_generated_aliases` |
| `documentation_equal_lookup_does_not_inherit_original` | Explicit lookup byte-equal to original | `critical_equal_lookup_has_no_original_credit` |

Первый fault возвращает реальный alias DTO только при совместном наличии
`architecture` и `token budget`; прежние 24 + 3 plan records его не достигают.
Второй fault меняет только equal-text host на допустимый `exact_anchor` DTO
с parent; constructor не должен выдать ValueError. Среди прежних explicit
fixtures равенства original/lookup нет. Оба source anchors уникальны, before/after
SHA256 и expected node/guard находятся в crosswalk.

Новые проверки исполняются после прежних alias guards. Поэтому старый generic
alias mutant первым попадает в `critical_alias_no_generated_queries`, а прежний
Russian-router mutant сохраняет собственный guard. Старые DQP3 duplicate/fifth
faults по-прежнему останавливаются на своих ранее расположенных checks.
Новые mutants должны первыми нарушать только свой named assertion: один FAIL,
ноль errors/skips. Ранний parser/collection/другой assert не считается kill.

Существующие независимые guards и их конкретные faults перечислены в crosswalk:
alias API, отдельный intent DTO, original/host credit и unknown-tail bytes.
Три literal DQP faults принадлежат отдельному literal comparison, а не новым
двум normal mutants. Slot mutations не объявляются самостоятельным доказательством
каждой generated-query ветки; metadata-only/fidelity/MCP guards не заменяются этим gate.

## Строгое сохранение AST и отдельный DQP3

Старый `_explicit_plan_inputs` проверял все nodes кроме своего DQP3 subset.
Теперь вместо общего исключения compiler family строятся два полных ожидаемых
AST sequences:

- exact precheck: все 12 functions / 35 cases прежние;
- exact future retirement: удалены десять перечисленных functions, у двух других
  сохранены только точные разрешённые negative rows; **каждый остальной AST node
  остаётся byte-bound к frozen source по смысловой AST структуре**.

Проверка сравнивает целую последовательность с одним из двух шаблонов.
Частичный retirement, перестановки, arbitrary bodies/decorators/imports/helpers
не принимаются. Copy для двух decorators меняет только разрешённые `elts`;
function bodies не реконструируются и не упрощаются.

Прежние три DQP3 functions проверяются отдельно: ровно три исходных AST либо ноль.
Их archive, input roster, five-slot/duplicate guards и отдельное runtime условие
сохранены. Structural допуск будущего состояния не заменяет review/runtime
разрешение на его публикацию.

| Binding | SHA256 |
| --- | --- |
| Полный source/archive | `bb96a79c3005efd943b4f5bb11b4b8fdaf17c5d5cfcae871968870b55e0b9109` |
| Новый selected roster, source spans, indices и property mapping | `b910fa3dd979b133e630c45aa35c4b71fd66d5c62f95094422120c993d057b60` |
| Два representative records и literal expected values | `4c28bcbe98ec8fbb338555a7a45536139c60ace5dcfd2643b1cd12ae4bec6047` |
| Все 29 node IDs | `2fa96401eaed3a8a68e5993a07485bfe2bac6886fead9892214482ea73f3ac95` |
| Только retirement30: 19 node IDs / 40 cases | `cb9b114c9c4f43872e9f906c7f94bea4ab49b1ae718b6a48ae14607e8000922a` |
| После независимых retirement3 + retirement30: 16 node IDs / 37 cases | `3e87a5d20558573e7eb7e70b3a64a22b8528843879fc13a4965aa3578da0533b` |

JSON digests используют UTF-8, sorted keys, ensure_ascii=False и separators comma/colon.
Node hashes используют sorted полные path::function IDs через newline без trailing newline.

## Phase 1: применяемый сейчас manifest

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `tests/docs/test_project_retrieval_alias_contract.py` | `100644` | `b341749e7e1e5cef71311acd741df04ebac387ea` | `b691088f84e48599512fe7126463c4679a98de23` |
| `scripts/run_critical_mutation_gate.py` | `100755` | `ca11935e6c15c041da027805578fe4ed32a362df` | `d6e04f2459e5407c335d55964c9404e3ac871e1a` |
| `eval/task_level/contract_history/documentation_query_plan_compiler_retirement.json` | `100644` | `NEW` | `1cf4451a15cef17c4b8b4791ddc1e0182d6478f1` |

Этот note — четвёртый NEW путь:
`v2plan/pr211-execution/DQP_COMPILER_CONTRACT_PRECHECK_RU.md`, mode100644.

Все три code/data blobs roundtrip совпали с подготовленными strings.
Inverse семи bounded control edits и двух hash-guard refinements восстанавливает
`b341749e7e1e5cef71311acd741df04ebac387ea` побайтно.
Удаление только двух новых Mutant records восстанавливает
`ca11935e6c15c041da027805578fe4ed32a362df` побайтно.
Все прежние 27 mutants, target tests/counts/import modules и executor,
включая literal comparison, неизменны. Runner сохраняет mode100755.

## Phase 2: отложенный manifest, без готового удаления

После actual proof отдельный reviewed commit может менять только:

| Путь | Точная допустимая правка | Base/proposed |
| --- | --- | --- |
| `tests/docs/test_documentation_query_plan.py` | 10 functions и 9 положительных decorator rows; сохранить 5 negatives и всё остальное | Fresh exact base после решения по DQP3; proposed blob пока не создан |
| `tests/diagnostic_labels.compound_context.json` | Только owning module node-roster hash | Fresh exact base; proposed blob пока не создан |
| Новый compiler crosswalk | Реальная same-tree runtime receipt и retirement state | Phase-1 blob выше; future proposed пока не создан |
| Этот note | Actual acceptance и точный применённый retirement manifest | Phase-1 note; future proposed пока не создан |

Перед этим нужен current consumer/selector audit; прежний bounded workflow audit
не объявляется полным доказательством всех внешних selectors. Case filtering
сохраняет два действующих function names; удаляемые десять names проверяются отдельно.

## Runtime status

Normal gate после этого precheck должен дать **54 PASS / 0 FAIL / 0 ERROR / 0 SKIP**
и **29 intended kills**, включая два новых named failures. Отдельное DQP3 собственное
доказательство и используемые literal comparison receipts должны быть здоровыми
на соответствующих исходниках. Checkout merge SHA, PR head и same-tree evidence
фиксируются раздельно; store presence или console summary не заменяет receipt.

В начале этого среза root сообщил, что current113 critical step FAIL; его individual
first failure ещё не был доступен. В этом note новый или полный CI PASS не заявлен.
Ни один old case не удалён, локальные Python/AST/import/pytest/runtime не исполнялись.
Root/peer static review выполняется до commit; финальный actual runtime остаётся pending.
