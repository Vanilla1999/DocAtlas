# Exact-head audit results — 6 September 2026

Existing PR #178 / `fix/context-first-project-reads`. **Not ready to merge.**

## Published progress

- `146d7a80d25ebbcc1237075059e55a258b4cbcaa`: plan saved before measurements.
- `48421b8980ca442c051dda4763fd32f450b9b390`: first 79-call checkpoint.
- `bf663cb9838fe326579f258cffd05424fa003fbb`: implementation, six regression cases and diagnostic inventory published together; read back from GitHub.
- `99557cd4eb0bdc92a3fd0993f789fe376e15e778`: full audit, all thirty manual answer reviews and fixed retries. A parallel test commit was preserved without force update.

This audit starts at runtime `462fb13411cfd96ae2f1784c0a620b2601f86305`. It does not reuse earlier 13/15 results. The separate local reconstruction uses the preserved 3cae4f8 bundle plus the four published runtime files verified by Git blob identity. It is not the user's checkout or deployed server. The resulting local Git HEAD is not represented as the runtime commit.

## Actual measurements

161 public MCP calls were saved: 25 frozen v2 inputs/controls + 30 newcomer first calls + 24 fixed manual retries before the repair, the same 79 after the repair, and 3 diagnosis calls. A later replay of an already saved candidate pool inspected projection diagnostics only; it made no extra retrieval call.

| Frozen v2 metric | Input runtime | bf663cb |
| --- | --- | --- |
| Natural usefulness | 11/15 | 12/15 |
| Exposed paraphrases | 3/5 | 3/5 |
| False-full, positive cases | 0/20 | 0/20 |
| Safety / identity / budget / authorization-denied | 25/25 each | 25/25 each |

Gained: `storage/isolation`. Lost accepted obligations: **none**. Still missing: architecture infrastructure boundary; four internal request-flow stages; stale-health sync; review-ready tests; search-trust's accepted path-bound witness. Do not equate a different wording/path with factual absence; search-trust has semantically similar visible text that its frozen evaluator does not accept.

Source precision at bf663cb is 25/42 natural and 7/14 exposed under the unchanged evaluator's adjudicated-path policy. Other paths are unadjudicated, not automatically irrelevant.

All 161 public records passed normal projection and citation-integrity validation. Maximum: 3 sources / 800 actual estimated tokens across the whole audit. The first 30 newcomer outputs peak at 729 tokens; their selected final outputs peak at 798. Status and budget compliance are not semantic sufficiency.

Observed public-call timing, excluding index setup and manual formulation:
- 55 input first calls: median 0.675 s, nearest-rank P95 5.125 s.
- 55 post-fix first calls: median 0.656 s, P95 5.106 s.
- 24 post-fix retries: median 0.640 s, P95 1.233 s.
These include dispatcher/projection/observer overhead, not a pure search microbenchmark. There was no separate model-generation latency measurement.

## Minimal TDD / domain repair

A rolling window could start inside a short sentence and remove its subject. A numbered-list marker could be parsed as a complete sentence, separating the step number from its body.

RED: 5 failed, 1 passed. The pure `context_windows.py` rule now starts richer rolling windows at actual sentence/list boundaries and does not split numeric list markers. GREEN: 6 passed. Existing focused recovery/compound/context/service checks: 105 passed.

No application service, synonym set or semantic-verifier layer was added. The 3/800 contract, qualifier thresholds and attribution rules were unchanged. This is structural preservation, not a certificate for arbitrary meaning; overlong single spans retain the existing bounded policy.

Only this pure domain file plus its new test/inventory files were changed in the repair. All 1623 original tracked files in the pre-audit manifest remained byte-identical during this repair; the domain window file was new relative to that original snapshot and is verified separately. Its published blob after repair is `af2fd89b6652e2dfd091d10b93a525e25eedbfe0`.

## Thirty actual newcomer questions

See `ONBOARDING-30.md` for each question, grounded answer and limitation. First calls had no prefilled lookups: 16 ok, 14 insufficient. After the 24 fixed single retries and six baseline retentions: **27 ok, 3 insufficient**. The three insufficient selected payloads are newcomer-20, newcomer-27 and the retained encryption control newcomer-29. An earlier prose total omitted that retained control; the counts here were reconciled with all 30 saved payloads.

Manual judgments of those selected final payloads:
**12 sufficient, 10 partial, 5 off-topic, 2 no evidence, 1 unestablished capability.**

Question 29 is a control: no witness establishes encryption/key management; this does not establish that encryption is absent. The host knew the project. These are exposed coordinator judgments, not a holdout, frozen metric, or weak-model answer accuracy. The initial no-lookup condition also is not equivalent to an independent agent applying the documented first-call decomposition policy.

All proposals/declines were fixed after reading the public first payloads and before executing retries. The same proposals were replayed after the repair. At most two single-concept lookups; original question/scope unchanged; whole successful retry retained independent of later score. No source splicing, best-of-many selection, external model API, OpenCode, model installation or persistent indexing.

## Concrete remaining failure stages

- Request-flow: the application-orchestration paragraph from `docs/modules/project-context-retrieval.md` is found and qualifies. Existing projection diagnostics show all three variants of `child-eb4fc355e5166a1995deb87964002e9ad00bd637` rejected for token budget after the chosen tool-usage/ADR context. The resulting two-source payload uses 724 tokens. This proves selection/budget loss for that paragraph, not for every missing request-flow stage.
- Stale-health: the canonical sync paragraph is absent from the captured candidates. The exact `test_stale_health_live_status_sync_and_removal` fails before AND after this repair with StopIteration while locating that paragraph. Further retrieval/qualification diagnosis is required; window repair cannot create a missing candidate.
- Architecture: its infrastructure witness is not in the final output. A precise causal stage for that obligation has not been established.
- Newcomer topic mismatches remain: installation is incomplete, partial-answer recovery returns adjacent lifecycle information, new-format extension retrieves agent-contract setup, YAML fields and no-model indexing can return no evidence.

## Checks that are NOT green

GitHub CI run `34053433601` for bf663cb fails overall. Core matrix failures remain; advanced unit/recovery/hermetic checks pass but the live gate fails. No full-green or merge claim.

An additional local planning/generic selection ran 127 passed, 1 failed, 12 deselected. The failing table-window fixture returns 583 characters against an existing 520-character assertion. It fails identically before and after the new sentence fix: the earlier complete-short-source allowance reaches 640, while the older assertion still requires 520. This is an unresolved contract conflict, not a threshold/test changed to green. Whole-row preservation and total 800-token compliance do not erase that failure.

The freshness failure above is also reproduced before/after. Other CI failures are not all causally classified. A successful full local repository suite is not claimed; partial/interrupted logs are preserved but are not PASS.

## Next justified work

Fix candidate selection under the current budget without sacrificing explicit-source identity or already visible facts; separately diagnose missing sync/YAML/no-model candidates. Resolve the existing 520-versus-complete-source contract with explicit evidence rather than silently widening a frozen test. Re-run the affected and negative controls before any merge. Do not expand lexical synonym rules or repeatedly optimize this exposed question set to a score.

The companion archive contains every public response, separate private candidate/snapshot data, fixed rewrites, before/after hashes, RED/GREEN and failing logs, and full thirty-question reviews. Indexed docs, frozen evaluator, corpus, thresholds and the divergent branch were not changed. No merge was performed.
