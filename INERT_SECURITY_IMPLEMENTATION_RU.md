# Inert security — bounded implementation, НЕ full EXIT

2026-10-07. Worktree `/tmp/opencode/docatlas-resumed-inert-ee156cba`.
Baseline `ee156cba4cc6dd4bf51c0e2c8adf44907aac9633`.
Прочитан committed `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/FINAL_INTEGRATED_EXIT_AUDIT_RU.md`.
Старые vanished proposals не использовались как доказательство реализации.

**Результат:** реализованы non-authorizing consumer barriers в owned surfaces.
**Independent parent review: PENDING. NL detectors: RETAINED. Full EXIT/security/quality acceptance: NO.**
Нет broker, issuer authentication/key manager, новых execution capabilities,
dispatcher, commit/push, live HTTP/DNS/providers, reinstall или index rebuild.
Чужие production/test/gold/frozen assertions не менялись. `.venv` — существующий
untracked shared link, не создан/изменён этим slice; dependencies не устанавливались.

## Реальная consumer chain

1. `content_trust.annotate_context_pack` и `source_trust_dimensions` всегда дают
   `instruction_trust=untrusted_data`, включая canonical docs, AGENTS/CLAUDE,
   JSON, source comments и caller-supplied trust/content-boundary claims.
   Original content/document_data сохраняется. Policy filename/root/scope остаются
   path attribution (`scoped_repository_document`), не authenticated grant.
   `scope_verified` означает только path scope; outside-root policy path не verified.
2. `_action_packet_part01._effective_authority` больше не повышает raw
   `explicit_agent_policy` через scope; `_source_row` принудительно inert.
   Canonical source attribution для иных evidence lanes не становится permission.
   `_action_packet_part02._may_guide_workflow` всегда False: issuer/consent bool,
   fake host URI, пустые/unknown risk flags, canonical label ничего не разрешают.
3. ActionPacket schema и actual `validate_action_packet` допускают только
   `untrusted_data`; document-sourced policy rows и любые workflow checks
   отвергаются даже без переданного evidence_items. Typed request constraints
   и существующие hash/span/target checks не заменяются новой authentication fiction.
   `_extract_facts` уже пустой в baseline; положительная prose semantics не возвращалась.
4. `normalize_candidates` удаляет fake `host-policy://` exception из indexed
   project identity checks. Metadata/scope не освобождают от stable child,
   parent/hash/span validation. Literal display bytes/version сохранены.
5. Public SDK `project_patch_context` сам вызывает packet validator, а не
   полагается на предварительный MCP validation. Invalid policy/workflow packet
   даёт bounded insufficient result. `mutation_ready` остаётся typed intent
   resolution; `edit_ready=False` всегда, включая insufficient result.
   Projection validator запрещает edit promotion до early insufficient return,
   а также scoped-policy trust/workflow checks в successful patch contexts.
   Source snapshot/digest and cited quote mechanics сохраняются.
6. MCP raw compactors не echo-ят `edit_ready=True`. Public handler остаётся
   retrieval-only: wire kind/consent/issuer/mutation metadata не проходят как SDK
   mutation intent; network/bootstrap flags принудительно False. Typed top-level
   actions маркированы advisory, не authorization. Existing lifecycle/consent
   dispatch не изменён и не объявлен доказанным этим slice.
7. Empty trust contract больше не выдаёт `discovery_only` как permission:
   `direct_webfetch=forbidden` независимо от selected sources. Trust precedence
   больше не выделяет retrieved repository policy в instruction tier.

## Почему NL veto не удалены

Actual owned consumers проверены bounded tests, но independent parent review ещё
не выполнен; out-of-ownership SDK DTO aggregation и installed/current artifacts
не доказаны. По D2 retain-veto contract оставлены `_RISK_PATTERNS`, dangerous
content patterns, risk eligibility checks. Отсутствие detector hit НЕ permission.
Нет all-trusted default. Availability loss от retained veto честно остаётся:
некоторые quoted instruction-like spans могут по-прежнему быть исключены.
`pipeline/filtering.py` неизменён: login/account/signup, archive/media/font formats,
literal segment/HTTP/credentials/path escape guards — endpoint restrictions,
не NL trust taxonomy. Transport/DNS/finite membership не изменялись.

## Offline execution / normal conftest

Все runs: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q`.
Новый reviewed diagnostic shard добавлен отдельно, primary manifest не изменён.
Первый run до shard: collection ERROR `diagnostic_unclassified`; barrier не обходился.
Собственные fixture corrections (estimate refresh и required max_tokens) выполнены;
existing tests не исправлялись ради PASS.

- `tests/test_dictionary_exit_inert_security.py`: **43 passed**, 0.59s.
- Этот файл + `test_dictionary_exit_read_packet_residuals.py`,
  `test_dictionary_exit_public_request.py`, `test_dictionary_exit_admission.py`:
  **123 passed**, 0.86s.
- Frozen `tests/docs/test_content_trust.py`, `test_action_packet.py`,
  `test_mcp_boundary.py`: **29 failed / 12 passed**, 0.89s. NO WAIVER.
- `git diff --check`: PASS.

New tests выполняют actual annotation/workflow/packet/projector/public handler,
unknown source/issuer/consent/risk denial, fake-host identity rejection, original
bytes/hash/span/version retention и unchanged endpoint-format veto. Один successful
SDK projection test намеренно повышает status копии built insufficient packet и
recomputes estimate: это hostile caller fixture, НЕ selector approval/support.
Даже такой typed-ready packet не получает edit permission; baseline built packet
остаётся insufficient. Нет claims полной сети/security или independent answer quality.

Final logs (external temporary test output, не delivery artifacts):

```text
d05270f60d1c8ea3ae75a4d22a374b92c5e56d8070a167f42f7749fe30b7f4bf /tmp/opencode/inert-security-diagnostics.log
850e11378f566d7cf0b6c6ed649be6b1997280d0fbcd6b28966ce8ddf022b15e /tmp/opencode/inert-security-frozen.log
17407801411af4bf5edbd81ae0e910c73ab5f2204203d5dbe520f3eb1801c1bc /tmp/opencode/inert-security-new.log
```

### Exact frozen red ledger

Первая red прямо конфликтует со снятием AGENTS workflow grant. Остальные reds
не blanket-attributed baseline: baseline differential/full suites здесь не запускались.

```text
tests/docs/test_content_trust.py::test_ordinary_repository_docs_are_data_but_agent_policy_is_scoped
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Build FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Write FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Develop FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Introduce FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Replace FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Edit FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Migrate FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[Code FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[\u041d\u0430\u043f\u0438\u0448\u0438 FooHandler]
tests/docs/test_action_packet.py::test_every_routed_change_request_has_mutation_intent[\u0420\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u0430\u0439 FooHandler]
tests/docs/test_action_packet.py::test_mutation_readiness_does_not_infer_constraints_from_user_wording
tests/docs/test_action_packet.py::test_patch_request_plan_separates_mutation_and_preserve_targets
tests/docs/test_action_packet.py::test_patch_request_plan_keeps_implicit_targets_fail_closed[Fix the permission architecture.]
tests/docs/test_action_packet.py::test_patch_request_plan_keeps_implicit_targets_fail_closed[Update the relevant files.]
tests/docs/test_action_packet.py::test_patch_request_plan_keeps_implicit_targets_fail_closed[\u0418\u0441\u043f\u0440\u0430\u0432\u044c \u0441\u0432\u044f\u0437\u0430\u043d\u043d\u044b\u0435 \u043c\u043e\u0434\u0443\u043b\u0438.]
tests/docs/test_action_packet.py::test_named_permission_patch_resolves_all_decisive_fixture_targets_without_formatter_loss
tests/docs/test_action_packet.py::test_unique_source_path_alias_resolves_but_ambiguous_alias_does_not
tests/docs/test_action_packet.py::test_post_format_sufficiency_fails_closed_when_public_fact_is_not_rendered
tests/docs/test_action_packet.py::test_post_format_sufficiency_fails_closed_when_exact_symbol_is_dropped
tests/docs/test_action_packet.py::test_selected_document_terms_survive_action_packet_formatting
tests/docs/test_action_packet.py::test_patch_handler_uses_action_packet_completeness_for_explicit_target
tests/docs/test_action_packet.py::test_untargeted_patch_recovery_includes_safe_document_navigation
tests/docs/test_action_packet.py::test_post_format_sufficiency_accepts_camel_case_symbol_in_snake_case_source_path
tests/docs/test_action_packet.py::test_validator_rejects_truncated_packets_with_unclosed_required_evidence
tests/docs/test_action_packet.py::test_display_only_canonical_child_is_rendered_and_hash_bound
tests/docs/test_action_packet.py::test_python_imports_do_not_create_normative_facts_but_prose_does
tests/docs/test_action_packet.py::test_bounded_direct_is_one_existing_tool_call_and_returns_only_action_packet
tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields
```

## Parent dependencies / no edits outside ownership

- `application/_unified_context_service_part01.py:528-531` still derives SDK DTO
  `edit_ready` from typed operation + project result `answer_completeness` metadata.
  Parent must review/fail-close this actual aggregation consumer before claiming
  every public SDK result non-authorizing. Owned MCP/projector barriers do not
  establish safety of callers reading raw DTOs directly.
- `mcp/_docs_server_resources.py:139-140` still advertises `explicit_agent_policy`
  and `scoped_agent_policy`; `docs/mcp_footprint.py:244` contains the old sample.
  Parent documentation/artifact alignment required, no broad reinstallation here.
- Owner A's catalog/models/source boundary/project context not edited. Parent
  must independently review integration, source authorization versus attribution,
  raw/current SDK consumers, lifecycle/protected-path/cap/transport ceilings.
  Installed packs/index/stdio/external clients UNKNOWN. NL-removal gate remains BLOCKED.

## Exact file pins (SHA256, final slice)

```text
3b5bec24145c6702ba5cfb29602fee3ba0dfcae2e19c006b80f35d3d46c1aa97 docmancer/docs/application/_action_packet_part01.py
0d9daf64e205e831b2f87fdb2b9316d0d3723a1a26924a54f376b77f6fbd85b1 docmancer/docs/application/_action_packet_part02.py
56336adb0ac84546d91eea2afea86b9e74f39ded7b0a508f10e3da84ce05c5ac docmancer/docs/application/_action_packet_part04.py
399bddb0f1cdbf2e8a0798d2c5ecc7a0f9fa6052326caccb56a15fcbad774eb4 docmancer/docs/application/_action_packet_shared.py
e0cfead485d5745687cdd859a86da6e6695efb9ace3448a2e8cffd03c15e80b0 docmancer/docs/application/evidence_candidates.py
938965ff1e2c03d91ed8eff2a4d9e6f9f5eace5c79ff6e2ed800b1f77d646c0c docmancer/docs/application/model_visible_projection.py
5c1fd2a8ba81284e6ae42474c8b42c4ae0f3b8941cf76318f3a99548481706aa docmancer/docs/domain/content_trust.py
2f5c37e13c9b817489872b0861f7f5964114cac29b8f5572208c9e47ec63853e docmancer/docs/domain/trust_contract.py
73572b5daccbdd128fa63916a2600046d597c480451f7fb31f95a66df56fc8ac docmancer/docs/interfaces/mcp/context_tools.py
65aa2e149418bc16c3ada3577ff916e1c5d5adf2f36bb4bed182a36d89c1d59c tests/test_dictionary_exit_inert_security.py
38edd3a6980c5845661b129172ab74dd30f93bf176da7aa674a2d9550cd8775b tests/diagnostic_labels.dictionary_exit_inert_security.json
```

Owned unchanged pins:

```text
c9ef48fab56c82437f008f370d7e1654d21df70b539bafc5ae6f2523d0051805 docmancer/docs/application/_action_packet_part03.py
269d2367691889a480e219bed40a96095148cbc34b1d57336dd5293951fed43b docmancer/docs/application/_evidence_selection_part01.py
8006aa161192aef33df01798e9b2506bf7ce0b696aa2e7f292679a80558e84a3 docmancer/connectors/fetchers/pipeline/filtering.py
```
