# Host rephrase experiment — partial result, not acceptance

Date: 2026-09-06. PR #178, existing branch `fix/context-first-project-reads`.
Frozen source: `3cae4f83f0b2fa8be1c4597340a1fd4150104ce8`.

**Status: BLOCKED_GENERATOR. No production retry integration. No merge approval.**
This is a new baseline reconstruction and deterministic orchestration check,
not a completed three-run model experiment and not the lost historical run.

## Repository and provenance

The expected commit was present on GitHub. The user's workstation could not be
inspected because Tunnel3 returned HTTP 404. Its `/tmp/opencode` artifact state
therefore remains unknown. Exact previous 3 x 25 proposals were not recovered.
No coordinator-generated benchmark rewrites were substituted for isolated agents.
The divergent acceptance-closure branch at `08c2526` was not merged or rebased.

A separate clean checkout was reconstructed using source bundle artifact
`9990400314` from Actions run `34036748386`. Snapshot workflow commit: `f4c9bf0`.
All 1623 pre-existing tracked files matched the source SHA-256 manifest before
and after the local experiment. Production, evaluator, corpus, catalog and
thresholds were not changed. GitHub eventually reported PR #178 mergeable;
the initial false status was premature, not proof of a Git conflict.

## Measured new baseline

| Metric | Historical handoff only | New reconstructed run |
| --- | --- | --- |
| Natural semantic usefulness | 13/15 | **11/15** |
| Exposed paraphrase usefulness | 3/5 | **3/5** |
| False-full on 20 positive cases | 0 | **0** |
| Safety / identity / budget / denied authorization | not rerun here | **25/25 each** |
| Strict negative correctness | not rerun here | **3/3** |
| Unsupported-answer controls | not rerun here | **2/2** |

Missing obligations:

| Case | Missing obligations |
| --- | --- |
| architecture | infrastructure_boundary |
| request-flow | flow_mcp, flow_application, flow_gateway, flow_selection |
| sync-renames | orphans |
| stale-health | sync |
| review-ready | test |
| search-trust | not_proof |

`sync-renames` and `stale-health` are additionally incomplete relative to the
handoff list. The historical payloads and exact dependency environment are
unavailable. The difference is **unclassified**, not attributed to retries,
since no model retry was executed. Coarse evaluator stage labels do not prove
the failure stage of each missing witness. No lexical tuning was attempted.

Public payloads: 909–3187 canonical UTF-8 bytes, 228–797 recomputed estimated
tokens, at most 3 sources. Supplied estimates also stayed within 800.
Observed public-call latency over 25 calls: median 1.307864 s, nearest-rank
P95 7.734398 s, maximum 18.771289 s, total 59.515625 s. This includes retrieval,
projection and observer overhead, excluding index setup and the pre-sync
preflight; it is not a pure backend search microbenchmark.

The completed run had 25 evaluated calls plus one setup preflight. Three earlier
reconstruction attempts were interrupted. Their partial outputs were not used,
and complete call telemetry for those attempts was not retained.

Evaluator source precision: 26/42 natural, 9/14 exposed. These ratios count
accepted/adjudicated paths. Other paths are unadjudicated, not automatically
irrelevant. The v2 protocol is report-only on an exposed corpus, not a holdout.
Its runner's legacy-threshold FAIL on the v2 inventory is not a fresh frozen-v1
live-gate execution.

## Planned model runs

| Run | Status | Actual model generations | Retry searches | Model usefulness |
| --- | --- | --- | --- | --- |
| run-1 | BLOCKED_GENERATOR | 0 | 0 | not measured |
| run-2 | BLOCKED_GENERATOR | 0 | 0 | not measured |
| run-3 | BLOCKED_GENERATOR | 0 | 0 | not measured |

25 public-only packets were prepared and hashed. All 75 absent-generator slots
were recorded and preserved the whole baseline. These fallback scores are NOT
three model measurements. Gained/lost facts and model/retry latency are null,
not invented zero-effect findings. Pre-review and post-fix fallback replays
were deterministic checks, not six model runs. No retry searches were issued.

The fixed policy is one additional public call, at most two appended
single-concept lookups, **five total host lookups** (not five total query IDs),
no dropped original lookups, byte-identical original question, at most three
sources and 800 estimated tokens. A valid admitted retry replaces baseline
whole, independently of gold. Refusal, rejection, unavailable generator or error
keeps baseline. No splicing, original-coverage fabrication or full-answer claims.

## Local implementation, TDD and review

Prepared in the isolated checkout, outside production:

- `scripts/host_rephrase.py`: bounded orchestration, immutable-field schema,
  public-input hash binding, existing literal identifier extraction, durable
  one-attempt journal, whole-payload selection, runtime validation callback.
- `scripts/run_host_rephrase.py`: public packet preparation, all-three-run export
  sealing before scoring, lazy temporary indexing, existing public MCP handler
  and unchanged evaluator. No model calls or installation.
- `scripts/host_rephrase_self_test.py`: deterministic tests, not LLM evaluation.

Initial RED: 25 tests, 24 failure records including subtests, one error. The first
implementation passed 25 tests. Coordinator self-review then reproduced an
export reread after sealing and a journal-I/O exception escaping baseline
fallback: 28 tests, one failure and one error. Both defects were fixed. Final
**28/28 orchestration tests passed**. Existing focused tests: **145 passed**.
Compile, whitespace and Python-module-size checks passed. A fresh complete
local core/advanced suite was not run; historical 3874/593 counts are not reused.

Review was self-review, not independent blind review. The tests enforce schema,
ordering of operations and explicit review rejection. They do not prove arbitrary
semantic preservation. Exact-anchor checks and model review are not universal
semantic certificates. Runtime source/hash/span/identity rules are not weakened.

**Publication limitation:** the tool's safety check blocked publication of the
self-test file. The complete helper/test set was therefore NOT committed in a
partial form. The tested files, raw reconstructed baseline, public packets,
private seals, per-slot records, timing data, hash map and RED/GREEN logs are
provided in the companion experiment archive. Only the earlier snapshot workflow
and this status report have been added to this branch during the session.

## Environment and CI boundary

Local Python 3.13.5; pydantic 2.13.4; pydantic-settings 2.14.1; httpx 0.28.1;
PyYAML 6.0.3; pytest 9.0.2. mcp, sqlite-vec, qdrant-client, fastembed and
trafilatura were absent. The existing in-process vector-free path ran without
installing them. Equivalence to the former machine's environment is unproven.

Opening/updating the PR automatically triggered existing CI run `34036750556`.
Its installed-mcp-harness ran with `--planner scripted`; it was not an experiment
generator. Core matrix and advanced unit tests succeeded, but advanced-contract
failed in recovery before the frozen live gate, which was skipped. Other P1
checks failed too. This report commit uses `[skip ci]` to avoid repeating the
unrequested installed harness, not to claim green checks or bypass acceptance.
No CI gate or frozen threshold was weakened. Checks for this new head are not
claimed as passed, and the draft PR must not be merged on this evidence.

## Frozen hashes

| File | SHA-256 |
| --- | --- |
| docmancer/docs/domain/documentation_query_plan.py | 9e173dc6f475bb902850ba66424753c2f9b6679071de5fe810f943586999177c |
| docmancer/docs/interfaces/mcp/docs_context_routing.py | e165bd5f000c61fc03741569f82a3a4d488e82aded1d5d036cbbcc63a4503f7d |
| eval/project_context_quality_v2_protocol.py | ad1c520fa628133b8083475578f476af7e83f1fc99d5d931012c1d51aacc309c |
| eval/project_context_quality_v2/cases.json | 80a663d5e560fb039f6f1a30b2b1d634da7684af8b8c7d0976c7b60813370963 |
| eval/project_context_quality_v2/protocol.lock.json | b5339fd68d5701bbd08a8ca790566acd5b14e57e8c58d82f0b55f86062a66320 |
| eval/project_context_quality_protocol.py | 15beec27bc1f0c33d96f1521308850ae72e05a47daac411823c22c2d7edb5fa2 |

## Next justified step

Restore the exact former proposals or obtain three genuinely isolated native
model generations using only the sealed question/public payload packets. Review
before retry scoring, then replay once per original with the prepared runner and
compare visible obligations using the unchanged evaluator. Keep the baseline
discrepancy and exposed-corpus limitations explicit. Production integration,
frozen-v1 acceptance and merge remain unjustified until that evidence exists.
