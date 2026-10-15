# Finite corpus / dictionary exit — scoped implementation

2026-10-07. Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
Worktree `/tmp/opencode/docatlas-final-finite-corpus-42c72bd6`.
**PARTIAL; independent parent review required; FULL EXIT / quality NOT DONE.**
Primary не открывался для записи. Нет agents, commit/push, live network/crawl/index.
Тесты offline, normal conftest; HTTP/DNS и indexing в новых caller tests mocked.
Предсуществующий `.venv` symlink не изменён и не входит в extraction.
Frozen tests/gold/threshold224/ownership registries/historic reports untouched.

## Контракт и выполненные изменения

- Web fetch требует конечный `exact_urls`; legacy `seed_urls` — только concrete
  whole-document members, не subtree. Direct Web/factory без members fail closed.
  Agent `add`/`fetch_documents` считает явно переданный URL и seeds конкретными
  members; явно пустой `exact_urls=[]` не заменяется URL или seeds.
- Selection snapshot copied; unknown/empty/malformed sets и over-budget sets не
  truncate-ятся и не запускают HTTP. Вся selection проходит transport ceiling и
  DNS/private preflight до первого HTTP. Host/path ceilings не membership.
- Query spelling/order/`source,ref,from,utm_*` и trailing slash сохраняются.
  Fragment selection не удостоверяет whole document и отвергается exact contract.
  URL normalization для других consumers удаляет fragment, но больше не strips
  queries/trailing slash. Scheme/authority case + empty root path — mechanical.
- `discover_urls` возвращает только selected members без client calls. Forced
  strategy, platform, query, landing/nav/sitemap/Dartdoc/llms links и preloaded
  aggregate body не пополняют set. Protocol helpers/tables остаются, но public
  orchestrator их не dispatch-ит. Seed collision/early return больше не вытесняет
  выбранный URL. Web ранние direct/GH/Dartdoc/aggregate обходы removed.
- Whole llms document допустим только как отдельно selected exact URL; никаких
  auto llms probes, splitting, inferred package pages или aggregate expansion.
- `DocsFetchPolicy.exact_urls` enforced перед каждым dispatch/redirect, отдельно
  от existing host/path/DNS/private checks. Unselected canonical отвергается до
  выдачи Document; selected redirect не даёт private/DNS/ceiling bypass.
- Locale/topic/print/settings web veto и GitHub locale/legal/legacy/default-root
  dictionaries removed **за finite guard**. Account/auth and binary-format
  technical guards остаются; binary suffix проверяется на path, не на query.
  Explicit GitHub folder/exclusion/glob syntax остаётся как pure utility, НЕ fetch
  authorization; implicit root-file extras removed. Context7 не fetch-ится и не
  добавляет branch/previousVersions/ref membership.
- Direct GitHub lane только approved normalized immutable source manifest;
  ordinary repo/tree/blob/raw URLs без hashed manifest fail closed. Legacy raw
  clients/tree/default-branch/README fallback removed. Existing complete/digest,
  commit/blob/size/SHA256/page/byte/deadline/cancellation/provenance checks retained;
  raw redirects дополнительно exact-bound, actual redirect записан в provenance.
- Crawl4AI direct lane — deprecated secure finite static HTTP adapter. Raw
  browser/legacy discovery fallback removed, optional browser dependency больше
  не нужна этому adapter. Web browser fallback по-прежнему fail closed.
- Arbitrary injected Agent `fetcher=` отвергается: невозможно доказать enforcement
  до его сетевого вызова. Это intentional compatibility narrowing, не permissive
  fallback и не признание arbitrary fetched sources trusted.
- Prefetch propagates allowed_domains/path_prefixes and singleton exact operation
  consistently with refresh. Root/seeds каждый concrete URL, не discovery root.
  Prefetch больше не вызывает package или directory discovery. Unresolved GitHub
  declarations требуют resolved manifest. Refresh revalidates explicit target
  через target_urls, НЕ trusts resolved/discovered cache и НЕ uses record_urls
  fallback после validation error. Existing network consent flags не повышались.

### Robots/control contract — существенное ограничение

`robots_urls` — отдельно явно selected protocol-control URLs (только `/robots.txt`
без query); не document-membership и не автоматическая probe authority. Default
respect_robots остаётся True. Отсутствующий control member или ceiling, не
разрешающий его path/host, даёт **no HTTP**, а не silent skip/consent promotion.
Prefetch/refresh берут control только из уже выбранных target URLs/seeds;
не synthesise-ят разрешение. Robots client exact-bound отдельно от document client;
robots Sitemap directives не используются для discovery. Explicit robots seed
может также быть выбранным whole document; это уже declared URL, не expansion.
Legacy respect_robots=False остается только существующим explicit SDK input.
Immutable manifest lane сохраняет прежний отдельный file contract.

Time/byte/cancellation/rate/redirect/response ceilings retained. Web operation
deadline теперь общий для finite operation, not reset per document. Не заявляется
security certification: OWASP allowlist principle — только design aid
(`https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html`),
live source lookup не выполнялся. Spans/index lineage code outside owned files
не изменялся; mocked caller tests не являются live indexing/proof acceptance.

## Проверки и фактические reds

Environment `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`;
`.venv/bin/python -m pytest -p no:cacheprovider … -q`, без отключения conftest.

| Final bounded selection | PASS | FAIL |
|---|---:|---:|
| Новый finite module: 24 base nodes, 64 instances | 64 | 0 |
| Six technical suites | 78 | 0 |
| Все `tests/test_dictionary_exit*.py`, включая новый module | 1672 | 14 |
| Six old mixed modules | 105 | 55 |
| Combined disjoint modules, 1924 instances | **1855** | **69** |

Combined log `/tmp/opencode/finite-corpus-combined-final.log`.
Earlier standalone technical+new log `/tmp/opencode/finite-corpus-technical-final.log`
показывает 142 PASS; final combined подтверждает отсутствие failures в этих modules.
Technical: test_docs_fetch_policy, test_docs_fetch_transport,
test_github_source_manifest, tests/docs/{test_target_security,test_content_trust,
test_reference_hash_domains}. `git diff --check` PASS.

### Dictionary: пять existing reds сохранены, ещё девять new conflicts

Existing five (не waived, aliases/legacy credit не восстановлены):

1. `test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
2. `test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables`
3. `test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance`
4. `test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]`
5. тот же `[flutter]`.

New nine (assertions unchanged; НЕ baseline reds / НЕ waived):

- `test_dictionary_exit_corpus_policy.py::test_blocked_locale_and_topic_exclusions_do_not_silently_broaden`
- `test_dictionary_exit_corpus_policy.py::test_url_normalization_and_content_hash_dedup_remain`
- `test_dictionary_exit_corpus_policy.py::test_github_source_branch_path_provenance_remains`
- `test_dictionary_exit_discovery_literals.py::test_strategy_provenance_and_content_survive_deduplication`
- `test_dictionary_exit_discovery_literals.py::test_bounded_discover_urls_ranks_only_original_candidates`
- `test_dictionary_exit_discovery_literals.py::test_security_errors_are_not_converted_to_discovery_permission`
- `test_dictionary_exit_discovery_literals.py::test_blocked_exclusion_contract_is_not_broadened[/scope/ru/entity]`
- тот же `[/scope/blog/entity]` и `[/scope/changelog/entity]`.

Причины: old veto expectations, trailing-slash/tracking equivalence, removed
unhashed private GitHub helper, old discovery dispatch. Hash/blob positives для
реального approved manifest проходят. Existing technical parser был сохранён;
explicit GitHub folder/exclusion/format pure utility test также PASS.

### Mixed: exact failing base nodes (55 instances)

`tests/test_filtering.py` — 18:

```
TestNormalizeUrl::test_strips_trailing_slash
TestNormalizeUrl::test_strips_tracking_params
TestInferDocsetRoot::test_docs_subdomain_collapses_to_host
TestInferDocsetRoot::test_docs_path_collapses_to_docs_root
TestInferDocsetRoot::test_llms_full_strips_suffix
TestInferScopePath::test_deep_path_with_root_hint_widens
TestInferScopePath::test_deeper_path_with_root_hint
TestInferScopePath::test_reference_root_hint
TestInferScopePath::test_no_root_hint_strips_leaf
TestInferScopePath::test_api_root_hint
TestIsDocsUrl::test_blocklist_blog
TestIsDocsUrl::test_blocklist_pricing
TestIsDocsUrl::test_blocklist_print_pages
TestIsDocsUrl::test_deep_base_url_widens_scope
TestIsDocsUrl::test_search_blocked
TestIsDocsUrl::test_default_ingest_excludes_locale_mirrors
TestIsDocsUrl::test_default_ingest_excludes_locale_mirrors_below_docs_root
TestContentDeduplicator::test_url_dedup_trailing_slash
```

`tests/test_fetcher_github.py` — 7:

```
TestMatchesPatterns::test_matches_patterns_readme
TestMatchesPatterns::test_matches_patterns_docs
TestFetch::test_fetch_readme_only
TestFetch::test_context7_config_filters_and_ranks_docs
TestFetch::test_ipynb_cells_are_converted_to_markdown
TestSingleFileFetch::test_blob_url_fetches_single_file
TestSingleFileFetch::test_blob_url_missing_file_raises
```

`tests/test_web_fetcher.py` — 17:

```
test_identical_retry_uses_fresh_client_and_recovers_in_same_process
test_github_blob_raw_fetch_keeps_canonical_docset_root
TestWebFetcherLlmsFull::test_llms_full_txt_success
TestWebFetcherDirectText::test_direct_markdown_url_fetches_single_page
TestWebFetcherNavCrawl::test_nav_crawl_fetches_pages
TestWebFetcherNavCrawl::test_page_source_uses_in_scope_canonical_url
TestWebFetcherNavCrawl::test_duplicate_canonical_pages_are_deduplicated
TestWebFetcherErrors::test_no_pages_raises_error
TestDiscovery::test_query_skips_monolithic_llms_full_and_ranks_page_urls
TestDiscovery::test_oversized_llms_full_falls_back_to_page_index
TestDiscovery::test_discovery_merges_llms_sitemap_and_nav
TestDiscovery::test_nav_crawl_follows_links_bounded_bfs
TestDiscovery::test_cross_domain_seed_url_gets_own_docset_root
TestWebFetcherDartdoc::test_direct_dartdoc_class_page_without_browser
TestWebFetcherDartdoc::test_dartdoc_root_empty_does_not_fail_when_seed_page_succeeds
TestWebFetcherDartdoc::test_dartdoc_all_empty_reports_structured_failure
TestWebFetcherDartdoc::test_dartdoc_index_json_discovers_api_pages_when_html_shell_has_no_links
```

`tests/test_crawl4ai_fetcher.py` — 1:
`TestCrawl4AIAvailability::test_fetcher_import_error_when_not_available`.

`tests/test_docs_service_part07.py` — 11:

```
test_cancel_between_staging_fetch_and_commit_never_publishes_index
test_library_prefetch_job_deadline_is_terminal_and_retryable
test_library_prefetch_rejects_overload_before_staging
test_cancel_terminalizes_without_waiting_for_library_worker
test_registry_commit_failure_rolls_back_published_staging_index
test_library_prefetch_job_exposes_structured_retryable_network_error
test_partial_library_prefetch_job_never_reports_healthy_reason
test_prefetch_resolves_approved_github_directory_before_indexing
test_failed_manifest_candidates_retain_active_metadata_and_diagnostics[agent0-no_chunks-no_extractable_content]
test_failed_manifest_candidates_retain_active_metadata_and_diagnostics[agent1-source_set-manifest_source_set_mismatch]
test_failed_manifest_candidates_retain_active_metadata_and_diagnostics[agent2-vector-vector_indexing_failed]
```

`tests/test_docs_service_part09.py` — 1:
`test_pub_discovery_failure_does_not_abort_later_target`.

Nine root-inference reds documented in baseline checkpoint. Нового full-baseline
control не было: остальные mixed failures не объявляются reproduced baseline.
Ten service failures сверх прежнего narrower run вызваны revalidation вместо
record_urls fallback: fixtures не передают allowed_domains либо attempted manifest
не совпадает с approved target. Они прекращаются ДО FakeAgent/staging fetch;
это не доказательство исправности всего async/rollback lifecycle. Старые assertions
не переписывались; raw legacy API остаётся fail closed. Manifest cancellation/
post-response deadline diagnostics tests PASS после сохранения прежнего file
operation clock/ledger semantics; security semantics не ослаблялись ради tests.

## Remaining blockers / minimal nonowned allocation для parent

1. `docmancer/docs/application/_library_docs_service_part02.py:64–85` всё ещё
   constructs pub query target с `docs_url or pub_dartdoc_root_url(...)`. Это
   concrete **inferred** caller URL, не user-selected member. Нужен отдельный
   allocation на отказ без explicit target и mechanical forwarding only.
2. Legacy raw `prefetch_docs`/`refresh_docs` wrappers не могут передать полный
   explicit target/robots/ceilings: минимальный follow-up consumer allocation —
   `_library_docs_service_part02.py` + `library_ingest_orchestrator.py` (forwarding),
   и `_library_docs_service_part01.py` только при необходимости persist/register
   explicit target contract. Не infer host/robots consent из root ради green.
   Здесь такие операции fail closed; использовать уже существующий target lane.
3. `docmancer/docs/application/docs_target_service.py:69–107,475+` сохраняет
   отдельно callable GitHub directory/package discovery methods. Owned default
   prefetch/refresh больше их НЕ вызывает. Для claim all callable entry points
   finite-only требуется allocation только этих methods/consumers; inspect_docs_target
   technical exact inspection и approved immutable manifests не расширять.
   Заданные `docs/target_urls.py` и `docs/target_security.py` отсутствуют как physical
   root files в этой baseline; target URLs находятся в application/docs_target_service,
   security helper — domain/target_security. Эти nonowned files не редактировались.
4. Independent review, remaining dictionary/old mixed reds, full CI/MCP/rebuilt
   artifacts/frozen pin checks и live corpus/quality acceptance — parent gates.
   Ничего из этого не выполнено/не waived; no full completeness/security claim.

## Exact extraction / hashes

Ровно **17 files**: 13 tracked production changes ниже, new finite module,
new test/shard и этот new checkpoint. Не переносить `.venv` или local log files.
Tracked diff: **282 insertions / 1229 deletions** (13 files).
`SHA256(git diff --binary)` =
`6faecedd7036b79867e9f0d5286130ee2c05d11030d5cfbcc9372d2a10237a8d`.
Sorted 16-file map `path + " " + sha256`, joined with `\n` без final newline:
`559dfe49bbf93aeaf5717b0c9401ac666bb8fecf0e9ff843377ceb17a4a8b894`.
Checkpoint self hash отдельно в worker return (не recursive self-hash).

| SHA-256 | File |
|---|---|
| `abad7d7997e3cb6258cfdc02bc62af87aa3a0868f86e27be7b1dbc8a93d07d27` | `docmancer/agent.py` |
| `5ffda93826d131d9f5352cb22b55c9f4de7d3b236972a890a832916ebfc2e3a3` | `docmancer/connectors/fetchers/_web/part01.py` |
| `d7ac0bfd51156118af8bdb1123756b5cc0c2774e466e939e38fa592bbe896f07` | `docmancer/connectors/fetchers/_web/part02.py` |
| `0c25a5fc73ed990d216ba95174a4c64cf8f17aa39c2a39d775f59d55a317085d` | `docmancer/connectors/fetchers/_web/shared.py` |
| `a9537ae63f52cd20a124d3f266c9e5bf3d2e12b769b59b6bf809df6e61c5df70` | `docmancer/connectors/fetchers/crawl4ai.py` |
| `0b5eb211ecf897ad1a6996e635d360ff173a050a352cf6234991db4ea6ea2605` | `docmancer/connectors/fetchers/factory.py` |
| `31b94419b309b68ebab11b7e9d027d5416075e60588e274ae60b9cdfae0235dc` | `docmancer/connectors/fetchers/github.py` |
| `ec65fed0222b723c6de2e6877504a05f0a6d51433e39c247d39c59507fc65d44` | `docmancer/connectors/fetchers/pipeline/discovery.py` |
| `8006aa161192aef33df01798e9b2506bf7ce0b696aa2e7f292679a80558e84a3` | `docmancer/connectors/fetchers/pipeline/filtering.py` |
| `a6d5fcb348b18d77e6e90c9ace1eec64f2ac0f8dd11da42c54a5cce45bb67c18` | `docmancer/connectors/fetchers/web.py` |
| `21987b5b0ce0e550d73a2aa5859f9d941d24af3fb5b4aaf131e95f16cf79d664` | `docmancer/docs/application/docs_prefetch_service.py` |
| `2b000337dc7a3ca820b2716ada9ac688b15d08300d27022653b21eeab214bb16` | `docmancer/docs/application/library_refresh_ops.py` |
| `00e6e7515373dea1545b3b6fa245be9365b108673fdbd8b87e603c5841031d0f` | `docmancer/docs/fetch_policy.py` |
| `4d677ef16649c77c045ff3d2ebf5224ab7af27f967638cdfe88a7b97b0df65d2` | `docmancer/docs/finite_membership.py` |
| `f981f5f79af54dc67a203267ef713013d075f9db9a20a112c8573fd219086699` | `tests/test_dictionary_exit_finite_corpus.py` |
| `874be141fd4b8de24e9476f9d573808a3e78c1a0c7b5a89428c7be57fca27e92` | `tests/diagnostic_labels.dictionary_exit_finite_corpus.json` |

Normal-conftest base-node inventory hash (24 nodes):
`0df6c1e4df8dfcd39f726adb040dfeaf9a3d504a3d29750bad671c546a30f0cf`.
