# Local entry closure — final bounded correction

2026-10-07. ONLY `/tmp/opencode/docatlas-resumed-local-ee156cba`, baseline HEAD
`ee156cba4cc6dd4bf51c0e2c8adf44907aac9633` плюс previously delivered slices.
**Allocated ingest/resolver/guidance closure implemented; fresh parent review
required. Full EXIT / quality / release / installed-runtime acceptance НЕ заявлены.**

## 1. Exact six files / supersession

1. `docmancer/docs/application/_project_docs_service_part01.py` — approved correction
   only: early ingest denial, read inspection unchanged.
2. `docmancer/docs/dart_package_config.py` — actual public resolver fence.
3. `docmancer/docs/interfaces/mcp/error_contract.py` — authorization hint specificity only.
4. `tests/test_dictionary_exit_local_entry_closure.py` — new tests.
5. `tests/diagnostic_labels.dictionary_exit_local_entry_closure.json` — new shard.
6. This `LOCAL_ENTRY_CLOSURE_RU.md` in the same checkpoint directory.

**Explicit correction supersession:** old first-A part01 pin
`9b554a0834e0e9e12b92c1714d6cf50ea0170b91571d88b5eb7ce43c7b7a9770`
is superseded by
`41e74edd094f7710a1ef468abc07e0819a29d5a5968f6df2c1a68d6f60354037`.
Do not overwrite/rewrite the immutable historical reports to hide that change.

All **other first-A 19 files unchanged**: 18/18 other payload pins match and
first report hash remains
`5a2e339ae9511a4360bfe227f68ae084429b59579283f158c8102fdb3b8a2051`.
All **caller follow-up 5 files unchanged**: 4/4 payload pins match and report hash
remains `19867cef07c003cbeaac182fb521954ceaae81fa1105479bfc2aa356cec9166b`.
This is **24/24 frozen files verified**, excluding the one approved correction.
Original first/caller tests, shards, reports and all unrelated/B files untouched.

Source-history pins for the two formerly unchanged committed files (not current
payload pins): dart_package_config.py baseline SHA256
`4f11665d76a87a7b14668f963ad753b1989f7ea58051f007e17fc8a7709e5916`;
error_contract.py baseline SHA256
`cb4dd26be5b3a7ebc692f4b44f15d01cd83224f41d0a18764967ff930e1d4968`.

## 2. Actual reported chains closed without new grants

### Direct local ingestion

`docs/service.py:310–311` → ProjectDocsService.ingest_project_docs → early
**PermissionError** before validate_project_path, facade adapter, config/index
reads, locks, source probes, agent factory, queue, ingest or staging mutation.
The diagnostic explicitly says this API has no mutation grant + validated member
transaction, and catalog membership does not authorize indexing/staging/ingestion.

skip_known=False, with_vectors=True, exact/empty `_candidate_paths` and
`_coordination_held=True` are not consent and do not bypass denial. No broker,
fake boolean capability, mutation-consent API, implicit grant or allow fallback
added. Existing underlying lock/lifecycle/hash machinery was not rewritten or
certified as an authorized mutation lane; it cannot execute through this API.
Already-fenced sync/incremental code was not edited or re-enabled. Existing
explicit capability contracts outside these local read ports remain untouched.

### Public Dart resolver, including wildcard exports

`dart_package_config.resolve_dart_package_roots` and shared → part02 →
patch_plan_context exports now return the same typed tuple **({}, warnings)**
with an explicit **unresolved/no inspection** warning. Denial happens even before
coercing project_root, resolve/exists/stat/read/glob, package_config inspection or
following external rootUri. Empty output does not certify absent dependencies.

The current API has no separately selected/authorized dependency metadata/source
contract. Code/document selection alone does not create one. Conservative unknown
is intentional even for any future code set; no speculative new contract/fields
or selected production files added. Pure `_resolve_root_uri` URI/percent-decoding
grammar remains unchanged and is tested without filesystem access; its Path value
is syntax data, not permission to resolve/read that target.

### Authorization-specific MCP guidance

error_contract recognizes only **two exact emitted local guard diagnostics** on
PermissionError with errno=None and reason_code=permission_denied. Default hint
says missing local mutation authorization, read-only catalog selection and no
index rebuild/prune/retry on selection approval. This is negative error guidance,
not NL intent inference or a grant. Ordinary EACCES/EPERM/unrelated PermissionError
keeps filesystem guidance; same text without the actual permission exception does
not reclassify another error. Explicit hints and all other error paths unchanged.

Wire status=failed, nested permission_denied, retryable=False, exception type,
message redaction, where fields, budgets/debug redaction stay unchanged. Existing
public prepare_docs(sync_project_docs) catch is exercised with a fake storage-free
service and returns the accurate nonretryable authorization hint. No extra MCP
handoff files edited, no bootstrap/sync fallback re-enabled.

## 3. Effect-free checks / preserved read-only result

New tests spy/deny Path.open/stat/exists/is_file/is_dir/resolve/read_text/read_bytes/
glob/rglob/iterdir and os.scandir, adapters, locks, metadata/index reads, agent and
section extraction before invoking the real direct/public entries. Zero effects
observed. Public delegate uses an unbound LibraryDocsService method on a fake
facade; no real service/storage initialization. Resolver aliases are invoked on
absent/empty/invalid catalog fixtures with an external-root package_config decoy;
none of those files/roots are read. No sync/ingest bodies executed against any
index, including temporary indexes.

Frozen first shard **31 PASS** confirms actual 10-doc read inspection/bindings,
empty production code set, unchanged source hashes/spans and no discovery.
Frozen caller shard **34 PASS** retains genuine explicitly selected read-only
temporary-source bytes/hash/spans and excludes unselected import targets. New
resolver fence does not turn a source read into dependency-root authority.

No agents, network/provider calls, dependency installs, index creation/rebuild,
runtime index reads/mutations, reinstall, commit/push or primary/`/home` edits.
Only pytest source/YAML fixtures under `/tmp/opencode/local-entry-*` were written.
Preexisting shared `.venv` unchanged; existing dependencies sufficient.

## 4. Normal-conftest bounded execution / exact ledger

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/local-entry-bounded-ee156cba -q
tests/test_dictionary_exit_local_entry_closure.py
tests/test_dictionary_exit_local_membership.py
tests/test_dictionary_exit_local_callers.py
tests/test_dictionary_exit_local_residuals.py
tests/docs/test_mcp_error_contract.py

PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/local-entry-new-final-ee156cba -q tests/test_dictionary_exit_local_entry_closure.py
```

**New: 32 PASS**, 0.68s. **Combined: 138 PASS / 34 FAIL**, 172 cases, 1.17s.
Combined includes first 31, caller 34, new 32, existing MCP error-contract 4 and
old local-residual 37 PASS / 34 FAIL. Separate new-only not counted twice.
Normal conftest/DNS/socket/diagnostic guards used; new shard only, no base manifest,
old tests/assertions/golds/floors/thresholds changed. No failures waived or blanket
attributed baseline. The 34 red node set equals the previously delivered caller
ledger; no full baseline/CI/storage-mutation suite executed. `git diff --check` PASS.

Logs:
* `/tmp/opencode/local-entry-bounded-ee156cba.log` SHA256
  `dc38bcbfc9a43b0a235d238c79c6fe489509e39a093042e79cb251071e1f46c0`
* `/tmp/opencode/local-entry-new-ee156cba.log` SHA256
  `7f454bff5bf4d39afc32cfc8d5622d7430199c04faa4b1a99d30044d23e1734d`

Exact preserved 34 reds:

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

## 5. Acceptance / stop boundary

No additional production dependency edits needed/identified for the allocated
reported chain: actual direct/public ingest, raw resolver exports and existing
prepare catch are covered. Stop at this six-file scope; do not reopen frozen
reports/files or add speculative mutation APIs. Permission denial means these
local mutation operations are intentionally unavailable, not working auto-sync.

Fresh independent parent review remains a blocking integration gate. The 34 old
reds, current/installed index/SDK/transport identity, B-owned trust/packet/evidence
projection, explicit external capability contracts and wider release/security
acceptance remain outside this bounded verification. No full EXIT or authorization
for runtime index work inferred from read success or this checkpoint.

## 6. Current five payload SHA-256 pins

These five payload files plus this report are the exact correction extraction set.
The part01 pin below is the explicitly superseding effective pin from §1.
Parent should independently hash the report after delivery.

```text
41e74edd094f7710a1ef468abc07e0819a29d5a5968f6df2c1a68d6f60354037 docmancer/docs/application/_project_docs_service_part01.py
3d3afd2212a24edb06248ef5017f6a4c5e72ddbab05b6a9e5a7ac8d95db6ee93 docmancer/docs/dart_package_config.py
b75f6fa53c9309e3f7eddd08c4534a641d07feb6c34d66fd0cb2e61db6c83417 docmancer/docs/interfaces/mcp/error_contract.py
f971d6db9648e6e24d907d5004e6cbb5846fc3bb6588974b60cd43a8b312d2eb tests/test_dictionary_exit_local_entry_closure.py
f20c90cff957a07d6c78236d6d73f6b696398d2d584288d7863eceefca39d1d4 tests/diagnostic_labels.dictionary_exit_local_entry_closure.json
```
