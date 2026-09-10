# Evidence quality v2 — execution checkpoint

Work branch: `fix/evidence-quality-v2-20260910`. Runtime baseline: merged main
`e1daf4fa68f16f626068f2c58646e2ebfd4293f7`. No production change in this checkpoint.
No release, automatic merge, hidden holdout or autonomous host quality is claimed.

## Executed

- P1: conservative externally annotated assessment, complete same-call collector,
  exact prepared projector replay and transparent observer controls. Nested code
  snippets and non-source absence records are not confused with citation strings.
- P2: 80 frozen tasks from eight pinned real upstream projects: 40 development /
  40 exposed validation, grouped by project. 48 within-budget, eight each partial,
  unanswerable, ambiguous and deliberately over-budget. Original-15 is separate.
  `build_frozen_corpus.py` reconstructs exact source/case hashes from public inputs.
- P3: all 560 variant rows executed: 400 real handler requests and 160 frozen
  projector replays; final source ranges/hash/budget/flags validation retained.
  A/B/C/explicit/original-duplicate/nearby: 29/48 recognized sufficient;
  no-expansion replay: 19/48. Valid final inventory has zero operational errors
  and zero observed source-integrity/contract violations. These are conservative
  approved-witness counts, NOT human-adjudicated semantic accuracy or host success.
  Removing canonical aliases actually changed plans on only three tasks. Equal
  scores are inconclusive, not evidence that aliases never help.
- Grounded 3.1.0: exact 14-document manifest verified in SQLite, no extra pages,
  non-null embeddings zero. Official native stdio text at limits 1/3/5 gives
  22/32/32 recognized sufficient of 48. Native token p95: 1669/3072/4684 using
  tiktoken 0.11.0 o200k_base. Conservative source-paragraph mapping needs review
  for unrecognized alternatives. Native results are never called 800-token runs.
- Controlled Grounded + first-whole-paragraph adapter: 8/48 at each limit; the
  adapter spends its three-block cap poorly. This is evidence about our adapter,
  not a native Grounded failure or a fair proof of DocAtlas superiority. All raw
  native outputs remain separate. Same common adapter on DocAtlas retains 29/48.
- P4 neutral characterization: eight roots/order/format/neighbor/duplicate/seed
  runs, 40 handler calls. All three condition/list/table facts stay complete;
  all eight shared-database cross-project checks have both sides' sources and
  distinct identities. Zero observed integrity/isolation violations. No runtime
  patch justified by this synthetic fixture. Real-project gaps remain diagnostic.

## Invalid setup attempts retained separately

The first local tokenizer cache contained cl100k, not the protocol's o200k.
The initial observer captured an application dataclass rather than the prepared
projector input. Some nested snippets/non-source records were not normalized by
measurement. Two identical `lookup_queries` array items violate the *existing*
uniqueItems schema; the valid duplicate lane now repeats the implicit original
as one lookup. Grounded defaults `scrape --clean`; official `--no-clean` is needed
for additive per-file ingestion. None of these errors is a production RED or a
reason to weaken a gate. All 80 questions, witnesses and source hashes are unchanged.

## Still open at this checkpoint

P5 documentation-gap audit and P6 installed-wheel/workflow, oracle-input and cost
report closure. Live host and truly independent holdout: NOT_MEASURED.
Full local offline core: **3627 passed, 2 failed, 10 skipped, 593 deselected**.
Failures: original Q05 missing the no-confirmation fact (already seen in P0), and
`test_first_session_live_query` semantic usefulness. No threshold or frozen data
has been changed. This checkpoint is NOT merge-ready.
