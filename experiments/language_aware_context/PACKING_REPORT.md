# HTTPX packing loss: located and repaired in an opt-in experiment

Status: **DRAFT / DEVELOPMENT ONLY**. No default product change, no merge, no
language-profile claim and no completed A-E experiment. This follow-up supersedes
only the unresolved HTTPX loss diagnosis in DEVELOPMENT_REPORT.md / CI_RESULTS.md;
their earlier measurements remain historical, not overwritten.

## Exact failure mechanism

The real same-call trace for the previously viewed `httpx-disable-client` query
shows that `_facet_aware_candidates` already ranks the complete canonical code
example (timeouts.md lines 35-39) first. Then
`context_candidate_ranking._prefer_missing_baseline_candidate` promotes the
incidental environment-variables span (lines 4-7).

The helper treats all non-host public IDs as baseline directions, including the
optional `query-anchor-1` for `HTTPX`. The environment span satisfies that anchor
and the lookup, but not the original question. After accepting it, the core's
`insufficient_new_host_terms` branch rejects the complete timeout example: its
visible matched terms add only `timeouts` to `disable/httpx/client`, below the
existing two-new-terms rule for another span of the same host direction.

That is the **first observed rejection**, not a token-budget rejection. Later
budget omissions also occur, but were not the cause of losing the leading full
example. `_run_core` already returns an incomplete packet; joint selection,
query-block selection and query-block recovery do not restore it. No need to
invent a neighbor, expand the corpus, lower a qualifier threshold or relax the
novelty guard to repair this development case.

## Minimal intervention and boundaries

`packing_experiment.py` temporarily replaces only the baseline-preference hook.
For **exactly one** host lookup, that preference may protect `query-original`,
not optional anchor aliases. The existing implementation handles the filtered
preference set; zero/multiple lookups and canonical fallback remain unchanged.
The candidate list still contains anchors, and the actual query plan, source
filters, exact/path checks, qualification, coverage and public IDs are untouched.

No HTTPX name, answer string, corpus path, detector output, label, new model or
scoring threshold is used by the adapter. It only reorders existing objects.
The production novelty veto remains enabled. The real final DTO budget remains
800 and its source cap remains three. Full quotes are audited against canonical
source bytes and line ranges. Flags do not become `answer_supported`/`edit_ready`.

The monkeypatch is **process-global, not thread-safe**. It is only for explicit,
sequential tests/development runs, never a concurrent installed MCP server.
Nested and exceptional exits restore the prior hook. Production files are not
modified and importing the adapter does not activate it.

## Local validation

Code restored from GitHub artifact 11090200607, code revision
`b54faee8780a6babac79a588d96861578079c7f2`, ZIP SHA-256
`9bd5ce49e9a8d6dfd6ba2f688f5bc0b065f2d62ebb5e2f3fe965f72c1774440f`.
All 1200 archived `docmancer/` and `eval/` files remain byte-identical. The branch
parent `111e1047c53846210523806394f0fa97c232ae1e` adds result documentation only.
The extracted archive has no Git metadata; no synthetic local commit was made.

Local Python is 3.13.5 with installed dependencies, not the frozen CI environment.
A local frozen install was attempted but blocked by external DNS. The workflow
uses Python 3.12 and unchanged `uv.lock` via `uv sync --frozen --extra dev`.
The local results below were subsequently reproduced in the exact-revision
frozen CI run documented in the next section; the two environments are not identical.

- Fixed-process TDD (`PYTHONHASHSEED=0`): **2 FAIL / 9 PASS -> 11 PASS**. The
  failures were the ordering assertion and the full real-handler quote assertion.
  The first unseeded invocation had **1 FAIL / 10 PASS**, with the E2E case already
  passing in that process. Do not claim that every uncontrolled baseline run loses
  the quote. Main paired runs pin and record the seed before comparing conditions.
- Added collector/restoration and identical-prepared-input replay checks:
  **131 experiment tests PASS**, no failures/skips. The replay calls the real
  projector with copies of the very same handler input while source files live;
  the candidate passes the unchanged canonical/budget audit.
- The 11 adapter tests also pass in separate processes with hash seeds 1 and 2.
- **483 unchanged focused product tests in each condition:** 482 PASS / 1 FAIL
  baseline and 482 PASS / 1 FAIL candidate; identical test identities and statuses.
  Shared failure: `test_context_projection_boundaries.py::`
  `test_frozen_request_flow_prefers_project_context_module_witnesses` (`flow_mcp`).
  This is not a green regression suite, and its cause is not attributed here.
  The first baseline command was interrupted by an execution timeout; both full
  reports were subsequently rerun to completion and are the compared results.

## Same questions, same manual lookups: real handler pairs

`packing_probe.py` runs each unchanged request through baseline and candidate,
indexes only the same hash-checked sources, saves raw DTOs/decision traces and
performs the existing canonical claim checks **after** execution. Each run uses
an isolated fixture; incidental identity/locator costs can differ. The separate
same-prepared-input replay test controls that fixture difference at projection.

| Viewed development task | Original-only baseline / candidate | With lookup baseline / candidate |
|---|---|---|
| Typer mixed RU/EN | ABSENT / ABSENT | COMPLETE / COMPLETE |
| Typer RU | ABSENT / ABSENT | COMPLETE / COMPLETE |
| Typer EN | COMPLETE / COMPLETE | COMPLETE / COMPLETE |
| HTTPX default timeout | ABSENT / ABSENT | COMPLETE / COMPLETE |
| HTTPX disable Client timeouts | COMPLETE / COMPLETE | ABSENT / COMPLETE |

**With manual lookups: 4/5 -> 5/5.** One gain, no lost complete claims on these
five viewed questions. All 20 real-handler executions have empty audit errors;
the largest local packet is 798 tokens. This is delivery of a known canonical
claim, not correctness of a model answer. Three Typer questions share one fact;
these are not five independent trials. H1/H2/H3 remain unmeasured.

## Frozen CI verification on the committed code

- Executable code: `75cc12cdfb631bdffd59a3f155dba08fc4a6be5c`.
- Run: https://github.com/Vanilla1999/DocAtlas/actions/runs/36703938018
- Job: `109849611300`; Python **3.12.14**, `PYTHONHASHSEED=0`,
  `uv sync --frozen --extra dev`; clean exact-SHA checkout.
- Artifact: **11091019291**, SHA-256
  `68a665dd104e73c2d48f50f277cbcab8952206253ee17664bd48567b31b17745`.
  Downloaded bytes and source-head identity verified. All eight changed code,
  test, inventory and workflow files match the locally tested bytes; all 1200
  product/eval files match the preceding verified source snapshot.

| Check | Frozen CI result |
|---|---|
| Experiment tests including real-handler and identical-input replay | 131 PASS, 0 FAIL, 0 SKIP |
| Paired packing runs | 20 EXECUTED; same claim outcomes as local |
| With manual lookups | 4/5 baseline -> 5/5 candidate; zero lost COMPLETE claims |
| Canonical and DTO audits | Zero errors; max 798 tokens; source cap and flags preserved |
| Unchanged focused product cases, baseline | 482 PASS / 1 FAIL, 0 errors/skips |
| Same product cases with adapter | 482 PASS / 1 FAIL, 0 errors/skips |

Both focused JUnit reports contain the same 483 testcase IDs and identical
statuses. The shared failing test is the same `flow_mcp` obligation reported
locally; **no new failures in this selected suite**, not a full regression pass.
The workflow conclusion is **FAILURE**, correctly, because each focused command
exited 1. The experiment tests, baseline probe and paired-packing step succeeded.
No failure was suppressed and no global all-green/merge-readiness claim is made.

The artifact contains the JUnit reports, exact source snapshot and raw baseline /
packing reports. The accompanying download bundle retains the report bytes,
`ci/verification.json`, code delta and local RED/GREEN evidence. Traces in all 20
CI packing reports have zero omitted events. Dataset repetition in CI is not a
new independent experiment. H1/H2/H3 and live answer quality remain unmeasured.

## Reproduce and next decision

```sh
export DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0
uv sync --frozen --extra dev
.venv/bin/python -m pytest tests/docs/test_language_*.py -q
.venv/bin/python -m experiments.language_aware_context.packing_probe --output /tmp/new-packing-run
.venv/bin/python -m experiments.language_aware_context.packing_regressions --condition baseline --junit /tmp/new-baseline.xml
.venv/bin/python -m experiments.language_aware_context.packing_regressions --condition candidate --junit /tmp/new-candidate.xml
```

Use new output paths; prior evidence is not overwritten. The workflow executes
both focused conditions even if baseline fails and retains both JUnit files; it
does not turn a shared failure into PASS. CI artifact retention is seven days.

Next: investigate the shared `flow_mcp` regression failure, and freeze new
independent RU/EN/mixed and adversarial cases before evaluating real agent-generated
queries/answers. Frozen CI reproduction of this mechanism is complete.
Retain the same-input ordering ablation separately from any future neighbor
assembly/profile effect. Investigate the shared regression failure before any
merge decision. No production activation is justified by this diagnostic gain.
