# Legacy/direct-call compiler dictionary exit — bounded slice

Дата: 2026-10-07. Primary `/tmp/opencode/docatlas-stage3-integration-active`.
Baseline `307c480cd7ffe2fff5a264167dcb09a7974ffc20`. **Partial exit, не release acceptance.**
Owner разрешил parallel execution; соседние proof/discovery изменения не owned и
не reviewed этим executor. Network/commit/push не выполнялись.

## Scope / результат

Изменены только шесть production modules в `docmancer/docs/domain/`:
`question_plan.py`, `question_plan_surface_rules.py`, `question_semantic_frames.py`,
`question_frame_core.py`, `need_composition.py`, `compositional_question_plan.py`.
`question_plan_command_rules.py` не требовал import-ABI исправления и не изменён.
Новые tests: `tests/test_dictionary_exit_legacy_compilers.py` и отдельный hash-bound
`tests/diagnostic_labels.dictionary_exit_legacy_compilers.json`.

Удалены реальные NL rules: implicit sync API/aliases, public tool inventory,
Python-version/DocAtlas subject injection, release/storage/provider/MCP thematic
facets, governance expected values, comparison/condition/premise/location/action/
purpose/before/decision/argument frames, component generators, action/question
heads, request wrappers, NL conjunction splitting, count/category/set/precedence/
dependency proposals. Vocabulary не перенесён в prompt/config/другой producer.

Public compiler сохраняет прежний `str(question or "")[:4000]` ceiling, но не
переписывает исходный Unicode внутри него. Возвращает exact `(raw,)` clauses,
`unresolved_question_semantics`, пустые facets/consumed_spans и
`component_scope_complete=False`, включая blank input. `handled=True` здесь
означает наличие explicit unresolved результата, **не supported/certified**.
Даже quoted API name не удостоверяет NL relation и не создаёт answer facet.

DTO definitions, annotations/defaults, frozen/slots и прежние span validations
сохранены. AST comparison с baseline подтверждает identical DTO field/method
shapes и signatures сохранённых functions. Explicit `PlannedFacet`/`QuestionPlan`
конструкторы остаются data APIs, не дают proof/edit/authorization. Private
nonoptional `_governance_facet_plan` и `_inventory_frame` теперь бросают ValueError:
их signature не допускает unknown; positive facet не изобретается.
Facade импортируемые symbols и имена callable adapters сохранены. Adapters
optional→None, composition→(), independence→(), ownership predicate→False.

Structural paragraph spans остаются exact/trimmed, quote/backtick/link masking
сохраняет длину и offsets. Punctuation внутри программного literal не превращается
в request split. Whitespace/punctuation trimming остаётся structural; article /
politeness stripping удалён. Nonempty semantic tails не сертифицируются безопасными.
Programming-language grammar/source scanners/path recognition не редактировались.
`retrieval_needs` facade/immutable cache/IDs/hard literals и source identity binding
не изменены; raw question hashes/occurrence spans не переписывались.

## Callers / parent follow-up

Static current callers просмотрены, не только imports:

- `question_ownership.py:classify_question_ownership` реально вызывает compiler,
  но проверяет **contract.unresolved_parts**, затем **plan.facets**, а не
  `plan.unresolved_parts`. С current empty project contract unknown compiler
  может называться `legacy` в ownership telemetry. Frozen registry/ownership file
  не тронут; parent должен учитывать эту известную consumer incompatibility,
  не восстанавливать semantics ради frozen expectations.
- `scripts/run_question_surface_gate.py:_owner` также проверяет contract unresolved
  и plan facets; empty contract становится `silent_empty`. Gate остаётся historical
  red tooling, не evidence supported результата нового compiler.
- `_project_answer_contract_shared.py` импортирует `QuestionPlan` DTO; текущий
  `_project_answer_contract_part02.py` не вызывает compiler.
- `question_plan_core.py` использует frame helpers для legacy normalization/safety;
  wrapper теперь identity, nonempty tail conservative false. Это может уменьшать
  direct helper compatibility, не positive proof.
- Найденные direct test callers импортируют `_semantic_comparison`, frame matchers,
  splitter и independent spans. Symbols сохранены, старые positive expectations red.
- Уже очищенный ranking consumer больше не вызывает independent_sentence_spans.

Нет claims default reachability по наличию facade imports. Этот bounded slice не
runtime audit всех SDK users; внешние callers и их treatment `handled/unresolved`
**UNKNOWN**. Parent-owned consumer изменения здесь не выполнялись.

## Проверки / сохранённые reds

Обычный repository conftest, offline, `PYTHONDONTWRITEBYTECODE=1`,
`DOCATLAS_OFFLINE=1`, `.venv/bin/python -m pytest -p no:cacheprovider`:

- Новый owned module: **399 passed**.
- `tests/test_dictionary_exit_*.py`: initial **1302 passed**, final **1350 passed**
  после появления concurrent unit-helper tests в следующем snapshot
  (включает чужие новые modules, не scoped approval их implementation).
- Шесть checkpoint technical modules (`target_security`, `content_trust`,
  `reference_hash_domains`, `review_source_capabilities`,
  `finalized_mcp_output_integrity`, `mcp_boundary`): **45 passed / 1 failed**.
  Сохранённый red — `test_patch_constraints_debug_compaction_preserves_contract_fields`,
  demanding advisory `answer_available=True`; это ранее известный contract conflict.
- Unchanged mixed modules: `test_question_plan_v4`, `test_question_span_coverage`,
  `test_comparison_treat_frame`, `test_component_completeness`,
  `test_evidence_set_need_composition`, `test_question_frame_paraphrase_e2e`,
  `test_requested_need_partition`: **20 passed / 375 failed**.
- In-memory **six owned files baseline overlay**, остальные files current:
  **33 passed / 362 failed**. Это scoped attribution, не full baseline run.
  Delta: comparison treat +9 reds; clause/span coverage +3; need composition +1.
  Остальные module counts unchanged. Reds не waived и assertions не переписаны.
- `git diff --check` PASS на проверенном snapshot.
- Final targeted new compiler + literal-needs/MCP/read-tails + пять technical
  modules (без отдельно учтённого mixed `mcp_boundary`): **571 passed**.

Новые tests проверяют no-injection напрямую по бывшим EN/RU surfaces, отсутствие
delegation/rewrite, blank/cap negatives, immutable DTO validation, literal/path
recognition, exact quote/paragraph offsets и неизменённые cache/need IDs.
No `--noconftest`, frozen tests/cases/gold/thresholds/manifests не изменялись.
Full CI, package/wheel, actual MCP smoke, self-host quality этим executor не
запускались. Прежний quality FAIL остаётся открытым, этот report не replacement.

## Неудалённые / separate ownership

- `question_plan_core.py` содержит `_safe_coverage_gap` NL conjunction recognition
  и `_clean` article stripping. Новый compiler их не вызывает; legacy direct helper
  debt вне allocation. `_technical` использует explicit technical coercion, не
  повод массово удалять language/path grammar или literal spellings.
- Frozen `question_ownership.py` registry/cases и tooling gate не менялись.
- `_answer_units_part02.py`, `question_premise_proof.py`, `governance_value_proof.py`
  — parallel proof owner; их изменения/полнота не оценивались этим executor.
- Discovery/corpus bounds/source-map priorities/прочие repository dictionaries
  остаются отдельными boundaries, этот compiler slice не full dictionary exit.

Следующий parent шаг: independent scoped review и последовательная consumer
integration с сохранением negative authority и прежних red/frozen artifacts.
