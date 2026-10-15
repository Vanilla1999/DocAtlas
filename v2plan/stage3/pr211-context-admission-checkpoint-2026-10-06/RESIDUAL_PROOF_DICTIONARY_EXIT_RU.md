# Residual proof dictionary exit — bounded PRIMARY slice

Дата: 2026-10-07. Baseline `307c480cd7ffe2fff5a264167dcb09a7974ffc20`.
**Allocated implementation выполнена; full dictionary exit NOT DONE.**
User-authorized parallel PRIMARY; independent review/combined integration pending.

## Exclusive файлы

Production изменены только:
- `docmancer/docs/domain/governance_value_proof.py`
- `docmancer/docs/domain/question_premise_proof.py`
- `docmancer/docs/domain/_answer_units_part02.py`

Новые:
- `tests/test_dictionary_exit_residual_proofs.py`
- `tests/diagnostic_labels.dictionary_exit_residual_proofs.json`
- этот checkpoint.

Shared/part01, compiler/frames/ownership, existing tests, gold, frozen corpus,
thresholds и historical manifests не менялись этим исполнителем. Concurrent
discovery/compiler файлы других agents не reviewed и не approval этого slice.
Raw gzip не тронут. Network/commit/push не выполнялись.

## Удалено / сохранено

Governance: удалены NL policy/owner/defer/pin detectors, stopwords, inflection/
synonym canonicalization, version/owner binding и Android-13-specific requirement
reasoning. Typed governance relation и authority identities сохранены. Missing
canonical authority остаётся negative; canonical authority не даёт semantic credit.
Unknown relations получают immutable `PlannedProof(False, ...)`, не fallback None.

Premise: удалены causal/limitation/action synonym rules, NL number/tool cardinality,
universal contradiction/explanation logic и metadata subject fallback. Public ABI
`PremiseProofResult`/`premise_relation_proof` сохранён. Все relations, включая unknown,
возвращают negative tuple с reason, zero scores; это immutable negative trace.
Изменение прежнего unknown→None intentional: None больше не приглашает fallback.

Supplied AnswerUnit: удалены purpose/effect/attribute/inventory/command/location/
comparison/usage/special-relation semantic approvals и product/generic-subject
exceptions. Boolean/number/value sniffing не certifies факт. `proposition=True`
не открывает semantic approval. Exported helper symbols/imports сохранены;
semantic helpers возвращают conservative negatives. Local negation guard сохранён.
Frozen DTOs, extraction, structural context, spans/hashes и enum owners не менялись.

Единственное positive — прежний narrow `exact_fact`, explicit typed config/env/code
subject, exact single-line key/value equality. Нет relation/target/context, aliases,
metadata binding, value normalization, neighboring multiline declarations или
substring value credit. Matched quote pair — syntax, literal case exact.
`explicit_literal_value_only` не удостоверяет NL answer/edit/mutation authority.
Lifecycle guards сохранены. Дополнительно проверяются deterministic unit ID,
unit hash, span length, CR/multiline rejection; при supplied `content`/`text` — exact
source span и отсутствие nonwhitespace соседней части того же declaration line.
`best_local_proof` empty→None; overflowing supplied packet (>64)→None, не partial pass.

## Offline normal-conftest проверки

Все через `.venv/bin/python -m pytest -p no:cacheprovider -q`,
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`; repository network guard активен,
новый hash-bound shard loaded без `--noconftest`.

- Новый suite: initial **118 PASS**, затем добавлен 1 neighboring-line regression;
  final **119 PASS** (в обоих final combined runs).
- Новый + `test_dictionary_exit_structural_units.py`,
  `test_dictionary_exit_literal_needs.py`, `test_dictionary_exit_literal_needs_mcp.py`:
  final **246 PASS**.
- Новый + шесть technical modules (`test_target_security`, `test_content_trust`,
  `test_reference_hash_domains`, `test_review_source_capabilities`,
  `test_finalized_mcp_output_integrity`, `test_mcp_boundary`):
  final **164 PASS / 1 FAIL** = new119 + technical45pass/1red.
- Old mixed `tests/docs/test_governance_value_proof_p0.py`,
  `tests/docs/test_answer_units_v2.py`, `tests/docs/test_answer_units_v3.py`:
  **2 PASS / 28 FAIL**. Assertions не изменялись. Большинство fails происходит
  до local prover на empty old inferred obligations; есть прежние alias/group/
  projection expectations. Это не blanket attribution всех reds текущему slice.
- `git diff --check`: PASS на момент проверки concurrent tree.

Technical red: `test_patch_constraints_debug_compaction_preserves_contract_fields`
в `tests/docs/test_mcp_boundary.py:204` требует advisory `answer_available=True`.
Не восстановлено и не waived. Initial all combined run: 290pass/1fail до добавления
последнего negative case. Final combined subsets выше — current checks.

## Current bounded pins (не historical manifest и не acceptance)

| Файл | SHA256 |
|---|---|
| governance_value_proof.py | `69e0e18c4d2381809c9dc93398fc4a2dd46efeedbde6a507b91d11abdd777ca8` |
| question_premise_proof.py | `dc9f543bef179effe022784ecd739c0ec21b19ead007d047b32a8df2a419fdbc` |
| _answer_units_part02.py | `7afe6398c966dfebe5e7033a6e450ba0054d3a69a7919ec2fedc178ae5db337e` |
| test_dictionary_exit_residual_proofs.py | `8c58df46508abe1831e6b3e55b311af048b114f59c4c176e0b0d2659f90715b3` |
| diagnostic_labels.dictionary_exit_residual_proofs.json | `601ead2de4c0df5b467d4d784518775761c46bce5f3bca7bb511e1130e74da5f` |

## Остаток / provenance / next bounds

- `_answer_units_shared.py` всё ещё содержит NL usage/contrast/tool/count/purpose/
  effect/architecture/version/duration dictionaries. `_answer_units_part01.py`
  содержит callable `_purpose_clause`/`_effect_relation_valid` helpers. Этот slice
  больше не вызывает их для approval, но их existence/direct-call debt не удалён.
  Они unowned: нужна отдельная parent allocation, не silent shared edit.
- `_evidence_selection_part02.py` legacy non-obligation semantic matches,
  retrieval-need/selector/qualification consumers остаются отдельным caller audit.
  Technical assignment hash/span guards внешних consumers не изменялись.
- Compiler/frame/need-composition изменения идут disjoint; current concurrent
  runtime failures нельзя приписывать этому slice без integrator comparison.
- Without supplied source content, literal proof validates only local DTO equality.
  Он НЕ authenticate source path/version/snapshot/library/project identity или
  полный source hash. Source membership/hash/window identity остаются внешними
  consumer guards; metadata не считается answer subject или evidence содержания.
  Forged full source provenance вне этого local interface всё ещё review boundary.
- Exported ABI helpers сохранены. Removed private governance/premise lexical
  helper names не имеют найденных production imports; external SDK users UNKNOWN.
- Next: independent scoped review, parent combined snapshot/test pins и public
  indexed MCP/stdio; отдельно allocate shared/part01 semantic helper cleanup и
  non-obligation consumer audit. Не улучшать quality ручными topic exceptions.
- Full CI, rebuilt wheel/release, all corpus, completeness/self-host quality не
  запускались этим исполнителем. Прежний quality FAIL сохранён, не green gate.

**Full NOT DONE; bounded implementation не release acceptance.**
