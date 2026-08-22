# P1 Agent Truth closure scorecard

## Verdict

```text
P1 work-item execution: CLOSED
Autonomous Agent Truth: NOT PROVEN
Product maturity: Beta
Accepted production/API changes from P1: none
```

Closing P1 means that P1.1–P1.6 have each produced a reviewable evidence
outcome and product decision. It does **not** turn missing autonomous evidence
into a positive result.

| Item | Execution | Evidence outcome | Decision |
|---|---|---|---|
| P1.1 Installed-MCP harness | closed | installed transport/reviewer replay green; complete fresh same-model autonomous 11-task run absent | harness retained, autonomy unproven |
| P1.2 First-divergence atlas | closed | historical 0/11 classified as 8 selector-cardinality, 2 query-drift, 1 trajectory-order | diagnosis accepted, API freeze retained |
| P1.3 Contract v2 ablation | closed | working-path duplication and continuation token prevent 0 first divergences; conservative inference covers 8 counterfactually | no runtime change; inference deferred |
| P1.4 Paraphrase/proofability | closed | candidate discovery and final support measured separately; negative false support zero | provider-free robustness evidence accepted |
| P1.5 Mixed provenance | closed | protected claims assigned only to allowed roles under conflict | claim-local provenance accepted |
| P1.6 Evidence is data | closed | hostile document contents cannot control protected agent state | trust boundary accepted |

## Claim boundary

The following remain false:

```text
autonomous_agent_truth_proven
real_coding_outcome_improvement_proven
public_release_truth_closed
stable_claim_allowed
```

The absence of `OPENAI_API_KEY` and the intentionally deferred public release
mean the original positive P1 question cannot be answered affirmatively from
current evidence. The correct outcome is therefore a completed research phase
with a non-positive Agent Truth result.

## Product decision

No public MCP schema, retrieval stage, support rule, inference behavior or
continuation token is accepted by P1.

P2 may proceed only to methodology repair, positive controls and real coding
outcome measurement. P1 must not be cited as proof that DocAtlas already
improves autonomous coding-agent success.
