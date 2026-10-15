# Local membership — caller closure, bounded follow-up

2026-10-07. Worktree ONLY `/tmp/opencode/docatlas-resumed-local-ee156cba`.
HEAD baseline `ee156cba4cc6dd4bf51c0e2c8adf44907aac9633` плюс frozen first A slice.
**Два allocated caller gaps закрыты fail-closed. Full EXIT / release / SDK-wide
authorization closure НЕ заявлены. Fresh independent parent review обязателен.**

## 1. Exact follow-up scope / immutable first payload

Ровно **5 follow-up extraction files**:

1. `docmancer/docs/application/_project_docs_service_part02.py`
2. `docmancer/docs/_patch_plan_context_part01.py`
3. `tests/test_dictionary_exit_local_callers.py`
4. `tests/diagnostic_labels.dictionary_exit_local_callers.json`
5. Этот `LOCAL_MEMBERSHIP_CALLER_CLOSURE_RU.md` в committed checkpoint directory.

Все original **20 files** заморожены: **19/19 payload pins** из
LOCAL_MEMBERSHIP_IMPLEMENTATION_RU.md совпадают до/после follow-up. Сам first report
SHA256 также неизменён:
`5a2e339ae9511a4360bfe227f68ae084429b59579283f158c8102fdb3b8a2051`.
First test/shard/config/production/report не редактировались. Actual frozen pilot
по-прежнему **10 docs / 0 modules / code_files=()**, что повторно проверяет first
31-case shard. Не пересканированы 134 historical candidates; catalog narrowing
не является consent удалить former 124 docs/index rows.

Нет agents, network/provider calls, dependency installs, commit/push, edits primary
или `/home`. Нет runtime current-index reads/writes, index creation/rebuild, sync,
deduplication, pruning, vector mutation или orphan reconciliation. Test fixtures —
только временные YAML/source bytes под `/tmp/opencode/local-callers-*`; service
constructor с реальным storage не запускался. Предсуществующий `.venv` не менялся.

## 2. Direct sync: deny before effects, not fake consent

`ProjectDocsService.sync_project_docs` и independently callable
`_sync_project_docs_incremental` теперь сразу дают **PermissionError**:
API не имеет explicit mutation grant + validated member transaction, а catalog
membership не разрешает indexing/deduplication/orphan deletion.

Guard расположен до validate_project_path, facade/config/adapter dispatch, index
read, writer lease/lock acquisition, metadata read и любого mutation. Changed/
deleted/renamed paths, with_vectors=True и `_coordination_held=True` не обходят
denial и не превращаются в consent. Не создан broker, settings API, capability
flag, fabricated transaction/authorization token или auto-consent fallback.

Existing lock/lifecycle/incremental/tombstone/vector machinery ниже guard не
переписано и не объявлено authorized lane: при нынешней API signature оно не
исполняется. Future mutation support требует отдельно approved contract/allocation;
здесь нет positive mutation case. Даже отдельное public prepare confirmation не
подменяет отсутствующий contract этого direct API. Не заявляется working auto-sync.

New tests входят в реальные method entries только с fake facade, forbidden spies
на path/stat/open/scandir/index/agent/adapter/locks/ingest. **Sync bodies не
исполнялись.** Public LibraryDocsService.sync_project_docs delegate также вызван
unbound на fake facade без service initialization и доходит до того же guard.
Это offline effect-free entry proof, не запуск sync против какого-либо индекса.

## 3. Independently callable scanners: no implicit reads/proof

* `_iter_source_files` delegates frozen SourceBoundary finite code iterator,
  never rglob/root/name-family discovery. Empty/absent/invalid code membership
  yields nothing without reading/probing an unselected code file.
* Dependency APIs/roots/source iterator/lock helper теперь inert/unresolved;
  no package_config/pubspec metadata or imported package source reads. Shared raw
  package resolver alias удалён из namespace allocated part01. No dependency
  witness из caller text/path через `_find_dependency_symbol`.
* discover_missing_symbols returns empty **unknown**, not `not_found`, negative
  evidence, complete search or nearest API proof. discover_rejected_sources does
  not scan docs or manufacture topic/name-family demotion.
* `_read_text(path)` без root-bound membership returns None без file access.
  Optional private `root=` нужен для проверки actual finite set; repository root
  не угадывается через ancestors/Git/package metadata. Это read validation context,
  не новая settings/grant API.
* Root-bound read проверяет literal selected member, frozen boundary exclusions,
  gitignore/root/source-root/symlink/extension/generated restrictions, file/count/
  byte/depth caps и deadline до/после bounded binary read. Strict UTF-8 сохраняет
  исходные CRLF/Unicode bytes; content SHA-256 считается из этих же bytes.
  Никакой generated consent не синтезируется из changed path или question.
* `_changed_file_candidate` не разрешает path aliases/unselected siblings и
  возвращает только **action=read**, original hash + line refs. Changed path не
  даёт edit permission. `_find_patterns_for_plan` получает literal refs только из
  вновь проверенного selected source, без hardcoded menu/QR name family.
* build_implementation_map revalidates supplied file rows через selected read;
  no code membership → empty current_behavior/minimal_patch_path and unresolved
  warning. Selected context retains file hash and spans, confidence=unknown;
  no semantic behavior certification, minimal edit plan, checks or mutation grant.

Read-only positive исполняется только на explicit selected temporary `.py` fixture;
unselected import target ни читается, ни добавляется. Production code membership
осталось пустым. Frozen part02 bare `_read_text(path)` calls теперь conservative
unknown, а root-bound changed-source caller сохраняет genuine selected positive.
Не расширять read API обратно discovery/root inference ради compatibility.

## 4. Offline bounded tests / exact honest ledger

Normal conftest, existing outbound DNS/socket guard, original diagnostic inventory
и новый reviewed shard использованы без bypass. Final commands:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/local-callers-audit-bounded-ee156cba -q
tests/test_dictionary_exit_local_callers.py
tests/test_dictionary_exit_local_membership.py
tests/test_dictionary_exit_local_residuals.py
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_exposed_only_in_advanced_mcp_tools
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_schema_contains_required_fields
tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_routes_through_project_tools

PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/local-callers-audit-new-ee156cba -q tests/test_dictionary_exit_local_callers.py
```

* **New: 34 PASS**, 0.56s.
* **Combined: 105 PASS / 34 FAIL**, 139 cases, 1.02s. Includes frozen first
  shard **31 PASS** and three static old tool/schema/routing cases **3 PASS**.
  Separate new-only run не добавлен повторно к combined count.
* Все 34 reds — unchanged local-residual tests. Exact node set совпадает с
  соответствующей группой first report; это comparison с first delivered ledger,
  **не** independent baseline ee156cba rerun и не blanket baseline attribution.
* No old assertions/golds/floors/thresholds/manifest edited or waived. Full old
  sync/storage suites не запускались: их fixtures создают/изменяют индексы, что
  запрещено этой allocation. Old positive dependency/absence workflows не
  объявлены restored. Scope selection явный, не full CI/quality PASS.
* Initial collection: one error because new test used pytest-reserved parameter
  `request`; исправлено только имя в новом test. Then new-only 33 PASS, after
  adding public delegate case final 34 PASS. No historical test was weakened.
* `git diff --check` PASS. Existing Python 3.13.12 / pytest 9.0.3 sufficient;
  missing dependencies/install blocker отсутствует.

Logs:
`/tmp/opencode/local-callers-bounded-ee156cba.log` SHA256
`0e807445220db6857677716913eb674252df481d8b1f1e61d9ec43df66bc8e5d`;
`/tmp/opencode/local-callers-new-ee156cba.log` SHA256
`79c2c15672c83c3d58b39bcf12b511130e7510d6b098abacffdf13975f2c1beb`.

Exact 34 red nodeids:

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
```

## 5. Critical external gates / no full EXIT

Parent must separately allocate/review these **outside follow-up scope**; no edit:

* Frozen `_project_docs_service_part01.py::ingest_project_docs` is a distinct
  mutation entry. Denying sync does not certify all ingestion/creation ports.
  Do not invoke it against current runtime index on catalog-selection consent.
* Frozen `_project_docs_service_part03.py` / prepare/MCP adapters may expect
  successful automatic sync and need an approved unresolved/error handoff for
  PermissionError. SDK/mutation contract ownership stays with parent/B. No
  public/installed parity or every adapter exception mapping certified here.
* `_patch_plan_context_shared.py`, facade, and `dart_package_config.py` can expose
  the raw resolver separately. Allocated part01 no longer exposes/dispatches it;
  independently invoking outside raw helpers is not certified by this closure.
* Frozen part02 bare read helper callers deliberately get unknown without root
  binding; future nonempty-code lexical retrieval improvements need separate
  allocation rather than modifying frozen first files or guessing roots.
* Installed/current index membership, source-continuation artifacts, external SDK,
  B-owned trust/action/packet/evidence/model-visible projections, and all security/
  release acceptance gates remain outside this bounded run. No false approval
  inferred from successful read fixture or absence of observed mutation.

## 6. Exact follow-up payload SHA-256 pins

Only these four payload files + this report are follow-up extraction candidates.
Report self-hash should be computed independently by parent after delivery.

```text
fd46cfb8f423d5b816be96402744baa15c2d16ecadb81065afeca433bca3740d docmancer/docs/application/_project_docs_service_part02.py
64b0fa0fc7dc230cb2ed2daa0d7ffbc0abc9b86c7b8c0d1c25e99da59224491a docmancer/docs/_patch_plan_context_part01.py
58be45fbe5db468214eb7f4bb620094ab616061542c567eb17bcd4064f1a9f34 tests/test_dictionary_exit_local_callers.py
04cbede0466d5bde766fc1c9ad4b362d8e7370ec8d27c6001dc016bffd207304 tests/diagnostic_labels.dictionary_exit_local_callers.json
```
