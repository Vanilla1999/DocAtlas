# Local residual dictionary exit: bounded slice

2026-10-07. Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
Worktree ONLY `/tmp/opencode/docatlas-final-local-residual-42c72bd6`.
**Два allocated residual удалены; full dictionary exit / quality acceptance NOT DONE.**
Primary не редактировался. Network/commit/push/agents не запускались.
Предсуществующий untracked `.venv` оставлен; не extraction artifact.

## Ровно пять extraction files

1. `docmancer/docs/domain/source_map.py`
2. `docmancer/docs/domain/project_state.py`
3. `tests/test_dictionary_exit_local_residuals.py`
4. `tests/diagnostic_labels.dictionary_exit_local_residuals.json`
5. `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/LOCAL_RESIDUAL_DICTIONARY_EXIT_RU.md`

Прочитаны CORPUS_CONTRACT_OPTIONS_RU §6, IDENTITY_ADMISSION_PARALLEL_RU,
REMAINING_DICTIONARY_AUDIT_RU, READ_TAILS_DICTIONARY_EXIT_RU и
P0_COMPLETENESS_SOURCE_MAP_RU; current source boundary и consumers проверены отдельно.
Historical reports/tests/gold/thresholds/freeze/config не изменены.

## Изменение и original repro

* `_source_evidence_terms`: удалены role suffix priority
  `Gate/Service/Repository/Controller/Manager/Policy/Adapter` и утверждение, что
  такие имена определяют mutation targets. Literal first-occurrence order,
  normalized deduplication, exact path precedence и cap **16** сохранены.
  Ни PascalCase whitelist, ни guessed semantic boost не добавлены.
* `_documentation_gap_evidence`: вместо repo map с `query or "architecture"`
  используется existing `collect_project_source_facts`, original query (None →
  empty string), `include_unmatched=True`, прежние **6 files / 800 tokens**.
  Это bounded structural inspection, не universal empty-question match.
  Default repo map и snippets с пустым question по-прежнему пусты.
* Оба retry emitters `create_project_docs_next_action` и ready branch
  `project_docs_structured_next_action` сохраняют supplied empty string вместо
  его потери; None остаётся отсутствующим question. EN/RU/whitespace query
  передаются без rewrite. Existing handoff truncation **512 characters** и
  **12 KiB** ceiling сохранены: длинный retry всё ещё ограничен и отражён в
  omitted_counts, не заявляется unbounded byte-for-byte retry.

Readonly baseline/current executable repro:

| Вход | Baseline | Current |
|---|---|---|
| `AlphaWidget BetaService GammaGate DeltaProvider` | `BetaService,GammaGate,AlphaWidget,DeltaProvider` | `AlphaWidget,BetaService,GammaGate,DeltaProvider` |
| Empty gap, `a.py` + `z_architecture.py` | только `z_architecture.py` | `a.py,z_architecture.py` в стабильном path order, без synthetic topic |

## Реальная consumer chain / authority

Default `get_docs_context` → project context part01:209–223 вызывает inspection.
Inspection project-docs part01:510–516,532–535 вызывает gap action **без query**;
отсутствие вопроса здесь не dormant path. Missing-doc query path part03:576–595
передаёт original query и возвращает `answer_available=False`.
Все эти callers сходятся в двух owned gap/structured helpers.

Conditional `_source_ground_documentation_gap` shared:92–136 уже использует
`include_unmatched=True` для source facts и graph, затем classified structural
evidence и conservative section evaluator. Это существующий контракт inspection,
не новое source authorization. В owned helper добавляются только paths категории
`source map`; они не удовлетворяют required claim categories и не устанавливают
`evidence_complete`. Downstream structural section completeness, когда реально
есть все требуемые факты, отдельно от NL answer support и edit authority.

Новый production-consumer test исполняет ProjectContextService, default queryless
inspection и conditional gap: original EN/RU/empty question retained;
`answer_available=False`, `support_decision.answer_supported=False`,
`answer_completeness.edit_ready=False`, creation требует confirmation.
Внешняя runtime frequency/final public delivery всех consumers UNKNOWN; test не
выдаётся за full installed MCP / terminal mutation audit.

## Сохранённые boundaries / representation

`source_boundary.py`, built-in exclusions и corpus membership не изменены.
Generated допускаются только при **`include_generated is True`**; None/False/1/
string, literal generated path и prose не дают consent. True не обходит roots,
excludes/gitignore, supported extension intersection, symlink/out-of-root guards,
file/byte/deadline/depth caps. Gap callers не открывают generated.

Python AST/import/declaration grammar, programming keywords, language-extension
registry, line offsets, request-local independent captures, snippet redaction,
source provenance shapes и existing budgets сохранены. AST comparison baseline/
current подтвердил идентичные function signatures обоих production modules.
DTO/subject/scope/version/lifecycle consumers не редактировались.
CRLF + Cyrillic source fixture проверяет исходные bytes/SHA-256, AST spans и
retained unmatched context; source files не переписываются. Не вводится новый
source-hash field и не заявляется authentication external provenance по snippet.
Existing first-item token-budget exception сохранён, не объявлен strict total cap.

## Offline normal-conftest runs

Команда каждого run: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1
.venv/bin/python -m pytest -p no:cacheprovider -q …`; normal diagnostic manifest
и outbound DNS/socket guard. Новый shard hash-bound, base manifest untouched.

| Непересекающиеся группы | Current | Baseline two-module in-memory overlay |
|---|---|---|
| Все `tests/test_dictionary_exit_*.py`, включая 71 new | **1688 PASS / 5 FAIL** | existing modules **1617 PASS / 5 FAIL** |
| source_map, project_state, request_source_facts, code_graph, code_graph_golden, target_security, content_trust, reference_hash_domains, review_source_capabilities, finalized_mcp_output_integrity, mcp_boundary (все tests/docs) | **128 PASS / 5 FAIL** | **128 PASS / 5 FAIL**, identical nodes |
| project_evidence_production, task19_project_docs_closure, project_docs_service, project_context_service, project_context_service_part02 (tests/docs) | **45 PASS / 31 FAIL** | **45 PASS / 31 FAIL**, identical nodes |

Итого current groups: **1861 PASS / 41 FAIL**, 1902 collected, без повторного
учёта отдельного new-only run **71 PASS**. Baseline overlay восстанавливает только
два owned modules через `git show` + in-memory exec до pytest; tree не меняется.
Это bounded comparison, не full baseline checkout/CI. Все red node sets совпали.
Старые assertions не исключены, не waived, не исправлены ради green.

Logs: `/tmp/opencode/local-residual-{dictionary-final,guards,consumers}.log`;
baseline `/tmp/opencode/local-residual-baseline-{dictionary,guards,consumers}.log`.
Один intermediate new-only run: 68 PASS / 3 FAIL из-за неправильного доступа
нового test к Unified fields на ProjectContextResult. Исправлен только новый test:
проверяет реальные nested support_decision/answer_completeness; затем 71 PASS.

### Exact red ledger

Dictionary (5):

* `test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
* `test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables`
* `test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance`
* `test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]`
* `test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]`

Source/technical (5, prefix `tests/docs/`):

* `test_source_map.py::test_source_map_includes_generated_path_for_explicit_artifact_question`
* `test_request_source_facts.py::test_navigation_requires_relationship_before_graph_expansion`
* `test_code_graph.py::test_build_project_code_graph_links_dart_relative_imports_and_references`
* `test_code_graph_golden.py::test_code_graph_golden_source_facts_cover_dart_python_and_skip_generated`
* `test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`

Old consumer nodes (31, prefix `tests/docs/`; module headings below):

`test_task19_project_docs_closure.py`:
* `test_completed_roadmap_is_searchable_only_for_explicit_history_intent`
* `test_operational_completed_and_browser_history_api_are_not_history_intent`

`test_project_context_service.py`:
* `test_auto_mode_inferred_dependency_cannot_hide_supported_local_docs_answer`
* `test_canonical_support_overrides_conflicting_legacy_recovery_fields`
* `test_dependency_inference_does_not_confuse_docs_mcp_surface_with_mcp_package`
* `test_dependency_inference_uses_token_boundaries_not_substrings`
* `test_generic_test_query_is_not_trusted`
* `test_missing_exact_source_files_require_local_search_even_without_docs_answer`
* `test_project_context_budget_overflow_keeps_answer_when_retained_trusted_evidence_is_complete`
* `test_project_context_budget_overflow_stays_fail_closed_when_required_evidence_is_dropped`
* `test_project_context_drops_placeholder_readme_from_context_pack`
* `test_project_context_service_returns_selected_project_and_dependency_sections`
* `test_russian_architecture_query_prefers_architecture_docs_over_feature_plans`
* `test_source_backed_completeness_marks_local_search_completed`
* `test_story_specific_project_context_missing_terms_is_partial_navigational`

`test_project_context_service_part02.py`:
* `test_broad_story_query_with_code_identifier_still_requires_source_story_terms`
* `test_context_pack_snippet_and_metrics_shape_are_stable`
* `test_metrics_warn_when_changelog_present_for_non_release_query`
* `test_project_context_code_graph_failure_is_non_fatal`
* `test_project_context_includes_code_graph_lane_for_project_source_queries`
* `test_project_context_prefers_authoritative_workflow_docs_over_noisy_dogfood_artifacts`
* `test_project_context_skips_repo_map_when_source_evidence_proves_single_target`
* `test_project_context_source_evidence_exposes_absent_terms_without_proof`
* `test_reranked_context_pack_why_selected_includes_intent_and_ranking_reason`
* `test_russian_story_requirement_chunks_drop_question_scaffolding_and_connectors`
* `test_story_specific_project_context_with_only_docs_matched_terms_requires_source_search`
* `test_story_specific_unquoted_error_toast_phrases_are_missing_terms`
* `test_trust_contract_uses_canonical_sources_and_exposes_source_evidence_context_sources`
* `test_unquoted_russian_story_query_uses_requirement_chunks_not_weak_words`
* `test_why_selected_mentions_project_structure_for_contributing`
* `test_why_selected_mentions_release_history_for_changelog`

## SHA-256 / remaining debt

| File | SHA-256 |
|---|---|
| `docmancer/docs/domain/source_map.py` | `d3e7aaaa2681f323462f36a605da6f582a90e7be7aec2e309f56d6cad9c5b217` |
| `docmancer/docs/domain/project_state.py` | `a230b69953a27434fb3f65146c026871b487e22f2c3b54035e6de99ef984e0aa` |
| `tests/test_dictionary_exit_local_residuals.py` | `0c89449089df46a3c0a9b46a361412f641199a94b8120189190d7e58d1b5b831` |
| `tests/diagnostic_labels.dictionary_exit_local_residuals.json` | `5aed64227ade3f17398f130be1207dbaa8db8f9ec4b7668ae53b67a4deaf19bc` |

Checkpoint own digest отдаётся parent отдельно (self-referential hash не включён).
Remaining OUTSIDE allocation: blocked corpus membership/caller propagation,
source-boundary built-in corpus defaults, `has_high_level_project_overview`
filename/reason policy, downstream structural classification and original
queryless inspection retry omission, other nonowned inventory residuals,
quality/retrieval completeness and preserved compatibility reds. No aliases,
new semantic fallback, corpus/generated widening или secondary allocations.
Parent final inventory/review handles remaining debt; scoped completion не full exit.
