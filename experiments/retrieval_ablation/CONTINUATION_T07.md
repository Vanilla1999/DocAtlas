# Checkout audit and T07 continuation — 2026-10-01

## Actual stopping point

Remote main: `55637eb4d29a0d06c01714ee647a5b486a5be725`.
PR branch inspected: `2c861b5b4da5b7fed4002181b307200a51e455fd`.
Its actual source tree still contained diagnostic T00–T04 with A packets blocked.
Continuation and T05–T07 existed as compressed mail patches in
`.push-staging/cont-00..04` and `t05.gz.b64`, not applied source files.

This branch starts from remote main. Four implementation/report commits, five
continuation patches and three T05–T07 patches were applied locally. Staging blobs
and push workflows were not imported. Original dirty user checkout untouched;
nothing pushed, merged or activated. Earlier 80-case raw corpus/results were not
available here: the reported 46/48 versus 37/48 was not independently verified.

After restoration, project-only A packets, B, D_L and E_G_L existed; E_GR_L did
not. **B is only an FTS representation change:** source heading paths and display
text replace contextual boilerplate. It does not repair parsing, ownership or
chunk boundaries. Original T05 remains partial. D_L has same-call B controls but
does not replay an externally saved pool. Uncapped first-loss tracing is pending.

## Added implementation

E_GR_L invokes real `context_candidate_ranking._facet_aware_candidates` with real
`qualify_evidence` traces, once, then the unchanged whole-unit packer. No extra
retrieval, fabricated qualification or public answer/edit authority. The factor
is **one legacy candidate-ordering pass**, not the full legacy projector/packer.

Same assembled input produces a saved E_G control. Both hash the real gate-output
objects; all 12 paired hashes matched. Reviewer now supports explicitly planned
B/D/E arms, validates their packets and counts missing arms against that plan;
the default remains P/A for compatibility.

## Tests

Existing local Python 3.13 environment, unchanged lock; offline, no auto vectors,
`PYTHONHASHSEED=0`.

- Restored contract/integration/packet baseline: **69 passed**.
- New E_GR assertion: **1 failed** (unsupported arm), then **1 passed**.
  Initial diagnostic-registration collection error is not counted as RED.
- Contract/integration/packet/regression harness: **76 passed**.
- Adjacent qualification, discovery, bound-table, contiguous-seed, completion and
  candidate-ranking suites: **77 passed**.
- Harness including OS isolation: **78 passed / 8 failed**, all eight namespace
  setup errors (`uid_map: Operation not permitted`). No skips/fallback added.
  Full product offline gate not run.

Logs: `/tmp/opencode/ablation-t07-{red,green,core-final,suite}.log` and
`/tmp/opencode/ablation-product-regressions.log`.

## Development measurement

Artifacts: `/tmp/opencode/ablation-development-t07-final/`.
Driver: `/tmp/opencode/ablation-development.py`.

12 self-authored original-only questions, one real public Markdown source
(`README.md`), six arms: **72 planned / 72 executed / 72 audit-clean**.
11 answerable and one separately reviewed unanswerable question. Public inputs,
source hashes and limits saved before execution. Code-file hashes checked before
and after every run. A preliminary run spanning a code edit was excluded; only
the final unchanged-code run is reported.

Each arm ran in a separate ordinary process, **without OS namespace isolation**.
No private labels supplied; this does not prove OS-enforced gold isolation. The
production frozen-run CLI still fails closed. No downloaded models, dense search,
answer generations, holdout or speed claim.

Posthoc same-author inspection of final visible citations; source-phrase checks
retained in `case-review.json` for audit, not as a general semantic judge:

| Arm | Sufficient first packets / 11 | Max DTO tokens across 12 |
|---|---:|---:|
| P | 7 | 798 |
| A | 8 | 645 |
| B | 8 | 654 |
| D_L | 9 | 800 |
| E_G_L | 7 | 775 |
| E_GR_L | 7 | 775 |

Same-call contrasts, not cross-process tie-order comparisons:

- D_L−B: **1 win / 0 losses / 10 ties**. Case 1 gains the table naming the three
  default tools; the unassembled selected seed did not contain it.
- E_G_L−D_L: **0 wins / 2 losses / 9 ties**. Cases 4 (installer configuration
  paths) and 6 (resolved Python lockfiles versus declared intent) lose sufficient
  evidence at `insufficient_visible_match`. Admitted assembled units passed hard
  checks; strict gate output was empty.
- E_GR_L−E_G_L: **0 wins / 0 losses / 11 ties**. Some selected text changed,
  reviewed sufficiency did not. This does not establish equivalence.

Case 8 (unchanged library refresh) fails in all arms; A's admission trace includes
`missing_bound_subject`. Case 9 (Russian question over English source) returns no
sources in all arms. Neither is an established BM25-ranking failure. Case 12 asks
for an undocumented retry default: all six return nonempty insufficient context.
No answerer ran: neither abstention nor hallucination was measured.

One dependent document/family, 11 EN + 1 RU questions; unblinded posthoc review.
Do not extrapolate to old 80 cases, library-version scopes, independent evaluation
or product replacement.

## Next minimal work

1. Ratio-only remove-one on actual P for cases 4/6, retaining every hard check.
2. Complete source-derived ownership tests: current B does not fix ownership.
3. Measure multiple document families before changing product behavior.

T07 candidate-ordering diagnostic exists. Full T05/T07, independent evaluation,
hybrid, complete first-loss traces and simplification acceptance remain open.
