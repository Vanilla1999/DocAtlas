# Core / admission literal dictionary exit — bounded allocation B

2026-10-07. Baseline `9488cb66ab989f6f65bafbfae7d1eb3f844ce0a3`.
Workdir `/tmp/opencode/docatlas-next-admission-9488cb66`.
**Bounded implementation complete; full dictionary exit / release acceptance NOT DONE.**
Primary не редактировался; network/commit/push/agents не запускались.
Parent setup `.venv` symlink, `CONTINUE_HERE_RU.md` и `NEXT_PARALLEL_HANDOFF_RU.md`
оставлены как были и исключены из handoff diff.

## Allowlist / изменения

Только четыре production files в `docmancer/docs/domain/`:

- `question_plan_core.py`: `_safe_coverage_gap` допускает только прежние structural
  whitespace/punctuation separators, не conjunction vocabulary. `_clean` сохраняет
  literal Unicode в прежнем ceiling 160; article stripping, whitespace rewrite
  удалены. `_normalized_clause` возвращает original clause bytes. Span binders,
  consumed-span validation, technical coercion и conservative tail guard сохранены.
- `admission_contract.py`: unknown не наследует `legacy_qualified`; rejected /
  `unverified_local_demand`. Параметр и route enum `legacy_strict` сохранены как ABI,
  но route больше не выдаётся. Matched witness требует непустые identity/source/spans
  и valid nonnegative ranges; hard guards всё ещё первыми. Nonempty explicit matched
  witness остаётся `typed_local`, absent остаётся `missing_local_demand`.
- `admission_local_binding.py`: удалены NL default-property nomination, timeout/delay
  shortcuts, condition state aliasing, owner/heading borrowing, anaphoric stance/action
  rules, duration/value guesses, plural guessing. Optional semantic adapters дают
  None, approval predicates False, assignment/state patterns nonmatching. Unknown
  binding — None, **не supported empty tuple / False absence**. Technical `_WORD`,
  exact subject/literal escaping и punctuation clause-boundary guard сохранены.
- `admission_meaning.py`: supplied equal slots/canonical labels не доказывают NL
  equivalence; direct `same_supported_meaning` False, whole-question audit не выдаёт
  reflexive/blank approval. Uncovered emoji/nonword Unicode теперь explicit unresolved,
  только structural separators могут не создавать residue. Original demand spans,
  literal RetrievalNeed IDs, MeaningSlot DTO и immutable source trace сохранены.

Новые files:
- `tests/test_dictionary_exit_admission_literals.py`;
- `tests/diagnostic_labels.dictionary_exit_admission_literals.json`;
- этот checkpoint.

Vocabulary не перенесён в config/JSON/prompts. AST comparison against baseline:
**все function signatures и все DTO class ASTs identical** во всех четырёх files.
Technical grammar/relation enums, question ownership/frozen registry, selectors,
answer units, source/version/snapshot/lifecycle guards, budgets, hash domains и
historical manifests не редактировались. Local DTO matching не authenticates
source membership или terminal mutation authority.

## Реальные callers / mandatory parent follow-up

Static call sites проверены вместе с runtime probes, не только imports:

1. `question_plan.py` импортирует core helpers, но current public
   `compile_question_plan` возвращает unresolved напрямую. Probe заменяет импортированный
   `_finalize_full_span_coverage` throwing spy: compiler его **не вызывает**.
   Direct core coverage helper тестируется отдельно, без default reachability claim.
2. `choose_need_admission`, `choose_admission`, `compile_admission_demands`,
   `questions_have_same_supported_meaning` не имеют current production call sites
   вне owned modules; direct tests не выдаются за default indexed execution.
3. `retrieval_need_support.retrieval_need_local_witness` реально вызывает
   `default_local_witness` при supplied `need_relation=default`. Runtime spy через
   `apply_retrieval_need_witness` подтверждает вызов. **OPEN mandatory consumer**:
   adapter при None сохраняет incoming `qualified=True` (не добавляет witness).
   Вне allocation; parent должен решить fail-closed treatment unknown для внешних
   supplied callers, а не вернуть NL grammar. Тест записывает debt, не proof credit.
4. Main `evidence_qualification.qualify_evidence` rejecting `query-need-*` /
   `query_contract_mismatch` до default adapter: runtime throwing spy не вызывается,
   forged witness trace удаляется. Поэтому adapter debt **не доказанный default
   public authority bypass**. `_project_docs_service_part03.py` и
   `_docs_context_projection_core.py` содержат только imports adapter, без current
   calls; imports не доказательство execution. External SDK callers UNKNOWN.
5. `retrieval_need_support` state/behavior/requirement/exception NL obligation rules
   остаются вне ownership. Grammar/relations, question_ownership/tooling,
   qualification/selector/source provenance и unit consumers не редактировались.

Следующий allocation только parent; этот executor не расширяет bounded slice.

## Offline normal-conftest проверки

Все pytest commands используют:
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest
-p no:cacheprovider -q ...`. Hash-bound new diagnostic shard / normal conftest /
network guards active; нет `--noconftest`, old assertions/gold/224 registry untouched.

- NEW owned: **94 passed**. Unknown/direct NL negatives, no empty witness approval,
  structural coverage, original Unicode bytes, DTO immutability/span validation,
  literal key/value positive+negative, hashes и actual caller probes.
- `tests/test_dictionary_exit_*.py`: **1525 passed** (current isolated snapshot,
  не review остальных slices и не full CI).
- NEW94 + existing dictionary-exit admission29/compiler399/unithelpers48 + technical
  `target_security`, `content_trust`, `reference_hash_domains`,
  `review_source_capabilities`, `finalized_mcp_output_integrity`, `mcp_boundary`:
  **615 passed / 1 failed**. Единственный red:
  `tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`
  (`answer_available=True`, line 204), прежний documented conflict.
- Old mixed four modules ниже: **390 failed / 12 passed**.
- In-memory **four-owned-files baseline overlay**, все остальные modules current:
  **360 failed / 42 passed**. Это partial overlay, **не full baseline claim**.
  Current-only reds 30: guard legacy fallback [True]/[False] и 28 local-binding
  assertions ожидают False вместо нового explicit None. Overlay-only reds нет;
  meaning30 и coverage302 red nodes unchanged. Не blanket attribution всех reds.
- Initial old command имел неверный path `tests/test_question_span_coverage.py`:
  exit4/no tests; исправленный `tests/docs/...` run учтён выше, error не acceptance.
- `git diff --check`: PASS. Final status содержит только allowlisted edits плюс
  три исходных parent setup entries; existing tests/manifests не изменены.

### Полный red-node inventory в воспроизводимой сгруппированной форме

В каждой строке ниже **ВСЕ collected parameter variants** данного base node red
(проверено normal-conftest collect-only, нет partial red groups). Exact parameter
IDs определены неизменёнными pinned test modules. Поэтому таблица задаёт все 390
nodes, а не выборку; SHA256 sorted newline-joined exact red nodeids:
`a61ce944da01e8cdd21f7f7823460bf6cb37b67410e33712616539d7e1b3ad11`.
Overlay exact red-node digest:
`08a2b7a9dcdfcc427cf42fb46d4f7dda8030f344b8b17f25a0d3bb795ef2658e`.

Prefixes: G=`tests/docs/test_admission_guard_composition.py::`,
L=`tests/docs/test_admission_local_binding.py::`,
M=`tests/docs/test_admission_meaning.py::`,
C=`tests/docs/test_question_span_coverage.py::`.

| Prefix | Base node | Red variants |
|---|---|---:|
| G | test_actual_source_guards_precede_local_witness | 5 |
| G | test_forged_approval_and_old_body_span_are_recomputed | 1 |
| G | test_high_overlap_is_not_a_relation_witness | 3 |
| G | test_low_overlap_is_not_a_license_to_ignore_real_exact_symbols | 1 |
| G | test_missing_parent_identity_does_not_block_independent_need_or_forge_parent | 1 |
| G | test_missing_requested_condition_rejects_even_with_high_overlap | 1 |
| G | test_native_indexed_need_is_qualified_without_claiming_a_complete_answer | 1 |
| G | test_real_planner_and_qualifier_keep_actual_low_overlap | 1 |
| G | test_unknown_preserves_the_strict_legacy_decision | 2 |
| L | test_anaphoric_default_cannot_borrow_another_answer_subject_property_or_condition | 5 |
| L | test_anaphoric_default_cannot_change_polarity_owner_or_property | 3 |
| L | test_anaphoric_timeout_action_preserves_indefinite_article | 2 |
| L | test_compound_property_cannot_be_replaced_by_partial_word_match | 2 |
| L | test_compound_property_is_supported_when_fully_present | 1 |
| L | test_compound_property_with_behavior_suffix_is_not_silently_shortened | 1 |
| L | test_conditional_default_requires_the_requested_state | 3 |
| L | test_default_does_not_borrow_subject_property_or_value | 4 |
| L | test_default_local_layout_controls | 4 |
| L | test_default_requires_an_assignment_for_the_same_local_subject | 6 |
| L | test_default_value_does_not_borrow_another_predicate_or_condition | 4 |
| L | test_direct_default_statement_is_a_witness | 2 |
| L | test_explicit_anaphora_handles_infinitive_stance_and_soft_wrapping | 3 |
| L | test_unrelated_source_title_cannot_lend_subject_to_another_api | 1 |
| L | test_whole_page_membership_is_not_a_local_subject_binding | 1 |
| M | test_actual_query_planner_emits_original_derived_need | 5 |
| M | test_changed_arguments_conditions_and_unparsed_tails_are_not_audited | 10 |
| M | test_only_fully_verified_reformulation_can_derive_original | 1 |
| M | test_quoted_literals_and_original_offsets_are_preserved | 6 |
| M | test_supported_ru_en_frames_preserve_roles | 8 |
| C | test_clause_scanner_preserves_original_offsets_and_noun_coordination | 1 |
| C | test_existing_compounds_and_paraphrases_remain_supported | 1 |
| C | test_governance_question_models_scope_and_every_including_facet | 1 |
| C | test_governance_question_supports_bounded_russian_surface | 1 |
| C | test_known_frame_never_authorizes_an_unknown_tail | 288 |
| C | test_legacy_behavior_usage_fallback_rejects_extra_compound_tail | 1 |
| C | test_legacy_fallback_questions_remain_unclaimed_by_question_plan | 4 |
| C | test_plan_retains_exact_source_spans_after_wrapper_and_whitespace_normalization | 1 |
| C | test_russian_ambiguous_inventory_and_action_frames_fail_closed | 1 |
| C | test_unresolved_residue_reaches_the_requirements_gate | 3 |

Pinned unchanged test bytes (SHA256):
- G `215b2ef50ccc989faaead9063de3ec961b92f9c2b9381fa2149f27a39160d3c0`
- L `e3eec4a7f10584855352228cca65972f2747bb81e7d3693ec3253ac24ebcc676`
- M `3ecadb74c344ba2613adcf8a1c5ecbc937a8f42e77a88e538972102238dedfd7`
- C `2763921f0d8cb93fe5d7dfdd4e680228fab404fd219c2c24c7017d171b011d39`

Temporary full logs доступны parent в `/tmp/opencode/admission-literals-*.log`;
они не единственная provenance: counts, inventory, scope и hashes сохранены здесь.

## Current owned source pins (SHA256)

| File | SHA256 |
|---|---|
| question_plan_core.py | `71dccd291ba799149f5485fad818fb2a5008af3c79ca542053e50000a9ec5d5b` |
| admission_contract.py | `192e69f9043e109c63d7e13edf2afecc5d695121135c80d801cc8c833b9b91e1` |
| admission_local_binding.py | `efd2e2832ba10ebb69a9d780426850867c7d16e912d2d67ae53e5e3291caf33e` |
| admission_meaning.py | `9eea34d0250f79d9c12147b1a89efdc8ce3a9ffaf5109f63d67cd3086e53e9ab` |
| test_dictionary_exit_admission_literals.py | `2e4b1fe30810e77b106ef642a1902b1022a013f6f1f84fc22efd8e9a72f13c17` |
| diagnostic_labels.dictionary_exit_admission_literals.json | `b5cac7d50948029c4b1939c18c6949d08b914d73555647ca463c21d4570176d2` |

Parent extracts только семь allowlisted files; setup copies/symlink исключить.
Independent review, integrated actual indexed MCP/stdio smoke, full CI/rebuilt
package/self-host quality не выполнялись этим executor. Previous quality FAIL
не отменён. Corpus membership/source identity/other consumer debts остаются OPEN.
