# Selector visibility dictionary exit — bounded PRIMARY allocation

Дата: 2026-10-07. **Original false-coverage repro закрыт. Full release acceptance
и full dictionary exit НЕ заявляются.** Предыдущий residual-proof slice не изменён.

## Exclusive scope

Production изменены только:
- `docmancer/docs/application/_evidence_selection_part01.py`
- `docmancer/docs/application/_evidence_selection_part02.py`
- `docmancer/docs/application/_evidence_selection_part03.py`

Новые: `tests/test_dictionary_exit_selector_visibility.py`,
`tests/diagnostic_labels.dictionary_exit_selector_visibility.json`, этот checkpoint.
Unowned/shared/compiler/discovery/projection/candidate-normalization production
не изменялись. Old tests, gold, frozen manifests, thresholds не менялись.
Network/commit/push не выполнялись.

## Original repro closure

```python
raw = {
    'path': 'docs/example.md', 'authority': 'canonical',
    'content': 'Unrelated policy must remain.',
    'metadata': {'code_snippets': [{'code': 'erase_all()'}]},
}
d = select_evidence(
    [raw], question='inspect', config=patch_selection_config(2000),
    public_requirements=[{'kind': 'code_group', 'value': '["erase_all()"]'}],
)
```

Раньше: status=ok/support=True, requested code отсутствует в visible text,
unit-less assignment проходит binding/sufficiency. Теперь:
**insufficient_evidence, support=False, code uncovered, assignments empty**.
Это проверяется actual public-requirement selector test, не mocked helper.
Forged successful decision и whole-candidate content assignment отвергаются
strict binding/sufficiency validation. Hidden metadata/full-parent content не
используется как code witness.

## Что изменилось

Content coverage во всех profiles → `_witness_for_requirement` → actual normalized
display unit. Code group требует exact case-sensitive fragments в одном bounded
structural code unit: fenced code, code declaration или inline backtick code.
Для declarations, извлечённых как key_value, сохраняется mechanical
`const|let|var|final <identifier> = <literal text>` grammar. Это syntax, не
purpose/action/behavior interpretation. Prose mention без code structure не
certifies code presence. JSON fragments должны быть nonempty strings; numeric/
null coercion удалён. Существующие token/source/requirement budgets не изменены;
новый arbitrary cap количества fragments не введён (7-fragment positive tested).

Exact term/entity теперь дают только exact literal, boundary-aware visible
presence; no CamelCase/snake/case aliases. Explicit `required_fact` поддерживает
только equality с exact unit quote, не thematic substring/word overlap.
Semantic behavior/cross-module/canonical-policy/facet/target/preserve/unknown
non-obligation witness paths остаются uncovered. `proposition=True` не authority.
Normative vocabulary больше не создаёт canonical-policy requirement.
Semantic qualifier detectors не дают approval; supplied qualifiers fail closed.
Negative conflict/dedup polarity guards не превращены в positive witness.

`_candidate_source_view` теперь задаёт content/text **exact normalized display**,
а не metadata raw/full-parent content. Локальные offsets относятся именно к нему.
Separate window guard проверяет display hash, original→normalized equality,
явные stable/parent IDs, path/authority/project/module/version/snapshot consistency,
coordinate fields, freshness/index/risk и supplied display hash.
Unit guard сравнивает kind/ID/text/hash/spans с deterministic re-extraction;
source-field units исключены. Packet > existing MAX_ANSWER_UNITS fail closed.
Lifecycle current/historical/either сохраняется explicit protocol binding.

Assignment validation повторяет actual content matching, а не проверяет один DTO
hash. Проверяются requirement/evidence/path/proof-role identities, absolute
source-relative offsets/line и local unit offsets/hash. Unit-less assignments
разрешены только explicit valid evidence/target path, project/module identity,
exact version/snapshot constraints; никаких unit-less code/content witnesses.
Patch selector без assigned visible content не получает supported status.
Sufficiency вызывает тот же strict binding validator; unrelated canonical
`must` больше не заменяет required visible content.

## Preserved boundaries

Status enums, frozen DTOs, helper signatures, assignment/selection hash protocol
не менялись. Ranking/reserve/budget algorithms не переписаны; fitting остаётся
witness-scoped. Technical scope assignments сохраняются отдельно от content.
Current docs projection downgrade untouched: eligible quotation retained,
answer_supported=False, answer_available=False, edit_ready=False.
Positive patch literal coverage не grants mutation permission: terminal mutation/
edit gates вне allocation не изменялись и не объявляются proven bypass-free.

Local window/DTO consistency НЕ full source provenance. Self-consistent display
hash/snapshot не authenticate indexed parent/library/project/version history.
Upstream authoritative source/reference/window guards остаются обязательными.
Никакой `prepared_source_record` identifier/protocol не добавлен.

## Offline normal-conftest checks

Все pytest runs: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`,
`.venv/bin/python -m pytest -p no:cacheprovider -q`; normal conftest/network guard
и новый hash-bound diagnostic shard активны, без `--noconftest`.

- Final new suite: **74 PASS**.
- All `tests/test_dictionary_exit*.py`: **1431 PASS**; после последнего mechanical
  fragment-cap adjustment весь этот набор снова вошёл в combined run ниже.
- New + technical target_security/content_trust/reference_hash_domains/
  review_source_capabilities/finalized_mcp_output_integrity/mcp_boundary:
  **119 PASS / 1 FAIL**.
- Final all dictionary_exit + those technical modules: **1476 PASS / 1 FAIL**.
- Existing selector modules `test_evidence_selection.py`,
  `test_evidence_selection_part02.py`, `test_evidence_selection_v2.py`:
  **25 PASS / 57 FAIL**. Old assertions unchanged. Есть old inferred facets,
  supported-docs expectations, thematic substring/qualifier expectations и changed
  literal witness ranking; нет blanket attribution всех reds этому slice.
- Scoped `git diff --check`: PASS.

Preserved technical red: `tests/docs/test_mcp_boundary.py:204`,
`test_patch_constraints_debug_compaction_preserves_contract_fields` требует
advisory answer_available=True. Не waived, не исправлен восстановлением authority.

Новый suite покрывает original selector repro, hidden full parent, strict
sufficiency/unit-less content forgery, valid fenced/inline/declaration code,
manual proposition negatives, transplanted literal/kind/ID/window, absolute
assignment span/hash/path/role mutations, original/DTO scope and freshness/risk/
lifecycle/hash mutations, technical scope positives/negatives, capacity/overflow,
immutability и retained context-only quotations.
Initial new-test failures исправлены без изменения old tests: extractor отнёс
`const ... = ...` к key_value (добавлена mechanical declaration grammar); первый
budget test имел short assigned unit, корректно помещавшийся после witness crop
(заменён oversized actual code unit). Final результаты приведены выше.

## Import/dependency risks / residual OPEN

Part02 больше не зависит от evidence_semantic_density для positive witnesses.
Part01 validator использует local import part02 matcher: предотвращает module
initialization cycle при existing part02→part01 helper imports.
Window guard переиспользует existing evidence_candidates `_span`, authority,
source_path/version helpers; coordinate/normalization contract changes требуют
повторного integration audit. Deterministic re-extraction использует existing
structural extractor (не менялся здесь); новые shapes не разрешать bypass без
ID/span/hash/window binding. Bounded re-extraction добавляет CPU work; whole-corpus
performance/release benchmarks не запускались.
SDK semantic qualifiers/source-fact/request-plan consumers могут потерять coverage:
intentional conservative debt, не чинить ручными topic exceptions.
Full CI, rebuilt wheel/release, live indexed MCP, whole old corpus и mutation
authority end-to-end не заявляются checked. Existing quality FAIL сохраняется.

## Current pins

| Файл | SHA256 |
|---|---|
| _evidence_selection_part01.py | `269d2367691889a480e219bed40a96095148cbc34b1d57336dd5293951fed43b` |
| _evidence_selection_part02.py | `e7426b05e91b4db87abd1cc79a49a9e0b81cd0ea2f4af336f41cbe1bc3c25a0f` |
| _evidence_selection_part03.py | `7a7d56bdffe0c3cc47cd22865cf6ef0810f9a3ab082e7187db2b0eb10de2b093` |
| test_dictionary_exit_selector_visibility.py | `cf9e72885504d31300b8f21c685796bd2375f3f5956ea77617f6aba111fedf9b` |
| diagnostic_labels.dictionary_exit_selector_visibility.json | `5db463c749a12d2840a9810eadd98c07050b8dce5a5c7996d0235f75267e717e` |

Previous approved residual production pins unchanged: governance
`69e0e18c4d2381809c9dc93398fc4a2dd46efeedbde6a507b91d11abdd777ca8`, premise
`dc9f543bef179effe022784ecd739c0ec21b19ead007d047b32a8df2a419fdbc`, answer part02
`7afe6398c966dfebe5e7033a6e450ba0054d3a69a7919ec2fedc178ae5db337e`.

**Allocated implementation complete; independent scoped review / parent acceptance
pending. Full NOT DONE.**
