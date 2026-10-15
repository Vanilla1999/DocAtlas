# Final integrated exit audit — bounded snapshot

2026-10-07. PRIMARY `/tmp/opencode/docatlas-stage3-integration-active`.
HEAD/baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57` плюс текущие
reviewed uncommitted local/Packs/read-packet/callable/finite/correction/caller/identity slices.

**Publication blocker для bounded текущих изменений: NO — нового cross-worker
false approval/support/authority или finite-fetch bypass не обнаружено.**
Это scoped audit, не разрешение public release при красных acceptance gates.
**Full EXIT: NO. Quality/release/security acceptance: НЕ подтверждены.**
R11/R12 и negative security policy остаются OPEN/intentional; current index и
external SDK callers UNKNOWN. Parent отвечает за итоговый acceptance/staged ledger.

## 1. Scope и фактически выполненная проверка

Прочитаны `FINAL_DICTIONARY_EXIT_INVENTORY_RU.md`,
`FINAL_FINITE_CORPUS_PARALLEL_RU.md` и восемь delivered slice reports:
LOCAL_RESIDUAL, PACKS_SAFETY, READ_PACKET_RESIDUAL, CALLABLE_RESIDUAL,
FINITE_CORPUS, FINITE_CORPUS_CORRECTIONS, FINITE_CALLER, FINITE_REFRESH_IDENTITY
(`*_DICTIONARY_EXIT_RU.md` / соответствующие correction report names).
Historical ACTIVE/NOT INTEGRATED строки внутри reports не переопределяют final
coordinator closure; FIRST pins superseded corrections, SECOND part02 pin
superseded identity correction. Проверены текущие определения и actual consumers,
не сделан вывод из одних imports.

Единственная запись этого audit — этот checkpoint. Production/tests/config,
gold/threshold/frozen assertions не редактировались. Нет agents, HTTP/DNS/crawl,
изменения настоящего индекса, commit/push. Offline tests используют temporary
fixtures/local stores и mocked transport; parent full suites не повторялись.

## 2. R1–R10: текущая closure, не новый список taxonomy

Пути `A/` = `docmancer/docs/application/`, `D/` = `docmancer/docs/domain/`.

| Inventory | Actual current chain / результат |
| --- | --- |
| R1 | `mcp/registry.py::_derive_safety` → compiled hash-bound pack → installer/dispatcher → `mcp/safety.py::check`: POST/PUT/PATCH/DELETE destructive независимо от search/query/list/find. DELETE `/search/all` теперь blocked без destructive grants; GET/auth/network gates не заменены. |
| R2 | `A/_docs_context_projection_core.py::_expand_selected_snippets` → current quote retention/requalification: must/never больше не выбирают сохранение span. Exact bound span сохраняется одинаково; ambiguity, window/token budgets и witnesses остаются. |
| R3 | `A/action_packet.py` + `_action_packet_part01/02/03.py` → `D/normative_language.py`: modality `None`, `_extract_facts` пустой, behavioral readiness False. Prose не становится required/forbidden policy или edit authorization. Canonical prose без semantic contract остаётся unresolved/manual-review, не harmony proof. |
| R4 | `A/evidence_candidates.py` → `_evidence_selection_part02/03.py`: inferred qualifiers пусты, patch prose-fact selection удалён, CamelCase→snake_case credit отсутствует. Dedup требует identical display bytes: различная negation/условие не исчезает из-за удаления polarity veto. Multiple distinct canonical windows дают manual-review missing requirement; docs answer остаётся context-only/insufficient. |
| R5 | `D/evidence_qualification.py` → `D/technical_tokens.py`: literal matching вместо retry→retried morphology. Legacy relation helpers не дают semantic witness. Original/direct attribution и context-only distinction не заменены permissive relation support. |
| R6 | `A/source_reference_evidence.py` → source dependency preparation/validation → `D/source_dependency_graph.py`: нет inferred anaphora/cause/definition. Markdown heading/list/table edges, immutable source/hash/span/hop bounds остаются. Examples/Aliases — обычные list members, не inferred exclusions. |
| R7 | `A/retrieval_need_support.py::apply_retrieval_need_witness` вызывает fresh default hook; other legacy relations `None`, inferred obligations пусты. Unknown veto-ит qualified trace; inherited need/context metadata очищается. Unknown не сохраняет старый witness. |
| R8 | `D/_code_graph_part02.py` score → code graph contexts: use/reference wording больше не даёт +7. Parsed references/imports/confidence/literal terms остаются retrieval data, не authority. |
| R9 | `A/_library_docs_service_shared.py` → part03 library read: нет NL list requirements или copy/translation label deletion; untyped prose не становится complete request. Exact RST syntax, identity/version checks и quote budgets остаются. |
| R10 | `D/legacy_question_coverage.py` возвращает unresolved даже для historical approved frame; `_project_answer_contract_part01/shared.py` не переводят number words в cardinality. `D/patch_request_plan.py` operation none/unsupported для prose; `_answer_units_part02/shared.py` и `A/model_visible_projection.py` не восстанавливают dormant positive semantics. DTO/literal coordinates и negative adapters сохраняются. |

Allocated local corrections также присутствуют: `D/source_map.py` сохраняет
request order без Gate/Service/Repository suffix priority;
`D/project_state.py::_documentation_gap_evidence` вызывает structural source facts
с literal query или empty string, не подставляет `architecture`. Unmatched
structural facts — inspection context, не supported answer. Это не closure R11/R12.

Технические command/HTTP/DTO/Markdown/Python syntax recognizers не объявлены NL
authority. В частности `_validation_bucket` не получает новых synthesized prose
facts через `_extract_facts`; standalone bucket не является execution grant.
Negative compatibility означает потерю прежней функциональности, не качество PASS.

## 3. Finite remote chain и межworker границы

Actual library flow:
`_library_docs_service_part02.py::{prefetch_docs,refresh_docs}` →
`LibraryIngestOrchestrator.prefetch_docs` → `_prefetch_explicit_targets` →
scoped `LibraryRefreshOps` → agent → factory/WebFetcher → `DocsHttpClient`.
Target service / direct target-prefetch lane также propagates snapshot members,
ceilings, manifest и selected robots controls, без resolver-discovery fallback.

- Orchestrator требует один typed target; deepcopy до dispatch/job reservation;
  library/ecosystem/version/source/URL/template mismatch — unresolved. Async identity
  включает full target-plan SHA256, не только redacted URLs. Stored refresh сверяет
  каждый identity component и canonical id **до** target/network/staging mutation.
  `pub` не приравнивается к `dart` для identity authorization.
- `_FiniteStagingGateway` проверяет positive int result, complete diagnostics,
  отсутствие page/fetch failures и точное равенство persisted `sources` expected set.
  Commit guard не публикует incomplete/foreign source staging; previous record
  восстанавливается при failed result. Cancellation/deadline/generation guards
  достигают существующей guarded publication, не старого безguard adapter.
- `finite_membership.py` требует непустой finite set, rejects malformed/over-budget
  declarations целиком. Query order/values/trailing slash не стираются; HTTP
  serialization проверяется до dispatch. `exact_urls=[]` не превращается в fallback.
- Web `_fetch_finite` preflights весь set/controls, не crawling links. Каждая selected
  locale/topic страница допускается как literal member; `/ru`, `/blog`, `/changelog`
  не дают discovery/authority credit. Sibling URL остаётся unselected. Negative
  login/account/archive-format exclusions сохранены как restrictions, не topic proof.
- `DocsHttpClient.get` проверяет selected outgoing URL с params, scope/DNS/private
  IP и stable resolution; redirect проверяется на следующем hop до request.
  Web `_fetch_page` отдельно проверяет final/canonical URL membership. Canonical
  alias внутри selected set не может незаметно завершить library ingest с потерянным
  expected source: persisted source-set equality остаётся commit veto.
- Robots controls явно selected; нет автоматического добавления hosts/locales/
  sitemap/aggregate URLs. Whole llms document — один выбранный source, не permission
  читать URL внутри него. Budget/bytes/time/robots/security checks не заменены query.
- `GitHubFetcher.fetch` delegates immutable schema-v2 manifest lane: complete
  manifest, blob seed membership, exact raw URLs, commit/blob/size/UTF-8/content hashes.
  No branch/tree/API discovery fallback. `_select_documentation_files` — legacy
  pure utility, не current fetch authorization. Browser fallback fail-closed;
  Crawl4AI delegates finite HTTP lane, не запускает скрытые browser requests.
- `library_source_discovery.py::_python_candidates` больше не ранжирует Reference/
  Documentation/Home labels: deterministic URL ordering, medium confidence.
  Registry proposals остаются confirmation-required; они не selected membership.

В bounded проверках не найдено нового positive support от narrowed corpus,
canonical metadata, отсутствие inferred conflict, successful staging или query
rephrasing. Fetch selection ≠ source authority ≠ answer support ≠ edit permission.
Не сертифицирован каждый private legacy network helper или внешний SDK caller;
current entry points их не dispatch-ят как discovery fallback.

## 4. Offline execution и preserved reds

Мой independent normal-conftest bounded run:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q
tests/test_dictionary_exit_packs_safety.py
tests/test_dictionary_exit_read_packet_residuals.py
tests/test_dictionary_exit_callable_residuals.py
tests/test_dictionary_exit_local_residuals.py
tests/test_dictionary_exit_finite_corpus.py
tests/test_dictionary_exit_finite_corrections.py
tests/test_dictionary_exit_finite_callers.py
tests/test_dictionary_exit_refresh_identity.py
```

**362 passed, 9.92s.** Это один command с перечисленными arguments, не full CI.
Executed fixture chains включают real pack install/dispatcher gate, contradictory
canonical quotes/manual review, fresh need veto, source/span/hash retention,
finite mocked transport/canonical/redirect/params rejection, actual caller staging
и stored identity mismatch/positive. HTTP requests вне mocked fixture не выполнялись.

Parent final results прочитаны из текущих logs, **не мои повторные runs**:
dictionary **1970 passed / 14 failed**; combined **2080 passed / 17 failed**;
old-mixed **331 passed / 311 failed**. Последние не blanket-attributed baseline.
MCP stdio PASS — parent observation, не independent transport rerun.

Точные 14 dictionary reds из `/tmp/opencode/final-exit-integrated-dictionary.log`:

```text
tests/test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt
tests/test_dictionary_exit_corpus_policy.py::test_blocked_locale_and_topic_exclusions_do_not_silently_broaden
tests/test_dictionary_exit_corpus_policy.py::test_url_normalization_and_content_hash_dedup_remain
tests/test_dictionary_exit_corpus_policy.py::test_github_source_branch_path_provenance_remains
tests/test_dictionary_exit_discovery_literals.py::test_strategy_provenance_and_content_survive_deduplication
tests/test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables
tests/test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance
tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]
tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]
tests/test_dictionary_exit_discovery_literals.py::test_bounded_discover_urls_ranks_only_original_candidates
tests/test_dictionary_exit_discovery_literals.py::test_security_errors_are_not_converted_to_discovery_permission
tests/test_dictionary_exit_discovery_literals.py::test_blocked_exclusion_contract_is_not_broadened[/scope/ru/entity]
tests/test_dictionary_exit_discovery_literals.py::test_blocked_exclusion_contract_is_not_broadened[/scope/blog/entity]
tests/test_dictionary_exit_discovery_literals.py::test_blocked_exclusion_contract_is_not_broadened[/scope/changelog/entity]
```

Combined дополнительно сохраняет:

```text
tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields
tests/test_github_source_manifest.py::test_schema_v1_round_trips_and_plain_github_blob_remains_single_page
tests/test_github_source_manifest.py::test_target_service_resolves_approved_directory_declaration_before_ingest
```

Не waived/rewritten. Semantic/finite contract conflict не новый exploit, но красный
test остаётся красным. MCP advisory `answer_available=True` assertion не даёт
основания менять current nonauthorizing context. Acceptance debt не закрыт.

## 5. Current pins и archived payload validation

Effective delivered pin union: **64/64 matched** (48 production + 8 tests + 8 shards).
Algorithm: взять per-file pins из восьми reports в порядке §1, применить correction
supersession, SECOND identity override для part02; отсортировать строки
`path + ' ' + sha256`, join `\n` **с final newline**.
Current union SHA256:
`21a8b65b261275c44688ea9e65f9a517e2e76beea59ef05edc88a4a19ef75204`.
Historical hex внутри parametrized nodeids — не file pins.

Critical current pins (не FIRST historical values):

```text
5a1dcfbab2f26e228a687289bc2af646d956ad9ba955a7c89921f9bbe318fb82 docmancer/docs/application/_library_docs_service_part02.py
40ee42f49d24d9f19312f989af672d64b4f2264721ff434983c0dc1774641bcc docmancer/docs/finite_membership.py
596e918da12ff349bf640539cca33f9e86f9c6f20fac363e72eebd5d3d71251d docmancer/docs/fetch_transport.py
33f1ae1ce66d82fea610aa76497e73ab8fc3d082c1f9badf999b27b2fb1b4122 docmancer/connectors/fetchers/github.py
cfaf0b7de37059334fa569924c66e8061cccda01dde499418859fdfd294404b3 docmancer/docs/application/docs_prefetch_service.py
9d3d0eb439fdfaf2f57ff8fca6895a9150a450ab6df159a2c6654787db108fea docmancer/docs/application/library_refresh_ops.py
93d3a13e2c52bb1a54c47d28a4517ad2c1b9493f8b940732d7b4d5d386a097b7 docmancer/mcp/registry.py
```

Current archive `archives/dictionary-exit-final-finite-self-host-v1.json`:
file SHA256 `1485715aa40661894d3eb3b85ed6125f53882cce433eae1094dc94b884cabfd0`.
Embedded deterministic digest recomputed using runner canonical JSON without digest
field: **MATCH** `de26e98bffec1ee8185b0e8c6fb5aae1c70729f4da7647f87ba798dc8621084b`.
All **17 visible source snippets** occur within their current file line_start/end
windows; no archived payload claims answer_supported/edit_ready True.
Archive verdict **FAIL**, 10/16 cases passed, positive 9/15;
false_supported_count=0, false_docs_answer_count=0, source/token violations=0.
Это не quality PASS и не полная completeness проверка.

Важно: public `content_sha256` здесь вычисляет `model_visible_projection.py::_source_digest`
из path/section/content/snippet/version binding material. Он **не** whole-file SHA
и **не** snippet-only SHA. Из compact archive без private original material/snapshot
невозможно независимо recompute все source binding digests: эта часть **UNKNOWN**,
не fabricated pin match и не доказанный hash bypass. Runtime validators и bounded
tests проверяют binding отдельно; visible line-span validation не заменяет их.

Прочитанные parent logs pinned:
dictionary SHA256 `5bb32eadff84b62c95744c336133f6d063895fb3e48cab80b213001209f58a2e`;
combined SHA256 `9661e2da01b1be49dc84b61abbe16dd11624a25ac86e37c07bbb7e6a8e7b5324`.
Не выдавать эти logs за новый полный independent прогон.

## 6. Remaining exact files / обязательные owner choices

**R11/R12 local finite catalog — отдельное authorization решение, OPEN:**

- `docmancer/docs/domain/source_boundary.py`: package/tool/generated/archive defaults.
- `docmancer/docs/project.py`: root doc names, doc/module directory selection.
- `docmancer/docs/domain/project_doc_ranking.py`: filename/path restrictions/risk lanes.
- `docmancer/docs/application/_patch_constraints_service_part01.py` и
  `_patch_constraints_service_shared.py`: fixed candidate/glob/doc directory defaults.
- `docmancer/docs/application/_patch_review_service_part02.py`: fixed prefix demotion.

Owner должен выбрать concrete LOCAL catalog files и scope/roles, отдельно подтвердить
availability loss от прекращения automatic scanning. Finite REMOTE permission не
разрешает whole-repo expansion, generated/vendor admission, local index rebuild или
перенос прежней guessed taxonomy в config. До решения сохранить ограничения или
консервативно unresolved при отсутствии explicit membership. Root/resolve/symlink,
gitignore/exclude, extension/byte/time/depth/file limits и source identity остаются.

**Security negative NL guards — намеренно сохранены, НЕ full dictionary-free:**
`docmancer/docs/domain/content_trust.py`,
`application/_action_packet_part01.py`, а также endpoint restrictions в
`connectors/fetchers/pipeline/filtering.py`. Они не дают положительную authority;
их отсутствие тоже не должно стать permission. Dictionary-free alternative требует
отдельного owner contract: считать все external prose inert/untrusted, принимать
только authenticated structured scope-specific instructions, explicit execution
capabilities/consent; unknown source/intent запрещает execution/promotion. Нельзя
просто удалить veto или автоматически доверять canonical prose. Здесь такая замена
НЕ авторизована и НЕ реализована; impact на availability/workflow требует решения.

**External/current artifacts UNKNOWN:** установленные packs могут содержать старую
compiled safety; требуется отдельный authorized recompile/reinstall. Current
historical indexed URL/file set, external SDK/private helper callers, installed
skills/wheel/stdio parity и public release identity не установлены этим audit.
Ни source import, ни finite tests не обновляют эти surfaces автоматически.

## 7. Handoff

Можно передать reviewed bounded changes с честными preserved reds и quality FAIL:
**нового audit publication blocker NO**. Нельзя публиковать full EXIT/quality PASS
или считать local/security choices согласованными. Parent review/extraction —
только этот новый report; no production changes от audit. Дальнейшие действия:
owner local catalog/availability contract, owner security inert-data contract,
отдельный artifact/index/SDK acceptance при явной authorization, без crawl здесь.
