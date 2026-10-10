# PR #211: fixture-owned member transaction migration

Дата: 2026-10-08. Author review узкого slice после `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.
Runtime-результат этой новой версии: **NOT RUN locally; требуется normal CI**.

## Изменённые файлы и границы

- `tests/_fixture_member_transaction.py`: новый test-only helper настоящей cold member transaction.
- `tests/test_named_document_context_integration.py`: подготовка `_named_document_service` и двух самостоятельных fixtures; два новых integrity tests.
- Этот review.

Production, публичный read handler, planner/admission, retrieval, schema/output
ceilings, CI selectors/markers и required gates не изменяются этим slice.
Root совместной волны может отдельно менять planner tests; это другой review.
Тексты fixture documents, roles/authority и questions сохранены.

## Почему это текущий контракт

`project_docs_member_transaction.MemberTransaction.parse` требует полный объект:
точную operation, literal `confirm=True`, host-selected absolute storage_path,
SHA256 catalog bytes, явный expected_generation_id (включая `None` для cold
store) и конечные documents с path/content_sha256/catalog_entry_hash.
Catalog membership сама по себе не даёт mutation consent.

`LocalMemberService` выбирает private host store `tmp_path/home/mcp/members.db`
вне отдельно созданного `tmp_path/project`. Fixture передаёт explicit config
через обычный constructor и не использует project config для выбора storage.
До подтверждённой transaction нет database, owner marker и materialized facade.
Helper передаёт mutation в настоящий `cold.project_docs.sync_project_docs`;
`PinnedProject`, `MemberStoragePolicy`, descriptor/source bounds и SQLite CAS
исполняются без monkeypatch. Только после commit вызывается `materialize()`:
read tests получают обычный `LibraryDocsService` с тем же host-selected store.

Конечные member paths приходят от fixture: `paths` в `_named_document_service`,
`(plan_path, 'ARCHITECTURE.md')` и `(plan_path,)` в standalone cases. Helper не
сканирует directory/glob, не выводит selection из prose, не добавляет roots
или code_files. Existing authored YAML с explicit documents остаётся исходным.
Пустые roots/code_files и остальные ограничения валидирует настоящий producer.

Generation не вычисляется и не обновляется внутри request helper: caller обязан
передать `expected_generation_id`. Cold preparation передаёт `None` ровно один
раз. Нет retry с новым CAS, подавления PermissionError, автоиндексации при read,
legacy changed/deleted/renamed flags, orphan deletion или vector side effects.

После commit helper проверяет настоящий generation ID, точный набор generation
sources и их UTF-8 bytes, source content hashes, catalog-entry hashes и root
identity. `members == new_count`, `changed_count == sources_deleted == 0` и
`vector_sync == not_requested` подтверждают начальную finite lexical preparation.
Проверка отсутствия extraction directory стоит до materialize и относится к
самой mutation transaction, не ко всему lifecycle read-service constructor.

## Отрицательные controls нового helper

Два новых теста — не mocks и не общая замена старых expectations:

1. `test_named_document_fixture_requires_confirmed_hash_bound_members`:
   legacy call без mutation, confirm=False, content hash mismatch, catalog hash
   mismatch, entry hash mismatch, missing generation, wrong operation, wrong
   storage и nonmember path отклоняются настоящим service. После каждого
   отклонения private home не существует, read facade не создан, bytes обоих
   fixture files прежние. Потом исходный правильный grant успешно индексирует
   ровно README; uncataloged `unselected.md` остаётся только на диске.
2. `test_named_document_fixture_cas_preserves_unselected_source`:
   два точных member files подготовлены настоящим helper. Старый content hash
   отклоняется без изменения sources/sections/index_state/generations/children;
   точный fresh hash с исходным CAS обновляет только выбранный member. Полная
   sources row второго member сохранена. Повтор той же transaction после
   generation change отклоняется по CAS, вся таблица состояния остаётся прежней,
   оба fixture file contents не меняются индексатором.

Существующие dedicated member/storage/runtime negatives также не изменены:
`tests/test_mcp_delivery_member_transaction.py`,
`tests/test_mcp_trusted_storage_lifecycle.py`,
`tests/test_evidence_quality_v2_fixture_runtime.py`.
Они остаются обязательной частью совместного core CI.

## AST / assertion inventory

Статическое сравнение с `git show df9b682f:tests/test_named_document_context_integration.py`:

- Все **18** исходных test functions, их arguments и parameter decorators
  сохранены AST-exact; **21** concrete старых JUnit cases сохраняют identity.
- Добавлены **2** новые test functions выше; они дают 2 дополнительных cases,
  не маскируют и не заменяют исходные failures.
- Все **110 read/content/assertion ASTs** исходных test functions сохранены.
  Единственная из 111 assertions внутри old test functions, чьё AST изменилось,
  — вызов legacy sync внутри `assert ...status == 'success'` в single-fact
  fixture. Теперь `assert sync.status == 'success'` относится к result настоящей
  confirmed member transaction. У helper аналогично заменена ещё одна setup
  assertion. Ни один критерий read-result/fidelity/guards не удалён.
- Во всём старом module было **112 Assert** nodes (111 test + 1 helper);
  в новом **130** (те же 112 с двумя setup migrations + 18 в новых integrity
  tests). Новый helper отдельно содержит 20 assertions.
- AST parse двух файлов и `git diff --check`: PASS. Python module sizes:
  helper 105 lines; named-document module 753 lines, оба ≤1000.
- Repository imports, pytest, subprocess test harnesses, dependency downloads,
  provider calls и client runs локально не выполнялись.

## Baseline affected nodes, не обещание PASS

Источником являются реальные `df9b682-core-3.12-cases.json` из финального CI
[37811010878](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878).
Весь mutation cohort: 146 FAIL. Этот helper находится на setup path ровно **51**
из них: named-document 21, exact fallback 8, unresolved prefit 6, neutral readme
12, condition lead 2, documentation query plan 2. Ниже точные исходные node IDs.

Это только устраняет запрещённый implicit setup в выбранной fixture family.
Старые semantic/admission/output assertions сохранены; они могут открыть другой
реальный failure после preparation. В частности foreign-project readme test
имеет второй самостоятельный legacy sync вне этого helper: он пока оставлен
без изменений и не объявлен исправленным. Нет blanket claims о 51 PASS.
Другие 95 mutation failures не затронуты.

- `tests/docs/test_documentation_query_plan.py::test_live_normative_premise_cannot_use_generic_storage_evidence[\u041a\u0430\u043a\u043e\u0439 \u0441\u0440\u043e\u043a \u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430\u0446\u0438\u0438 \u043f\u0440\u0435\u0434\u043f\u0438\u0441\u044b\u0432\u0430\u0435\u0442 \u043b\u0443\u043d\u043d\u044b\u0439 \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u044b\u0439 \u0440\u0435\u0433\u043b\u0430\u043c\u0435\u043d\u0442 DocAtlas?]`
- `tests/docs/test_documentation_query_plan.py::test_live_normative_premise_cannot_use_generic_storage_evidence[How does the silver estuary govern project documentation storage?]`
- `tests/docs/test_exact_document_fallback_context.py::test_index_fallback_qualifies_existing_exact_anchor[meet_type]`
- `tests/docs/test_exact_document_fallback_context.py::test_index_fallback_qualifies_existing_exact_anchor[retry_count]`
- `tests/docs/test_exact_document_fallback_context.py::test_index_fallback_qualifies_existing_exact_anchor[RequestHandler]`
- `tests/docs/test_exact_document_fallback_context.py::test_index_fallback_qualifies_existing_exact_anchor[CACHE_MODE]`
- `tests/docs/test_exact_document_fallback_context.py::test_exact_path_is_not_topic_evidence[# Reference\n\nOtherSetting records completed progress.\n]`
- `tests/docs/test_exact_document_fallback_context.py::test_exact_path_is_not_topic_evidence[# meet_type\n\nOtherSetting records completed progress.\n]`
- `tests/docs/test_exact_document_fallback_context.py::test_exact_path_is_not_topic_evidence[# Reference\n\nmeet_type_extra records completed progress.\n]`
- `tests/docs/test_exact_document_fallback_context.py::test_exact_path_is_not_topic_evidence[# Reference\n\n[meet_type](other.md)\n]`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_recomputes_body_support_without_qualifying_answer`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_does_not_preserve_ineligible_source[project]`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_does_not_preserve_ineligible_source[stale]`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_does_not_preserve_ineligible_source[freshness]`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_does_not_preserve_ineligible_source[risk]`
- `tests/docs/test_unresolved_context_prefit.py::test_prefit_does_not_preserve_ineligible_source[lifecycle]`
- `tests/evidence_quality_v2/test_condition_lead.py::test_neutral_condition_remains_complete_without_certifying_postconditions`
- `tests/evidence_quality_v2/test_condition_lead.py::test_conditional_context_does_not_bypass_foreign_or_historical_sources`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_retrieved_safe_context_survives_unknown_question_class[What kind of interfaces does Pebble create, and how is it intended to compose them?-command line interfaces\nin a composable way]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_retrieved_safe_context_survives_unknown_question_class[\u041f\u0435\u0440\u0435\u0447\u0438\u0441\u043b\u0438 \u0432\u0441\u0435 \u0442\u0440\u0438 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0438 Pebble \u0438\u0437 \u0441\u043f\u0438\u0441\u043a\u0430 Pebble in three points.-Pebble in three points:\n\n- Arbitrary nesting of commands\n- Automatic help page generation\n- Lazy loading of subcommands at runtime]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_hint_context_does_not_bypass_candidate_safety[project]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_hint_context_does_not_bypass_candidate_safety[stale]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_hint_context_does_not_bypass_candidate_safety[freshness]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_hint_context_does_not_bypass_candidate_safety[risk]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_hint_context_does_not_bypass_candidate_safety[lifecycle]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_foreign_project_same_path_never_enters_owned_context`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_lookup_identical_to_original_is_not_a_new_requirement[What kind of interfaces does Pebble create, and how is it intended to compose them?-command line interfaces\nin a composable way]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_lookup_identical_to_original_is_not_a_new_requirement[\u041f\u0435\u0440\u0435\u0447\u0438\u0441\u043b\u0438 \u0432\u0441\u0435 \u0442\u0440\u0438 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0438 Pebble \u0438\u0437 \u0441\u043f\u0438\u0441\u043a\u0430 Pebble in three points.-Pebble in three points:\n\n- Arbitrary nesting of commands\n- Automatic help page generation\n- Lazy loading of subcommands at runtime]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_name_only_hint_does_not_establish_an_unknown_topic[\u041a\u0430\u043a Pebble \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0447\u0435\u0440\u0435\u0437 \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u044b\u0439 \u043a\u0430\u043d\u0430\u043b?]`
- `tests/evidence_quality_v2/test_readme_neutral_context.py::test_name_only_hint_does_not_establish_an_unknown_topic[\u041a\u0430\u043a Pebble Pebble \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0447\u0435\u0440\u0435\u0437 \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u044b\u0439 \u043a\u0430\u043d\u0430\u043b?]`
- `tests/test_named_document_context_integration.py::test_named_plan_is_scoped_complete_and_visible_end_to_end`
- `tests/test_named_document_context_integration.py::test_named_document_single_fact_does_not_expose_unrequested_document_content`
- `tests/test_named_document_context_integration.py::test_public_named_document_unknown_locator_fails_closed`
- `tests/test_named_document_context_integration.py::test_public_project_answer_requires_all_semantic_facets`
- `tests/test_named_document_context_integration.py::test_public_project_answer_accepts_all_semantic_facets`
- `tests/test_named_document_context_integration.py::test_public_project_answer_heading_only_is_not_factual_proof`
- `tests/test_named_document_context_integration.py::test_public_project_answer_negated_facet_is_not_factual_proof`
- `tests/test_named_document_context_integration.py::test_project_context_remains_available_when_authority_facet_is_missing`
- `tests/test_named_document_context_integration.py::test_public_project_answer_accepts_recall_with_authority_invariant`
- `tests/test_named_document_context_integration.py::test_public_project_context_keeps_comparison_subjects_without_certifying_relation`
- `tests/test_named_document_context_integration.py::test_public_project_context_returns_documented_comparison_without_authorization`
- `tests/test_named_document_context_integration.py::test_public_project_answer_supports_russian_behavior_and_usage`
- `tests/test_named_document_context_integration.py::test_public_project_answer_rejects_incomplete_russian_usage`
- `tests/test_named_document_context_integration.py::test_public_named_document_ambiguous_basename_fails_closed`
- `tests/test_named_document_context_integration.py::test_real_sqlite_newcomer_topics_reach_expected_project_docs[What public MCP tools does DocAtlas expose?-docs/mcp-docs-server.md-get_docs_context]`
- `tests/test_named_document_context_integration.py::test_real_sqlite_newcomer_topics_reach_expected_project_docs[How do I configure DocAtlas in OpenCode?-README.md-opencode.json]`
- `tests/test_named_document_context_integration.py::test_real_sqlite_newcomer_topics_reach_expected_project_docs[How are external dependency docs prepared for a project?-docs/project-docs-mcp-workflow.md-prefetch_project_dependency_docs]`
- `tests/test_named_document_context_integration.py::test_real_sqlite_newcomer_topics_reach_expected_project_docs[What output budgets apply to Docs MCP responses?-docs/mcp-docs-server.md-800 tokens and three sources]`
- `tests/test_named_document_context_integration.py::test_real_sqlite_compound_onboarding_maximizes_host_lookup_coverage`
- `tests/test_named_document_context_integration.py::test_real_sqlite_audited_russian_alias_covers_original_question`
- `tests/test_named_document_context_integration.py::test_real_sqlite_docs_mcp_intent_excludes_packs_and_adrs`

## Frozen review hashes

| Файл | SHA256 |
|---|---|
| `tests/_fixture_member_transaction.py` | `87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe` |
| `tests/test_named_document_context_integration.py` | `0ecdcbdf0ed96cb76c80af3fc8c7f357ee64f9aed2fa86977b1bc6341a082f5a` |

Результат author review: implementation соответствует узкому подтверждённому
fixture-only scope. Перед push требуется независимый review этих hashes;
затем совместный CI на одном HEAD и сравнение конкретных исходов с baseline.
