# Audit follow-up: evidence checks, preserved answers and replay

Follow-up code commit: `a34d254`. Base remains `58c7f37c` (PR #204).

## Changes

- Installed skills and the repository skill now require final-evidence coverage
  of all requested obligations, semantic reading, claim-level citations and
  explicit missing-fact handling. Explicit logical implications count; an
  evaluator must not invent additional obligations after seeing the answer.
- Historical strong-pilot answer-quality claims are narrowed to what is saved:
  final packets, not actual answer generations. `sol-02` rubric sensitivity is
  documented without changing frozen questions or substring labels. The
  `sol-01-B` profile-specific evidence gain remains supported.
- Django/mixed Vue first-loss attribution is unresolved. Future strong runs
  preserve complete raw handler output rather than dropping the trace.
- The four-question skill smoke includes actual authored answers and original
  final packets, with source/runner/skill hashes. Portable replay and CI artifact
  retention provide future raw traces. Same-author evaluation is explicitly not
  a skill-effect control or independent holdout.

This follow-up changes installed prompt templates, unlike the earlier
experiment-only commits. It does not change default retrieval/qualification,
MCP schema, source policy, authority, `uv.lock`, P0, frozen v3 or MPNet thresholds.

## Local checks

Python 3.12.3; `uv sync --frozen --extra dev --python 3.12`;
`DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0`.

| Check | Result |
|---|---|
| Install tests + all `tests/docs/test_language_*.py` | 232 passed |
| Public docs/CLI/MCP/tool-choice/support contracts | 100 passed |
| Focused product regressions, baseline | 482 passed, 1 failed |
| Same product regressions, explicit flow hook | 483 passed |
| Portable four-question handler replay | 4 executed, zero audit errors |
| Replay final blocks versus original saved packets | 4/4 identical |
| Original fixture hashes versus saved freeze | match |
| `uv lock --check`, experiment compileall, diff whitespace | pass |

The selected paired failure is
`test_frozen_request_flow_prefers_project_context_module_witnesses` only.
Replay DTO costs are 797/799/781/798; original costs are 798/797/791/798.
Public text is unchanged, but ephemeral source identities can change packet
overhead; do not relabel these as identical prepared projector inputs.

An initial full offline-core invocation was interrupted by the 120-second tool
timeout. The completed rerun (no ordering hook) reports **5048 passed, 20 failed,
10 skipped, 622 deselected**, zero collection errors, in 270.05 seconds.
At `main`, the same command and environment report **4858 passed, 20 failed,
10 skipped, 622 deselected**, zero collection errors, in 292.99 seconds. JUnit
comparison shows identical statuses for every shared testcase, no removed tests,
and 190 additional passing branch tests. Thus no new failures in this completed
offline-core comparison, but it is not a green full suite. Advanced/live tests
are outside this command, not implicitly passed. Failures are not waived or
marked xfail.

## Follow-up CI artifacts

Run https://github.com/Vanilla1999/DocAtlas/actions/runs/36732891557 on executable
commit `a34d254ad2fd989063bb95e95e230afe8019fbe1`; downloaded artifact
`11106300457` includes exact source, JUnit and full smoke traces.
The source-head agrees with that commit. JUnit: 34/34 guards, baseline 482/483
(exit 1), flow 483/483 (exit 0), zero errors/skips in these suites. The workflow
conclusion is FAILURE because it retains baseline exit 1.

All four CI smoke handlers execute with no audit errors, DTO costs
799/789/784/789. Three final packets exactly match the saved original; fresh-01
adds one canonical sentence about resolve resolving symlinks. The original
answer's cited facts remain supported. These are new replay traces, not the
historical original traces or new model answers. All-required CI remains a
separate gate; this diagnostic job is not represented as overall CI success.

An initial attempt to put the long check in the shared project-bootstrap contract
failed eight existing <250-word installation assertions. The final change puts
the check in the full skill templates instead. All 232 focused tests then pass;
the bootstrap contract and its limit were not changed.

## Remaining gates

Full required CI and independent quality evaluation remain separate gates. Do
not infer general source-policy safety from four benign fixtures, or strong
answer quality from a packet-only run. No automatic merge or activation follows.
