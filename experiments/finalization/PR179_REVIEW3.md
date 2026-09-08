# PR #179 third review: source-span and query-lineage integrity

## Scope and baseline

Production baseline: `981de86ce9c42c13443b9ef819969032de35784f`.
Reviewed checkout: `3ff09f6125bf97e1af77f6ba0458a2b3dd6c0391`, which adds
only the temporary source-snapshot workflow. This corrective review completes
three reproduced findings; it is not approval of the accumulated PR or merge.

## Fixed findings

### P2: failed direct requalification overwrites a valid derived parent

In `docs_context_projection._requalify_visible_source`, an audited child could
qualify its public host parent before the parent's direct trace was visited.
The later failed direct trace overwrote that successful derived attribution.
Reversing the trace dictionary therefore changed public lookup coverage. A
successful direct trace could also discard the already observed derived lineage.

All requalified probes now use the existing `merge_query_matches` policy:
qualified evidence precedes failed evidence; successful direct and derived
attribution coexist without inventing direct coverage. Generated child IDs remain
private. Public projection regression tests exercise both input orders.

### P2: old derived provenance survives a smaller visible window

A direct parent trace could retain `coverage_kinds` and
`derived_from_query_ids` from an earlier, larger snippet. When the new snippet
still qualified the direct lookup but no longer contained the child evidence,
those annotations incorrectly continued claiming derived provenance.

Requalification now drops the old aggregate annotations and rebuilds lineage
from the probes that qualify against the current visible text. Actual query
text, exact terms, relationship rules, scope and eligibility checks are unchanged.

### P1: an identical sentence elsewhere is credited as the selected witness

`context_selection.visible_assignment_hashes` verified an assignment's source
identity, raw offsets and content hash, but then tested only whether its text
appeared anywhere in the public snippet. Equal text at another offset could
therefore falsely count as retention of the selected canonical witness.

For example, `Before migration: ALPHA_KEY retains backups.` and
`After migration: ALPHA_KEY retains backups.` contain the same hashed sentence,
but are not the same source location. A snippet of the second line must not
satisfy an assignment bound to the first line.

The pure domain helper `context_windows.source_local_span` resolves one exact
occurrence of the complete snippet. Existing source/visible line provenance
disambiguates repeated text when sufficient. A unique verbatim snippet also
works without optional line metadata. Ambiguous occurrences or inconsistent
ranges cannot acquire assignment credit. Application code then requires the
assigned character range to be contained in that resolved visible span, in
addition to the existing source-ID and SHA-256 checks.

No text is joined, rewritten or synthesized. Absolute and source-local offsets,
Unicode witnesses, foreign IDs and invalid hashes/ranges are tested. This is
source-location validation, not a general semantic equivalence verifier.

## TDD and validation

New tests: `tests/docs/test_review_span_lineage.py`, with its own hash-bound
behavioral diagnostic shard. Existing test assertions were not weakened.

- Clean production plus the new tests: **14 failed, 10 passed** for the stated
  defects, not import or dependency errors.
- Corrected runtime and neighboring lineage/component/window/query-plan tests:
  **179 passed**, including all **24 new scenarios**.
- Full local offline suite on the canonical clone: **4031 passed, 10 skipped**.
- `compileall`, Python module-size gate and `git diff --check`: PASS.
- P1.4, P1.5, P1.6, P1 closure, closure self-tests, recovery contract and recovery
  mutation gate: PASS without rewriting their committed reports.
- All **720** checked frozen evaluator/corpus/quality-script files retained their
  original SHA-256 values. No qualification, source, token or scope limit changed.

The publication workflow requires the full offline suite and static checks
before publishing, and records its actual result below from JUnit. It removes
its own workflow, the staged patch and the now-obsolete source-snapshot workflow.

## Paired quality measurement and limits

Both versions were measured in normal Git clones with the canonical origin
`https://github.com/Vanilla1999/DocAtlas.git`, using `PYTHONHASHSEED=0` and temporary
local indices. No installed-agent harness, external model API or model download
was used. These are in-process public-handler measurements, not LLM answer scores.

| Measurement | Baseline | Corrected runtime |
| --- | --- | --- |
| Legacy positives passing every check | 11/15 | 11/15 |
| Legacy useful-result metric | 12/15 | 12/15 |
| Legacy verdict / process exit | FAIL / 1 | FAIL / 1 |
| V2 natural semantic usefulness | 14/15 | 14/15 |
| V2 exposed-paraphrase usefulness | 3/5 | 3/5 |
| V2 safety and source/token budgets | 25/25 | 25/25 |
| V2 false-full | 0 | 0 |
| V2 verdict | REPORT_ONLY | REPORT_ONLY |

Per-case obligation outcomes, hard gates and lookup coverage were compared for
all 25 V2 cases: no changes, no newly lost mandatory facts. This is non-regression
for this slice, not proof that the outstanding quality problem is solved.

An initial clone inherited the local Git-bundle filename as its remote identity.
That produced a stale-health failure and different retrieval ordering. A linked
worktree also did not reproduce the normal-clone baseline. Those exploratory
logs are retained but excluded from the paired canonical-clone comparison;
neither was used to relax a test or alter an evaluator expectation. Both normal
clones pass the unchanged stale-health test.

The legacy quality gate remains blocked; V2 remains report-only. This review
does not enable automatic host retry, claim autonomous agent truth, or authorize
merge. PR #179 stays draft for the owner's review.

## Publication validation

GitHub Actions run: 34123092089.

Full frozen-dependency offline suite: **4031 passed, 10 skipped**.
Static checks and all seven P1/recovery checks passed; 720 frozen files unchanged.
This validates the corrective slice, not the outstanding quality/release gate.
