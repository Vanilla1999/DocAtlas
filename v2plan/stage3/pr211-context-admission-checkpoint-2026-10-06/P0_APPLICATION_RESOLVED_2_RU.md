# P0 application — аудит 83 владельцев, часть 2

**Обработаны 83/83 строки.** Все file SHA256 и owner SHA256 совпадают с входными pins (owner: полный диапазон, strip, UTF-8). Применимых AGENTS.md в репозитории и проверенных родителях не найдено.

**Классификации:** OPEN: 4, REMOVE: 7, SPLIT: 22, TECHNICAL-RETAIN-CANDIDATE: 50.

Это кандидаты миграции механизмов, не разрешение удалить функции целиком, не реализация и не утверждение об исчерпывающем транзитивном аудите. REMOVE — указанная семантическая эвристика; SPLIT — доказанная смесь конкретной семантики и перечисленных структурных guards; TECHNICAL-RETAIN-CANDIDATE — условное сохранение механизма с его границами. OPEN честно остаётся у четырёх крупных orchestration-владельцев.

JSON сохраняет все исходные поля и исторические unresolved_expressions, добавляет previous_decision/reason, полный исходник каждого владельца, проверку pins, dependency definitions или явно отмеченные call-site-only и окна статических потребителей. consumer_guards содержит конкретные локальные проверки и требуемые границы. Facade export, статическая ссылка и MRO spelling не являются доказательством выполнения. Не все implementation bindings разрешены; это явно отражено в limitations.

Сохранять: источник/проект/версия/hash/span/generation; catalog/lifecycle/scope; token/line/read bounds; user/network/index-write consent; mandatory loss → insufficient_evidence; inspection/recovery без повышения answer_supported/edit_ready; unknown/manual validation не считать pass. Удаление семантической эвристики не разрешает ослабление этих guards.

## Построчные выводы

### 1. `_ensure_selection_survives_packet` — SPLIT
Источник: `docmancer/docs/application/_action_packet_part01.py:20–115`; оба pins подтверждены.
Keep assigned evidence/unit IDs, target bindings, exact paths/versions and mandatory loss downgrade; normalized whole-packet containment and requirement_value_visible fallback are lexical proof substitutes to replace.
Статических consumer-окон: 2; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 2. `_authority_conflicts` — SPLIT
Источник: `docmancer/docs/application/_action_packet_part02.py:8–36`; оба pins подтверждены.
Keep canonical/current/path/risk/blocked-source eligibility; _extract_facts modality plus _constraint_signature prose collapse infers required/forbidden conflict, which must be separated from explicit conflict inputs.
Статических consumer-окон: 2; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 3. `_remove_one_budget_item` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_action_packet_part02.py:167–245`; оба pins подтверждены.
Budget eviction compares mandatory (text,evidence_id) identity and required target keys, records omissions and fails closed on critical/mandatory loss. Keep subsequent packet survival validation; schema field names are not semantic topics.
Статических consumer-окон: 3; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 4. `_validate_evidence_fidelity` — SPLIT
Источник: `docmancer/docs/application/_action_packet_part03.py:631–704`; оба pins подтверждены.
Keep source-row attribution, cited paths/symbols and exact guidance-byte membership; invariant/check validation reruns normative _extract_facts and must not conflate modality extraction with provenance.
Статических consumer-окон: 2; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 5. `_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_docs_context_payload.py:11–142`; оба pins подтверждены.
Facet DTO joins requirement/assignment/qualified-query IDs and strips private keys; answer_supported/answer_available/edit_ready remain false. Keep retrieval-attribution-only coverage and empty-source insufficiency.
Статических consumer-окон: 8; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 6. `project_docs_context` — OPEN
Источник: `docmancer/docs/application/_docs_context_projection_core.py:65–794`; оба pins подтверждены.
730-line projection mixes source identity/path, visible requalification, component proof, host priorities, hint fallback and replacement budgets. Local guards are established, but complete transitive replacement/fallback authority is not; preserve provenance/bounds without certifying semantic admission.
Статических consumer-окон: 2; неразрешённых implementation call sites: 17. Полные evidence и guards: соответствующая строка JSON.

### 7. `_candidate_source_view` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_evidence_selection_part01.py:454–480`; оба pins подтверждены.
Candidate metadata view preserves project/module/path and declared authority/lifecycle precedence. It performs no prose matching; active fallback is a policy default, not proof of currentness, requiring upstream valid metadata.
Статических consumer-окон: 5; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 8. `_facet_requirement_matches` — REMOVE
Источник: `docmancer/docs/application/_evidence_selection_part02.py:18–113`; оба pins подтверждены.
Hardcoded comparison/result/request/architecture/responsiveness/workflow vocabulary, sentence-distance and negation patterns grant facet coverage. Remove this semantic classifier, not exact identities or factual-only witness requirements in callers.
Статических consumer-окон: 3; неразрешённых implementation call sites: 4. Полные evidence и guards: соответствующая строка JSON.

### 9. `_reserve_and_select.mandatory_choice_key` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_evidence_selection_part02.py:443–466`; оба pins подтверждены.
Mandatory chooser ranks existing covered IDs and supplied witness completeness before authority/version/snapshot/cost/rank/stable ID. Keep budget/eligibility checks; ranking cannot manufacture missing proof.
Статических consumer-окон: 2; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 10. `_with_coverage` — SPLIT
Источник: `docmancer/docs/application/_evidence_selection_part03.py:553–680`; оба pins подтверждены.
Keep typed source/path/version/snapshot/project/module and proof-role boundaries plus bound witness materialization; facet dictionaries, qualifier regexes and entity/fallback containment infer semantic coverage and require replacement.
Статических consumer-окон: 2; неразрешённых implementation call sites: 11. Полные evidence и guards: соответствующая строка JSON.

### 11. `requirement_probe_query` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_evidence_selection_part04.py:8–40`; оба pins подтверждены.
Probe query is bounded lexical scheduling from an existing typed obligation/exact terms/comparison/code fragments. Keep 320-char bound and unsupported None; retrieval text is not evidence authorization.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 12. `_LibraryDocsApplicationServicePart01._inspection_recovery_action` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_library_docs_service_part01.py:589–627`; оба pins подтверждены.
Registered-source retry action has bounded seeds/errors, registered_source_only and no scope expansion. Keep explicit confirmation before network/index writes; the action cannot certify an answer.
Статических consumer-окон: 2; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 13. `_LibraryDocsApplicationServicePart01.resolve_docs_source` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_library_docs_service_part01.py:661–699`; оба pins подтверждены.
resolve_library supplies locator provenance input/registry and ambiguity metadata. Keep resolver validation and confirmation; has_registered_source including ambiguous is not a unique source binding.
Статических consumer-окон: 0; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.
### 14. `_LibraryDocsApplicationServicePart02._flutter_targets_for_request` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_library_docs_service_part02.py:135–156`; оба pins подтверждены.
Exact Flutter aliases/ecosystems and URL host choose predefined guide/API targets; custom templates bypass. Keep fetch scope/version validation; endpoint choice is not exact SDK snapshot proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 15. `_LibraryDocsApplicationServicePart04._bounded_library_index_witness` — SPLIT
Источник: `docmancer/docs/application/_library_docs_service_part04.py:8–117`; оба pins подтверждены.
Keep complete-manifest/root/library rejection and diagnostic-only omission status; low-value-section filter and select_evidence infer semantic witness coverage. Never upgrade support from this diagnostic probe.
Статических consumer-окон: 1; неразрешённых implementation call sites: 3. Полные evidence и guards: соответствующая строка JSON.

### 16. `_PatchConstraintsServicePart01._code_graph_constraints` — SPLIT
Источник: `docmancer/docs/application/_patch_constraints_service_part01.py:283–313`; оба pins подтверждены.
Graph edge_kinds/confidence/unresolved-only metadata are structured; path-noise filtering and generated project-convention instruction infer normative guidance. Keep graph provenance/uncertainty, not graph-to-policy authority.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 17. `_PatchConstraintsServicePart01._iter_constraint_lines` — SPLIT
Источник: `docmancer/docs/application/_patch_constraints_service_part01.py:491–529`; оба pins подтверждены.
Keep fence/table/heading/declaration structural exclusions; _source_authority and example-line/heading heuristics interpret policy/example meaning and must be separated from source spans.
Статических consumer-окон: 2; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 18. `_PatchConstraintsServicePart01._repo_artifact_examples` — SPLIT
Источник: `docmancer/docs/application/_patch_constraints_service_part01.py:547–575`; оба pins подтверждены.
Bounded glob/file enumeration mixes recognized generated artifacts with eval/task_level/results and patch-review repository priors. Keep actual artifact discovery; paths alone cannot establish edit prohibitions or evidence relevance.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 19. `_PatchConstraintsServicePart01.get_patch_constraints` — OPEN
Источник: `docmancer/docs/application/_patch_constraints_service_part01.py:17–113`; оба pins подтверждены.
Constraint packet combines architecture/generated/dependency/graph/symbol/fallback inference, actionable filters and multiple budget clamps. Full transitive authority is not reconciled; preserve pins/budget safety, leave packet-wide semantic migration unresolved.
Статических consumer-окон: 0; неразрешённых implementation call sites: 3. Полные evidence и guards: соответствующая строка JSON.

### 20. `_PatchConstraintsServicePart02._dependency_constraints` — SPLIT
Источник: `docmancer/docs/application/_patch_constraints_service_part02.py:274–313`; оба pins подтверждены.
Keep resolved/exact dependency observations and lockfile/source provenance; task-intent/relevance thresholds and generic do-not-change-lockfile instruction infer task policy. Explicit dependency-update authorization must remain separate.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 21. `_PatchConstraintsServicePart02._is_broad_acronym_symbol_candidate` — REMOVE
Источник: `docmancer/docs/application/_patch_constraints_service_part02.py:586–590`; оба pins подтверждены.
3–5 uppercase acronym shape and unequal symbol spelling reject task-term candidates without declaration proof. Remove ambiguity heuristic; preserve exact declaration/source validation elsewhere.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 22. `_PatchConstraintsServicePart02._symbol_candidate_constraints` — REMOVE
Источник: `docmancer/docs/application/_patch_constraints_service_part02.py:607–622`; оба pins подтверждены.
Term-to-symbol confidence becomes source_of_truth/project_convention plus prefer-reuse advice. Remove normative authority/advice inference; retain source-attributed discovery candidates.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 23. `_PatchConstraintsServicePart02._symbol_from_line` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_constraints_service_part02.py:551–575`; оба pins подтверждены.
Call/declaration regexes extract candidate symbols, excluding control words and generic calls. Keep as lexical discovery only; consumer must verify declaration/source before claiming semantic equivalence or owner authority.
Статических consumer-окон: 1; неразрешённых implementation call sites: 2. Полные evidence и guards: соответствующая строка JSON.

### 24. `_PatchConstraintsServicePart03._dependency_source` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_constraints_service_part03.py:133–150`; оба pins подтверждены.
Structured version_source/ecosystem chooses manifest/lock locator, preferring existing lockfile. Keep diagnostic fallback; guessed locator cannot replace actual version observation evidence.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 25. `_PatchConstraintsServicePart03._most_relevant_lockfile` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_constraints_service_part03.py:124–130`; оба pins подтверждены.
Present lockfile is chosen by changed basename then deterministic ecosystem order. Preserve actual membership and downstream dependency observation validation; ordering proves no exact version.
Статических consumer-окон: 1; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 26. `assignment:ARCHITECTURE_DOC_RE` — REMOVE
Источник: `docmancer/docs/application/_patch_constraints_service_shared.py:104–107`; оба pins подтверждены.
Architecture/README/ADR/contributing filename regex feeds architecture-rule extraction. Remove filename-to-authority/document-role inference; retain explicitly catalogued/configured source discovery.
Статических consumer-окон: 4; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 27. `assignment:EXCLUDED_SOURCE_PARTS` — SPLIT
Источник: `docmancer/docs/application/_patch_constraints_service_shared.py:124–145`; оба pins подтверждены.
Excluded parts mix .git/venv/node_modules/build/cache technical traversal limits with eval/fixtures/oracles/hidden_tests/results/workspaces evidence priors. Keep storage/artifact boundaries, replace benchmark-directory semantic exclusions.
Статических consumer-окон: 4; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 28. `assignment:NON_ACTIONABLE_CONSTRAINT_HEADING_RE` — REMOVE
Источник: `docmancer/docs/application/_patch_constraints_service_shared.py:112–117`; оба pins подтверждены.
English rules/constraints/requirements/notes/guidelines grammar suppresses non-actionable candidates. Remove language-specific semantic heading classifier, not Markdown heading recognition.
Статических consumer-окон: 4; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 29. `_PatchReviewServicePart01._constraint_coverage_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_review_service_part01.py:428–466`; оба pins подтверждены.
Report groups existing constraint IDs/validation statuses and counts, explicitly avoids correctness/test replacement/unknown-as-pass. Keep unknown/manual distinct; category labels are report schema, not admission.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 30. `_PatchReviewServicePart01._review_summary_bot_bundle_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_review_service_part01.py:529–562`; оба pins подтверждены.
Bot bundle serializes existing artifacts and advisory decision with schema/source names. Keep non-blocking avoided claims; attachment is not correctness or mutation approval.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 31. `_PatchReviewServicePart01._review_summary_pr_comment_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_review_service_part01.py:320–374`; оба pins подтверждены.
PR comment formats existing violations/signals/checklist with escaping/truncation and explicit non-blocking disclaimer. Keep upstream statuses; literal headings/artifact names make no proof decision.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 32. `_PatchReviewServicePart02._actionable_item_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_review_service_part02.py:193–220`; оба pins подтверждены.
Actionable item projection preserves source/confidence/instruction and optional validation result with Markdown escaping. Keep unknown states/attribution; formatting does not prove instruction validity.
Статических consumer-окон: 0; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 33. `_PatchReviewServicePart02._review_summary_actions_payload` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_patch_review_service_part02.py:144–190`; оба pins подтверждены.
Action report serializes upstream model/ranked items/violations and avoided claims. Keep advisory-only contract; upstream ranking is a separately audited dependency.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 34. `_PatchReviewServicePart02._summary_constraint_rank` — SPLIT
Источник: `docmancer/docs/application/_patch_review_service_part02.py:402–430`; оба pins подтверждены.
Keep explicit type/confidence/changed-source report keys; generated/lockfile/policy/provider/UI vocabulary and dogfood-directory penalty are semantic/topic priors. Ranking must remain advisory, never validator authority.
Статических consumer-окон: 0; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 35. `_ProjectContextServicePart01.get_project_context` — OPEN
Источник: `docmancer/docs/application/_project_context_service_part01.py:17–865`; оба pins подтверждены.
Large project orchestrator joins mutation parsing/routing/trust/selection/rescue/confirmation/delivery. Rescue span/hash/scope checks are visible, but all transitive selectors and answer routes are not certified. Keep operational/trust boundaries; OPEN is not removal approval.
Статических consumer-окон: 0; неразрешённых implementation call sites: 109. Полные evidence и guards: соответствующая строка JSON.

### 36. `_qualify_same_atom_continuations` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_project_docs_continuations.py:47–99`; оба pins подтверждены.
Qualified canonical probe propagates only through structured source/parent-contiguous continuation route with derived coverage and cleared matched terms. Keep no public/original query coverage and downstream body requalification; provenance is not semantic proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 37. `_ProjectDocsServicePart01._project_docs_preflight_next_action` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_project_docs_service_part01.py:207–231`; оба pins подтверждены.
Preflight action projects existing risk codes/sync args and explicitly requires user confirmation before reconciliation. Keep confirmation; tool/action fields are operational protocol.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 38. `_ProjectDocsServicePart01._unsupported_root_doc_files` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_project_docs_service_part01.py:278–310`; оба pins подтверждены.
Root file/extension checks report unsupported ingest formats, not answer relevance. Keep file-only/root-relative/supported-extension exclusions and convert-or-confirm guidance; no automatic ingest consent.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 39. `_ProjectDocsServicePart01.ingest_project_docs._verified_state` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_project_docs_service_part01.py:658–668`; оба pins подтверждены.
Discovered paths reconcile with current/stale index partition to enumerate missing paths. Keep content/catalog freshness in partition dependency; membership is state bookkeeping, not semantic absence proof.
Статических consumer-окон: 2; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 40. `_ProjectDocsServicePart02.bootstrap_project_docs` — SPLIT
Источник: `docmancer/docs/application/_project_docs_service_part02.py:481–608`; оба pins подтверждены.
Keep initial/post-sync confirmation, allow_sync and structured readiness codes; dependency_mentioned_in_question interprets task meaning to trigger prefetch. Replace semantic trigger without weakening consent/network gates.
Статических consumer-окон: 0; неразрешённых implementation call sites: 6. Полные evidence и guards: соответствующая строка JSON.

### 41. `_ProjectDocsServicePart03.query_project_docs` — SPLIT
Источник: `docmancer/docs/application/_project_docs_service_part03.py:136–420`; оба pins подтверждены.
Keep source filters/lifecycle/dedup/token limits; canonical_intent/concept_alias/fail_closed_workflow scheduling and continuation propagation are semantic recall policies. Recall must not become public coverage without qualification.
Статических consumer-окон: 1; неразрешённых implementation call sites: 9. Полные evidence и guards: соответствующая строка JSON.

### 42. `assignment:PLACEHOLDER_PROJECT_DOC_RE` — REMOVE
Источник: `docmancer/docs/application/_project_docs_service_shared.py:53–57`; оба pins подтверждены.
TODO/TBD/WIP/placeholder/coming-soon/sample-code literals classify document incompleteness. Remove language/sample-specific semantic risk inference; retain explicit format/hash/catalog checks and confirmation.
Статических consumer-окон: 4; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 43. `SourceContinuationReader.read` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_source_continuation_core.py:142–197`; оба pins подтверждены.
Opaque cursor is consumed once under lock; expiry, authorization before/after read, snapshot SHA256 and line/token/read limits guard continuation. Preserve all capability/policy checks; statuses are operational protocol.
Статических consumer-окон: 0; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 44. `_UnifiedDocsContextServicePart01.get_docs_context` — OPEN
Источник: `docmancer/docs/application/_unified_context_service_part01.py:58–580`; оба pins подтверждены.
Unified mixed lanes join mode/network consent, trust/snippets, support aggregation and delivery. Missing canonical lane fails closed locally, but dispatch/MRO and semantic aggregate prerequisites are not fully resolved; no whole-owner retention approval.
Статических consumer-окон: 0; неразрешённых implementation call sites: 8. Полные evidence и guards: соответствующая строка JSON.

### 45. `_UnifiedDocsContextServicePart02._can_return_partial_project_context` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_unified_context_service_part02.py:570–577`; оба pins подтверждены.
Partial indexed-context exception requires exact preflight reason and nonempty risk subset only placeholder_project_doc. Keep rejection of all other risks/no support promotion; upstream lexical placeholder classifier is independently REMOVE.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 46. `_UnifiedDocsContextServicePart02._dependency_prefetch_guidance` — SPLIT
Источник: `docmancer/docs/application/_unified_context_service_part02.py:246–278`; оба pins подтверждены.
Keep dependency missing/stale state counts and explicit ask-before-network guidance; question-based dependency ranking is semantic recommendation. Preserve include_packages bounds and consent while replacing relevance priority.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 47. `_UnifiedDocsContextServicePart02._library_context_pack` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/_unified_context_service_part02.py:319–357`; оба pins подтверждены.
Library lane projection preserves source/library/version/exactness/freshness and binds selected IDs only on count agreement. Keep upstream source/version rejection; why_selected text is descriptive, not canonical evidence.
Статических consumer-окон: 2; неразрешённых implementation call sites: 2. Полные evidence и guards: соответствующая строка JSON.

### 48. `_declared_authority_by_path` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/action_packet.py:51–67`; оба pins подтверждены.
_effective_authority requires declared enums, scoped agent/module policy and active valid source_of_truth catalog, with explicit legacy project_rule fallback. Keep scope/catalog checks; normalized path map is not authority proof and legacy fallback remains a policy caveat.
Статических consumer-окон: 1; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 49. `assignment:_DESTRUCTIVE_UNRESOLVED_RE` — REMOVE
Источник: `docmancer/docs/application/action_packet.py:26–29`; оба pins подтверждены.
English/Russian delete/drop/remove/erase/purge regex infers destructive mutation from unresolved text. Remove semantic intent dictionary, not explicit typed mutation operations/targets or fail-closed confirmation.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 50. `prepare_delivery_inventory` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/context_variant_retention.py:30–62`; оба pins подтверждены.
Prepared inventory requires exact raw reference text and integer char_start, then delegates to bounded block/requalification owner. Keep hash/span/current source ownership; a callable requalifier is not automatically trusted admission.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 51. `flutter_docs_url_for` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/dependency_resolution.py:22–26`; оба pins подтверждены.
Explicit main/master channel maps to main API endpoint, otherwise normal API endpoint. Keep project-version warning/binding outside helper; default endpoint is not exactness proof.
Статических consumer-окон: 3; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 52. `project_version_for` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/dependency_resolution.py:63–203`; оба pins подтверждены.
Parsed ecosystem/source_kind/resolved-version observations bind registry docs; path/git/direct URLs fail exactness and Flutter channel mapping warns/returns false. Keep no-version/no-docs outcomes and do not promote approximate binding.
Статических consumer-окон: 1; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 53. `DocsJobTracker.update` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_job_service.py:441–467`; оба pins подтверждены.
Job update locks state, durable path checks expected lease, terminal/running transitions stamp timestamps. Keep lease/history pruning; status enums are operation states, not prose inference.
Статических consumer-окон: 4; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 54. `project_job_diagnostic` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_job_service.py:111–145`; оба pins подтверждены.
Typed job diagnostic projects counts/timestamps, bounded failure list and vector allowlisted fields. Keep operational-only interpretation; indexing success is not answer proof.
Статических consumer-окон: 5; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 55. `DocsManifestService.prefetch_docs_manifest` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_manifest_service.py:184–228`; оба pins подтверждены.
Sync manifest prefetch validates before fetching and writes lock only for nonfailed/nonaborted results; async dispatches worker. Keep manifest/fetch validation and caller network authorization; completion statuses are technical.
Статических consumer-окон: 0; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 56. `DocsPrefetchService.progress_callback_for._callback` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_prefetch_service.py:67–90`; оба pins подтверждены.
Progress callback updates attributed target/page counters and event telemetry through job tracker. Preserve lease-aware updates; phase/message values do not establish indexed evidence validity.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 57. `DocsTargetService.discover_pub_dartdoc_target` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_target_service.py:475–528`; оба pins подтверждены.
Dartdoc discovery uses scoped DocsHttpClient, allowed hosts/path prefixes, no redirect/env trust, rethrows nontransport security errors. Keep security/fallback warnings; query seed ranking schedules fetch only, not evidence support.
Статических consumer-окон: 0; неразрешённых implementation call sites: 5. Полные evidence и guards: соответствующая строка JSON.

### 58. `DocsTargetService.target_from_record` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/docs_target_service.py:169–194`; оба pins подтверждены.
Stored target reconstruction preserves explicit locator-key presence, allowed domains/path prefixes and version/coverage policy. Keep downstream record/fetch validation; default fields are not scope authorization.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 59. `IndexStorageCleanup` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/index_storage_cleanup.py:54–496`; оба pins подтверждены.
Cleanup enforces exact config scope/ownership/root containment, preview digest/fingerprints, writer/process blockers, quarantine rollback and incomplete-state consent. Preserve all safety guards; storage directory/status names are technical ownership protocol.
Статических consumer-окон: 3; неразрешённых implementation call sites: 33. Полные evidence и guards: соответствующая строка JSON.

### 60. `inspection_recovery_seeds` — SPLIT
Источник: `docmancer/docs/application/inspection_recovery_seeds.py:7–59`; оба pins подтверждены.
Keep current project/source snapshot, no hard-stop/explicit-path/component bypass and no parent coverage; mixed_script_phrases/requalification decide hint eligibility. Separate mixed-script semantic restriction from bounded inspection authorization.
Статических consumer-окон: 1; неразрешённых implementation call sites: 2. Полные evidence и guards: соответствующая строка JSON.

### 61. `_context_row` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/joint_context_candidates.py:39–82`; оба pins подтверждены.
Exact contiguous source bytes/owner span are rebound and reference/project/lifecycle policies rerun; supplementary rows clear assignment/query IDs. Keep provenance and downstream admission; larger context does not expand proof automatically.
Статических consumer-окон: 7; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 62. `_finish` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/joint_context_selection.py:42–82`; оба pins подтверждены.
Private clones finalize quality/readers, compact labels for budget and retain unread obligations only for matching project/path/snapshot. Failed retention returns None; preserve no issued-capability mutation and register only winning DTO.
Статических consumer-окон: 2; неразрешённых implementation call sites: 5. Полные evidence и guards: соответствующая строка JSON.

### 63. `seed_envelopes` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/joint_seed_envelopes.py:13–56`; оба pins подтверждены.
Verified envelopes group by project/path/snapshot/catalog/version/owner, equal raw bytes and bounded parent count, expanding contiguous structural atoms via guarded _context_row. Keep provenance; prose atom is structure, not semantic proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 64. `LibraryIngestOrchestrator._run_prefetch_docs_job` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/library_ingest_orchestrator.py:197–329`; оба pins подтверждены.
Worker validates generation/cancellation/deadline around fetch and commit, forwards staging owner, maps structured result counts/status. Preserve begin_commit and cancellation guards; operation success is not support.
Статических consumer-окон: 1; неразрешённых implementation call sites: 3. Полные evidence и guards: соответствующая строка JSON.

### 65. `LibraryRefreshOps.prefetch_docs` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/library_refresh_ops.py:762–815`; оба pins подтверждены.
Prefetch forwards refresh versions/default latest and cancellation/deadline/staging hooks, warning on latest default. Keep downstream fetch/version validation; latest never proves exact project pin.
Статических consumer-окон: 0; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 66. `LibraryRefreshOps.refresh_record._sync_vectors_before_commit` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/library_refresh_ops.py:364–406`; оба pins подтверждены.
Staged vector synchronization runs only for dense/sparse/hybrid and requires non-None result plus success metrics; catches failure for outer commit decision. Preserve fail-closed publication; lexical-mode exemption is operational.
Статических consumer-окон: 1; неразрешённых implementation call sites: 6. Полные evidence и guards: соответствующая строка JSON.

### 67. `refresh_failure_code` — SPLIT
Источник: `docmancer/docs/application/library_refresh_policy.py:23–38`; оба pins подтверждены.
Typed security/HTTP exceptions give technical failure categories; final extract substring guesses extraction/indexing phase from message. Keep typed taxonomy, replace text guess; failure codes cannot grant evidence support.
Статических consumer-окон: 2; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 68. `LibraryRegistryOps.prune_library_docs` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/library_registry_ops.py:381–419`; оба pins подтверждены.
Prune filters library/keep versions and age/status, defaults dry_run and invokes guarded removal only on apply. Preserve destructive consent/registry ownership; malformed timestamp treating record as oldest is an explicit safety caveat.
Статических consumer-окон: 0; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 69. `_npm_candidates` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/library_source_discovery.py:204–228`; оба pins подтверждены.
Npm registry homepage/repository metadata form deduped discovery candidates through safe-public URL/repository normalization. Preserve fetch security/version attribution; locator confidence is not canonical proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 70. `_answer_text` — SPLIT
Источник: `docmancer/docs/application/model_visible_projection.py:903–934`; оба pins подтверждены.
Keep quoted answer containment in projected sources, cited IDs and require_all_sources; _needs_actionable_limitation applies question/snippet regexes as semantic sufficiency. Separate actionable inference from exact quote attribution.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 71. `_docs_source` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/model_visible_projection.py:845–873`; оба pins подтверждены.
Source DTO enforces path/section/snippet/version lengths and computes digest-based identity. Preserve downstream snapshot validation; digest/ID construction alone does not prove provenance.
Статических consumer-окон: 5; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 72. `project_patch_context` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/model_visible_projection.py:535–619`; оба pins подтверждены.
Validated patch flattening binds raw evidence; edit_ready requires valid packet, mutation readiness and no mandatory omissions. Token overflow returns insufficient, never silently discards selected proof. Keep all readiness/snapshot boundaries.
Статических consumer-окон: 1; неразрешённых implementation call sites: 14. Полные evidence и guards: соответствующая строка JSON.

### 73. `_probe` — SPLIT
Источник: `docmancer/docs/application/need_context_disposition.py:38–47`; оба pins подтверждены.
Probe preserves typed need subject/relation/context/hard_exact; query_constraint_roles/documentation_query_terms add lexical role/token interpretation. Keep occurrence/exact identity while separating semantic inference from query metadata.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 74. `project_need_context_fallback` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/need_context_projection.py:174–185`; оба pins подтверждены.
Fallback emits first upstream-prepared variant with decision/payload/snapshot binding. _payload keeps answer/edit false. Preserve upstream variant admission; context presence is not proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 75. `PatchConstraintValidationService._is_generated_path` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/patch_constraint_validation_service.py:251–254`; оба pins подтверждены.
Explicit generated glob patterns match normalized path/basename for artifact protection. Keep consistent configured patterns and explicit task overrides in consumers; filename alone cannot establish normative rule authority.
Статических consumer-окон: 7; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 76. `ProjectDocsState.indexed_project_doc_sources` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/project_docs_state.py:22–72`; оба pins подтверждены.
Scoped SQL projects project_file/project_docs records for resolved root and config-hash chunking freshness. Preserve actual file/catalog/lifecycle verification downstream; persisted rows alone do not attest current evidence.
Статических consumer-окон: 0; неразрешённых implementation call sites: 3. Полные evidence и guards: соответствующая строка JSON.

### 77. `ProjectSectionIndexReader.read` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/project_section_index.py:34–104`; оба pins подтверждены.
Bounded SQLite/JSON read verifies safe project file, indexed/current hash, section schema and parse status/reason pairing. Current requires all checks; preserve stale distinctions and fail-empty read behavior.
Статических consumer-окон: 0; неразрешённых implementation call sites: 2. Полные evidence и guards: соответствующая строка JSON.

### 78. `bridge_options` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/query_block_bridge.py:9–51`; оба pins подтверждены.
Bridge permits only heading/whitespace gaps, rebinds exact document bytes and requalifies visible body; rejects loss of qualified IDs. Keep no disjoint omission/no issued-resource mutation and reference policies; requalification is independent semantic owner.
Статических consumer-окон: 1; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 79. `select_query_block_recovery` — SPLIT
Источник: `docmancer/docs/application/query_block_recovery.py:22–128`; оба pins подтверждены.
Keep inspection-only flags, verified snapshot/range/reference/policy, token bounds and final validator; question-driven ranked_blocks chooses read target. Separate relevance ranking from evidence sufficiency and preserve issued-capability restrictions.
Статических consumer-окон: 1; неразрешённых implementation call sites: 4. Полные evidence и guards: соответствующая строка JSON.

### 80. `build_recovery_diagnosis` — SPLIT
Источник: `docmancer/docs/application/recovery.py:195–354`; оба pins подтверждены.
Keep operational recovery codes, documentation_supported=false and authoritative-conflict hard stop. Requirement reconstruction/recognized spans/generated rephrase patterns interpret meaning. Replace semantic rephrase heuristics without granting recovery answer support.
Статических consumer-окон: 2; неразрешённых implementation call sites: 0. Полные evidence и guards: соответствующая строка JSON.

### 81. `_tag_retrieval_query` — SPLIT
Источник: `docmancer/docs/application/reference_query_tagging.py:11–90`; оба pins подтверждены.
Keep normalized exact path and retrieval lineage/derived-parent audited rewrite checks; query roles/terms, qualify_evidence and local-witness adapter decide semantic qualification. Preserve source/project/lifecycle guards; adapter only vetoes already-qualified traces.
Статических consumer-окон: 10; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.

### 82. `retrieval_need_local_witness` — SPLIT
Источник: `docmancer/docs/application/retrieval_need_support.py:82–114`; оба pins подтверждены.
Typed obligation/relation and subject-owner binding meet proof primitives plus English if/when enabled/disabled comma-consequent regex. Keep local provenance and tri-state unsupported model; replace behavior-shape semantic veto/sufficiency and never convert None into proof.
Статических consumer-окон: 1; неразрешённых implementation call sites: 2. Полные evidence и guards: соответствующая строка JSON.

### 83. `SourceReferenceContext.prepare` — TECHNICAL-RETAIN-CANDIDATE
Источник: `docmancer/docs/application/source_reference_evidence.py:99–181`; оба pins подтверждены.
Reference preparation requires exact bytes/digests/canonical path/current or verified embedded generation and at most one owner. No snapshot gives body-only fallback; dependency records are verified-source proposals, not independent semantic authority. Keep all span/hash/generation checks.
Статических consumer-окон: 0; неразрешённых implementation call sites: 1. Полные evidence и guards: соответствующая строка JSON.
