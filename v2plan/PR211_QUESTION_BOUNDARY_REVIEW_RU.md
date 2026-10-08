# PR #211: миграция literal question boundary tests

Дата: 2026-10-08. Author review от исходного HEAD
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.
Изменён только `tests/docs/test_question_span_coverage.py`; production producers,
retrieval/admission, frozen ownership cases и gates не изменены.

## Основание и действующий контракт

Исходный [CI 37811010878](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878)
даёт в этом module 303 cases: 302 FAIL и 1 PASS. Текущий slice относится к
295 FAIL в шести функциях. Это выполненный baseline, не результат изменённого кода.

Прочитаны настоящие producers:

- `question_plan.compile_question_plan`: сохраняет полный исходный текст в
  пределах прежнего 4000-character input bound, не выводит facets и consumed
  spans, сообщает `unresolved_question_semantics`. `handled` означает наличие
  facets **или** unresolved частей, а не распознанный semantic frame.
- `question_retrieval_needs.retrieval_needs`: для непустого вопроса сохраняет
  один literal need со всем исходным span, пустым subject/context и relation
  `unresolved`; это retrieval input, не entailment.
- `build_project_answer_contract`: identity исходного вопроса без inferred
  subjects, proof obligations, concept queries и retrieval hints.
  `can_authorize_docs_answer` не выдаёт answer authority этому DTO.
- `build_documentation_query_plan`: original question сохраняется буквально;
  явно переданный host lookup остаётся отдельным query без parent attribution
  и без переноса coverage на original.
- `build_requirements`: ordinary project-docs request может не содержать
  обязательных semantic requirements; явные evidence paths сохраняются,
  неподдерживаемый provenance отклоняется. `component_scope_complete=False`
  обозначает отсутствие полной интерпретации вопроса.
- `split_question_clause_spans`: структурные границы — пустые параграфы;
  sentence punctuation, wrappers и conjunctions не дают semantic decomposition.

Эти границы соответствуют разделению ответственности в
[V4_PRODUCT_DECISIONS_RU.md](V4_PRODUCT_DECISIONS_RU.md): MCP доставляет context,
host оценивает смысл и полномочия; literal occurrence не создаёт semantic proof.
Это не разрешение возвращать скрытые rewrites или исправлять отложенный retrieval.

## Точные successors

| Существующая функция | Cases | Изменение и сохраняемый смысл |
|---|---:|---|
| `test_known_frame_never_authorizes_an_unknown_tail` | 288 | Все 18 prefixes × 16 tails остаются. Старый clause-specific reason заменён полным literal/span/no-authority boundary. Explicit prefix lookup действительно сохраняется вторым query, но не заменяет original и не получает parent coverage. Hash полного вопроса отличается от prefix-only hash. |
| `test_unresolved_residue_reaches_the_requirements_gate` | 3 | Не требует придуманного semantic `unsupported_query` для ordinary read. Проверяет отсутствие inferred facets/obligations и полной component interpretation, полный исходный need. Positive explicit evidence path доходит до requirements; malformed provenance отвергается. |
| `test_legacy_behavior_usage_fallback_rejects_extra_compound_tail` | 1 | Полный compound tail сохраняется; compatibility contract не выдаёт subjects/proof/answer authority. |
| `test_plan_retains_exact_source_spans_after_wrapper_and_whitespace_normalization` | 1 | Проверяет настоящий literal need и original query с wrapper/whitespace целиком. Hash отличается от сокращённого normalized вопроса. Semantic facet/obligation из prose больше не ожидается. |
| `test_clause_scanner_preserves_original_offsets_and_noun_coordination` | 1 | Сохраняет исходный offset round-trip; один абзац не делится по question mark. Реальный positive из двух paragraphs проверяет оба точных spans, punctuation и noun coordination. |
| `test_russian_ambiguous_inventory_and_action_frames_fail_closed` | 1 | Все три русских case остаются unresolved без выдуманной inventory/action classification; полный literal/span/no-authority boundary проверяется для каждого. |

Общий helper применим только к коротким непустым authored inputs этого module.
Он не меняет старый input ceiling и не заявляет поведение за его пределами.
Positive controls запрещают получить PASS простой заменой всех результатов на
пустые структуры: original/host lookup, full need, explicit path и paragraph
spans должны действительно присутствовать.

## Граница assertions и оставшиеся failures

`component_scope_complete=False` **не является самостоятельным universal
downstream selector veto**. Этот slice проверяет producer boundary вместе с
отсутствием inferred obligations, отдельным no-answer-authority API и сохранением
literal inputs. Он не сертифицирует semantic entailment, answer quality,
доставку useful partial facts или полный downstream acceptance.

Следующие старые тела функций оставлены буквально:

- governance English и Russian positives — два cases;
- compounds/paraphrases/premise proof — один case;
- четыре legacy fallback cases с `frozen_ownership_mismatches()`;
- nested governance tail negative — один существующий PASS.

Таким образом 7 baseline FAIL и 1 PASS вне slice остаются видимыми. Frozen
ownership gate, positive semantic expectations и deferred admission не удалены
и не подменены новыми actual values.

## Inventory и проверка

- Все 11 `test_*` функций, arguments и parameter decorators сохранены.
- Все 303 concrete node IDs сохранены, включая 288-element matrix.
- Изменены ровно шесть перечисленных функций, 295 baseline FAIL.
- Новых test nodes, skip/xfail, selectors и pytest markers нет.
- `assert` AST: до 46, после 74, включая общий boundary helper. Это не заявление
  о побуквенном сохранении всех старых assertions: retired semantic assertions
  имеют указанные выше отдельно обоснованные successors.
- AST parse/compile и `git diff --check`: PASS. Module: 376 строк.
- Изменённые tests runtime: **NOT RUN**, ожидаются review и normal CI.
  Локальные installs, repository imports, providers/clients не запускались.

SHA256 проверяемого test file:
`7e487c6927677f0bb0a4ad8a0a6424e51e97b1f11a6ad0d1f7f272a50a98d6b7`.

Независимый review:
[PR211_QUESTION_BOUNDARY_INDEPENDENT_REVIEW_RU.md](PR211_QUESTION_BOUNDARY_INDEPENDENT_REVIEW_RU.md).
