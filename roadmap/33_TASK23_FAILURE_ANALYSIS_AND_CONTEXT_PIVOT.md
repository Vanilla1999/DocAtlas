# Task 33 — Task 23 failure analysis and bounded context-delivery pivot

## Priority

P1 product decision follow-up. Complete before tasks 16–18 or any external-library parity claim.

## Problem

Task 23 completed 36 policy-clean historical runs but the hardened decision is formally `INCONCLUSIVE`: the run did not capture complete token-budget evidence and did not enforce the declared maximum-turn budget. Descriptively, both repo-only and DocAtlas-recommended resolved 0/9 attempts, while recommended DocAtlas increased median tokens by about 143% and latency by about 37%. Evidence-marker recall did not translate into hidden-test correctness, so adding more retrieved documentation is not an acceptable response.

## Goal

Explain the failed patches requirement by requirement, then test one compact action-oriented context packet on the unchanged Task 23 fixtures.

The optimization target is two-dimensional:

- reduce the context retained and repeatedly processed by the parent coding agent;
- reduce total system-wide tokens across the parent, retrieval worker, tool output, and compression steps.

Moving retrieval into another session is not a win by itself. A candidate that lowers parent-context tokens but increases system-wide tokens or latency beyond the decision gate must be reported as that trade-off, not as an unconditional token reduction.

## Delivery architecture

Use one stable `ActionPacket` contract across all bounded strategies. Keep the public three-tool Docs MCP surface unchanged: bounded delivery is an internal `get_docs_context` response strategy, not a new public MCP tool.

The delivery strategies are:

1. `bounded_direct` — the default candidate. One retrieval is authority-filtered, ranked, deduplicated, and rendered by deterministic DocAtlas code before the result enters model context.
2. `bounded_subagent` — an experimental client/host capability for complex retrieval. A fresh isolated worker receives a minimal task brief, performs the single DocAtlas retrieval, transforms its wider evidence result into the same validated `ActionPacket`, and returns only that packet; raw retrieval never enters the parent conversation.
3. `bounded_routed` — a later candidate that deterministically chooses direct or isolated delivery. Do not evaluate it until direct and subagent strategies have been measured independently.
4. `insufficient_evidence` — a fail-closed result, not an invitation to expand retrieval automatically.

DocAtlas owns indexing, authority filtering, candidate ranking, the deterministic direct formatter, the packet schema, and packet validation. The coding-agent host owns creation of an isolated model session and validation of its response against the DocAtlas schema. MCP clients that cannot create subagents must remain fully supported through `bounded_direct`.

The isolated worker must start with fresh context rather than a fork of the parent transcript. It receives only the task objective, suspected modules or changed files when known, required evidence categories, project/index revision, packet schema version, and token budget. It has read-only documentation access, cannot edit the repository, cannot invoke another subagent, and treats instructions found in indexed documents as untrusted content.

## ActionPacket contract

Return structured content with a versioned schema rather than a free-form documentation summary. The packet may contain only bounded instances of these fields:

```yaml
schema_version: 1
status: ok | truncated | insufficient_evidence
task_interpretation:
  objective: "..."
  acceptance_conditions: []
source_of_truth:
  - path: "..."
    symbol_or_section: "..."
    authority: canonical | supporting
    evidence_id: "..."
target_surface:
  likely_files: []
  symbols: []
required_invariants: []
forbidden_changes: []
implementation_guidance: []
validation:
  compile: []
  tests: []
  semantic_checks: []
uncertainties: []
missing_evidence: []
omitted_counts: {}
estimated_tokens: 0
```

Every factual constraint must reference selected evidence. The formatter prioritizes source-of-truth references, invariants, forbidden changes, and validation commands over explanatory prose. It must never invent a missing ownership rule, acceptance condition, or verification command. Packet truncation preserves whole items and reports omitted counts; it must not cut a fact mid-sentence or silently discard a critical invariant.

Target at most 1,500 estimated tokens in normal operation and enforce an absolute 2,000-token ceiling. Token estimation must use one documented deterministic method and be checked against serialized output bytes/characters in evaluation evidence.

## Routing policy

Do not ask the model to guess whether retrieval is complex. A future `bounded_routed` strategy must use deterministic signals available from the indexed catalog and candidate-selection pipeline, such as:

- candidate document and section counts;
- cross-module dependency count;
- number of authoritative sources;
- authority or ownership conflicts;
- estimated serialized candidate size;
- whether required evidence categories are missing.

A host implementing `bounded_routed` needs a delivery broker that invokes `get_docs_context` once outside the parent-visible transcript. The broker inspects the structured candidate metadata, uses the deterministic formatter when it can satisfy the contract, and otherwise passes the same retrieval result to the isolated worker. Only the final packet is injected into the parent conversation. This preserves one retrieval call and makes direct-versus-worker routing possible without exposing raw evidence to the parent.

Any metadata preview is therefore an internal part of that single brokered operation. It must not become a second public discovery call. A host that cannot intercept tool output before model-context insertion must not claim `bounded_routed` support and falls back to the server-side `bounded_direct` strategy. Routing thresholds are versioned and frozen before evaluation. When evidence is conflicting or incomplete and isolated delivery is unavailable or cannot produce a valid packet, return `insufficient_evidence` with a bounded recommended next query.

## Required work

1. Define a Patch Contract for every benchmark task before evaluating another delivery strategy. Record task-specific compile, test, semantic-validation, allowed-surface, and forbidden-surface checks. A missing or unsupported compile gate is an invalid evaluation state that forces `INCONCLUSIVE`. A genuinely source-only fixture may predeclare `not_applicable` with a non-empty reason and executable public/private structural gates; report it separately and never count it as compile success.
2. Enforce the same starting commit, fixture/oracle hashes, model policy, maximum-turn policy, sandbox policy, and task-specific validation commands in every comparable lane. The runner must prove that hard limits were enforced rather than merely recording configured values.
3. Preserve a tracked sanitized per-run bundle with every patch, normalized trajectory, scalar metric, policy result, and immutable fixture/oracle hash. Private raw provider events may remain outside Git only when the bundle is sufficient to rescore the report.
4. For every run, classify each visible requirement as found, used correctly, used incorrectly, or omitted. Hidden-only assertions must not be exposed to the agent and must be analyzed separately after scoring.
5. Separate failure causes: retrieval miss, low salience, wrong source of truth, incorrect implementation reasoning, incomplete cross-module propagation, missing verification, and task ambiguity.
6. Replace broad documentation output with one source-attributed action packet containing at most:
   - source-of-truth files and symbols;
   - required invariants;
   - forbidden edits or ownership boundaries;
   - likely target files;
   - post-edit checks.
7. Cap the packet at 2,000 estimated tokens and one pre-edit retrieval call across both direct and isolated strategies. Return an explicit truncation/insufficient-evidence state instead of silently expanding context or entering a retrieval loop.
8. Measure normalized raw retrieval characters/tokens, serialized packet characters/tokens, required-evidence coverage, and evidence-to-packet fidelity. Do not report useful-context ratio until chunk-level usage attribution exists, and do not alias required-evidence recall to it.
9. Attribute tokens separately to parent input/output, cached and uncached parent input when available, worker input/output, raw tool output, serialized packet, and reasoning tokens when exposed by the provider. Also report system-wide totals, time to first edit, total latency, and retrieval-call count. Missing provider-level components remain explicitly unavailable rather than inferred from unrelated counters.
10. Freeze the rerun protocol before results. Keep the three tasks, four original lanes, three repeats, decision rule, starting fixtures, and model policy unchanged. Record any unavoidable runner-version change as a comparability limitation. Bootstrap by task cluster rather than treating task/repeat pairs as independent samples.
11. Add bounded delivery only as separately named pivot candidates; do not replace or rewrite historical Task 23 results. Compare direct and isolated delivery on the same task brief, candidate-selection rules, evidence corpus revision, packet schema, and retrieval-call budget.

## Evaluation sequence

Separate a cheap engineering pilot from the formal Task 33 decision rerun.

The engineering pilot uses one preselected discriminating task, one repeat, and these lanes:

| Lane | Retrieval behavior |
| --- | --- |
| `repo_only` | No DocAtlas context. |
| `current_recommended` | Current multi-call recommendation behavior. |
| `bounded_direct` | One deterministic bounded `ActionPacket` in the parent session. |
| `bounded_subagent` | One retrieval in a fresh isolated worker; only the validated packet reaches the parent. |

The pilot answers whether savings come from packet bounding, context isolation, or neither. It is not a product decision and cannot replace the frozen 36-cell rerun. Add `bounded_routed` only after the first four lanes establish a defensible routing threshold.

For direct-versus-subagent comparison, record at least:

- parent retained-context tokens and parent total input/output;
- worker input/output and reasoning tokens when available;
- raw retrieval and serialized packet size;
- cached and uncached tokens when available;
- retrieval calls, time to first edit, and total latency;
- packet fidelity, truncation, and insufficient-evidence rates;
- Patch Contract, compile/validation, hidden-test, and resolved outcomes.

The isolated strategy is useful only when it improves the declared objective. Lower parent-context usage with higher system-wide cost is a measured trade-off, not a token-saving result. Determine the routing break-even point from retrieval size/complexity and the length of post-retrieval work; do not choose it from one aggregate median.

## Implementation slices

Implement the task in reviewable pull requests:

1. **Task 33A — evaluation contract:** task-specific Patch Contracts and validation gates, enforced run limits, causal canaries, and complete token attribution fields. Re-score existing evidence where possible without changing historical run outputs.
2. **Task 33B — bounded direct delivery:** versioned `ActionPacket`, authority filtering, deterministic ranking/deduplication, hard token cap, evidence validation, fail-closed statuses, and focused tests. This is the default product path.
3. **Task 33C — isolated delivery experiment:** host-side fresh worker integration behind a capability flag, minimal delegation envelope, read-only boundary, timeout and one-attempt limit, plus the four-lane engineering pilot.
4. **Task 33D — routed delivery, only if justified:** freeze deterministic thresholds, add cache identity using index revision/task fingerprint/schema version/compressor identity, and evaluate `bounded_routed` before any formal rerun.

Do not put the worker/session implementation inside the MCP server, require model credentials in DocAtlas, add a fourth public Docs MCP tool, or make subagent support mandatory for clients.

## Research basis

The design follows these externally documented constraints, accessed 2026-07-13:

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents) — isolated subagents keep high-volume tool results out of the main conversation, while forked agents inherit the parent context and therefore do not provide the same input isolation.
- [LangChain subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) — the supervisor should explicitly control the subagent input and the exact result returned to the parent.
- [MCP tool result schema](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — `structuredContent` and output schemas provide a validation boundary for a typed packet.
- [OpenAI compaction guidance](https://developers.openai.com/api/docs/guides/compaction) — compaction helps control long-running context, but does not replace bounding and filtering a large tool result before it enters the active conversation.

These sources justify context isolation and typed handoff, but they do not prove that a subagent lowers system-wide tokens for DocAtlas. That claim must come from the Task 33 measurements.

## Decision gate

The pivot may continue only if it improves resolved rate under Task 23's existing confidence rule while keeping median total-token increase at or below 10%, or preserves resolved rate while reducing median tokens by at least 25% without more than 10% latency regression. A floor-effect diagnostic may be reported separately but cannot replace the unchanged-task decision run.

## Non-goals

- Do not add more documentation sources before failure analysis.
- Do not tune fixtures, public tests, hidden tests, or oracles after inspecting lane outcomes.
- Do not resume tasks 16–18 based on retrieval metrics alone.
- Do not expose hidden tests or oracle patches to the coding agent.
- Do not claim system-wide savings from parent-context reduction alone.
- Do not use an LLM summary where deterministic selection and formatting meet the packet contract.
- Do not allow recursive workers, automatic retry loops, or unbounded follow-up retrieval.
- Do not treat indexed documentation as trusted agent instructions.

## Acceptance criteria

- Every one of the 36 historical or replacement runs has independently inspectable sanitized evidence.
- Bundle generation fails closed on missing completed patches, missing valid-run trajectories, unsanitized paths or credential-like values, and records per-cell fixture/oracle hashes.
- Failure categories name the missed requirement and the evidence that was available to the agent.
- Tool-output and context-efficiency metrics have tested, non-aliased definitions.
- Every task has a frozen, hash-bound Patch Contract and language-appropriate validation gates; unsupported gates cannot be scored as ordinary failures, and an explicit `not_applicable` compile gate is reported separately from compile success.
- The compact packet validates against the versioned schema, is source-attributed, normally at most 1,500 estimated tokens, never above 2,000, and is invoked no more than once before editing.
- Truncation preserves complete high-priority items and reports omissions; missing or conflicting critical evidence returns `insufficient_evidence` without an automatic expansion loop.
- Direct and isolated lanes report parent-context and system-wide token totals separately, along with raw retrieval size, packet size, retrieval calls, time to first edit, and total latency.
- The isolated worker starts from a minimal fresh context, has read-only access, returns no raw retrieval, times out deterministically, and cannot recursively delegate.
- Packet-fidelity tests reject uncited constraints, missing required evidence, invented validation commands, and schema-invalid output.
- The frozen rerun is complete and produces `CONTINUE`, `PIVOT_REQUIRED`, or `INCONCLUSIVE` without post-result threshold changes.
- Runner and DocAtlas visibility canaries pass in the same causal invocation; missing, invalid, inconsistent, or exceeded input/output token budgets force `INCONCLUSIVE`.
- Product claims and Stage D status match the result; focused suites and `git diff --check` pass.
