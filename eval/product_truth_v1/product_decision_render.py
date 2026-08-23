from __future__ import annotations

from typing import Any, Mapping


def render_analysis(report: Mapping[str, Any]) -> str:
    facts = report["measured_facts"]
    return f"""# P2.3 — Product Truth decision

Status: **P2 worklist closed; Product Truth not proven**.

## Decision

```text
P2 execution status              {report["execution_status"]}
Product Truth outcome            {report["outcome"]}
Comparative experiment executed  {str(report["claim_boundary"]["comparative_experiment_executed"]).lower()}
Product failure proven           {str(report["claim_boundary"]["product_failure_proven"]).lower()}
Stable decision                  {report["decision"]["stable_decision"]}
Conditional expansion            {report["decision"]["conditional_expansion_decision"]}
Product maturity                 {report["product_maturity"]}
```

Completing the P2 worklist is not the same claim as proving product benefit.
The preregistered eligibility gate stopped execution before any provider-backed
A/B/C/D comparison. Therefore the evidence supports neither a positive Product
Truth claim nor a conclusion that DocAtlas failed.

## Measured evidence

```text
positive-control tasks          {facts["positive_control_tasks"]}
gold reproducible               {facts["gold_reproducible_tasks"]}
oracle evidence present         {facts["oracle_evidence_tasks"]}
real-model oracle passed        {facts["real_model_oracle_passed_tasks"]}
task specs                      {facts["task_specs_total"]}
materialized fixtures           {facts["materialized_fixture_tasks"]}
structurally complete tasks     {facts["structurally_complete_tasks"]}
two-clean-gold tasks            {facts["two_clean_gold_tasks"]}
valid Product Truth tasks       {facts["valid_tasks"]} / {facts["required_valid_tasks"]}
canary planned / executed       {facts["canary_planned_runs"]} / {facts["canary_executed_runs"]}
full pilot planned / executed   {facts["full_pilot_planned_runs"]} / {facts["full_pilot_executed_runs"]}
comparative metrics available   {str(facts["comparative_metrics_available"]).lower()}
```

The exact blocker is a preregistered eligibility failure: there are not 24
valid tasks across three repositories with at least eight per repository, and
no task has a passing same-model real-model oracle control.

## Product action

- retain **Beta**;
- do not promote to Stable;
- do not authorize P3 conditional expansion;
- pause benchmark-driven retrieval/API expansion;
- accept no production or public-API changes from P2;
- preserve the four-condition harness and immutable protocol for a future
  eligible task pack.

## Reopening P2

P2 may be reopened only after all of the following are true:

1. at least 24 valid tasks exist across at least three repositories, with at
   least eight valid tasks in each;
2. every task passes its gold patch in two clean worktrees;
3. every task passes a real-model oracle-evidence control using the same model,
   tools and hard budgets as the comparative run;
4. hidden tests, gold patches and oracle evidence remain evaluator-only;
5. the protocol is preregistered before scored execution;
6. the 16-run canary passes infrastructure/scoring checks without being used as
   product evidence;
7. only then may the 576–720-run paired pilot begin.

## Claim boundary

This closure does not publish a release, close P0, prove Autonomous Agent
Truth, prove a product regression, or authorize Stable maturity. It records the
honest result of the preregistered P2 process: **Product Truth is not proven**.
"""


def render_scorecard(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        f"| {row['id']} | {row['execution_status']} | "
        f"`{row['evidence_status']}` | {row['decision']} |"
        for row in report["scorecard"]
    )
    return f"""# DocAtlas Product Truth scorecard

Protocol: `{report["protocol_sha256"]}`

```text
execution_status: {report["execution_status"]}
outcome: {report["outcome"]}
product_maturity: {report["product_maturity"]}
```

| Work item | Execution | Evidence | Decision |
|---|---|---|---|
{rows}

## Closure boundary

P2 work-item execution is closed, but no comparative coding experiment was
authorized or performed. Product Truth and product failure are both unproven.
Stable and P3 conditional expansion are not authorized. Reopening requires the
exact eligibility controls recorded in
`eval/product_truth_v1/results/product-decision.json`.
"""


__all__ = ["render_analysis", "render_scorecard"]
