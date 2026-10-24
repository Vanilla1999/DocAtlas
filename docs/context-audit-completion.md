# Context-token audit: completion and remaining evidence

This is the scope ledger for the owner's attached token audit. A code change,
a replay measurement and a real strong-agent acceptance are distinct claims.
No heuristics, new trained weights or V40 oracle rules are introduced.

| Audit item | Implemented boundary | Remaining evidence |
| --- | --- | --- |
| Language before first search | Consistent skill/tool guidance and ModelContextSession preflight guard | Autonomous target agent must use the installed skill/adapter |
| Concrete question separate from paths/instructions | Distinct immutable arguments and skill guidance | A server cannot infer arbitrary user intent from text |
| Normal selection incorrectly marked truncated | Actual delivery status separated from selection counts and semantic assessment | No claim of semantic completeness |
| Costly machine metadata in prompts | Explicit model view plus private exact packet and validated citation resolver | External clients must exclude _meta from their prompts |
| Repeated context/history | Managed session retains each exact same-snapshot record once; emits a fresh bounded block | Caller must replace evidence block, not replay both versions |
| Large tool catalog | Host tools() exposes real definitions for the current phase; lifecycle requires explicit need | Not automatic in unrelated clients |
| Wire v1/v2 compatibility | v1 is default; adaptive-v2 is an explicit host setting | Clients opting in must accept both |
| 800 versus 12000 budget mismatch | GroundedMCPSession accepts an explicit evidence_budget, default 12000; 800 remains opt-in | Whole provider prompt has additional costs |
| Empty heading consumes a rank slot | Opt-in structural markdown-owner-v1 keeps exact acquired headings with descendants | Policy quality is measured separately; no default change |
| Fixed top-5 unnecessary context | Predeclared k=1,2,3,5 actual MCP policy comparison | Never accept smaller k solely because output is shorter |
| Exact Q02 missing session lease | Full rank trace and independent source controls exist | Original Q02 documents, question, scope/snapshot and raw trace are absent |
| Provider bill and final answer correctness | No substitute measurement | Same strong model and deployed client A/B still required |

## Additional review fixes

Managed sessions serialize actual client operations. Concurrent language requests
share one real preflight rather than racing the request/event limits. Transport
failures, cancellations and invalid freshness responses drop active context and
citations while keeping private audit attempts. A delayed real reply after
invalidate() is discarded, not allowed to resurrect sources. model_input() and
resolve() cannot expose context during a pending recheck. No error is called a
successful no-answer decision.

These paths are exercised by installed stdio/SQLite integration, including a
real closed connection and a real MCP response paused only at transport delivery.
Neither the server, source selection nor validator is mocked. Existing V40 gold
and questions are unchanged. Normal post-preparation reads remain read-only.

## Running the predeclared policy study

The existing context-delivery workflow runs all diagnostic arms on manual
workflow_dispatch, or when a PR has the explicit run-selection-study label at
synchronize time. Remove the label after the requested experiment to avoid
repeating expensive arms on unrelated edits. Diagnostic job success means the
measurement completed. Only quality_gate_passed and the independent source-span
scores determine quality acceptance. Results must include failures.

The normal default remains legacy top-5 until a separately accepted change.
Real source preservation is not proof that an answering LLM uses it correctly.
Do not mark Q02, all-language answer quality, deployment or provider-cache savings
as fixed from this suite. Main and the owner's perf branch are not changed here.
