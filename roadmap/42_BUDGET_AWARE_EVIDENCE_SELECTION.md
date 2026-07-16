# Task 42 — budget-aware minimal evidence selection

## Priority

P1 direct model-token reduction without quality loss. Start after Task 41 produces a reproducible candidate pool.

## Problem

Top-K followed by a token cutoff is not the same as selecting the most useful evidence under a budget. It can spend the budget on:

- several near-duplicate children from one source;
- a long high-ranked section that covers only one query term;
- an exact match from the wrong version;
- navigation metadata without authoritative facts;
- adjacent expansion that duplicates the winning span;
- supporting evidence while omitting a required path or invariant.

Tasks 36 and 37 bound output and internal stages, but the final selector should explicitly optimize quality per visible token and fail closed when the budget cannot retain all critical evidence.

## Goal

Select the smallest complete evidence set that supports the requested result:

```text
ranked candidates
→ hard eligibility filters
→ exact/near-duplicate collapse
→ required-evidence reservation
→ marginal fact/authority/novelty utility per token
→ sufficiency check
→ canonical projection
```

No model call participates in selection.

## Hard eligibility before optimization

Reject or quarantine before scoring:

- wrong or unknown version when exact version is required;
- forbidden/rejected source identity;
- stale project documentation when confirmation is required;
- untrusted content attempting to act as agent policy;
- source outside project/module scope;
- generated/changelog/research artifacts when the query requires canonical policy;
- invalid source hash/span/parent identity;
- navigation-only evidence for a factual answer;
- conflicts that cannot be resolved by explicit authority precedence.

An ineligible chunk cannot buy its way back through semantic similarity.

## Deduplication and diversity

1. Exact dedupe by stable span/content hash.
2. Collapse overlap-only children from the same parent.
3. Detect bounded near-duplicates using deterministic shingles/Jaccard or equivalent; do not add an embedding call solely for dedupe.
4. Preserve the highest-authority/exact-version representative.
5. Limit repeated evidence from one source unless multiple distinct required facts are proven only there.
6. Record every omitted stable ID and reason in host diagnostics, not model-visible prose.

## Required-evidence reservation

Before optional ranking, reserve complete items for:

- host-owned `required_evidence_paths` and `required_target_paths`;
- exact identifiers explicitly present in the task;
- canonical project policy/ownership documents;
- exact dependency version evidence;
- each independent required fact/acceptance condition when declared by a public task contract;
- conflicts/uncertainties that must be disclosed.

If the reserved set alone exceeds the hard projection budget, return `insufficient_evidence` with a bounded reason. Never silently prune a required invariant or source to produce a successful-looking packet.

## Utility model

Use transparent named features rather than one opaque score. A candidate's marginal utility may include:

- corrected retrieval/fusion relevance;
- exact symbol/path/phrase coverage;
- required-fact or requirement coverage;
- source authority and scope;
- exact-version confidence;
- usable code/signature/config snippet;
- novelty relative to already selected evidence;
- target/module coverage for patch tasks;
- token cost and expansion cost;
- risk penalties for stale, low-trust, generic, or ambiguous evidence.

A practical deterministic selector may use greedy marginal utility per token with a final repair pass for mandatory coverage. It must be tested against counterexamples where naive greedy selection fails. If a small bounded dynamic-programming/knapsack step is clearer and deterministic, prefer correctness over cleverness.

Do not infer an undeclared “required fact” from hidden tests. Query-derived concepts and public task contracts are allowed; evaluator-only fields are not.

## Result-specific policies

### Documentation answer

Target:

- one primary source span;
- zero to two non-duplicate supporting spans only when they add a distinct fact;
- no more than three sources;
- normal goal 400–650 estimated visible tokens;
- hard ceiling 800 estimated visible tokens.

An exact signature/config/error answer may need one span. A conceptual or multi-document answer may need two or three. Source count is a ceiling, not a quota.

### Patch context

Target:

- every source required by an invariant/forbidden change/check;
- exact likely targets where supported;
- distinct sources only when they contribute independent constraints;
- normal goal 900–1,200 estimated visible tokens;
- hard ceiling 1,500, with the existing 2,000 recovery/absolute contract unchanged where already defined.

The selector allocates evidence first. The formatter then emits claims with exact evidence IDs. Do not spend tokens on empty fields, repeated paths, or generic implementation advice.

## Sufficiency and stopping

After each selected item, recompute covered requirements and unresolved conflicts. Stop when:

- every mandatory evidence requirement is covered;
- no unresolved authority/version conflict remains;
- answer/packet minimum fields can be cited;
- adding another candidate has no distinct supported fact above a frozen marginal threshold.

Fail closed when:

- an authoritative source is missing;
- only navigation metadata is available;
- exact-version evidence cannot be proven;
- required evidence cannot fit as whole items;
- critical sources conflict without precedence;
- a required target/check would be invented.

There is no automatic widening loop. The bounded recommended next action may request a narrower question, explicit source, version confirmation, or local `prepare_docs` step.

## Ordering for model use

Keep the structured contract, but order within fields deterministically:

1. objective/task state;
2. primary canonical source and exact targets;
3. required invariants/forbidden changes with adjacent evidence IDs;
4. implementation guidance only when cited;
5. checks;
6. uncertainties/omissions.

Do not rely on ordering alone to overcome long-context positional bias. The main defense is a small packet with claims next to citations.

## Cache

Cache only after selection is deterministic. Key by:

- normalized query/task fingerprint;
- project/dependency/index revision;
- retrieval config and candidate trace hash;
- selector schema/config;
- projection schema and token budget.

Cache stores stable IDs and hashes, not an unchecked copy of stale source text. Revalidate active index/source hashes on read.

## Metrics

Add:

- candidate-to-selected ratio;
- exact and near-duplicate omission counts;
- selected sources/parents/children;
- mandatory coverage before/after fitting;
- distinct required facts covered;
- redundant visible-token ratio;
- selected evidence tokens;
- canonical output tokens;
- facts per 1,000 visible tokens;
- insufficient-evidence rate by reason;
- cache hit/miss/invalidation counts;
- selector latency.

## Acceptance gate

- Every successful result covers all declared mandatory evidence and has valid citations.
- No wrong-version, forbidden-source, or overlap-only duplicate reaches model-visible output in protected cases.
- Existing protected required-fact pass rate remains unchanged or improves.
- Median model-visible tokens decrease from the Task 41 baseline for docs and patch fixtures separately, or quality improves at the same token count.
- Holdout Recall is evaluated before selection; answer/packet sufficiency is evaluated after selection. Neither may be hidden by the other.
- `insufficient_evidence` is returned when mandatory whole items cannot fit.
- Selection is byte-for-byte deterministic for one query/index/config identity.
- Task 36 ceilings and Task 37 stage budgets remain enforced.
- Full provider-free, adversarial fitting, cache invalidation, `compileall`, and `git diff --check` gates pass.

## Non-goals

- Do not summarize evidence with an LLM.
- Do not increase candidate or visible budgets to avoid insufficiency.
- Do not add recursive retrieval.
- Do not treat source diversity as more important than complete required evidence.
- Do not claim end-to-end provider savings until Task 43's production-host evidence gate.

## Handoff to the next task

Task 43 evaluates whether the selected evidence produces more complete, correctly cited answers and patch contracts at the reduced visible-token budget.
