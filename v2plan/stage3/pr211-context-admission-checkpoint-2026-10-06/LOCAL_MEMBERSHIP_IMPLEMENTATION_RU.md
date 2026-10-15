# Local membership A — bounded implementation / handoff

2026-10-07. Только `/tmp/opencode/docatlas-resumed-local-ee156cba`.
Baseline `ee156cba4cc6dd4bf51c0e2c8adf44907aac9633`.
**Finite local read slice implemented; full EXIT / integration acceptance NOT DONE.**
Нужен independent parent review до extraction/integration. Нет commit/push/agents,
network/provider calls, установки dependencies, rebuild/reinstall или обращения к
настоящему runtime index. Старые tests/gold/floors/diagnostic manifest не менялись.
Предсуществующий untracked `.venv` не extraction artifact и не изменён.

Прочитаны committed FINAL_INTEGRATED_EXIT_AUDIT_RU,
FINAL_DICTIONARY_EXIT_INVENTORY_RU и LOCAL_RESIDUAL_DICTIONARY_EXIT_RU.
DocMCP не использовался: source/caller inspection fallback.

## 1. Exact owner decision / current counts

`docatlas.project-docs.yaml` содержит ровно 10 literal documents:

| Path | Role |
| --- | --- |
| README.md | overview |
| CONTRIBUTING.md | development |
| docs/INDEX.md | overview |
| docs/PROJECT_MAP.md | project_architecture |
| wiki/Architecture.md | project_architecture |
| docs/adr/0003-context-first-project-reads.md | development |
| docs/mcp-docs-server.md | api_contract |
| docs/testing.md | runbook |
| docs/project-docs-mcp-workflow.md | runbook |
| wiki/Supported-Sources.md | api_contract |

Все scope=project, module_path=null, status=active. Description/authority/impact
каждой строки сверены с baseline catalog и сохранены точно. Routing metadata не
становится execution/edit permission. `code_files: []` → runtime tuple `()`.
Новый actual reader: **10 candidates, 0 modules, 0 code members**, whole-file
SHA-256 и catalog metadata SHA-256 retained. No roots/links/module expansion.

Baseline YAML через `git show HEAD:docatlas.project-docs.yaml`: **38 explicit rows,
3 roots**. Исторические 96 root-derived / 134 total / accepted loss 124 не
пересчитаны новым сканированием и не выдаются за new-run counts. Исторический
availability loss принят owner; настоящие indexed rows не проверялись/не менялись.

## 2. Actual owned chains

* Catalog rejects nonliteral/normalized aliases, duplicates, invalid/symlink/outside
  members and nonempty roots. Code files are an optional bounded literal set,
  default empty; malformed declarations fail the whole catalog.
* ProjectMetadataReader.read/discover_docs reads only declared documents. Removed
  root filename/directory/module/index-link discovery and dependency/.fvmrc/package
  metadata reads. Compatibility ROOT_DOC_FILES/DOC_DIRECTORIES labels remain for
  outside impact imports; the reader does not use them as selectors.
* SourceBoundary iterator preflights the finite code set and never walks directories.
  Empty/absent/invalid membership → no code read. Existing source-root restrictions,
  root resolution, every symlink component, gitignore/excludes, supported-extension
  intersection, generated **literal boolean True** consent, file/count/byte/time/depth
  budgets remain. Documentation extension checks use documentation formats, not the
  repo's `.py` source-only include_extensions. Symlinked gitignore fails closed.
* source_map source evidence returns empty for a no-scan set, not absent_in_source.
  Graph reports unresolved_membership / analysis_complete=False and zero nodes;
  package imports no longer read pubspec identity or unselected import targets.
* Patch constraints uses actual finite metadata candidates, no glob/name selector,
  repo artifact enumeration, owner scan, changed-parent expansion or manifest reads.
  Advisory changed-path/generated restrictions are retained, not permission.
* Patch-plan part02 uses finite code paths; no-code returns unresolved with no missing
  symbol certification. Dependency metadata/source and rejected-source scans are not
  dispatched by this caller. Changed_files does not add a read member.
* ProjectContextService reads current finite metadata and checks path + content hash
  + catalog hash before admitting project-doc results. DTO source hashes, version,
  line/char spans and downstream trust/qualification/budget guards are not rewritten.
* Ranking skips guessed path lanes only for caller-supplied actual finite member
  paths; unbound compatibility restrictions remain. Review prefix demotion is skipped
  only after local_membership mechanically rechecks actual selected path, file hash
  and catalog hash. A local_read_binding is read provenance, **not authentication,
  policy authority, capability, consent token, broker or action authorization**.
* Inspection no longer enumerates root files or probes guessed manifest/lock names.
  State guidance no longer calls an unselected indexed row obsolete or recommends
  pruning without separate review/grant. Mutation/cancellation code was not edited.

## 3. Offline execution / honest red ledger

Normal conftest, existing DNS/socket guard and diagnostic inventory used:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q
tests/test_dictionary_exit_local_membership.py
tests/test_dictionary_exit_local_residuals.py
tests/docs/test_project_metadata_reader.py
tests/docs/test_project_docs_catalog.py
tests/docs/test_source_map.py
tests/docs/test_project_state.py
tests/docs/test_project_doc_ranking.py
```

Final bounded run **119 passed / 89 failed**, 1.36s. New-only **31 passed**, 0.56s.
Separate new-only run is not added again to the combined count. New shard executes
actual ProjectDocsService.inspect_project_docs and PatchConstraintsService callers
with ten documents and forbidden Path.glob/rglob/iterdir; tests also cover invalid
literals, empty/absent code, symlink-outside, index link non-expansion, no dependency
metadata reads, finite code/import boundaries, source line spans, hashes, exclusions,
generated consent and no ranking authority field. Temporary legacy test fixtures may
use local test stores; no installed/current index was rebuilt or ingested.

Initial new-only collection stopped on missing diagnostic shard (0 tests). Added only
the new hash-bound shard; normal conftest rerun passed. Python 3.13.12 / pytest 9.0.3
were available in the shared preexisting venv; no installation or dependency blocker.
`git diff --check` passed.

Logs (local coordinator can read; not repository artifacts):
* `/tmp/opencode/local-membership-bounded-ee156cba.log` SHA256
  `0022b3784ba83629d3f51f5c6bb58a044ba1fe46a4f0b400dc68b5ccbd69bddf`
* `/tmp/opencode/local-membership-new-ee156cba.log` SHA256
  `dcfc889e3ada7858cac9e7f3164b52d0ded0ff360708074cc655cc59fe3669e1`

All 89 reds are preserved below. No baseline rerun was performed, so none are
blanket-labelled baseline failures. Metadata/autodiscovery/absence expectations
conflict with the newly selected no-scan contract; ranking/NL gold expectations also
remain red. This explains review areas, not a waiver or security/quality PASS.

```text
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Gate]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Service]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Repository]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Controller]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Manager]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Policy]
tests/test_dictionary_exit_local_residuals.py::test_real_snippet_budget_does_not_prefer_role_names[Adapter]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[None]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[   ]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[Explain UnseenQuux]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[\u041e\u0431\u044a\u044f\u0441\u043d\u0438 \u041d\u0435\u0432\u0438\u0434\u0438\u043c\u044b\u0439\u041a\u0432\u0430\u0440\u043a]
tests/test_dictionary_exit_local_residuals.py::test_gap_passes_original_query_and_explicit_unmatched_contract[  AlphaWidget?\n\u041d\u0435 \u043c\u0435\u043d\u044f\u0439 BetaService!  ]
tests/test_dictionary_exit_local_residuals.py::test_empty_or_unmatched_gap_has_context_without_synthetic_topic[None]
tests/test_dictionary_exit_local_residuals.py::test_empty_or_unmatched_gap_has_context_without_synthetic_topic[]
tests/test_dictionary_exit_local_residuals.py::test_empty_or_unmatched_gap_has_context_without_synthetic_topic[UnseenQuux]
tests/test_dictionary_exit_local_residuals.py::test_empty_or_unmatched_gap_has_context_without_synthetic_topic[\u041d\u0435\u0432\u0438\u0434\u0438\u043c\u044b\u0439\u041a\u0432\u0430\u0440\u043a]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[facts-None]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[facts-False]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[facts-1]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[facts-true]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[facts-True]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[snippets-None]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[snippets-False]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[snippets-1]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[snippets-true]
tests/test_dictionary_exit_local_residuals.py::test_generated_requires_boolean_true_even_for_explicit_path[snippets-True]
tests/test_dictionary_exit_local_residuals.py::test_generated_consent_never_bypasses_roots_excludes_gitignore_or_symlinks
tests/test_dictionary_exit_local_residuals.py::test_gap_honors_config_and_retains_six_file_deterministic_cap
tests/test_dictionary_exit_local_residuals.py::test_ast_spans_original_bytes_and_new_unmatched_context_survive
tests/test_dictionary_exit_local_residuals.py::test_supported_extension_intersection_and_secret_scrubbing_remain
tests/test_dictionary_exit_local_residuals.py::test_default_inspection_conditional_gap_remains_context_only[]
tests/test_dictionary_exit_local_residuals.py::test_default_inspection_conditional_gap_remains_context_only[Explain UnseenQuux]
tests/test_dictionary_exit_local_residuals.py::test_default_inspection_conditional_gap_remains_context_only[\u041e\u0431\u044a\u044f\u0441\u043d\u0438 \u041d\u0435\u0432\u0438\u0434\u0438\u043c\u044b\u0439\u041a\u0432\u0430\u0440\u043a]
tests/docs/test_project_metadata_reader.py::test_cargo_project_output_matches_golden_fixture
tests/docs/test_project_metadata_reader.py::test_pub_project_output_matches_golden_fixture
tests/docs/test_project_metadata_reader.py::test_python_project_binds_direct_dependencies_to_uv_lock_versions
tests/docs/test_project_metadata_reader.py::test_python_project_uses_poetry_lock_when_uv_lock_is_absent
tests/docs/test_project_metadata_reader.py::test_python_project_uses_pdm_lock_when_it_is_the_available_lock
tests/docs/test_project_metadata_reader.py::test_python_manifest_pin_is_not_claimed_as_resolved_without_lock
tests/docs/test_project_metadata_reader.py::test_python_project_reads_pipfile_lock_exact_versions
tests/docs/test_project_metadata_reader.py::test_poetry_path_and_git_dependencies_are_never_registry_version_bindings
tests/docs/test_project_metadata_reader.py::test_python_git_lock_entry_cannot_bind_registry_documentation
tests/docs/test_project_metadata_reader.py::test_flutter_project_reads_pubspec_without_requiring_fvmrc_or_lock
tests/docs/test_project_metadata_reader.py::test_node_project_reads_direct_exact_versions_from_package_lock
tests/docs/test_project_metadata_reader.py::test_node_project_prefers_package_manager_pnpm_lock_and_normalizes_peer_suffix
tests/docs/test_project_metadata_reader.py::test_node_project_reads_yarn_v1_lock_for_scoped_and_unscoped_packages
tests/docs/test_project_metadata_reader.py::test_node_project_reads_bun_json_lock_for_direct_dependencies
tests/docs/test_project_metadata_reader.py::test_node_project_reads_realistic_bun_text_lock_array
tests/docs/test_project_metadata_reader.py::test_node_exact_version_is_available_to_project_library_resolution
tests/docs/test_project_metadata_reader.py::test_python_lock_version_is_available_to_project_library_resolution
tests/docs/test_project_metadata_reader.py::test_pub_git_dependency_is_not_bound_to_pubdev
tests/docs/test_project_metadata_reader.py::test_pub_custom_hosted_dependency_is_not_bound_to_pubdev
tests/docs/test_project_metadata_reader.py::test_project_metadata_exposes_shared_dart_package_source_roots
tests/docs/test_project_metadata_reader.py::test_node_manifest_ranges_are_never_reported_as_exact_without_lockfile
tests/docs/test_project_metadata_reader.py::test_node_full_semver_manifest_is_exact_without_lockfile
tests/docs/test_project_docs_catalog.py::test_absent_catalog_keeps_cold_start_discovery
tests/docs/test_project_docs_catalog.py::test_catalog_normalizes_paths_before_duplicate_detection
tests/docs/test_source_map.py::test_build_project_source_evidence_includes_match_type_and_confidence
tests/docs/test_source_map.py::test_named_gate_source_evidence_exposes_declaration_metadata
tests/docs/test_source_map.py::test_build_project_source_evidence_finds_camel_case_from_nl
tests/docs/test_source_map.py::test_source_evidence_skips_generated_plugin_registrant
tests/docs/test_source_map.py::test_project_repo_map_extracts_static_source_facts_and_honors_budget
tests/docs/test_source_map.py::test_collect_project_source_facts_returns_python_and_dart_facts
tests/docs/test_source_map.py::test_collect_project_source_facts_skips_generated_files
tests/docs/test_source_map.py::test_source_boundary_loads_project_manifest_and_limits_roots
tests/docs/test_source_map.py::test_source_boundary_applies_excludes_and_gitignore
tests/docs/test_source_map.py::test_source_boundary_gitignore_anchored_negation_only_reincludes_root_path
tests/docs/test_source_map.py::test_source_boundary_distinguishes_anchored_and_nonanchored_directories
tests/docs/test_source_map.py::test_source_boundary_preserves_legacy_positional_source_roots
tests/docs/test_source_map.py::test_source_boundary_generated_paths_require_explicit_opt_in
tests/docs/test_source_map.py::test_source_map_includes_generated_path_for_explicit_artifact_question
tests/docs/test_source_map.py::test_source_boundary_enforces_file_byte_depth_and_deadline_budgets
tests/docs/test_source_map.py::test_collect_project_source_facts_selection_score_favors_exact_question_term
tests/docs/test_source_map.py::test_source_facts_diagnostics_contains_counts
tests/docs/test_source_map.py::test_collect_project_source_facts_honors_token_budget
tests/docs/test_project_state.py::test_has_high_level_project_overview_recognizes_architecture_and_readme
tests/docs/test_project_state.py::test_manifest_only_evidence_is_partial_and_not_complete
tests/docs/test_project_doc_ranking.py::test_changelog_boosted_for_release_question
tests/docs/test_project_doc_ranking.py::test_source_lanes_fail_closed_for_operational_questions
tests/docs/test_project_doc_ranking.py::test_architecture_project_structure_includes_contributing_when_available
tests/docs/test_project_doc_ranking.py::test_docs_mcp_query_demotes_packs
tests/docs/test_project_doc_ranking.py::test_packs_mcp_query_boosts_packs
tests/docs/test_project_doc_ranking.py::test_broad_query_backfill_preserves_source_diversity_when_enough_sources_exist
tests/docs/test_project_doc_ranking.py::test_explicit_dogfood_query_can_promote_artifact_source
tests/docs/test_project_doc_ranking.py::test_exact_filename_outranks_generic_configuration_boost_without_query_trace
tests/docs/test_project_doc_ranking.py::test_is_specific_docs_mcp_source_matches_docs_server_py
tests/docs/test_project_doc_ranking.py::test_docs_mcp_weight_boost_docs_server_py
tests/docs/test_project_doc_ranking.py::test_mcp_disambiguation_boost_interfaces_mcp
```

## 4. Outside allowlist / blockers for broader closure

**Do not integrate as full authorization closure.** Files below were inspected,
not edited. Parent must allocate/review any necessary follow-up:

1. `docmancer/docs/application/_project_docs_service_part02.py:373–401` direct
   sync lane deduplicates/deletes stale and unselected rows. It has no local
   consent parameter at that point. Existing public prepare/inspection guards are
   not a proof for every direct SDK caller. Narrow catalog does **not** grant
   pruning 124 historical candidates. No sync method was invoked here against
   the current index. Coordinator review required before any runtime use.
2. `docmancer/docs/_patch_plan_context_part01.py` retains independently callable
   discovery/dependency/source helpers with glob/rglob and metadata reads. Owned
   part02 caller no longer dispatches those scanning helpers, but external direct
   callers are not certified. Allocate part01 separately if callable closure is
   required; no unauthorized edit made here.
3. `docmancer/docs/_impact_shared.py` and impact shards still consume compatibility
   filename/directory labels for impact classification. This is not current read
   discovery, but outside caller-wide dictionary-free closure remains UNKNOWN.
4. B-owned trust/action/evidence/projection consumers were not edited. This slice
   does not remove their negative security guards or certify model-visible
   execution readiness. Installed index/SDK/pack/source-continuation behavior and
   public MCP transport were not independently exercised.

## 5. Exact extraction files / SHA-256 pins

**20 files total:** 17 production/config (including one new mechanical helper),
one new test, one new diagnostic shard, and this report. Only the following 19
payload files plus this checkpoint should be considered for parent extraction.
Report cannot contain its own final hash; parent can pin it independently.

```text
4e51d2baee5be889a9828d5f5527e1f937c59c3ba67cba056e59b4e9cf6a86e1 docatlas.project-docs.yaml
17f9c73cea4f2372d1c18031e27a027f9f0503731a724c802baf7af2c3cafd3a docmancer/docs/_patch_plan_context_part02.py
239a75b8a6a26c0c7fb1dff3c28d8e00d7506b511bec151c566944fe403fed03 docmancer/docs/application/_patch_constraints_service_part01.py
1c38652b4cf41af635e77ae763dcf4c1c8daf85cdfddbf7edf81f94726bc30df docmancer/docs/application/_patch_constraints_service_part02.py
3aa217e07f66ff3bf5aee7c4fdc7c720083a6875525006f7f2a94654ea2766d5 docmancer/docs/application/_patch_review_service_part02.py
cefa020ca9c80e808ccaef4d8c1e735cae2e24f6aca86338208d3ac842680a81 docmancer/docs/application/_project_context_service_part01.py
9b554a0834e0e9e12b92c1714d6cf50ea0170b91571d88b5eb7ce43c7b7a9770 docmancer/docs/application/_project_docs_service_part01.py
a87fa4eeca4c695cedc2942ad5de30890520267209fe0f35e0f45a996916f992 docmancer/docs/application/project_docs_state.py
0c7d08e7c2e319955e5cc692cd04af7a98c5070744db2d59bca556c129b48e40 docmancer/docs/domain/_code_graph_part01.py
f4c8fdd4c4adef960dffa6bc4ca4a27cb405e63833e0f6913f981ad449a3ecbf docmancer/docs/domain/project_doc_ranking.py
26ade5123720fb61ceb8976fc4c19641423a60d6d24ca3c1fb4c9f15a6d77021 docmancer/docs/domain/project_state.py
1fcfcc4805bd1538dba9899d78d55cc7c97393432f0e90beff24737d78a8ce61 docmancer/docs/domain/source_boundary.py
46381d0409ba0c9cc0a77911379241e682fc8b486d0861ba744f79ff4ee15f20 docmancer/docs/domain/source_map.py
fc990a47230f2f43d93b65f95940177c806b94556f09344712fdf4f1f67753da docmancer/docs/local_membership.py
d622d554a284a3bbf832d523e009dff1fe8bf4d49c13e81299697de3da343fc6 docmancer/docs/models.py
c0f5eb9a3e72342d86f2f824b1e65e65b5aba0cce7c2cbf0fa2974f5db23becf docmancer/docs/project.py
25236b585a48d17d8461d49d0cd6a7ecc3a913da494e3aecb35e2bf50ff70637 docmancer/docs/project_docs_catalog.py
71deee2933d8ecbecef648feddb4d1bd9a8a7077bf704f85a7bc23d5ec1c87e3 tests/diagnostic_labels.dictionary_exit_local_membership.json
323bb27d4a3574e69beae91c936bbcb1682e56a2f94d55f7abfe425abaec4e43 tests/test_dictionary_exit_local_membership.py
```
