# PR #179 second review — source boundaries and public-query priority

## Scope

Reviewed production baseline: `6113a19abb476dce63e1bb6457e675688bbea83b`.
The local checkout `77e6a598e4421c5fe3beb7e873eb6d057bc3df97` adds only a
read-only snapshot-export workflow. This review targets the preceding review's
query-lineage changes, bounded source windows, and final public projection.
It is not approval of the entire accumulated PR or a release/merge approval.

## Fixed findings

### P1 — Optional-edge Markdown table rows lose their subject or restriction

`docmancer/docs/domain/context_windows.py` recognized a table row only when
both outer pipes were present. A row such as `ProductionOnly | ... |
ResetAgent clears the cache | forbidden without approval` could therefore
become a suffix beginning at `ResetAgent`, or a prefix without its restriction.
Long bare-pipe tables also hid a later, short matching row during unit scoring.

Source-unit scanning and boundary repair now preserve whole unescaped
pipe-bearing lines, including rows with either or both outer pipes omitted.
A fitting row remains an exact contiguous substring; an oversized row is not
returned piecemeal. Odd-backslash-escaped literal pipes remain ordinary prose.
This is deliberately conservative for headerless chunks and shell pipelines,
not a complete Markdown parser: a long unescaped pipe-bearing prose line can
also be withheld rather than clipped. No synthetic cell/row reconstruction is
performed. Public source containment, budget, and validator checks are retained.

### P1 — Audited rewrites discard modifiers and extra clauses

`docmancer/docs/domain/documentation_query_plan.py` used a negative-word guard
plus stem matches to authorize audited host rewrites. Positive search aliases
could then be attached to lookups asking about `except`, `unsupported`, past
behavior, archive-only selection, or an additional audit-log question.

Audited rewriting now requires a full match against two bounded, positive
relation families: request-boundary inputs and selection of retrieved sources.
Unsupported modifiers, negation, extra clauses, and unrelated exact identifiers
do not gain an audit. The original host lookup is retained verbatim and remains
searchable. This narrows only audited attribution, not ordinary retrieval, and
adds no answer-proof authorization or general semantic translation.

### P2 — Final projection still counts audited children as public directions

The preceding review separated public and audited priorities in upstream
ranking, but `docmancer/docs/application/docs_context_projection.py` reunited
them in its candidate-priority count. One lookup with one/two generated aliases
could outrank two independent public lookups, including at the 256-token
boundary where only one source fit.

Final candidate ordering now counts public directions first and uses audited
supplemental directions only to break that coverage tie. Supplemental directions
still participate in exact-anchor deferral, preserving the real request-flow
gateway witness. Simply removing supplemental handling was tested and rejected
because it displaced that witness. Audited child IDs remain outside public
`covered_query_ids`; answer/edit authorization remains false.

## Executed validation

New cases are in `tests/docs/test_review_boundary_semantics.py`, registered by
`tests/diagnostic_labels.review_boundary_semantics.json`.

- Clean production baseline plus the final unchanged tests: **35 failed,
  15 passed**, confirming all three findings independently of earlier edits.
- Corrected runtime: all **50 new cases pass** as part of **116 passing targeted
  and neighboring tests**, including the prior review regressions and all four
  request-flow facts within the existing 3-source / 800-token public limit.
- `compileall`, Python module-size gate (all files <= 1000 lines), and
  `git diff --check`: PASS.
- Full-suite results are recorded in the accompanying validation run's JUnit
  and log; they must not be inferred from the targeted result alone.

The publication workflow applies a checksum-bound patch, runs the full offline
suite with frozen dependencies, and publishes only on success. It removes the
patch and both temporary review workflows from the published source tree.
The artifact records the resulting commit. This does not imply that every
ordinary PR-triggered CI workflow or the outstanding quality gate is green.

## Quality acceptance remains blocked

Both complete in-process live protocols were repeated before and after these
fixes with `PYTHONHASHSEED=0`, without changing frozen inputs or thresholds.

| Measurement | Baseline | Corrected runtime |
| --- | --- | --- |
| Legacy positive cases passing every check | 11/15 | 11/15 |
| Legacy `useful_result_count` metric | 12/15 | 12/15 |
| Legacy verdict / process exit | FAIL / 1 | FAIL / 1 |
| V2 natural semantic usefulness | 14/15 | 14/15 |
| V2 exposed-paraphrase usefulness | 3/5 | 3/5 |
| V2 safety and budget compliance | 25/25 | 25/25 |
| V2 false-full coverage | 0 | 0 |
| V2 verdict | REPORT_ONLY | REPORT_ONLY |

Legacy failed cases remain `ru-overview`, `ru-selection`, `ru-offline`, and
`ru-server-command`. Its all-check pass count and usefulness metric are distinct;
neither is silently substituted for the other. V2 also retains its existing
chunking-parent, review/testing, and search-trust witness gaps. These metrics
show no regression from this corrective slice, not quality acceptance closure.

No frozen corpus, evaluator, expected witness, scope rule, source limit, token
limit, or threshold was relaxed. PR #179 remains draft and unmerged.
