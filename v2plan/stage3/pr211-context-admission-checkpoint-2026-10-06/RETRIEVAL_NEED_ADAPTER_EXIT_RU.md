# Retrieval-need adapter — minimal SECOND consumer closure

2026-10-07. Workdir `/tmp/opencode/docatlas-next-admission-9488cb66`;
baseline `9488cb66ab989f6f65bafbfae7d1eb3f844ce0a3` плюс approved B overlay.
**Original direct-call repro CLOSED; full dictionary exit / acceptance NOT DONE.**
Primary не редактировался; network/commit/push/agents не запускались.

## Только четыре SECOND allowlisted files

1. `docmancer/docs/application/retrieval_need_support.py`;
2. `tests/test_dictionary_exit_retrieval_need_adapter.py`;
3. `tests/diagnostic_labels.dictionary_exit_retrieval_need_adapter.json`;
4. этот checkpoint `RETRIEVAL_NEED_ADAPTER_EXIT_RU.md`.

Все семь prior B files оставлены без SECOND edits, включая B test и checkpoint.
Parent setup `.venv`, `CONTINUE_HERE_RU.md`, `NEXT_PARALLEL_HANDOFF_RU.md` untouched
и не входят ни в B, ни в SECOND diff. Old tests/gold/thresholds/frozen registry и
historical manifests не редактировались.

## Минимальный production diff / ABI

AST comparison с baseline: изменена **только** definition
`apply_retrieval_need_witness`; все function signatures identical, остальные
helpers AST-identical. Никаких новых NL semantic detectors/positive contracts.

- Non-need lane возвращает прежнюю shallow copy без witness calls и изменений.
- Retrieval-need lane очищает inherited `need_local_witness`, `admission_route`,
  `matched_need_ids`, `need_witness_spans`, `need_witness_source_key`,
  `_admission_demands`, `context_eligible`, `context_need_ids`, `_need_context`.
  Поля source/text/version/hash и независимые diagnostic context bytes не удаляются.
- Не-True prequalification становится strict False, без попытки promotion;
  прежний rejection reason сохраняется, отсутствующий получает explicit reason.
- Empty/non-string body или non-Mapping source rejected до primitive вызова.
- Fresh primitive **is True** может только сохранить already-True prequalification
  и записать новый `need_local_witness=True`; old IDs/spans/routes не возвращаются.
- None, False, truthy non-bool/invalid primitive values дают `qualified=False` /
  `missing_need_local_witness`. Входной trace не мутируется, nested objects не меняются.

Original reviewer input:

```python
apply_retrieval_need_witness(
    {'query_origin': 'retrieval_need', 'need_relation': 'default'},
    {'qualified': True, 'need_local_witness': True},
    'Unrelated quux is 9000.',
)
```

Теперь результат:
`{'qualified': False, 'qualification_reason': 'missing_need_local_witness'}`.
Тест проверяет exact original chain, не mocked semantic proof, и неизменность input.

## Reachability / provenance boundaries

Current production invocation **не найдена**: `_project_docs_service_part03.py` и
`_docs_context_projection_core.py` только импортируют adapter. Это dormant callable
consumer compatibility defect, **не доказательство active default pipeline bypass**.
Prior B runtime qualifier control по-прежнему rejects old need lane раньше adapter.
External SDK callers UNKNOWN; этот SECOND slice не делает terminal-authority claim.

Adapter не проверяет source membership/project/version/snapshot/lifecycle/full-source
hash и не может заменить guards domain qualifier. Positive stub test доказывает
только veto-only bool ABI, **не authenticates source/NL evidence**. Existing exact
key/value literal ProofObligation positive и wrong-value negative сохранены и
исполняются настоящим unit proof API. У adapter нет current supported literal-default
relation contract: literal unit positive сам по себе не номинирует NL relation;
adapter с таким text остаётся unknown/rejected. Новый contract не изобретён.

Downstream real `select_evidence` сохраняет исходный Unicode quote как context,
но не возвращает answer support; need trace False без inherited need credit.
Source bytes/technical grammar/guards/caps/hash domains не менялись. Оставшиеся
state/behavior/requirement/exception helpers за пределами minimal fix, AST unchanged.

## Normal-conftest offline tests / сохранённые reds

Команды: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest
-p no:cacheprovider -q ...`. Normal conftest + new hash-bound diagnostic shard;
никакого `--noconftest` / test-assertion rewrite.

- NEW adapter tests: **47 passed**. Original repro, all inherited need fields,
  immutable MappingProxy trace, invalid prequalification/body/source/proof values,
  no promotion, non-need lane, exact literal proof и downstream context selection.
- NEW47 + prior B94 + six technical modules (`target_security`, `content_trust`,
  `reference_hash_domains`, `review_source_capabilities`,
  `finalized_mcp_output_integrity`, `mcp_boundary`): **185 passed / 2 failed**.
- All current `tests/test_dictionary_exit_*.py`: **1571 passed / 1 failed**.
- Old `tests/docs/test_need_local_admission.py`: **9 failed / 0 passed**.
- Adapter-only in-memory baseline overlay, approved B and other modules current:
  prior B + old need suite **94 passed / 9 failed**, exact old red nodes unchanged.
  Это **partial single-file overlay**, не full-baseline comparison.
- `git diff --check`: PASS; SECOND production diff ограничен одним adapter body.

Два targeted red nodes, не waived:

1. `tests/test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
   — frozen-by-current-approval B diagnostic asserted old unknown passthrough.
   SECOND closes precisely that debt; test оставлен untouched по allocation.
   Теперь incoming `qualified=True` превращается в False. Parent решает отдельно,
   когда authorised reconcile historical debt assertion; executor не редактирует B.
2. `tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`
   — прежний documented `answer_available=True` expectation, line 204.

Все девять old need red nodes (identical adapter-overlay):

- `test_separate_default_and_exception_survive_long_root[17-LeaseExpired]`
- `test_separate_default_and_exception_survive_long_root[29-WaitExpired]`
- `test_need_local_admission_does_not_accept_full_keyword_distractor`
- `test_need_local_admission_keeps_subject_binding`
- `test_need_local_admission_does_not_fabricate_missing_second_need`
- `test_typed_need_proof_allows_subject_bound_elsewhere_in_same_source_span`
- `test_requirement_need_uses_normative_relation_not_keyword_overlap`
- `test_disabled_behavior_need_accepts_not_enabled_but_rejects_enabled_state`
- `test_single_typed_need_keeps_internal_probe_even_when_text_equals_root`

Prefix у всех: `tests/docs/test_need_local_admission.py::`. Эти reds не приписаны
новому adapter change. Logs: `/tmp/opencode/retrieval-need-adapter-{targeted,
old-mixed,baseline-overlay,all-dictionary-exit}.log`; эта committed-file candidate
запись сохраняет counts/nodes/limits независимо от temporary logs.

## SECOND source pins (SHA256)

| File | SHA256 |
|---|---|
| retrieval_need_support.py | `d2de34da2c656c9beb70c34314daf8761aeaec1c4917d1928771792b548362d7` |
| test_dictionary_exit_retrieval_need_adapter.py | `f89bc143661348084e9fd694a46b5f882e95e3fd80f1ab67b628086771e46507` |
| diagnostic_labels.dictionary_exit_retrieval_need_adapter.json | `4d7436f43e7787310ae6bf0f00c4ae1d16db2d1ce6985c4044d7cca6998e37fd` |

Parent extracts **только четыре SECOND files** отдельно от approved B seven;
не staging whole dirty worktree. Full CI/rebuilt package/integrated indexed MCP/
stdio/self-host quality не запускались; previous quality FAIL не отменён.
**Full NOT DONE.**
