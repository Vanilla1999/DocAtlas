# Failed setup attempts: incurred usage only

These are historical attempts under `/tmp/opencode/terra-step10-final`.
They are excluded from the final baseline/candidate quality comparison.

| Attempt | Recorded sessions | Input | Cache read | Input + cache | Output | Reasoning | Top-level calls | Nested calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| file-current: external-directory denied | 16 | 44147 | 0 | 44147 | 2215 | 38 | 30 | 0 |
| minimal-context: unprepared store, interrupted | 6 | 28455 | 26112 | 54567 | 821 | 0 | 14 | 8 |

All 30 baseline file-operation attempts failed before execution. Candidate
setup was invalid because stores were unprepared; zero top-level tool errors
does not prove retrieval succeeded. Incomplete attempts include only recorded
`step_finish` usage and can undercount a partially completed final step.
Nested calls and top-level calls are separate counts, not additive independent
product requests. Output and reasoning remain separate provider fields.

`failed-attempts.json` contains short per-session accounting and original artifact
hashes. Earlier `baseline.json`/`baseline.md` retain the detailed review of the
denied-access attempt; they are historical, not the final valid baseline.

Replacement run: `/tmp/opencode/terra-step10-prepared`. Its source-access fix and
explicit public preparation were reported by the main agent. No replacement
session has been inspected or polled by this evaluator. Final evaluation waits
for the explicit completion notification.

`account_sessions.py` is ready for offline extraction of final answers, tool
traces and reconciled step/session usage after completion. It does not grade
answers automatically: required facts and citations still require independent
review against frozen dev witnesses.
