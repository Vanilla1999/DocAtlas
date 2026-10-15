# PR211 — первый comparison slice сокращения literal-contract tests

Дата: 2026-10-09. Реализация готова к обычному PR CI; локальный repository runtime не исполнялся.

## Решение и этап

Пока **historical остаётся default: 303 + 399 = 702 executions**. Кандидат compact выполняет **33 + 49 = 82 executions** тех же 24 test functions. Это уменьшение на 620 развёрнутых случаев; удаление повторов из обязательного default ещё не активировано. Сначала CI должен подтвердить обе зелёные baseline и обнаружение тех же 51 конкретных production defects.

Не добавлен отдельный evaluator/framework: используются существующие pytest tests и `scripts/run_critical_mutation_gate.py`. Новый stdlib helper только выбирает случаи и записывает происхождение импортов внутри реального pytest child; JSON manifest хранит явные production mutations и review map.

## Изменения и сохранённые свойства

| Семейство / свойство | Historical | Compact | Что делает меньший набор |
|---|---:|---:|---|
| Unknown-tail cross product | 288 | 18 | Каждый из 18 prefixes и каждый из 16 tails присутствует; пара проверяет полный original, изменённый question hash, unresolved semantics и отдельный explicit lookup. |
| Public compiler | 45 | 7 | EN/RU, цитируемый identifier, program syntax, compound wording, exact whitespace/CRLF и combining Unicode. |
| 9 semantic APIs | 135 | 9 | Каждая API имеет собственный случай с исходным и одним заранее заданным mixed-script/unknown-tail преобразованием. |
| 7 surface APIs | 105 | 7 | Та же отдельная ответственность каждого API; нет скрытого цикла по всем 15 прежним вопросам. |
| Frame/composition APIs | 45 | 5 | Все семь отдельных entry points проверяются на двух variant inputs для каждого случая. |
| No legacy delegation | 10 | 2 | Два самостоятельных EN/RU запроса; вызов любого legacy producer остаётся ошибкой. |
| Wrapper/structural identity | 45 | 5 | Точный текст и source offsets с whitespace, цитатами и Unicode. |
| Остальные distinct checks | 29 | 29 | Scope/authority, 4000 input bound, explicit requirements/paths, paragraph/quote masking, immutable DTOs, пять invalid spans, exact reference coordinates/cache/source paths, historical premises. |
| **Всего** | **702** | **82** | **24 test functions в обоих режимах.** |

Compact adapter-case выполняет **ровно два API вызова**, historical — один. Для 9 semantic API фактические вызовы сокращаются 135→18, для 7 surface API 105→14. Frame/composition case вызывает семь API: 315→70 вызовов. Остальные существующие небольшие внутренние циклы не расширены; 288 итераций не перенесены внутрь одного test.

Второй metamorphic input добавляет leading/trailing whitespace, Ω, combining é, quoted `Client.  send` и русский неизвестный хвост. Эти изменения сохраняют независимое ожидание: неразмеченный текст не может создать typed semantics/authority. Это не обещание поиска по произвольным перефразировкам.

Все исторические 18 prefix strings, 16 tails, 45 compiler questions и остальные original literals остаются на месте. Historical expanded roster/order/IDs статически сопоставлен с реально зелёным 99106c9 и заперт hash `f95734c90614be039fb00ae042a66c91066816401013452e93da86edccab3e63`. Compact roster — точное подмножество. Новый namespace или тестовые имена не вводятся; оба diagnostic node hashes неизменны.

## Mutation comparison и честная атрибуция

51 production mutation проверяет каждый отдельный semantic/surface/frame/composition API и риски сохранения raw Unicode/whitespace, unknown tails, source offsets, masking, input bounds, no delegation, original/lookup coverage, answer authority и DTO integrity. Мутации меняют только временную копию production source. Исходники retrieval в рабочей ветке не меняются этим slice.

Каждый режим сначала обязан иметь полную зелёную baseline. Затем каждый mutant запускает полный заранее выбранный target function roster, включая все его оставшиеся parameter cases. Проверяются точное число ожидаемых failures, полный неизменный roster, конкретная первая строка AssertionError guard, отсутствие errors/skips и exit code 1. Arbitrary nonzero, import/setup exception, timeout, vanished report, changed roster, no-op mutation или survivor не засчитываются.

Same-pytest-process plugin проверяет, что изменённый production file, target test и helper действительно импортированы из проверяемой копии; сохраняет их фактические SHA256. Все production/tests/config/helper/manifest files хешируются до и после; отличаться может только явно указанная mutation. Семь синтетических evaluator controls проверяют accepted expected assertion и rejection неправильных assertion/exception/skip/error/roster/survivor reports. Это controls отчётного валидатора, не доказательство продуктового поведения.

Независимый reviewer заметил, что первоначальная выборка adapter inputs теряла RU/Unicode для отдельных API. Исправлено без роста числа вызовов: второй variant смешанный; добавлены два conditional non-ASCII mutants с ожидаемыми 3 historical и 1 compact failures. Unconditional `return None` mutations сами по себе не считались доказательством этого свойства.

## Точный CI запуск

```bash
PYTHONPATH=. python scripts/run_critical_mutation_gate.py \
  --compare-literal-contracts \
  --output-dir "$RUNNER_TEMP/literal-contract-comparison"
```

Нужны обычные уже разрешённые fixture-only Python/pytest subprocesses в CI. Не нужны provider calls, модели, сетевые источники, installation или server processes. Текущий default critical mode с его шестью mutants сохраняется; comparison включается явным flag.

Артефакты: `comparison.json`, baseline historical/compact JUnit, отдельный JUnit каждого mutant/mode, stdout/stderr и same-child `*.imports.json`. Сохраняются expanded executions, testcase seconds и полное wall time каждого child. До подтверждения результата нельзя писать «51 mutants killed».

## Активация после evidence

1. Опубликовать этот comparison slice; выполнить команду на его конечном SHA, сохранить все artifacts.
2. Если обе baseline зелёные и все 51 defects одинаково обнаружены, выполнить отдельный reviewed default change `historical`→`compact` в helper. Полный historical режим остаётся явно доступным для воспроизводимого расширенного прогона; input corpus не удаляется.
3. Повторить ordinary core на окончательном SHA с compact default и подтвердить 82 executions этих семейств. Сохранить независимые transaction/security 109 cases и остальные families без изменения.
4. Частоту дорогостоящего mutation comparison определить отдельно по измеренному CI времени. Один comparison запускает обе версии для каждого дефекта, поэтому сам по себе он дороже обычного набора. Уменьшение ordinary invocations не означает автоматического уменьшения всей CI стоимости.

## Статическая проверка и ограничения

AST/compile четырёх Python files без исполнения; все 51 anchors ровно один раз и каждый mutated source разбирается AST; JSON, historical constants/roster/order, compact82 subset и неизменные 24 test names/diagnostic hashes проверены. `git diff --check` прошёл. Подробные SHA256 и матрица — `literal-contract-reduction-static-audit.json` рядом.

В историческом 99106c9 JUnit body time этих 702 случаев составляет примерно **0.207 секунды** (0.182 + 0.025); startup/collection туда не включены. Поэтому основной ожидаемый результат — меньше повторных проверок и явные свойства, а не обещание большого wall-time ускорения. Новые времена должен измерить CI.

## Полная карта property → old/new target → mutant

В колонках counts указано число выполняемых target parameter cases и ожидаемых assertion failures. Это **ожидания**, подлежащие проверке CI.

| Property | Target function | Executions old→compact | Expected failures old→compact | Mutant / assertion |
|---|---|---:|---:|---|
| raw-whitespace | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 1→1 | `literal_whitespace_preservation` / `literal_original_question` |
| raw-unicode | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 1→1 | `literal_unicode_normalization` / `literal_original_question` |
| input-work-bound | `test_empty_and_bounded_questions_never_become_complete_empty_plans` | 4→4 | 1→1 | `literal_input_bound` / `literal_input_bound` |
| no-inferred-semantics | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 45→7 | `literal_inferred_facets` / `literal_no_inferred_facets` |
| no-complete-empty-plan | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 45→7 | `literal_missing_unresolved_state` / `literal_unresolved_semantics` |
| no-inferred-scope | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 45→7 | `literal_complete_scope` / `literal_incomplete_scope` |
| no-hidden-normalizer | `test_public_compiler_does_not_delegate_to_normalizers_or_legacy_generators` | 10→2 | 10→2 | `literal_legacy_delegation` / `literal_compiler_no_legacy_delegation` |
| distinct-api:match_argument_value_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_argument_value_frame` / `literal_adapter:match_argument_value_frame` |
| distinct-api:match_before_behavior_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_before_behavior_frame` / `literal_adapter:match_before_behavior_frame` |
| distinct-api:match_contract_scope_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_contract_scope_frame` / `literal_adapter:match_contract_scope_frame` |
| distinct-api:match_comparison_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_comparison_frame` / `literal_adapter:match_comparison_frame` |
| distinct-api:match_condition_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_condition_frame` / `literal_adapter:match_condition_frame` |
| distinct-api:match_location_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_location_frame` / `literal_adapter:match_location_frame` |
| distinct-api:match_decision_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_decision_frame` / `literal_adapter:match_decision_frame` |
| distinct-api:match_premise_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_premise_frame` / `literal_adapter:match_premise_frame` |
| distinct-api:match_purpose_behavior_frame | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 15→1 | `literal_match_purpose_behavior_frame` / `literal_adapter:match_purpose_behavior_frame` |
| distinct-api:governance_facets | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_governance_facets` / `literal_adapter:governance_facets` |
| distinct-api:mcp_request_handling | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_mcp_request_handling` / `literal_adapter:mcp_request_handling` |
| distinct-api:provider_request_timeout | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_provider_request_timeout` / `literal_adapter:provider_request_timeout` |
| distinct-api:public_tool_usage | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_public_tool_usage` / `literal_adapter:public_tool_usage` |
| distinct-api:public_tools_with_purposes | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_public_tools_with_purposes` / `literal_adapter:public_tools_with_purposes` |
| distinct-api:python_version_support | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_python_version_support` / `literal_adapter:python_version_support` |
| distinct-api:semantic_components | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 15→1 | `literal_semantic_components` / `literal_adapter:semantic_components` |
| distinct-api:match_action_frame | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_match_action_frame` / `literal_adapter:match_action_frame` |
| distinct-api:match_inventory_frame | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_match_inventory_frame` / `literal_adapter:match_inventory_frame` |
| distinct-api:match_requirements_frame | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_match_requirements_frame` / `literal_adapter:match_requirements_frame` |
| distinct-api:independent_sentence_spans | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_independent_sentences` / `literal_adapter:independent_sentence_spans` |
| distinct-api:compositional_parts | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_composed_relations` / `literal_adapter:compositional_parts` |
| distinct-api:conflict_question_plan | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_conflict_semantics` / `literal_adapter:conflict_question_plan` |
| unknown-tail-authority | `test_frame_and_composition_entry_points_cannot_infer_contracts` | 45→5 | 45→5 | `literal_unknown_tail_authority` / `literal_unknown_tail_authority` |
| wrapper-whitespace-offsets | `test_nl_heads_wrappers_and_connectives_do_not_erase_or_split_text` | 45→5 | 1→1 | `literal_wrapper_erasure` / `literal_wrapper_identity` |
| quote-link-mask-offsets | `test_mask_preserves_literal_offsets_and_unquoted_syntax` | 1→1 | 1→1 | `literal_mask_offset_loss` / `literal_mask_offsets` |
| quote-protected-paragraphs | `test_exact_paragraph_spans_protect_quotes_links_and_program_syntax` | 1→1 | 1→1 | `literal_quote_paragraph_split` / `literal_quote_paragraph_protection` |
| structural-offsets | `test_clause_scanner_preserves_original_offsets_and_noun_coordination` | 1→1 | 1→1 | `literal_punctuation_as_semantics` / `literal_paragraphs_only` |
| source-path-body-separation | `test_literal_retrieval_identity_cache_and_source_paths_survive_without_plan_facets` | 1→1 | 1→1 | `literal_path_as_body_identity` / `literal_symbol_path_separation` |
| source-reference-offsets | `test_literal_retrieval_identity_cache_and_source_paths_survive_without_plan_facets` | 1→1 | 1→1 | `literal_reference_offset_shift` / `literal_reference_offsets` |
| explicit-lookup-no-coverage-credit | `test_known_frame_never_authorizes_an_unknown_tail` | 288→18 | 288→18 | `literal_lookup_required_credit` / `literal_lookup_no_coverage_credit` |
| explicit-lookup-no-parent-credit | `test_known_frame_never_authorizes_an_unknown_tail` | 288→18 | 288→18 | `literal_lookup_parent_promotion` / `literal_lookup_no_coverage_credit` |
| unknown-tail-question-identity | `test_known_frame_never_authorizes_an_unknown_tail` | 288→18 | 36→3 | `literal_unknown_tail_hash_loss` / `literal_unknown_tail_identity` |
| no-answer-authority | `test_governance_question_models_scope_and_every_including_facet` | 1→1 | 1→1 | `literal_answer_authority` / `literal_no_answer_authority` |
| explicit-dto-immutability:QuestionPlan | `test_public_direct_compiler_is_explicitly_unresolved` | 45→7 | 45→7 | `literal_mutable_questionplan` / `literal_plan_immutable` |
| explicit-dto-immutability:PlannedFacet | `test_explicit_dtos_keep_field_shapes_and_do_not_require_prose_approval` | 1→1 | 1→1 | `literal_mutable_plannedfacet` / `literal_facet_immutable` |
| explicit-dto-immutability:ComposedPart | `test_explicit_dtos_keep_field_shapes_and_do_not_require_prose_approval` | 1→1 | 1→1 | `literal_mutable_composedpart` / `literal_composition_immutable` |
| invalid-span:clause_negative | `test_existing_span_validation_still_rejects_invalid_dtos` | 5→5 | 1→1 | `literal_invalid_clause_negative` / `literal_invalid_span_dto` |
| invalid-span:clause_length | `test_existing_span_validation_still_rejects_invalid_dtos` | 5→5 | 1→1 | `literal_invalid_clause_length` / `literal_invalid_span_dto` |
| invalid-span:facet_partial | `test_existing_span_validation_still_rejects_invalid_dtos` | 5→5 | 1→1 | `literal_invalid_facet_partial` / `literal_invalid_span_dto` |
| invalid-span:facet_reversed | `test_existing_span_validation_still_rejects_invalid_dtos` | 5→5 | 1→1 | `literal_invalid_facet_reversed` / `literal_invalid_span_dto` |
| invalid-span:plan_negative | `test_existing_span_validation_still_rejects_invalid_dtos` | 5→5 | 1→1 | `literal_invalid_plan_negative` / `literal_invalid_span_dto` |
| non-ASCII-semantic-branch | `test_semantic_matcher_compatibility_is_non_authorizing` | 135→9 | 3→1 | `literal_unicode_semantic_branch` / `literal_adapter:match_location_frame` |
| non-ASCII-surface-branch | `test_surface_adapters_cannot_inject_subjects_relations_or_expected_values` | 105→7 | 3→1 | `literal_unicode_surface_branch` / `literal_adapter:python_version_support` |
| original-query-credit-independent-of-lookups | `test_known_frame_never_authorizes_an_unknown_tail` | 288→18 | 288→18 | `literal_original_query_credit_lost` / `literal_original_coverage_preserved` |

## Independent review

# Independent review: literal contract reduction comparison

Decision: **APPROVE for ordinary PR CI comparison.** Compact default activation remains conditional on the same-SHA green historical and compact baselines plus all intended production mutant kills. This review does not claim runtime equivalence from static analysis.

## Reviewed scope

- `tests/docs/test_question_span_coverage.py`
- `tests/test_dictionary_exit_legacy_compilers.py`
- `eval/task_level/literal_contract_reduction.py`
- `eval/task_level/literal_contract_mutations.json`
- `scripts/run_critical_mutation_gate.py`, comparison branch

Historical remains the default: 303 + 399 = 702 collected cases. Proposed compact selection: 33 + 49 = 82. The original 18 prefixes, 16 adversarial tails, 45 compiler questions, and all 24 test function names remain unchanged. The existing green 99106c9 JUnit artifact independently confirms the 702 historical cases and the manifest's exact roster hash.

## Strength and guard coverage

Every distinct compatibility API still has its own collected case. The compact compiler set retains Russian, quoted symbol comparisons, program syntax, whitespace/CRLF and combining Unicode. The 18 tail pairs preserve each prefix and each distinct tail. Existing focused DTO validation, immutability, offset, source path separation, unknown-tail identity, non-authorizing ownership and explicit lookup/original identity checks remain.

The first proposed adapter schedule had a concrete blind spot: its index stride selected only English inputs and its second metamorphic call only added whitespace. Each API would therefore lose its historical Russian/Unicode input coverage. This is now closed: the second input contains whitespace, mixed script, a combining character, literal quoted syntax and a Russian unknown tail. Two conditional non-ASCII production mutants were added, alongside an explicit loss-of-original-query-credit mutant. The final manifest contains 51 concrete production mutations.

I independently checked all 51 mutation anchors occur exactly once and every changed source parses and compiles. Expected failure assertions are named and inspected directly; no import or arbitrary runtime crash is counted as a kill.

## Comparison runner

The runner requires complete green baselines in both selections. It binds the historical roster to the previously green evidence and requires compact identities to be a subset. Each mutant runs its exact target family in both selections, with exact expected failure counts, the complete target roster, no errors/skips, exit code 1 and the intended assertion guard. Seven evaluator controls include a valid kill and rejection of survivor, missing roster, skipped case, setup error, wrong assertion and runtime exception.

The actual pytest child reports imported test/helper/mutated module paths and file hashes. Reviewed production/tests/config/helper/manifest input hashes are checked before and after the child; only the single declared production mutation may differ. Fresh source copies exclude Python bytecode and runtime caches. Evidence is retained for each validated run, while failed copies remain available for diagnosis.

## Practical limits

- Runtime comparison is still required; static anchor validity is not a kill.
- Passing 51 specific mutants demonstrates the reviewed defect classes, not equivalence against every possible future regression.
- This pure literal-family comparison cannot establish retrieval source qualification or current source/member binding. Those obligations remain in the independent public retrieval/recovery gates.
- Do not activate compact default if either baseline fails, a mutation survives, or the observed failure differs from its intended guard.

Evidence: `literal-contract-reduction-independent-static-audit.json`. No project imports, tests, provider calls or runtime were executed locally.
