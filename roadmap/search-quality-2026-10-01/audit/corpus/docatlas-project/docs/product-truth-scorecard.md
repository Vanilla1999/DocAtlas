# DocAtlas Product Truth scorecard

Protocol: `78521ab7dfae4f51cc55d4225054a1b38375a80be1d76d894ba74d9c851cc367`

```text
execution_status: CLOSED
outcome: PRODUCT_TRUTH_NOT_PROVEN
product_maturity: Beta
```

| Work item | Execution | Evidence | Decision |
|---|---|---|---|
| P2.1A | closed | `green_preregistered_protocol` | The causal protocol, schemas, budgets, conditions and decision thresholds are frozen before scored execution. |
| P2.1B | closed | `negative_zero_valid_tasks` | Gold controls reproduce for three tasks, but no task has a passing real-model oracle control. |
| P2.1C | closed | `blocked_task_pack_not_ready` | The repository has zero valid tasks and insufficient cross-repository structural capacity for the frozen 24-task gate. |
| P2.2A | closed | `green_harness_execution_blocked` | A/B/C/D isolation and randomization are implemented, but no executable run identities are emitted while eligibility is closed. |
| P2.2B | closed | `not_executed_by_preregistered_gate` | The canary was not authorized or run; this is not a model failure and cannot support a product claim. |
| P2.2C | closed | `not_executed_by_preregistered_gate` | The full pilot was not authorized or run; no comparative correctness, safety, cost or latency metric exists. |
| P2.3 | closed | `product_truth_not_proven` | Do not promote to Stable, do not authorize conditional expansion, and retain Beta until a valid preregistered experiment is executed. |

## Closure boundary

P2 work-item execution is closed, but no comparative coding experiment was
authorized or performed. Product Truth and product failure are both unproven.
Stable and P3 conditional expansion are not authorized. Reopening requires the
exact eligibility controls recorded in
`eval/product_truth_v1/results/product-decision.json`.
