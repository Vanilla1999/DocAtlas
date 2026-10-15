# Callable residual dictionary exit — R6–R10

2026-10-07. Dedicated worktree:
`/tmp/opencode/docatlas-final-callable-helpers-42c72bd6`.
Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
Прочитан полный FINAL_DICTIONARY_EXIT_INVENTORY_RU.md, включая R6–R10 и §3.
**Allocated cleanup выполнен; full EXIT / release acceptance НЕ подтверждены.**

## 1. Изменения и ограничения

Только 13 выделенных production-файлов + новый behavioral test, отдельный
diagnostic shard и этот checkpoint. Frozen tests/registries/gold/thresholds,
historic reports, selector/qualification/normative/action-packet allocation,
source boundary defaults и security negative patterns не изменены.
Нет commits/push, network requests, subagents или primary changes.

- R6: удалены subject/anaphora/cause/definition NL edges. Prose nodes и source
  bytes остаются. Examples/Aliases больше не исключают Markdown list members.
  Heading/list/table syntax, cached immutable graph, exact source/window hashes,
  list sibling closure и caller ceilings ≤2 hops/≤8 spans остаются. Отсутствие
  NL edge не доказывает независимость или полноту потребности.
- R7: `_state_condition` → None, `_need_obligations` → (). Legacy relations
  exception/requirement/behavior дают unknown witness, а не invented obligation.
  Реальный default hook, fresh-True-only adapter, cleanup inherited metadata,
  immutable input trace и non-need passthrough сохранены. Unknown veto не ослаблен.
- R8: удалён `reference_intent_match:+7`; `_has_reference_intent` → False.
  Parser/reference edges, exact literal credit, confidence и budgets сохранены.
  Inventory probe RelayClient и use RelayClient теперь оба score=2.5.
- R9: prose list grammar больше не создаёт public requirements и не удаляет все
  chunks. `_explicit_library_query_analysis` — ABI-only `([], False)`, не complete
  request certificate. Original topic передаётся в retrieval без replacement;
  literal public requirements и supplied contract argument сохранены. Baseline
  index-generated `library_requirement_contract` НЕ стал новой authority.
  Copy/translation labels и prefixes больше не удаляют source lines. RST module/
  function/class syntax, literal symbols, oversized-source rejection/excerpt hash,
  version/source guards и MMR/budgets остаются. Refresh/rephrase guidance заменён
  bounded inspection; consent/network access не равны lifecycle authorization.
- Переданный единолично library_source_discovery.py: PyPI project_urls теперь
  сортируются по URL, label только display data, все confidence=medium. Никакого
  docs/reference/home label bonus. URL safety/identity/version/confirm decisions
  сохранены. npm exact registry field grammar не переписывался.
- R10: cardinality только явные digits 1..32; number-word table пустая. Patch NL
  operation/preserve/acceptance/rename grammar удалена; `_operation` → none,
  public builder остаётся negative ABI. DTO/hash/bounds и literal path/symbol
  coordinates/commas остаются; typed consumer mutation guards не изменены и DTO
  не выдаёт authorization. Legacy coverage всегда explicit unresolved, включая
  прежнюю hardcoded recall/authority exception; empty obligations отдельно veto.
  Dormant negative helpers и `_NEGATION_RE` дают равномерный negative guard без
  NL classification; narrow typed literal equality/source hashes остаются positive.
  `_needs_actionable_limitation` всегда True: ни prose, ни code-looking answer
  не снимают limitation. Source quotations и projection budgets не переписывались.

## 2. Новые проверки и actual runs

Новый `tests/test_dictionary_exit_callable_residuals.py`: 17 base functions,
45 parametrized cases. Реальные inventory inputs, source/hash/span validation,
list closure/table syntax/caps, adapter input immutability/default hook, exact
code-reference score, original library caller topic/context with unresolved answer,
source UI quotes, positive bounded RST excerpt hash, URL ranking/confirmation,
digits limits, negative patch ABI + typed DTO, legacy exception rejection,
uniform negative helpers и narrow typed literal equality.

Normal repository conftest, outbound-network blocker и diagnostic inventory;
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`, `-p no:cacheprovider`, никаких
`--noconftest`, expectation rewrites или floor waivers.

1. Новый module отдельно: **45 passed**, 0.68s. После добавления excerpt/hash
   assertions тот же module также прошёл в all-run ниже.
2. Все `tests/test_dictionary_exit_*.py` плюс
   `tests/docs/test_mcp_token_footprint.py`, `tests/docs/test_mcp_boundary.py`,
   `tests/docs/test_finalized_mcp_output_integrity.py`,
   `tests/test_support_surface_policy.py`, `tests/docs/test_target_security.py`,
   `tests/docs/test_content_trust.py`: **1721 passed / 6 failed / 1 existing
   multipart warning**, 7.33s. Это inventory 1676/6 +45 новых passes, не full CI.
3. Relevant old mixed modules (ниже): **148 passed / 92 failed**, final 1.38s.
   Контроль baseline посредством in-memory import loader: только 13 выделенных
   модулей загружены через `git show 42c72bd6:path`, файлы не восстанавливались и
   не переписывались; тот же normal pytest/conftest: **154 passed / 86 failed**.
   Итого +6 red, 0 resolved baseline red. Это targeted baseline comparison, не
   полный clean-worktree release run.

Relevant old modules и failure counts baseline→current:

| tests/docs module | baseline | current |
|---|---:|---:|
| test_evidence_set_dependencies.py | 0 | 4 |
| test_evidence_set_disposition.py | 5 | 5 |
| test_code_graph.py | 1 | 2 |
| test_code_graph_golden.py | 1 | 1 |
| test_library_docs_service.py | 0 | 0 |
| test_library_source_discovery.py | 0 | 1 |
| test_model_visible_projection.py | 25 | 25 |
| test_model_visible_projection_part02.py | 11 | 11 |
| test_patch_request_plan.py | 24 | 24 |
| test_answer_units_v2.py | 7 | 7 |
| test_answer_units_v3.py | 12 | 12 |

Новые old-test reds: `test_declared_relations_have_actual_source_endpoints`
три parametrizations definition/anaphora/cause, `test_dependency_hop_limit_is_applied_to_real_closure`,
`test_build_code_graph_context_items_selects_screen_for_cubit_reference`,
`test_python_discovery_prefers_pypi_documentation_metadata`. Это прежние NL edges,
reference-intent rank и label-confidence expectations; **не waived/green**.

Сохранён exact all-run ledger (первые пять — old dictionary-exit reds):

1. `tests/test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
2. `tests/test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables`
3. `tests/test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance`
4. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]`
5. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]`
6. `tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`

Exploratory new-test runs: сначала diagnostic shard отсутствовал/затем hash был
ошибочно рассчитан по parametrized IDs вместо base IDs; это collection errors,
не passes. Затем два неверных fixture assumptions (index-generated contract как
authority и oversized unrelated source как bounded excerpt) исправлены только
в новом тесте. Uniform negative ABI pattern исправил промежуточный old helper
red без vocabulary detector. Предварительный delta printer имел newline mismatch;
повторный normalized comparison подтвердил ровно шесть новых reds. Не скрывать
эти попытки как successful acceptance.

## 3. Exact extraction inventory и SHA-256

Production diff: **13 files, +44/-774**.
`git diff --binary 42c72bd6 -- docmancer` SHA-256:
`c2fdf7e4d1297a5e45bc4e909ab9d2cc1b4fddeea281bd8c0450d048c750bae2`.
Пути ниже относительны dedicated worktree; каждый hash — полный final file hash.

| File | SHA-256 |
|---|---|
| docmancer/docs/application/_library_docs_service_part03.py | ee39430efb34137b30186ffbb0c1a2b9a92c17d2c983602d9184d0f187499b04 |
| docmancer/docs/application/_library_docs_service_shared.py | 8d1a13e3acafb512a71eb39c9fe82fb13e5e1e86a67d1a42a0461ffcdfe9a03d |
| docmancer/docs/application/library_source_discovery.py | cfba1656a4acfa696c401d4bc22e18690f98334a1a31979aa03d832307b33d12 |
| docmancer/docs/application/model_visible_projection.py | 76fa3c0194784f6597de2052c383eec333ef8511b370f1fa685710f56c35d089 |
| docmancer/docs/application/retrieval_need_support.py | 948ae91f89f1efe49f20cceee496b7bcb05112fcc97ab7130ea0a8f17fb488ef |
| docmancer/docs/domain/_answer_units_part02.py | 807987c2b165f25a4b1ee5fede241cc65ac48bf91ac7ae0eefade00369b1f8bf |
| docmancer/docs/domain/_answer_units_shared.py | 235186478b21fc7a717db4e39f7e924548de9bad7c9d32d92ccc79c574dde443 |
| docmancer/docs/domain/_code_graph_part02.py | f9d30740c3d44febc8bc88e3a8a9b3700285c2c6d9b207508c2c3a79ac0f5992 |
| docmancer/docs/domain/_project_answer_contract_part01.py | 95437dfcc68bb1b3c95a36ea4ed2be42293bcef5646fd1e98991f9b5b2d74988 |
| docmancer/docs/domain/_project_answer_contract_shared.py | b99965cb91486c06116c06c4e5e8c80a584da915d5ca3ebb7351cdc29b96780e |
| docmancer/docs/domain/legacy_question_coverage.py | e6b3dcde6fe7779b14427139a6829acc037ba73df308f419d8664c273fd48431 |
| docmancer/docs/domain/patch_request_plan.py | 4171dbf13ebbbbf37b2b6ca591b1734f721ca74ec6496d4fb8a15e27e048f56a |
| docmancer/docs/domain/source_dependency_graph.py | e2f64b2e5ba7b6f87387dd6cd776faba58790842dde544a2c459e13536ee3959 |
| tests/test_dictionary_exit_callable_residuals.py | b4aa1e18de701d3311458d0a18f76168bd9de94f7792a5f4a7da1781ca23a75b |
| tests/diagnostic_labels.dictionary_exit_callable_residuals.json | 6d63aa1d747ac347c81792d5372c390473d313bce89b769fc9140235f79118cb |

Шестнадцатый extraction file — этот checkpoint; его hash возвращается parent
отдельно, без self-referential file hash. Diagnostic base-node inventory hash:
`254a26168e2278859bdf35a9d1b5f14b16cb4b18a15b21acabf0809a72aa15e4`.

## 4. Dependencies / blocked / не заявлено

Selector/qualification/normative/action packet R2–R5 — другой worker, здесь не
интегрирован и не approved. Corpus/local allocations не изменены; их concurrent
results не certified. Integration parent должен проверить shared consumers вместе,
не возвращать unknown passthrough ради старого red. New library context-only
caller tests не означают support/edit grant.

R11/R12 source membership defaults и security negative detectors (§3 inventory)
остаются blocked pending explicit finite source/negative-policy decision. Никакого
расширения corpus/scanning или разрешения execute по отсутствию detector findings.
Old semantic quality failures не waived; нет full CI/self-host quality rerun,
stdio transport, indexed corpus/wheel/installed copies/client caches/release
verification. No full release/EXIT claim.
