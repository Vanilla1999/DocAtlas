# Project context quality implementation report

## Status

Implemented separate natural and independent paraphrase datasets, immutable
legacy snapshot checks, frozen lane inventory, fact alternatives, scope and
stable ID forwarding, isolated question-only report mode, CLI report output,
and always-upload CI artifacts. Runtime work also moved evidence qualification
into the domain, made projection requalify only model-visible snippets, preserved
bounded public lookup coverage, and fixed retrieval-first import order.

The user's follow-up supplied all five original questions verbatim. They now
replace the purpose, architecture, request-flow, evidence-selection, and public
tools questions under their existing stable IDs, with `original_user_verbatim`
provenance. The other ten authored positive cases, both negatives, and the
separate paraphrase file remain unchanged. Data is frozen before any live run.

## Frozen files

| File | SHA-256 |
| --- | --- |
| `cases.json`, `cases.legacy.json` | `b77ae44e8fb41bc53a6aa6cf584d886ee884ba337302285e4de9af2e4a5d829a` |
| `natural.json` | `ea8e4d9e6b518cb41b39c12ef3bc57424bf4dae8a408a451da67a8871a09a5b4` |
| `paraphrases.json` | `9b575bff7c2906dc8c91e94f2ad3d5c80607893e0c15188c986b6e2f2588d658` |
| `protocol.lock.json` (unchanged) | `58322c3af9cea3ebb74b76f7438d0abf677a4f98e94bd483550086bf4ac83516` |

New inventory: 15 positive + 2 negative natural cases, 5 positive + 1 negative
independent paraphrases. Every positive requires at least two independent fact
groups. Natural lookup minima are 2 or 3 per positive. All ordered IDs and hashes
are in `lanes.lock.json`. Thresholds were frozen before live execution and remain
unchanged: 1.0 / 0 / 13 / 12 / 15 / 12 in original lock-key order.

The five originals are not reduced to weak shared facts: request flow requires
MCP input -> `ProjectContextService` plan -> retrieval gateway -> visible-source
selection; tools require all three identifiers with independent usage facts;
selection spans domain qualification, application allocation, certification
proof, and the project-context boundary. Architecture requires application,
domain, transport, and infrastructure boundaries. The maintained module docs
were checked against the current MCP handler, unified service, projection, and
selection source without changing runtime aliases or code. All new gold and
allowed paths are active documentation; the superseded ADR remains legacy-only.

## Verification

Recorded verification for the runtime changes committed in `17df071` (not a
claim about subsequent edits):

| Check | Result |
| --- | --- |
| Targeted affected modules | 214 passed |
| Full offline suite | 3662 passed, 10 skipped |
| Advanced suite | 593 passed |
| Legacy live self-host | 9/15 positives, 1/1 negative; FAIL |
| Natural live self-host | 3/15 positives, 2/2 negatives; FAIL |
| Natural question-only | 1/15 positives, 2/2 negatives; report-only FAIL |
| Independent paraphrases | 0/5 positives, 1/1 negative; report-only FAIL |

All four live lanes retained zero false support, zero metadata-only evidence,
zero contamination, and no source/token budget violations. The primary natural
lane reached relevant Top-3 sources in 15/15 positives, but only 4 useful results
and 11 Top-1 fact-bearing results. Original coverage remained 0 because broad RU
questions are not falsely treated as completely equivalent to English retrieval
aliases. The current planner does not supply audited rewrites for the natural
questions. This explains the observed zero; it does not prove that sound
cross-language attribution is impossible or that the 12/15 target is invalid.
The historical false-green run cannot validate that target either. Keep the
target unchanged while separating attribution correctness from usefulness.

The frozen corpus also records expectation limitations requiring review:
`--no-vectors` is visible in `wiki/Supported-Sources.md` but accepted only from
`wiki/Commands.md`; `while preserving project sources` does not satisfy the
literal `preserves project sources`; and safe extra sources fail
`only_allowed_sources`. Safe does not necessarily mean relevant, so an alternative
path needs a reviewed factual witness, not blanket acceptance. These inputs
remain unchanged so the measured baseline is reproducible.

The five-positive paraphrase lane cannot meet absolute minima above five. It is
explicitly report-only in v1, so this is not an impossible primary release gate.
Its per-case failures remain meaningful even when aggregate thresholds are not
applicable to its denominator. See `V2_DESIGN.md` for the proposed migration.

The installed-agent run was explicitly cancelled and is not verified.

Red phase: six parameterized tests failed on the missing lane interfaces and
CLI option before implementation. The exact-five follow-up added four red test
instances for the original wording/fact components and truthful planning labels.
Green phase: **67 passed**, comprising all 19 targeted protocol test instances
and the evaluator's 48 release-gate tests.
The tests exercise scope at the actual runner dispatch boundary, stable positive
and negative IDs, all-required compound groups, alternate path witnesses,
covered-plus-missing original inventory, positive counts, corpus hash drift,
active source text, report-only isolation, and nonzero primary lookup minima.

Exact green command:

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q \
  tests/test_project_context_quality_protocol.py::test_legacy_bytes_and_thresholds_are_frozen \
  tests/test_project_context_quality_protocol.py::test_frozen_inventory_and_independent_components \
  tests/test_project_context_quality_protocol.py::test_scope_inventory \
  tests/test_project_context_quality_protocol.py::test_fact_alternatives_are_active_document_text \
  tests/test_project_context_quality_protocol.py::test_live_scope_stable_ids_and_report_only_isolation \
  tests/test_project_context_quality_protocol.py::test_paraphrases_do_not_enter_natural_gate \
  tests/test_project_context_quality_protocol.py::test_report_only_cli_retains_failed_verdict \
  tests/test_project_context_quality_protocol.py::test_gate_cli_failure_still_fails \
  tests/test_project_context_quality_protocol.py::test_project_context_quality_contract_passes \
  tests/test_project_context_quality_protocol.py::test_runner_forwards_scope_and_requires_each_fact_group \
  tests/test_project_context_quality_protocol.py::test_lock_rejects_corpus_drift \
  tests/test_project_context_quality_protocol.py::test_exact_original_five_questions_and_fact_components \
  tests/test_project_context_quality_protocol.py::test_contract_labels_and_executes_planning_not_retrieval \
  tests/test_release_gate.py
```

No manifest validator was disabled. The reviewed diagnostic shards contain the
current node hashes and full-suite collection succeeds.

The legacy contract executes alias recognition, query planning, and answer
requirements for RU/EN pairs. Natural/paraphrase contracts execute the query
planner and check public inventory and optional lookup semantics, not alias
recognition, visible evidence, or relevance. Reports explicitly label the two
evaluation kinds and set `retrieval_executed=false`. These are not retrieval
results. Planning checks pass legacy 16/16, natural 17/17, and paraphrases 6/6.
See `README.md` for exact standalone contract and live report commands. The
historical retrieval-first failure remains documented in `BASELINE.md`; current
fresh-process checks pass in both import orders.

## Ownership

Manual edits are limited to `eval/project_context_quality/*`,
`eval/project_context_quality_protocol.py`,
`tests/test_project_context_quality_protocol.py`, minimal `LiveCase`/runner
interfaces for IDs, scopes and fact alternatives, and CI's upload condition.
Existing evaluator attribution, citation integrity, budget, contamination and
threshold logic is preserved. The evaluator's `tests/test_release_gate.py` was
not edited. Concurrent production/query-plan changes were not reverted or
attributed to this task. No new agent harness or MCP schema was added.
