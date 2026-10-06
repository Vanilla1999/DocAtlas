# Unit helper dictionary exit — SECOND disjoint slice

Дата: 2026-10-07. PRIMARY baseline `307c480cd7ffe2fff5a264167dcb09a7974ffc20`.
**Bounded implementation выполнена; full dictionary exit NOT DONE.**
Independent review/integrator checks остаются next, не release acceptance.

## Exclusive ownership

Изменены только production:
- `docmancer/docs/domain/_answer_units_shared.py`
- `docmancer/docs/domain/_answer_units_part01.py`

Новые:
- `tests/test_dictionary_exit_unit_helpers.py`
- `tests/diagnostic_labels.dictionary_exit_unit_helpers.json`
- этот checkpoint.

FIRST production/test files под independent review не редактировались: их четыре
hashes совпали с `RESIDUAL_PROOF_DICTIONARY_EXIT_RU.md`. First diagnostic shard и
checkpoint не менялись. Compiler/discovery/common consumer файлы других agents,
existing tests/gold/freeze/thresholds не менялись этим SECOND исполнителем.
Нет network/commit/push. Historical raw gzip сохранён.

## Реализация / инварианты

Shared NL usage/contrast/tool/count/purpose/effect/architecture/version/duration
lexicons удалены, не перенесены. Старые exported regex symbols остаются как
nonmatching `(?!)` ABI adapters, number-word map пуст. Они не распознают даже
пустую строку и не предоставляют semantic credit.

Part01 `_purpose_clause`→None, `_effect_relation_valid`→False. Также удалены
callable generic object/predicate approvals: `_predicate_has_object`,
`_positive_relation_match`, `_positive_relation`→False. `_context_score`→0 даже
для empty context; metadata overlap не proof и нет empty/all-pass defaults.
Signatures и exported helper names сохранены. Negation guard shared сохранён
как negative-only; absence of negation не используется для approval.

Не изменены exact structural segmentation/source slices, source-relative char
offsets и physical-line boundaries, deterministic unit IDs/hash, frozen AnswerUnit/
LocalProof validation, caps, softwrap, bounded clauses, word distance, makeunit,
boundedtext/source-field extraction, ordering/dedupe/materialization и structural
bullet grouping. Extracted units остаются `proposition=False`, context only.
Новые tests проверяют полезные EN/RU/unknown prose quotes с исходными bytes,
Unicode/softwrap, table/code/bullets/source fields, IDs/hashes/offsets/immutability.

Strict key/value technical grammar и first-slice literal exception не изменены:
typed exact subject/key/value, matched quote syntax, literal case, lifecycle/span/
unit-identity checks остаются. NL duration/version detector removal не выключает
literal `17 ms`/`^3.11` equality. Технические code-declaration/Markdown/punctuation
patterns сохранены, а не заменены universal negative.

Read-only AST comparison against baseline:
- Part01: изменены ровно 6 semantic helper definitions выше;
  остальные **14 definitions AST-identical**, включая extractor/DTO/materializer.
- Shared: **12 structural/schema/cap/negative-guard assignments AST-identical**:
  heading/bullet/table/key-value/code/sentence/paragraph/identifier/negation patterns,
  schema и оба limits.

## Normal-conftest offline проверки

`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest
-p no:cacheprovider -q ...`; repository network guard и hash-bound NEW shard active,
нет `--noconftest`, existing manifest/tests не переписаны.

- NEW second: **48 PASS**.
- NEW second + untouched first119 + structural55: **222 PASS**.
- Those three + шесть technical modules (`test_target_security`, `test_content_trust`,
  `test_reference_hash_domains`, `test_review_source_capabilities`,
  `test_finalized_mcp_output_integrity`, `test_mcp_boundary`):
  **267 PASS / 1 FAIL** = 222 + technical45pass/1red.
- Old mixed `test_governance_value_proof_p0.py`, `test_answer_units_v2.py`,
  `test_answer_units_v3.py`: **2 PASS / 28 FAIL**, как first-slice run.
  Empty inferred obligations/old group/alias/projection assertions остаются red,
  не blanket attribution concurrent compiler edits этому slice.
- Scoped `git diff --check`: PASS.

Technical red сохранён: `tests/docs/test_mcp_boundary.py:204`,
`test_patch_constraints_debug_compaction_preserves_contract_fields` требует
advisory `answer_available=True`. Не waived, authority не восстановлена.

## Current bounded source pins

| Файл | SHA256 |
|---|---|
| _answer_units_shared.py | `a02ba9ba79f70453198cda66545ffd655d5c5ae008c49a068cbcda2fe264d90b` |
| _answer_units_part01.py | `fe6dedce9c3afa818ffd18d605905208026f3d5111f052dcebcb83aff2b414d9` |
| test_dictionary_exit_unit_helpers.py | `2725785079d29f024779bc124dbf9d52b39bda980cf3a8cf18cfd2c2c09408c6` |
| diagnostic_labels.dictionary_exit_unit_helpers.json | `3118f4a18dc8bdfd218b6a1f8385d0f12217cdffd6f51f36af89d87e8e1fbbef` |

Это bounded local snapshot, не manifest acceptance concurrent tree.

## Remaining consumer audit — отдельный parent next

- `admission_local_binding.py` импортирует `_DURATION_RE` из public answer_units;
  matches в `_value_is_local:99` и `_discourse_value_is_local:125` теперь negative.
  Import/runtime ABI не сломан. No parent edit required для import preservation,
  но NL timeout/default/anaphoric/condition rules самого consumer ещё существуют.
  Explicit typed duration contract/cleanup требует отдельного allocation; не
  восстанавливать semantic duration dictionary ради old coverage.
- Non-obligation `_evidence_selection_part02.py` branches (behavioral contract,
  cross-module invariant, facet, canonical-policy/qualifier matches), а также
  `retrieval_need_support.py`/selectors/qualification остаются separate audit.
  Этот SECOND slice не утверждает отсутствие их semantic rules/SDK direct callers.
- Literal helpers `_subject_spans`/`_contains_term` остаются exact caller-supplied
  technical identity/span operations, не relation entailment. Shared negative
  symbols сохраняют external ABI; external SDK reliance на старые positives UNKNOWN.
- Source membership/library/project/version/snapshot/full-source hash authority
  остаётся внешней consumer boundary; local equality не full provenance certification.
- Next: independent SECOND review + parent combined current pins/tests и indexed
  MCP/stdio, затем отдельно allocate non-obligation/admission consumer cleanup.
  Common consumer edits не выполнять конкурентно с их owners/review.

Full CI/rebuilt wheel/release/all corpus/self-host quality этим slice не проверены.
Прежний quality FAIL не отменён. **Full NOT DONE.**
