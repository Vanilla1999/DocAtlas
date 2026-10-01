# Heading admission versus final validation

Follow-up to HEADING_REMOVE_ONE.md, same controlled fixture roots and inputs.
Diagnostic instrumentation records three caller frames and evaluates the original
and changed pure qualifier on identical arguments. Counters describe local
qualification changes, not independently improved questions. Double evaluation
is diagnostic overhead: do not make latency claims from these runs.

68 instrumented B executions are audit-clean and reproduce the earlier hooked
DTOs exactly. Real panels: no local qualification changes. Synthetic panel:
10 local gains at each of three sites across two repeats (five cases):

1. `prepare → allowed_ids`: candidate admission;
2. `pack:189`: before budgeted DTO append;
3. `pack:212`: whole-packet final revalidation.

Then **24 executions** on the six synthetic mechanisms separate the phases:

| Intervention | Candidate effect | Visible DTO effect versus baseline |
|---|---|---|
| Admission only | Five target units recovered | None: `final_hard_gate_rejected` removes them |
| Final checks only | No new target units admitted | None: early admission still rejects them |
| All three sites | Five target units recovered | Previously reported sufficiency 1/6 → 6/6 |

All phase executions successful/audit-clean. Admission-only case 4 preserves
the old unrelated gamma snippet and omits the recovered target; final-only has
the same baseline pool. Neither isolated intervention supplies the requested
evidence. This demonstrates why changing just an early overlap test is insufficient
for this B harness. It does NOT prove the same result for the real P handler.

`phase` routing is process-local diagnostic call-chain matching, intentionally
not a product API or semantic policy. Unrecognized caller chains retain original
behavior for admission/final-only modes; unknown phases refuse execution.
Restoration and fail-closed safety tests remain green: **94 focused tests passed**.

Artifacts:
- `/tmp/opencode/ablation-heading-sites-v2-{readme,four-docs,mechanisms}/`
- `/tmp/opencode/ablation-heading-call-sites-v2.json`
- `/tmp/opencode/ablation-heading-phase-{admission,final}/`

The first single-frame trace could only identify the shared `qualify` wrapper;
it is retained but superseded by v2, which distinguishes all three caller chains.
The measurements are development controls; no holdout, generated answers,
hybrid activation or production gate changes. T07 call-site diagnosis is now
measured for B/heading; other components and P phase interventions remain open.
