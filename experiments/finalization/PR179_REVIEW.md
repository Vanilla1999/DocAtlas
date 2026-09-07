# PR #179 review and fixes — 2026-09-07

## Scope and revision

Review started from `484c4beb908c463812fe9b7352bb43f25d659904` on
`fix/context-first-project-reads-finalization`. The local reproducible baseline
was `4d93a5f3be9cd5bc31f3079d6fddb571cf0a96d7`; the intervening changes only
prepared temporary review artifacts.

Validated production fixes are published as
`c5c8c679e51805354234721d2951941efedc869d`.
This report is a follow-up documentation change, not a claim that every PR
workflow or the remaining quality acceptance gate is green. PR stays draft.

## Findings fixed

### P1 — Host lookup overwrote the original question's exact-term lineage

In `docmancer/docs/domain/documentation_query_plan.py`, the host lookup loop
reassigned `parent_exact_terms`, which was subsequently reused by original
`query-intent-*` aliases. Adding a lookup could erase `FooEngine` or replace it
with `BarEngine` in a question about `FooEngine`.

The host rewrite now uses `host_parent_exact_terms`, leaving the original
question's exact terms intact. Four regression cases cover lookup contents and
ordering.

### P1 — Negative contractions acquired positive audited rewrites

The same module's host negation guard missed `doesn't`, `doesn’t`, `cannot`,
`can't`, `can’t`, and `won't`. Such lookups could receive a positive request-boundary
rewrite. The guard now handles contractions and additional negative forms.
Six regression cases preserve the original lookup and reject positive audited
lineage. This is a conservative rewrite guard, not a general semantic verifier.

### P2 — Generated aliases multiplied public coverage priority

In `docmancer/docs/domain/project_doc_ranking.py`, a public lookup and its
multiple audited aliases were all counted as distinct public directions. A
single requested topic with three aliases could outrank three distinct public
lookups.

Public coverage and audited retrieval directions now have separate sets.
Novel public directions have priority. Validated audited directions are a
secondary tie-break and may preserve supplemental evidence only when their
public parent also qualified. The regression explicitly compares one public
lookup plus three aliases against three distinct public lookups. The final
implementation also preserves all four request-flow witnesses; merely removing
alias handling was tested and rejected because it lost the gateway witness.

### P2 — Two budget tests depended on removed prose overhead

In `tests/docs/test_docs_context_compound_projection.py`, a 256-token payload
now fits and a full two-direction payload is below the former 375-token test
boundary after removal of the redundant prose instruction.

The insufficient-envelope test uses a genuinely insufficient 200-token budget.
The smaller-qualified-variant test derives its boundary from the measured full
payload minus one token. Source containment, reduced visible coverage, snippet
size, budget compliance, and projection validation assertions remain in place.
These are synthetic unit-test boundaries, not changes to frozen quality gates.

### P2 — P1 closure referenced stale evidence artifacts

Regenerated and reviewed
`eval/agent_developer_v1/results/p1-agent-truth-closure.json` after checking the
current P1.4/P1.5/P1.6 evidence. The diff changes three artifact blob hashes and
`answer_supported` from 5 to 6. The conclusion remains
`AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN`. CI validates the refreshed artifact without
rewriting it.

### Reporting and temporary infrastructure

Corrected `CHECKPOINT.md`: successful execution of the V2 report is
`REPORT_ONLY`, not a passing release/quality gate. Removed temporary review
artifact/publication workflows and the obsolete PR178 architecture trace
workflow after validation. No main-branch merge was performed.

## Validation evidence

New regression module: `tests/docs/test_review_query_lineage.py`, with its
behavioral diagnostic manifest.

| Check | Result |
| --- | --- |
| New review regressions before fixes | 11 failed |
| New review regressions after fixes | 11 passed |
| Targeted and neighboring contracts | 128 passed |
| Full local offline suite, Python 3.13, locked dependencies | 3957 passed, 10 skipped |
| Repeated full GitHub Actions suite, Python 3.13, locked dependencies | 3957 passed, 10 skipped |
| compileall, module-size check, diff check | PASS |
| P1.4, P1.5, P1.6 and refreshed P1 closure | PASS |
| P1 closure self-tests | 4/4 PASS |
| Recovery contract | PASS |
| Recovery mutation gate | 6/6 mutants killed |

GitHub Actions run: https://github.com/Vanilla1999/DocAtlas/actions/runs/34112750154

Artifact: `pr179-reviewed-validation` (ID `10015122078`), containing full JUnit,
pytest log, and the published revision. The run started at
`853b955471651db4c1da5b158c1b779074eb17eb`, applied the checksum-bound reviewed
patch, removed the temporary workflows, tested, and published `c5c8c679...`.
It is evidence for that resulting source tree, not a claim that all normal
PR-triggered workflows passed on the bot-authored commit.

## Remaining acceptance blocker — NOT fixed in this review pass

`python eval/project_context_quality_protocol.py --live` still exits 1:
legacy live quality is FAIL, with 11/15 positive cases useful. Remaining failed
cases include `ru-overview`, `ru-selection`, `ru-offline`, and
`ru-server-command`. The default self-host gate also fails. These failures were
not hidden by relaxing thresholds, changing frozen expected facts, expanding
scope after misses, or replacing the gate with a report-only evaluation.

The separately measured V2 report remains REPORT_ONLY:

- Natural positive usefulness: baseline 13/15, reviewed fixes 14/15.
- Exposed paraphrase positive usefulness: 3/5 before and after.
- False-full: 0 in both lanes.
- Safety and token/source budgets passed for all 19 natural and 6 exposed cases.
- Remaining positive gaps: `v2-natural-chunking` (parents),
  `v2-paraphrase-review-ready` (test), and
  `v2-paraphrase-search-trust` (not_proof).

The observed natural-lane improvement is `v2-natural-stale-health`; its
before/after result was also checked with PYTHONHASHSEED 0 and 1. Neither this
report nor passing unit tests establishes general autonomous-agent usefulness.

## Review disposition

The concrete lineage, negation, ranking, budget-test and stale-artifact fixes
are published and validated. Overall quality acceptance remains blocked.
Keep PR #179 draft; do not represent this review as merge approval.
