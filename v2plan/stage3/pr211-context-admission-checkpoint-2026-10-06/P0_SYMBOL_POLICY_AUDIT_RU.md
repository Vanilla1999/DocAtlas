# P0 slice 2: symbol decisions и происхождение policies

2026-10-06. **P0 ACTIVE**, production/test code не изменён. Baseline HEAD и product
hashes остаются из [предыдущего slice](P0_READ_PATH_AUDIT_RU.md).
S означает подтверждённый source mechanism; диагностические observations ниже не
превращают всю группу в доказанную retrieval regression.

## D20: stopword lists имеют разные обязанности

| Symbol / caller | Подтверждённое действие | Migration decision |
|---|---|---|
| `context_windows._QUERY_STOP_WORDS` → `_query_terms` → window selection (`146`) | Удаляет project/when/after и RU работает/проект/когда из lexical window terms | S / REMOVE semantic list после paired window checks. Оставить structural spans/rolling caps отдельно; не считать окно источником proof. |
| `query_terms._REQUEST_FRAMING_TERMS` → `documentation_query_terms` → reference tagging/qualification | Фильтрует не только articles, но `mcp`, `compare`, `summarize`; leading enumerate/перечисли удаляется отдельным regex | S / SPLIT: список и framing rewrite — semantic migration; literal spans/caps остаются. |
| `query_terms._SUPPLEMENTAL_FUNCTION_WORDS` → `supplemental_query_is_useful` → optional scheduling | `if not`/`если не` сами по себе не admitted как optional probe; quoted `if` сохраняется. Также исключает function word как command option value (`70`) | S / SPLIT: proposal usefulness не proof. Replacement не должен стирать conditions в original; option-value parsing требует проверки literal values. |
| `retrieval.query_planning._STOPWORDS` → `_concept_queries` | EN content words выделяются из исходного query | S / REMOVE ручной list после dictionary-independent proposal replacement; budgets сохранить. |
| `legacy_question_coverage._STOP_TOKENS`, `_GENERIC_LIST_TOKENS` → `_tokens` → coverage gaps | Удаляет policy/contract/public/между и использует stemming для сопоставления obligations | S / SPLIT: это semantic guard, не безвредный retrieval stopword. Заменить completeness guarantee, не отключать guard. |
| `query_terms.documentation_technical_anchors:95` | Явно исключает `docatlas`, `docmancer`, включая quoted values | S / REMOVE product-specific exception; проверить exact bindings и видимый контекст при renamed controls. |

Ни одна semantic list из этой таблицы не закрыта как TECHNICAL-RETAINED.
Технические части пока кандидаты на сохранение, а не готовое разрешение на весь модуль.

## D25: premise/governance proof не dictionary-independent

### `question_premise_proof.py`

- `_ACTION_FORMS` → `_target_parts` → `_target_bound` → `_premise_check`: ручные
  RU/EN equivalences delete/remove, preserve/keep, retry, bypass. **S / REMOVE**.
- `_CAUSAL_RE`, `_LIMITATION_RE`, `_negative_action`, `_universal_action` определяют
  causal/negative/universal meaning и premise contradiction. **S / SPLIT**:
  смысловые формы заменить; запрет доказывать premise простым повторением сохранить.
- `_STOP_TARGET_TOKENS` участвует в object binding. **S / REMOVE**, не technical enum.
- `_NUMBER_VALUES`/`_NUMBER_TOKEN` входят в D28: numeric normalization отделить от
  source-subject/cardinality proof. Caller — `question_plan_proof.premise_relation_proof`.

### `governance_value_proof.py`

- `_OWNER_RE`, `_REQUIREMENT_RE`, `_DEFERRED_STATE_RE`, `_SCOPE_RELATION_RE`,
  `_GENERIC_VALUE_RE`, `_NAVIGATION_META_RE`, `_PLACEHOLDER_VALUE_RE` и `_tokens`
  распознают meaning через lexical forms/stems. **S / SPLIT**: удаление требует
  сохранения value-bearing vs navigation-only negative controls.
- `_ANDROID_13_RE` — product/platform-specific rule внутри generic proof module;
  **S / REVIEW**, требуется caller-level разбор use sites прежде удаления.
- `_GOVERNANCE_RELATIONS` — internal relation enum; `_CANONICAL_AUTHORITIES` —
  authority labels. **Technical-retain candidate** только для проверки явно
  переданных schema/metadata values, не для authority inference из free text.
- `_VERSION_VALUE` — shaped version syntax, не source authority и не exact-version binding.

Остальные `question_plan*` и semantic frame consumers остаются C/OPEN. D25 целиком
не закрыта: этот slice проверяет две конкретные ветви, не все proof paths.

## D28: числа — не blanket exemption

| Symbol | Роль | Решение |
|---|---|---|
| `need_composition._COUNT_WORDS` → `_set_part` | Word→integer внутри распознанного list request; expected count с диапазоном 1–128 | S / SPLIT: ограниченная literal normalization может сохраниться только после явного согласования исключения. NL set/type/action templates — semantic migration P5. |
| `_project_answer_contract_shared._NUMBER_WORDS` → `_cardinality` | Digit branch берёт первый digit; word branch перебирает dict, не query offsets; диапазон 1–32 | S / SPLIT: value parsing отдельно, привязка cardinality к нужной obligation — обязательный replacement. |
| `_answer_units_shared._NUMBER_WORD_VALUES` → `_inventory_facts`/`_value_score` | Распознаёт word count около lexical inventory anchor либо наличие какого-либо number word | S / SPLIT: numeric normalization не доказывает requested subject/value; anchor synonyms отдельно D24. |
| `question_premise_proof._NUMBER_VALUES` | Count parser для premise | S / SPLIT: shared literal parser возможен, но это ещё не approved retained contract. |

Предложенное исключение на **общие числительные RU/EN** не принято автоматически:
оно явно ручное, хотя не product/topic словарь. На P1 владелец должен выбрать
согласованную literal-normalization границу либо общий языковой replacement.
Digit syntax, integer bounds и source offsets не требуют смысловых таблиц и сохраняются.

## Policy provenance: D01/D02 → D34

```text
project_retrieval_intent aliases: forbidden roles/terms
 → DocumentationLookup / DocumentationQueryPlan.as_payload
 → reference_query_tagging._tag_retrieval_query: trace fields 51–52
 → qualify_evidence → evidence_policy_rejection_reason

plan payload
 → context_query_probes.independent_query_probes: probe fields 28–29
 → qualify_evidence (final snippet recheck)
```

В `evidence_policy_rejection_reason` порядок сейчас:

1. Candidate identity, freshness, index synchronization, risk flags, lifecycle (`211–225`).
2. Forbidden terms из probe + explicit kwargs (`227–230`), substring test (`235`).
3. Forbidden roles из probe + kwargs (`231–234,237`).

Эти две разновидности inputs не имеют отдельных typed provenance полей. **Не
выключать функцию целиком:** независимые source guards остаются нужны, а forbidden
fields требуют audit producer/migration. Lifecycle parameter также может быть NL-derived
(D18); сохранение lifecycle check не означает сохранение текущего inference.

В grep по `docmancer/docs` новые producers этих двух полей вне alias/plan не найдены;
это не доказательство отсутствия dynamic/внешних producers. API kwargs остаются
публичной для внутренних callers возможностью; package/bridge audit ещё OPEN.

## Diagnostic evidence на неизменённом коде

Runner: [p0_policy_probes.py](p0_policy_probes.py).
Output: [archives/p0-policy-probes.json](archives/p0-policy-probes.json).
Python — `.venv/bin/python` (версия и source hashes в output).

```bash
PYTHONPATH=. .venv/bin/python v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/p0_policy_probes.py
.venv/bin/python -m pytest -q tests/docs/test_evidence_qualification.py tests/docs/test_governance_value_proof_p0.py tests/docs/test_evidence_set_need_composition.py
```

Наблюдения:

- Current synthetic source admitted; wrong project/stale/unsynchronized отвергаются.
- Proposal role/term запрещают тот же current source независимо от lexical proof.
- Forbidden `policy` отвергает также текст `policyCache` (substring semantics).
- `When does project work after launch?` window terms = `launch`, `work`;
  RU pair даёт `запуска`, `после`. Это асимметрия window cues, не доказанная final loss.
- Quoted `DocAtlas` не даёт exact anchor; quoted `NovelProduct` даёт anchor.
- Для четырёх RU/EN multi-count texts `_cardinality` возвращает 2, даже если nine/девять
  стоят первыми. Это parser observation; нужная cardinality должна связываться с facet,
  а не фиксироваться новым ожидаемым значением на основе этих искусственных texts.
- Три существующих набора: **81 passed in 3.30s**, exit 0.
  [Лог](archives/p0-policy-baseline-pytest.log). Это subset baseline, не required CI.

Probes не входят в frozen gold и ничего не отключают. Новые product fixes не делались.

## Next slice

Разобрать оставшиеся D25 frames/bridges и D30–D32; отдельно проверить фактическую
роль Android-specific proof rule. Для P1 подготовить ledger предложенных technical
исключений и behavioral migrations. P0 exhaustive DONE пока не доказан.
