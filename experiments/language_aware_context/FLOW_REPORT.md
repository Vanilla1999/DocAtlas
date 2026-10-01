# Flow selection investigation — verified, opt-in only

## Decision and scope

The unchanged frozen `flow_mcp` regression has a reproduced ordering defect.
An opt-in experimental ordering adapter repairs that case and passes all 483
selected product regression tests in the frozen CI environment. This is not a
change to production/default behavior, a full-repository PASS, or permission to
merge. P0, source-policy, the public MCP API, uv.lock, and frozen task-44 v3 remain unchanged.

Evidence code: `16b00f9265d8ba96567c83c94bf6f42b216e2f05`.
The flow adapter and its initial tests were already present at
`767faefef295cfdaa1931f3f9497150f003a7f8b`; the follow-up adds paired regression
execution and integrity-checked review tooling. No existing frozen test was edited.

## Root cause

The first incomplete part is not a missing document or an embedding problem.
`context_candidate_ranking._prefer_missing_baseline_candidate` treats partial
`attributable_query_ids` as representation of host lookups. A general passage can
therefore appear to represent several directions of the original request.
Subsequent ordering protects optional/general matches rather than unseen precise
module witnesses. MCP boundary and gateway passages then lose the limited packet
space; their selection traces include `token_budget` rejections.

The unchanged case requires four witnesses: MCP boundary, application,
gateway, and selection. Baseline and the previous single-host packing adapter
both deliver only application and selection. This is a multi-host case, not the
previous HTTPX single-host case.

On separate fresh runs the original request, retrieved candidates, query window,
and all 36 qualification events are identical after replacing only ephemeral
`snapshot_id` values for ANALYSIS. Ranking and later ordering differ. Raw traces
retain their actual generation IDs and are not normalized or rewritten.

## Minimal experiment

`flow_experiment.py` changes only the candidate preference hook. With multiple
host lookups, it preserves a directly fully matched leader; otherwise it gives
an unrepresented, fully matched, internally audited canonical direction an
opportunity. It recognizes only registered `canonical_intent / audited_rewrite`
traces bound to the missing parent host, with no derived/admission-only flag and
with `match_ratio == 1.0`. With zero or one host lookup, it delegates to the
previous behavior.

This does NOT say that fully matching a rewrite fully answers its parent.
Candidate text, identity, qualifications, query plan, public coverage, source
policy, novelty thresholds, and budget are not modified. The normal qualifier
and projector remain responsible for all those decisions. No project name or
answer literal is hard-coded. The hook restores itself on context exit.

This process-global monkeypatch is for a separate sequential experimental
process, not for a concurrent MCP server. Import alone does not activate it.

## Actual frozen case

| Condition | MCP | Application | Gateway | Selection | DTO tokens |
|---|---|---|---|---|---:|
| Baseline | absent | present | absent | present | 798 |
| Previous single-host packing | absent | present | absent | present | 798 |
| Flow ordering experiment | present | present | present | present | 796 |

All existing safety, source-identity, budget, estimated-token, and authorization
hard gates pass. `answer_supported` and `edit_ready` remain false. The flow
packet has three final sources, all from the canonical project-context module;
it does not create new answer authority from their proximity.

## Paired regression evidence

CI run `36712916587`, job `109878757662`, Python 3.12, uv 0.9.25,
`uv sync --frozen --extra dev`, `PYTHONHASHSEED=0`. Separate Python processes run
the SAME selected test modules, first without and then with the hook.

| Check | Passed | Failed | Errors | Skips |
|---|---:|---:|---:|---:|
| Flow guard + review-tool unit tests | 34 | 0 | 0 | 0 |
| Product regressions, baseline | 482 | 1 | 0 | 0 |
| Same product regressions, flow adapter | 483 | 0 | 0 | 0 |

The testcase ID sets are identical. The only status change is
`tests.docs.test_context_projection_boundaries::test_frozen_request_flow_prefers_project_context_module_witnesses`,
FAIL to PASS. This is the behavioral RED/GREEN; importing or collecting tests is
not counted as a RED. Review helper tests separately recorded 18 behavioral
failures against their stub, then 18 passes locally and in CI.

The workflow as a whole is deliberately FAILURE because it preserves the raw
baseline exit 1 alongside candidate exit 0. Neither a waiver nor an xfail hides
the original failure. The normal product still lacks this opt-in repair. The
full repository regression gate is NOT claimed green.

Downloaded artifact `11094737012` has verified SHA-256:
`12d1385c6527b53f3b045b5906414d4948b06910256202c967dd8b7fe99ac0fa`.
All 2,234 tracked source files in its archive match the tested local source,
including 1,200 product/eval files. A prior flow observation on commit 767faef
(run `36711421196`, artifact `11094318514`) reproduced the same four obligations.
Raw packets, JUnit, exact source archive, and exit codes are in the artifacts;
they are not committed to the repository.

## What this proves / does not prove

It proves an isolated repair of a known selection failure with no new failures
in these 483 tests. It does not prove cross-language generalization, language
profile benefit, neighbor expansion benefit, or model answer quality. The new
live pilot uses a single lookup and the original packing adapter, not this
multi-host flow intervention; those results must not be conflated.

Before promotion, replace the experimental global hook through the normal
maintainer-reviewed integration, run full regressions, and evaluate multi-host
ordering on unseen tasks. No product activation or merge was performed.
