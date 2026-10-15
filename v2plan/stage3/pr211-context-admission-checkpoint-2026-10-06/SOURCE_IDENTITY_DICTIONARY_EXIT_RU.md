# Source identity dictionary exit — bounded allocation A

2026-10-07. **Implemented / scoped tests PASS; integration NOT GREEN, full exit NOT DONE.**

Workdir: `/tmp/opencode/docatlas-next-identity-9488cb66`.
Verified HEAD: `9488cb66ab989f6f65bafbfae7d1eb3f844ce0a3`.
Primary не редактировался. Network/commit/push/agents не запускались.
Прочитаны NEXT_PARALLEL_HANDOFF, DISCOVERY_LEGACY_EXIT и
DISCOVERY_LITERAL_DICTIONARY_EXIT. Предсуществующие local CONTINUE_HERE,
NEXT_PARALLEL_HANDOFF и `.venv` оставлены как были и не входят в extraction.

## Owned files для parent extraction

Production (ровно allowlist):
- `docmancer/docs/curated_sources.py`
- `docmancer/docs/dart_official_docs.py`
- `docmancer/docs/application/_library_docs_service_part01.py`

Tests/report:
- `tests/test_dictionary_exit_source_identity.py`
- `tests/diagnostic_labels.dictionary_exit_source_identity.json`
- `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/SOURCE_IDENTITY_DICTIONARY_EXIT_RU.md`

Diff production доступен обычным `git diff 9488cb66 -- <три owned paths>`;
новые tests/shard/report — untracked files этого workdir. Parent извлекает
только шесть перечисленных files; commits и отдельный patch artifact не созданы.
JSON registries, filtering/GitHub/discovery/config/prompts, old tests/gold/floors,
historical/frozen manifests не изменены. Corpus не расширен.

## Решения и реальные execution edges

1. `_ecosystem_aliases` сохраняет ABI, но возвращает только trim/lower literal ID.
   javascript/typescript/node не становятся npm; flutter/pub не становятся dart.
   Реальный caller `curated_source_for` больше не открывает source другой ecosystem.
   npm/pub остаются настоящими protocol identities: explicit docs_url и registry
   resolution сохраняют их; никакого package-manager→framework inference нет.
2. Из `resolve_library` удалён whole knowledge-based guide auto-registration lane:
   non-pub.dev substring selection и riverpod.dev/bloclibrary.dev host whitelist.
   Automatic roots теперь выбирает существующая explicit curated source policy,
   а не знание host. Registered sources и explicit input всё ещё имеют приоритет.
   Для riverpod/latest это прежний curated root, только прежний host, no advisory
   seeds, прежний curated max_pages=24 (вместо guide lane 100 + second host).
   Exact version без explicit source_type=api не получает unversioned root.
   Source_type default остаётся существующим curated `api`; web→api compatibility
   change виден в старом test_library_discovery_candidates, не скрыт.
3. Literal Dart + explicit source_type=api сохраняет protocol API template,
   exact snapshot/version fields, allowed_domains, empty seed list и max_pages=100.
   Пустой unresolved locator не проходит upsert. Framework/manager IDs не выбирают
   эту lane. Deterministic literal sorted URL ranking и caps resolver сохранены.
4. `firebase_firestore` key оставлен как explicit unresolved identity:
   official_guides=(), pubdev_api=None, package_page=None. Contract equivalence с
   cloud_firestore не найден в allocated code; mapping удалён fail-closed.
   Resolver возвращает urls=[], pubdev_docs_url="", strategy=unresolved и не
   придумывает replacement URL даже для include_pubdev=True. DTO string field
   сохранён, no exception/type migration. Medium confidence остаётся legacy
   advisory field, не source/network authority. Real cloud_firestore API intact.
   Explicit caller locator/уже registered source не переписывается этим cleanup.
5. `_with_dart_diagnostics` больше не считает любой non-pub.dev URL official:
   used_official_docs требует exact registered locator membership и availability.
   Это diagnostic equality, НЕ authentication content/library/snapshot provenance.

Actual callers проверены public LibraryDocsService.resolve_library→owned part01,
registry get/upsert, direct resolver/seeds и actual diagnostic/chunk/recovery helpers.
Существующий facade override `_library_resolve_library_impl` оставлен untouched:
наличие direct helper не доказывает default execution каждого external caller.

## ABI и barriers

AST comparison с git-show baseline: function arguments/return annotations всех
трёх files IDENTICAL; class annotated DTO fields/defaults IDENTICAL.
В part01 изменены только resolve_library и _with_dart_diagnostics. Chunk rejection,
library/project/ecosystem/version/source-type/docset-root guards, recovery consent,
registry conflict/ambiguity/lifecycle handling byte/AST untouched. New tests проверяют
actual negative identity guards, project leak, path/host mismatch и confirmation.
Curated version locks, exact/unversioned barrier, verified-seed-only boundary,
path/host validation, budget и deep-copy source_manifest сохранены.
Extraction original bytes/IDs/hashes/spans и immutable provenance modules не edited;
network/byte/consent policy не relaxed. Local equality не заменяет external source
membership/hash/window authentication или terminal mutation authorization.

Baseline source SHA-256 всех трёх owned production files совпал с historical
dictionary-exit-discovery-legacy-source-manifest. Этот manifest не переписан.

## Offline checks — normal conftest, no waivers

Во всех runs prefix:
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q`
Mixed/combined дополнительно `--tb=short`. No --noconftest, no threshold/gold edits.
New module: **50 behavioral instances / 16 base nodes**.
Normal diagnostic hash: `fd4ea230e0794aca1c0b3dfdfbcbe2a0151cd07430458504a9daa04474cebf7e`.

| Selection | Actual result |
|---|---|
| tests/test_dictionary_exit_source_identity.py | 50 PASS |
| New + six technical modules below | 95 PASS / 1 FAIL, 1 existing multipart warning |
| Twelve old mixed modules below | 189 PASS / 32 FAIL |
| tests/test_dictionary_exit_*.py | 1477 PASS / 4 FAIL |
| git diff --check | PASS |

Technical modules: tests/docs/test_target_security.py, test_content_trust.py,
test_reference_hash_domains.py, test_review_source_capabilities.py,
test_finalized_mcp_output_integrity.py, test_mcp_boundary.py (все под tests/docs).
Technical red:
`tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`
— unchanged advisory answer_available=True expectation, уже recorded baseline debt.

Old mixed modules: tests/test_dartdoc_pub_ingestion.py, test_dart_service_integration.py,
test_library_discovery_candidates.py, test_preindex_coverage.py, test_web_fetcher.py,
test_crawl4ai_fetcher.py, test_filtering.py, test_fetcher_github.py,
test_docs_fetch_transport.py, test_docs_fetch_policy.py; дополнительно
tests/docs/test_dartdoc_discovery.py и tests/docs/test_curated_sources.py.

### Все 32 actual old mixed red nodes

```text
tests/test_dartdoc_pub_ingestion.py::TestDartOfficialDocsResolver::test_normalize_package_name
tests/test_dartdoc_pub_ingestion.py::TestDartOfficialDocsResolver::test_riverpod_has_official_docs
tests/test_dartdoc_pub_ingestion.py::TestDartOfficialDocsResolver::test_get_seed_urls_returns_list
tests/test_dartdoc_pub_ingestion.py::TestDartOfficialDocsResolver::test_get_seed_urls_respects_max_urls
tests/test_dartdoc_pub_ingestion.py::TestOfficialDocsFallback::test_riverpod_official_docs_preferred
tests/test_dartdoc_pub_ingestion.py::TestEndToEndDartIngestion::test_flutter_bloc_preindex_query_end_to_end_mocked
tests/test_dartdoc_pub_ingestion.py::TestEndToEndDartIngestion::test_riverpod_preindex_query_end_to_end_mocked
tests/test_dart_service_integration.py::test_riverpod_auto_uses_official_docs
tests/test_dart_service_integration.py::test_flutter_bloc_auto_uses_official_docs
tests/test_dart_service_integration.py::test_ecosystem_pub_also_works
tests/test_dart_service_integration.py::test_dart_aliases_share_one_registry_identity
tests/test_dart_service_integration.py::test_refresh_receives_auto_registered_seed_urls
tests/test_dart_service_integration.py::test_refresh_metadata_overwrites_fetcher_identity_but_preserves_docset_root
tests/test_dart_service_integration.py::test_dart_explicit_api_source_type_registers_pubdev_api_docset
tests/test_dart_service_integration.py::test_dart_api_concrete_version_is_exact_snapshot
tests/test_dart_service_integration.py::test_dart_api_version_string_does_not_override_latest_url_semantics
tests/test_dart_service_integration.py::test_riverpod_refresh_ingests_and_queries_official_and_pubdev_roots
tests/test_dart_service_integration.py::test_flutter_bloc_refresh_ingests_and_queries_official_and_pubdev_roots
tests/test_library_discovery_candidates.py::test_known_riverpod_auto_registers_without_discovery_candidates
tests/test_filtering.py::TestInferDocsetRoot::test_docs_subdomain_collapses_to_host
tests/test_filtering.py::TestInferDocsetRoot::test_docs_path_collapses_to_docs_root
tests/test_filtering.py::TestInferDocsetRoot::test_llms_full_strips_suffix
tests/test_filtering.py::TestInferScopePath::test_deep_path_with_root_hint_widens
tests/test_filtering.py::TestInferScopePath::test_deeper_path_with_root_hint
tests/test_filtering.py::TestInferScopePath::test_reference_root_hint
tests/test_filtering.py::TestInferScopePath::test_no_root_hint_strips_leaf
tests/test_filtering.py::TestInferScopePath::test_api_root_hint
tests/test_filtering.py::TestIsDocsUrl::test_deep_base_url_widens_scope
tests/docs/test_curated_sources.py::test_curated_manifest_covers_the_parity_libraries_with_bounded_official_sources
tests/docs/test_curated_sources.py::test_exact_curated_source_renders_the_requested_version[resolution]
tests/docs/test_curated_sources.py::test_exact_curated_source_renders_the_requested_version[refresh-dispatch]
tests/docs/test_curated_sources.py::test_flutter_bloc_exact_target_is_allowed
```

Disposition: literal package invalid aliases/guide-first/topic-seed expectations,
framework/manager cross-ecosystem identity expectations, knowledge-guide multi-root
registration и curated source_type compatibility. Девять filtering root/sibling
inference reds уже recorded в предыдущем checkpoint; filtering не edited.
Это failure descriptions, НЕ waivers или blanket baseline attribution.
Clean full baseline/control overlay не запускался; counts — именно этот isolated
snapshot, не объединённые изменения parent/другого worker и не full CI.

### Все 4 actual existing dictionary-suite red nodes

```text
tests/test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables
tests/test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance
tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]
tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]
```

Первый требует format для каждого mapping, включая теперь unresolved identity.
Второй требует automatic unversioned guide для exact version; последние два
требуют старого curated cross-ecosystem fallback. Старые тесты/hash shards не
переписаны; parent получает conflicts как OPEN integration debt.

Logs вне Git: /tmp/opencode/source-identity-new-technical.txt,
/tmp/opencode/source-identity-old-mixed.txt,
/tmp/opencode/source-identity-dictionary-combined.txt. Counts/modules/red nodes
сохранены здесь, logs не единственная provenance.

## Current source pins (SHA-256)

| Path | SHA-256 |
|---|---|
| docmancer/docs/curated_sources.py | b24075dd2c4d8e9c0c4cd431551c9db3351cd672d5debfc1ba7e91b4b68ae0c9 |
| docmancer/docs/dart_official_docs.py | da2d7b8847757849b9f47aea449d84563b46316d49bf4e430373da7667d329dc |
| docmancer/docs/application/_library_docs_service_part01.py | 0ba8ded59dd99fa67b21070dd25877e4494f7c7f2bb65c46bbc5140bff468b8b |
| tests/test_dictionary_exit_source_identity.py | 1a2badf17a6573837ba4d366882712b0192420ba6cba4d3973f289859653a30e |
| tests/diagnostic_labels.dictionary_exit_source_identity.json | 70d3000b294354e041bb26bcdb558d25fdef8b02a008999f579c90e97d4ae0fc |

## OPEN — external allocation / parent integration

- Four unchanged discovery-suite conflicts and old mixed compatibility reds;
  no permission to alter existing tests/gold/frozen hashes/floors.
- Distinct pub protocol lane still exists in library_source_discovery,
  dependency_project_prefetch/pub_project/ecosystem_adapters. Their interaction
  with literal curated dart entries needs owner decision, not restored collapse.
- External callers of pubdev_docs_url must respect empty unresolved string;
  default owned API caller tested. External SDK consumers UNKNOWN.
- Previously populated registries/explicit caller locators remain caller/registry
  policy; no database migration/authentication/rewrite in this allocation.
- Corpus locale/topic/GitHub exclusions remain BLOCKED pending bounded membership
  authorization. Filtering/GitHub/discovery and JSON policies unchanged.
- Source-map suffix/topic fallback, nonowned refresh diagnostic host heuristic,
  common projection/admission/selector consumers and full transport provenance
  certification outside allocation. Do not infer completion from direct calls.
- Existing self-host quality FAIL remains FAIL; actual indexed MCP/stdio/full CI,
  rebuilt package and independent review are parent gates, not executed here.

Bounded allocation закрыт без secondary slices; full dictionary exit не заявлен.
