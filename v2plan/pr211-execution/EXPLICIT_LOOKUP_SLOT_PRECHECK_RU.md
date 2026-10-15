# PR211: precheck сохранности явных lookup slots

## Узкое решение

База анализа и архивных inputs: `34913345f8f6f491fc707a9028c58d7d68319cd5`,
tree `018a4d9d4d006bf6a5522039afd75c5514f43183`.
Исходный модуль `tests/docs/test_documentation_query_plan.py`,
blob `25de8f3898ba60a33a08425d3e045353fa8014f9`, содержит **29 definitions / 70 cases**.
Сообщённый root actual95 результат — **25 PASS / 45 FAIL**; этот slice не
объявляет весь набор failures отменёнными требованиями.

Выбраны только три mixed plan tests: public IDs (строки 13–37), direct/host
lineage (40–59), повторяющийся lookup (116–130). В existing independent alias
control добавляются их **три точных original questions** и **5 / 1 / 3**
исходных explicit lookup strings. Все 70 старых cases пока остаются collected.
Другие 67 cases, все imports и non-test statements сохраняются.

Это предварительный proof для последующего узкого сокращения трёх tests.
Новых ordinary test functions нет; production не изменяется этим slice.
Проверка создаёт реальные current plan DTO и сериализует их, но не запускает
retrieval и не доказывает качество source facts или MCP delivery.

## Основание текущего контракта

`docs/adr/0003-context-first-project-reads.md`, blob
`9ec7ca998294b171ea3e0e52972ffbdd673116dc`, оставляет original question и
explicit host lookups, отменяет generated translations/questions/source names
и запрещает перенос lookup credit на original.

`docmancer/docs/domain/documentation_query_plan.py`, blob
`0cd20b1138f1a3a2740729677d9588414f2dcf32`:

- строки 13–40 сохраняют DTO validation, включая запрет parent у direct/host;
- строки 53–82 сериализуют явные IDs и coverage-required флаг;
- строки 85–109 создают original и до пяти явных host lookup slots, сохраняя
  исходные строки и номера slots; original required, host lookups optional;
- explicit path остаётся scope metadata, requirements не создают дополнительные
  executable queries, component completeness не выводится из текста.

Пять input slots — сохранённая граница request work, а не output ceiling.
Новые 800/6144 или иные output caps не вводятся.

Старые ожидания `required_query_ids=[]`, generated canonical/exact-anchor
rows и audited parent lineage заменяются именно этим текущим контрактом.
Сохраняемые свойства — все explicit public IDs, точные тексты, порядок,
multiplicity, required original, отсутствие inherited parent и inferred policies.
Идентификатор `get_docs_context` остаётся буквальной частью original и
проверяется текущим `technical_anchors` API; отдельная generated query ему не нужна.

## Независимый oracle и архив

Архив `documentation_query_plan_explicit_inputs.py.txt` — точная полная копия
исходного Python module, сохранённая как неколлектируемый текст. Control читает
его через AST как данные: исторические assertions не импортируются и не выполняются.
Для трёх выбранных functions извлекаются только literal question и literal
`lookup_queries`. Проверяются definition/source lines, полный hash архива,
все девять lookup strings и hash каждого original/lookup.

Crosswalk содержит явно зафиксированные expected rows:
`query_id, text, origin, relation, coverage_required`, public ID arrays и
required ID arrays. Expected не строится через production DTO или его defaults.
Одинаковый `get_docs_context` в slots 1 и 3 должен оставаться двумя host requests.

Hash bindings:

| Запись | SHA256 |
| --- | --- |
| Exact original/archive source | `bb96a79c3005efd943b4f5bb11b4b8fdaf17c5d5cfcae871968870b55e0b9109` |
| Selected source roster | `7577838d21c2121b60804f1e1c798cd5f87303477bb96ca5b0f801a5f12e23d1` |
| Frozen inputs и independent expected rows | `ee96d2abc69481735513a82a70a7db2d6b3729fb5612db2b6e7247292591d3c5` |
| Все 29 полных test node IDs | `2fa96401eaed3a8a68e5993a07485bfe2bac6886fead9892214482ea73f3ac95` |
| Остальные 26 полных test node IDs | `8662d4c3549155598e1d084dfa7664a2cfd1ce8b9a7a50fec4bfc71fe2b728f2` |

Input digest — canonical UTF-8 JSON, ensure_ascii=False, sorted keys и separators
comma/colon. Node hash — отсортированные полные path::function IDs, соединённые
переводом строки без завершающего newline. Эти node hashes считают definitions,
а не параметризованные expanded IDs.

AST preservation сравнивает все unselected nodes, включая imports и каждый
сохраняемый test body. Если selected functions присутствуют, их должно быть
ровно три и все их AST должны совпадать с архивом. Разрешение на future отсутствие
selected nodes не является runtime proof: удаление остаётся отдельным reviewed slice.

## Две адресные production mutations

Существующий runner `scripts/run_critical_mutation_gate.py`, base
`de247bb93baac2f328ab98aea130d82b4a7a6cbd`, остаётся mode **100755**.
В него добавлены только два Mutant records; target tests/modules/counts,
все прежние 25 mutants и весь executor после `def _ignore` побайтно прежние.

| Mutation | Реальная поломка | Новый decisive input | Named guard |
| --- | --- | --- | --- |
| `documentation_plan_keeps_duplicate_lookup_slots` | Dedup lookup_queries перед построением DTO удаляет повторный явный запрос | Record 2, исходные slots 1/3 с `get_docs_context` | `critical_explicit_lookup_duplicate_slots` |
| `documentation_plan_keeps_fifth_lookup_slot` | `lookup_queries[:5]` → `lookup_queries[:4]` теряет разрешённый пятый request | Record 0, `test commands` в slot 5 | `critical_explicit_lookup_fifth_slot` |

Обе мутации имеют один unique source anchor и независимые before/after SHA256
в crosswalk. Они не меняют результаты прежних 24 fixtures existing alias control:
каждый из них передавал только один host lookup. Два из трёх новых originals
также отсутствовали среди этих 24; общий Docs MCP original ранее имел другой lookup.

В control сначала сохраняются все прежние healthy original-only/explicit plans.
Затем три новых exact fixtures проверяют DTO rows и public serialization.
Первый нарушенный assert у dedup должен принадлежать record 2, у truncation —
record 0, с указанным guard. Старые alias mutation guards выполняются далее;
их код и inputs сохраняются.

**Ожидаемая конфигурация normal gate: 54 baseline cases / 27 mutants.**
До mutation credit необходим здоровый baseline: 54 PASS, ноль failures/errors/skips.
Каждый новый fault должен дать ровно один expected assertion FAIL, ноль errors/skips,
correct import/source hashes и named guard. Поломка AST loader, collection или
другой assert не считается intended kill. Это пока требования, а не actual result.

## Audit всех functions: ничего не удалено

| Функция в исходном модуле | Строка | Cases | Решение по смыслу |
| --- | ---: | ---: | --- |
| `test_documentation_query_plan_owns_public_retrieval_query_ids` | 13 | 1 | Selected: сохранить original и пять public host IDs; отменены пустой required roster и generated canonical rows. |
| `test_documentation_query_plan_owns_retrieval_only_alias_lineage` | 40 | 1 | Selected: сохранить direct original и independent host lookup; canonical audited lineage больше не создаётся. |
| `test_documentation_lookup_rejects_invalid_lineage` | 62 | 1 | Сохранить. Проверяет фактический DTO constructor: unsupported relation и audited DTO без parent запрещены. |
| `test_context_budget_is_a_product_invariant` | 69 | 1 | Отдельная миграция. Fixed 3/800 defaults отменены; optional caller bounds и invalid input guards не удалять. |
| `test_evidence_qualification_fails_closed_and_owns_derived_lineage` | 77 | 1 | Mixed qualification: сохранить unrelated/missing terms и исходный body; audited relation теперь отвергается до body. Нужен здоровый explicit host lane. |
| `test_evidence_qualification_rejects_metadata_only_term_matches` | 104 | 1 | Сохранить. Metadata words не заменяют содержательный body; проверяется insufficient_visible_match. |
| `test_same_text_lookups_retain_independent_public_and_canonical_ids` | 116 | 1 | Selected: сохранить повторяющиеся host inputs под независимыми IDs. Literal get_docs_context не обязан создавать дополнительную query. |
| `test_derived_merge_never_invents_successful_direct_coverage` | 134 | 2 | Сохранить. Merge уже supplied traces не должен выдумывать successful direct credit, включая оба порядка. |
| `test_exact_project_facets_and_negative_neighbors` | 160 | 10 | Input-only classifier family: восемь inferred topics отменены; оба negative neighbors сохранить в будущей independent property. |
| `test_alias_budget_is_fair_across_requested_facets` | 165 | 1 | Input-only alias family: fairness четырёх generated facets отменена; два точных вопроса остаются историческими inputs. |
| `test_partial_canonical_facets_cannot_cover_original` | 180 | 3 | Input-only alias family: три полных вопроса с compound/unknown tail не должны превращаться в generated parent credit. |
| `test_only_audited_complete_equivalence_derives_original` | 187 | 1 | Input-only equivalence family: полное совпадение topic text не создаёт audited query/parent authority. |
| `test_host_policies_follow_relevant_facets_not_compound_union` | 196 | 1 | Mixed policy: source restrictions больше не выводятся из Docs/Packs topics; два authored host inputs и их independent lineage сохраняются. |
| `test_unrecognized_host_inherits_only_single_facet_policy` | 209 | 1 | Mixed policy: незнакомый lookup не наследует запреты из inferred facet. Сохранить raw lookup и отсутствие parent. |
| `test_operational_facets_have_role_policies` | 219 | 4 | Input-only alias/role policy family: четыре operational questions не создают inferred source roles. |
| `test_output_budget_wording_gets_requested_facet` | 230 | 2 | Input-only topic routing: две формулировки output budget не являются runtime output-cap проверкой. |
| `test_audited_installation_equivalence_is_complete_and_bounded` | 241 | 4 | Input-only equivalence family: сохранить все четыре suffix variants; три negative ожидания уже согласуются с отсутствием rewrites. |
| `test_narrow_operational_probes_have_policies` | 257 | 3 | Input-only alias/role policy family: markers/config/state questions не создают inferred source policies. |
| `test_project_query_routing_distinguishes_purpose_from_failure` | 269 | 3 | Input-only intent family: classifier теперь general. Эти три labels не проверяют фактическое качество ответа. |
| `test_failed_derived_probe_does_not_contribute_successful_lineage` | 274 | 1 | Сохранить. Failed derived probe не должен добавлять successful lineage к direct trace. |
| `test_requirement_hints_inherit_applicable_host_policies` | 284 | 1 | Mixed policy: requirements hints принадлежат proof owner; planner не превращает их в самостоятельные retrieval queries. |
| `test_failure_neighbors_do_not_become_product_purpose` | 301 | 2 | Input-only intent/alias family: два failure questions не маршрутизируются по topic dictionary. |
| `test_novel_normative_premises_are_not_replaced_by_topic_aliases` | 320 | 10 | Сохранить. Все десять original questions, отсутствие aliases/canonical rows и unknown normative-premise boundary. |
| `test_novel_topics_without_normative_premises_still_search` | 337 | 4 | Mixed adapter migration: broad_context expectation отменена, но exact original input остаётся. fail_closed compatibility не означает blanket запрет реального docs_context. |
| `test_live_normative_premise_cannot_use_generic_storage_evidence` | 350 | 2 | Сохранить оба real MCP cases: explicit finite/member fixture, actual retrieval и no-source/no-answer abstention. Это не classifier control. |
| `test_audited_installation_needs_qualified_evidence_not_just_a_plan_alias` | 389 | 3 | Mixed qualification: все три original installation bodies и positive/negative fidelity обязательны; нужен authored host lookup со своим authoritative_query, без parent transfer. |
| `test_product_definition_host_lookup_without_product_name_can_derive_original` | 415 | 1 | Положительный audited-parent контракт отменён. Исходную question/lookup пару переносить только в no-transfer property с собственным proof. |
| `test_product_definition_neighbors_do_not_derive_original` | 430 | 3 | Сохранить три negative neighbors: explicit host lookup не получает original parent credit. |
| `test_conservative_ru_fallback_cannot_authorize_original_lineage` | 440 | 1 | Input-only fallback family: русская фраза больше не порождает storage/clear-index translation. |

Особенно сохраняются две qualification functions (четыре cases). Их ранний
legacy audited-lane отказ не заменяет живую body проверку. Current
`evidence_qualification.py`, blob `498a3941ce965443ee2508d4f88525966d3d581c`,
строки 246–268, даёт public credit только точному explicit authoritative request
и отвергает nonliteral parent carriers. `derived_parent_trace` (465–469)
возвращает None. Наличие audited-compatible DTO не означает runtime право
перенести credit. Peer независимо подтвердил эту границу.

Два live normative-premise cases используют реальный
`_named_document_service` (`tests/test_named_document_context_integration.py`,
blob `1d8db6ff588a9e2f639b6d7a5f7999f423bb2583`, 119–143):
explicit finite catalog и existing indexed member fixture. Их source/abstention
обязательства остаются независимо collected.

## Selectors и граница будущего retirement

Изучены точные current CI, direct-question-validation, оба Task33 workflows,
tests/conftest.py, pytest configuration и critical runner. В этих workflows нет
явных selectors на выбранные три functions; core собирает tests/ целиком.
Это bounded audit названных callers, не заявление об exhaustive repository scan.

Precheck не меняет original module, diagnostic registration, node hash или
selectors. Перед отдельным retirement обязательны повторный exact consumer/selector
audit, корректировка только owning module node hash и actual normal proof на том же
checkout tree. Все imports и non-test source остаются. Generic classifier reduction
не считается доказательством source-body, source-scope, no-answer или MCP guards.

## Exact manifest

| Путь | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `tests/docs/test_project_retrieval_alias_contract.py` | `100644` | `17f64832f9fe7a4d7532ebb0fe6b6ffbfb81dc8d` | `b341749e7e1e5cef71311acd741df04ebac387ea` |
| `scripts/run_critical_mutation_gate.py` | `100755` | `de247bb93baac2f328ab98aea130d82b4a7a6cbd` | `ca11935e6c15c041da027805578fe4ed32a362df` |
| `eval/task_level/contract_history/documentation_query_plan_explicit_inputs.json` | `100644` | `NEW` | `7b5ced0566acc0d9511926a292bedc1c8f0f4375` |
| `eval/task_level/contract_history/documentation_query_plan_explicit_inputs.py.txt` | `100644` | `NEW` | `25de8f3898ba60a33a08425d3e045353fa8014f9` |

Этот note — пятый новый/изменённый путь, mode100644.

## Статическая проверка и следующий proof

Четыре code/data blobs roundtrip совпадают с drafts. Удаление четырёх bounded
изменений control восстанавливает base побайтно; удаление двух добавленных Mutant
records восстанавливает весь runner base побайтно. В existing control остаётся
одна ordinary test function с тем же node ID. Original module и все 70 cases
остаются точными исходными bytes.

Локальные Python/import/AST execution, pytest/install и runtime не выполнялись.
Root и независимый peer выполнили code/data static review: **APPROVE**.
Actual normal baseline и два intended kills остаются pending. До собственного
runtime proof selected3 не удаляются и новый PASS не заявляется.
