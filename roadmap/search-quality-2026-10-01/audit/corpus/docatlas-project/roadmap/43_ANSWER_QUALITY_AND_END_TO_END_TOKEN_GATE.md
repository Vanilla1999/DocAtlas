# Task 43 — answer quality and end-to-end token decision gate

## Priority

P1 product-quality gate. Start after Tasks 39–42 establish truthful ranking, stable chunks, hybrid candidates, and minimal evidence selection.

## Problem

Retrieval quality, evidence selection, answer quality, and coding-task success are different layers:

- a relevant source can be ranked but omitted from the final packet;
- a good evidence bundle can be formatted into an incomplete answer;
- a concise answer can be correct but unusable for the coding task;
- a small MCP response can still lead to a large agent loop;
- a large token reduction can hide a correctness loss.

The current canonical projection correctly rejects ungrounded free-form answers and falls back to extractive evidence. That is safe, but safety alone does not prove that docs answers are clear or patch contexts are complete.

## Goal

Establish a layered, mostly provider-free quality gate and define the later local production-model experiment. A change is accepted only on the quality/token Pareto frontier.

## Layered evaluation model

### Layer 1 — retrieval

Owned by Tasks 39–41:

- expected-source Recall@K/MRR/nDCG;
- required facts present in candidates;
- forbidden source/version contamination;
- authority and exact-version correctness.

### Layer 2 — selected evidence

Owned by Task 42:

- mandatory evidence coverage;
- redundancy and diversity;
- selected evidence tokens;
- sufficiency/insufficiency decision.

### Layer 3 — canonical answer or patch context

Owned here:

- required facts present in the model-visible result;
- every claim bound to returned evidence IDs;
- cited source hash/span validity;
- no unsupported, wrong-version, or forbidden claim;
- concise answer structure and usable code/signature evidence;
- patch objective/targets/invariants/forbidden changes/checks completeness;
- uncertainty honesty;
- model-visible tokens.

### Layer 4 — coding-agent outcome

Deferred operator gate:

- patch correctness and hidden/public validation;
- model requests, repairs, tests, shell failures/retries;
- provider input/output/cached/reasoning usage;
- total latency and time to first edit.

Layer 4 requires a production adapter that proves Task 38 capabilities. It does not require GitHub Actions; it may run locally with user-owned credentials and a Docker/equivalent verified evaluator. Until then, the result remains `INCONCLUSIVE`, not failed and not a win.

## Documentation-answer quality

Keep answers source-grounded and compact. Implement deterministic answer assembly only where it improves usability without inventing prose:

- exact API/signature/config/error questions: return the exact relevant sentence/signature and minimal code span;
- conceptual questions: select a small ordered set of source sentences that jointly cover required facts;
- version/migration questions: place exact version binding and incompatibility caveats next to the claim;
- code-example questions: include the smallest complete example that contains required symbols/imports;
- multi-document questions: one concise fact per distinct source, with explicit evidence IDs.

The retrieval layer's arbitrary `message` must never become a successful answer. A synthesized answer is accepted only when every normalized claim can be mapped to source spans. If deterministic claim mapping cannot prove support, return extractive evidence or `insufficient_evidence`.

Do not add a second LLM call to make the answer sound nicer. The consuming coding model can reason from the compact evidence; DocAtlas's responsibility is precise source selection and a trustworthy contract.

## Patch-context quality

For every protected fixture evaluate:

- objective fidelity to the original task;
- required evidence and target path retention;
- invariant coverage;
- forbidden-change/ownership coverage;
- validation/check coverage;
- uncertainty/missing-evidence honesty;
- citation precision for every emitted claim;
- absence of invented commands, targets, symbols, policies, or acceptance conditions.

Empty optional lists are cheaper than generic filler. However, a missing required invariant/check is a quality failure, not a token saving.

## Provider-free answer dataset

Extend the Task 39 cases with expected model-visible behavior:

- required answer facts or exact spans;
- acceptable evidence IDs/sources;
- forbidden claims and versions;
- snippet requirements;
- expected `docs_answer`, `patch_context`, or `insufficient_evidence`;
- required patch fields and public validation commands where source-backed;
- maximum visible token budget.

Use exact/normalized fact matching for deterministic gates. Add a small checked-in human-review rubric for qualities that cannot be safely reduced to substring tests:

- directness;
- ambiguity;
- citation usefulness;
- whether code snippets are complete enough to use;
- whether omissions are clearly disclosed.

Human review is a named artifact, not an automated score and not a substitute for executable correctness gates.

## Pareto decision rule

Freeze before reading Task 43 results.

A candidate configuration may become default only if all are true:

1. protected required-fact pass rate does not decrease;
2. protected forbidden-source/version/unsupported-claim violations remain zero;
3. holdout Recall@5 and answer-fact coverage do not regress beyond the Task 39 tolerance;
4. citation validity remains 100% on successful canonical fixtures;
5. `insufficient_evidence` false-success rate does not increase;
6. median model-visible tokens do not increase for either docs or patch results;
7. p95 local retrieval+projection latency stays within the predeclared bound.

Prefer the configuration with lower visible tokens when quality is tied. Prefer higher quality at the same token ceiling. Reject lower quality even when tokens are substantially lower.

Do not combine docs and patch averages: report each result kind and taxonomy class separately so easy short answers cannot hide incomplete cross-module packets.

## Later local production-model gate

After the provider-free gate and a real Task 38 adapter exist, run locally:

```text
one frozen discriminating task
× repo_only_strict_offline and docatlas_bounded_direct
× three repeats
```

Only add `docatlas_tool_required_once` after it is byte/semantically identical to bounded direct and passes a provider-free smoke. Keep frozen:

- task/fixture/oracle/hidden-test identities;
- model snapshot and reasoning policy;
- one retrieval and packet hash/budget;
- 12-request, 7,000-input, one-repair, two-test profile;
- evaluator boundary;
- required evidence/targets;
- correctness and token decision rule.

Use the existing Task 33 product rule: correctness parity plus at least 25% median total-token reduction without more than 10% median latency regression, or the separately frozen resolved-rate improvement rule. Provider usage must come from provider records; deterministic bytes/4 estimates remain separate.

Because the user cannot currently use GitHub Actions, provide a documented local command, preflight, capability report, sanitized artifact bundle, and independent validator. Missing credentials/canaries/usage produce `INCONCLUSIVE`.

## Token accounting

Report separately:

- static tool-catalog bytes/estimate;
- raw retrieval bytes/tokens estimate;
- internal candidate and selected evidence tokens;
- canonical projection bytes/estimate;
- provider input/output/cached/reasoning usage when available;
- retained history per request;
- shell/tool output retained/omitted bytes;
- system-wide total tokens;
- indexing/embedding cost separately from per-request generation cost.

Do not say “the index saved tokens” when only internal retrieval bytes fell. The index saves model tokens only when the selected/canonical/provider-visible context or subsequent agent loop measurably shrinks.

## Acceptance gate

- The provider-free layered report is deterministic and bound to dataset/index/config/code hashes.
- Retrieval, selected evidence, projection, and later agent metrics are not aliased.
- Docs and patch quality gates pass independently.
- Every successful claim has valid evidence; every unsupported case fails closed.
- The Pareto decision rule is machine-enforced.
- Human-review rubric and a bounded representative review artifact are checked in.
- Public MCP and Task 36 token ceilings do not increase.
- Full provider-free suite, projection/adversarial validators, `compileall`, and `git diff --check` pass.
- Product documentation states that real provider savings remain unproven until the local production-model gate is complete.

## Non-goals

- Do not add an answer-writing model call.
- Do not use an LLM judge as the only quality gate.
- Do not run or tune against Task 33 hidden tests before freezing the protocol.
- Do not pool fake-adapter token estimates with provider usage.
- Do not require GitHub Actions for the local gate.
- Do not declare Context7 parity from DocAtlas-only retrieval metrics.

## Expected product outcome

If Tasks 39–43 pass, DocAtlas should spend more local indexing/retrieval computation once so that each coding-model request receives less, more authoritative evidence. The intended result is not merely a smaller response; it is fewer distractors, fewer repository-search/tool retries, more precise citations, and equal or better task correctness under a lower cumulative token budget.
