# Default-read follow-up после публикации checkpoint

**Следующий literal-needs срез реализован:**
[LITERAL_NEEDS_FOLLOWUP_RU.md](LITERAL_NEEDS_FOLLOWUP_RU.md).
447 новых tests PASS; scope review approved, quality остаётся red.
Ниже сохранён исторический план следующего шага от baseline `c4add087`.

2026-10-06. **ACTIVE / NOT DONE.**

Первый reviewed partial dictionary-exit checkpoint committed/pushed:
`58750962` → `origin/integration/stage3-v2-identity-pr1`, без force/merge.
В commit также вошёл ранее локальный checkpoint `9a7299e2`; опубликованная история
не переписывалась. Raw gzip archive остался локально согласно решению владельца.

Перед публикацией закрыты review blockers: cached current scope, explicit
consent/nondelivery, fresh serialized requirements. Independent 274 passed
(228 new +46 technical), 24 scope/16 malformed probes; stdio smoke повторно PASS.
Quality red и remaining dictionary inventory этим не закрыты.

## Согласованный контракт следующего среза

Два исполнителя работают в primary с непересекающимися ownership sets:

1. `query_reference_binding.py`, import consumer `question_retrieval_needs.py`,
   `context_candidate_ranking.py`: убрать NL role/relation/actor/source-prefix
   и action/topic ranking. Сохранить literal references/offsets/mention hashes,
   path normalization/catalog resolution/ambiguity checks и positional rank ABI.
2. `_answer_units_shared.py`, `_answer_units_part01.py`, `_answer_units_part02.py`:
   structural segmentation отдельно от semantic proposition/proof. Сохранить
   IDs/hash/spans/materialization bounds; removed semantic proof fail closed.

Common qualification/projection/selector consumers не меняются конкурентно.
Новые tests — отдельные `test_dictionary_exit_reference_ranking.py` и
`test_dictionary_exit_structural_units.py`, new-only diagnostic shards.
Existing tests/gold/thresholds не меняются. Старые source manifests сохраняются
как snapshots предыдущего состояния. После обоих slices — combined tests,
actual indexed public MCP/stdio и независимое review перед дальнейшей публикацией.

Это continuation, не полный dictionary exit. Corpus/advanced SDK rules и
прежняя original-coverage regression остаются отдельными OPEN задачами.

## Structural executor returned — independent review pending

Удалены copula/behavior/status dictionaries и action/sequence grouping.
Units остаются структурным context, не propositions/proof. Narrow typed literal
declaration equality помечена `explicit_literal_value_only`, без answer authority.
Executor: 55 новых structural tests passed, 46 technical passed; old unit suites
2 passed/19 failed, admission/component 39 passed/26 failed — assertions не менялись.
Combined run исполнителя наблюдал 336 new tests passed, но concurrent second slice
ещё требует окончательной combined проверки после его возвращения.

Actual stdio MCP smoke integrator: PASS после structural slice. Independent reviewer
проверяет IDs/spans/literal proof и proposition-filter consumers: context selection,
retrieval need support, admission local binding и selector. Не восстанавливать
support универсальным `proposition=True`; expected proof-loss не приравнивать
автоматически к безопасной потере полезной доставки.

## Reference/ranking executor returned — combined review pending

Удалены NL role/context/source-prefix/actor rules и stripping исходного текста;
consumer `_NON_ENTITY_ACTORS` адаптирован без переноса таблицы. Literal catalog
basename/stem/casefold tiers, identities/offsets/hash/window checks сохранены.
Semantic/action ranking priorities отключены при сохранённой tuple positional ABI.
Executor: 60 новых tests passed, 14 targeted reference checks passed, 46 technical
passed; mixed reference/ranking 51 passed/115 failed, need consumers 22 passed/
18 failed. Не все mixed failures причинно отнесены только к этому срезу.

Final combined integrator run после обоих исполнителей: **343 new tests passed**.
Frozen approved pins 13/13 совпали; existing tracked tests/eval/workflows diff пуст.
Два независимых scoped reviews выполняются раздельно, дальнейшей публикации ещё нет.

Remaining OPEN: `_need_relation`, NL clause/context inheritance, admission/comparison
parser consumers в `question_retrieval_needs.py`; common component-witness/variant
consumers; compatibility supplied `semantic_subject`; purpose/effect/usage/comparison/
inventory/special-relation/location proof и planned-proof modules. Их достижимость
и требуемые изменения оцениваются review, не признаны автоматически техническими.

## Independent reviews: structural approved, reference blocked

Structural review: scoped approval, без продемонстрированного delivery blocker.
105 bounded checks passed; legacy runs 65 passed/39 failed и 2 passed/7 failed.
Legacy negative fixtures часто не достигают old proof lane; эти red runs не являются
чистой negative-safety acceptance. Старые assertions не переписываем; новые
context-only negative checks дополняют coverage без подмены старых критериев.

Reference review выявил реальные constraint-placement/identity defects:
verified source locator ошибочно входит в body exact terms; filename parser
обрезает `Guide.md.bak`/`Guide.md-extra` до catalog `Guide.md`; symbol/catalog stem
collision может менять symbol role на source locator. Executor исправляет эти
случаи с occurrence-aware constraints и end-to-end qualification tests.
Follow-up commit/push пока заблокирован.

Reference review: 106 new+technical passed; broader mixed 172 passed/90 failed,
не все failures классифицированы как expected semantic-proof loss. Default read
достигает `compile_need_contracts → retrieval_needs` из SourceReferenceContext и
prefit set_context_variants: `_need_relation`/comparison/clause-context inheritance
и `need_contracts` остаются **live OPEN**, не только advanced SDK. Выполнение не
доказывает успешное proof/admission этих generated lanes.

## Final follow-up result: scoped approval

Reference blockers закрыты occurrence-aware body constraints, complete filename
identity и symbol/catalog separation. Дополнительный terminal-period defect
исправлен: `Guide.md.` перед whitespace/end — пунктуация, `.bak`/`-extra` —
продолжение другой identity. Independent reference reviewer дал scoped YES;
92 reference tests passed, original repro и negative scope/hash/window controls
проверены. Structural review также scoped approved.

Последний combined integrator run: **375 новых tests passed**, actual stdio MCP
smoke **PASS**. Это не full CI, не quality-green и не release acceptance. Existing
mixed suites red сохранены: reference/need 133 failed/73 passed по последнему
прогону executor (перед punctuation-only поправкой); structural red выше.
Frozen pins и старые tests/gold/thresholds не изменяются.

Срез готов к отдельному follow-up commit. Следующий bounded шаг: убрать live
`_need_relation`, comparison/admission parser use и NL clause/context inheritance
из default `question_retrieval_needs.py`/`need_contracts.py` и их producers;
сохранить explicit plan provenance и literal context без inferred semantic needs.
Advanced patch/corpus/delivered-policy остаются дальше по очереди.
