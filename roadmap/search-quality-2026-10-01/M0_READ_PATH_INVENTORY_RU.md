# M0: подтверждённая карта project read-path

Текущий статус: **M0 закрыт в scope inventory**; [приёмка](M01_ACCEPTANCE_RU.md).
Это source inventory и controlled boundary trace, не dynamic trace всех branches.
Дальнейший quality protocol нужен до M3; multilingual quality не подтверждена.

## Порядок работы

После первого slice M1 были выполнены узкие Unicode правки и удалён stopword
список window focus из M2. Это отклонение от последовательного M0 → M1 → M2.
На момент первых slices M0/M1 не были завершены. Последующая классификация и
isolated equivalence приёмка зафиксированы в M01_ACCEPTANCE_RU.md; прежние
локальные PASS сами по себе не были основанием закрытия.

## Active boundary

| Stage | Source | Решение / зависимость | Что сохранять |
|---|---|---|---|
| MCP input | `docs/interfaces/mcp/context_tools.py:296–338` | Original question, lookup normalization; `build_mutation_intent` и `is_change_request` определяют branch | Не разрешать network/bootstrap или mutation по prose документа |
| Project read / proof split | тот же файл `:379–419` | Только non-patch project-only request переходит в `docs_context`; library/mixed идут в другой projection | Library certification и patch fail-closed не менять вместе с read |
| Unified delegation | `docs/application/_unified_context_service_part01.py` | project/dependency/mixed routing | typed identity/scope/version inputs и recovery reasons |
| Project planning | `_project_context_service_part01.py:39–89` | NL intent, locator, requirements, query plan и need scheduling до вызова project docs | Не считать requirements parser универсальным пониманием вопроса |
| Search preparation | `_project_docs_service_part03.py:154–197` | Lifecycle intent из requirements или question; identity и lifecycle filters; query scheduling | metadata exclusions сохранять, intent inference мигрировать отдельно |
| Backend retrieval | тот же файл `:210–220` | gateway dispatcher, mode, filters | retrieval capabilities, unavailable/degraded states, caps |
| Tagging | тот же файл `:262–315`; `reference_query_tagging.py` | Original/lookup/derived query attribution и qualification | Exact reference binding; lookup не создаёт proof эквивалентности |
| Candidate ranking | `context_candidate_ranking.py` | Qualification вызывается и при вычислении ranking/preferences | Нельзя убрать только final veto и оставить ранний NL exclusion |
| Need selection | `need_context_disposition.py`, `joint_context_candidates.py`, `joint_context_selection.py` | Need-specific qualification, source policy и joint variants | per-source guards, не synthetic approval |
| Final visible window | `_docs_context_projection_core.py:238`, `:868–929` | Independent probes и requalification уже выбранного snippet | Actual window/source/span validation, не доверять старому trace |
| Window alternatives | `context_variant_retention.py`, `qualified_support_units.py` | Callback requalification для fragments/union/blocks | source-local contiguous offsets и structural completeness |
| Auxiliary continuation | `query_block_bridge.py`, `inspection_recovery_seeds.py` | Ещё два пути в visible requalification | recovery/continuation не обходят guards |
| Hint preferences | `domain/context_hint_policy.py` | Specific-contract NL predicate и минимум body terms | Hint не доказывает original-question coverage |
| Public output | `context_tools.py:403–407` | bounded projection и source continuation binding | attribution, snapshot binding, budgets, false permission flags |

Line references относятся к текущему slice и могут сдвигаться после edits.
Таблица показывает source call chain, не доказательство выполнения всех stages
для каждого request. Нужен controlled trace для original/lookup/exact-path/need
и explicit current/history inputs.

## Что изменено и что остаётся

- M1: metadata checks вынесены, wrapper сохранил legacy text/catalog exclusions.
- M2: четыре script whitelists заменены Unicode matching: query terms,
  qualification fallback, independent probes и window terms.
- M2: удалён **только** window-focus EN/RU stopword список.
- Остались query framing words/enumeration rewriting, admission grammar,
  English relation patterns/inflection, query aliases и NL lifecycle/mutation
  inference, backend stopwords и другие script-specific правила.

## Блокирующие условия для следующего широкого удаления

1. Catalog roles и forbidden terms: разделить явную operational policy и guessed
   intent relevance restrictions. Не считать их одинаково security-authoritative.
2. Exact references: отличать locator/symbol/subject и проверять actual source
   binding; filename mention не answer evidence.
3. Version/scope/snapshot: определить existing validator ownership; новая
   metadata функция не заменяет их проверку.
4. Library/mutation: подтвердить shared callers, не расширить permissions.
5. Задать acceptance protocol до tuning relevance: corpus/model/budget,
   development/holdout/negative cases, допустимые регрессии и стоимость.

Cross-language recall и host correctness не измерены. Шаг 07 не завершён.

## Классификация exclusions и guard ownership

### Не security-authoritative: intent-generated exclusions

`project_retrieval_intent.py:160–186` создаёт forbidden terms из guessed intent:
`docs/adr/`, `mcp pack commands`, `packs mcp runtime`, `install-pack`,
`packs-serve`; для offline intent без test words добавляет `pytest/smoke/fixture/
test suite`. Это product-specific routing/relevance heuristics, не детектор
опасного источника. Удаление допускается только с distractor/relevance проверкой,
но они не должны переноситься в новый metadata guard как security policy.

`documentation_query_plan.py:394–411` объединяет alias exclusions и кладёт их
на original query; explicit path их обходит. Далее поля копируются в traces,
и общий `evidence_policy_rejection_reason` исполняет их как text/catalog veto.
Поэтому происхождение constraint должно сохраняться: нельзя объявить любой
incoming `forbidden_evidence_terms` доверенной operational policy.

### Existing structural guard owners

- `source_metadata_rejection_reason`: project identity, freshness, index freshness,
  risk flags, metadata lifecycle. Не проверяет весь scope/version/snapshot.
- `query_reference_binding.prepare_reference_probe:242–277`: при наличии reference
  plan проверяет schema/scope/project/generation/version/path, дальше snapshot hashes
  и occurrence binding. Без reference plan остаётся legacy policy — это не новая
  unconditional snapshot гарантия.
- `_docs_context_projection_core.py:217–238`: project source class, explicit path,
  expected identity и visible requalification. Значение `doc_scope` в projected
  metadata само по себе не доказательство допустимого scope.
- `_unified_context_service_part02.py`: contamination check с `wrong_doc_scope`.
- `_library_docs_service_part01.py` и `_evidence_selection_part01.py`: library
  version rejection. Эти contracts не заменяются project relevance.
- `_source_continuation_core.py`: digest mismatch → source_changed. Это проверка
  последующего чтения, не замена validation первого packet.

### Разделение lanes

`context_tools.handle_context_tool` выбирает patch branch раньше project read;
non-patch project request без library/libraries становится docs_context.
Остальные requests сохраняют docs_answer projection. В shared policy refactor
не меняется выбор branch. Миграция language-based `is_change_request` требует
explicit intent contract: unknown mutation language нельзя считать безопасно
распознанным read и на этом основании предоставлять edit authority.

В M1 сохранена legacy wrapper policy для **всех** shared callers. В M2 изменились
Unicode terms, поэтому обещание packet equivalence M1 нельзя автоматически
распространять на весь текущий diff. Проверять эти две правки отдельно.

Проверка structural boundaries на текущем diff: **127 passed** —
reference-behavior-matrix, reference-hash-domains, query-reference-roles,
reference-transfer-regressions, context-trust-gates, patch-context-public,
admission-pipeline-invariants и joint-context-invariants.
Это не полный library/version end-to-end или cross-language acceptance.
