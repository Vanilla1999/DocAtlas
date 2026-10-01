# Heading threshold diagnostic — 2026-10-01

Phase-separated follow-up: [HEADING_CALL_SITES.md](HEADING_CALL_SITES.md).
Admission-only and final-only controls both retain the baseline DTO; changing
all reached phases is necessary for the measured synthetic packet recovery.

`heading_hook.py` changes exactly one AST comparison in the actual qualifier:
`len(body_matched) >= 2` → `>= 1`. Everything else, including ratio, exact terms,
reference preparation, versions, hard policy and final admission stays original.
Shape mismatch refuses execution; aliases restore even after exceptions.
This is a diagnostic soft-threshold intervention, NOT a verified-declaration
policy and NOT authorization to use arbitrary metadata as identity evidence.

Ran B with this hook on the same original fixture roots as the unmodified B
controls. No query rewriting, gold inputs, source edits, model downloads or
product changes. The external driver records code/input hashes; all baseline
controls are from the same-root batch documented in STRUCTURE_T05_REPORT.md.

**68/68 executions successful and audit-clean**, maximum 800 tokens. All 34 DTOs
match their repeats. On 28 real questions, hooked and unhooked B DTOs are exactly
equal. On six synthetic mechanisms, cases 1/2/3/4/6 now contain the requested API
rule and condition, with case 6 preserving negation; case 5 was already sufficient.
Posthoc manual packet review therefore changes synthetic sufficiency **1/6 → 6/6**.
Case 4 still includes irrelevant gamma/startup prose in addition to the correct
alpha rule. This does not establish selectivity or general false-admission safety.
The five real unanswerable controls are unchanged, not newly validated abstentions.

The qualifier is invoked at all actual call sites reached by B, not only one
early gate. Counts are saved in each result's `heading_hook`; do not attribute
the result solely to an isolated admission call. Complete call-site separation
and independent evaluation remain open. No answers were generated or scored.

Focused harness/adjacent product regression: **169 passed**. The restoration
exception test is incorporated in the existing structure test inventory.
Additional hook controls retain unsafe/stale/foreign-project rejection and reject
missing exact identity with zero or one body match; structure suite: **9 passed**.
Full offline pytest failed: **5764 passed, 28 failed, 10 skipped**; unchanged-HEAD
comparison is complete: zero candidate-only failure node IDs, 28 shared failures.
See [FULL_OFFLINE_GATE.md](FULL_OFFLINE_GATE.md); acceptance remains blocked.

Artifacts: `/tmp/opencode/ablation-heading-{readme,four-docs,mechanisms}/`,
`/tmp/opencode/ablation-heading-summary.json`, `/tmp/opencode/ablation-heading-tests.log`.
These are inspected same-author development controls, not a holdout or product
acceptance. KEEP production unchanged; use this result to target declaration
binding and admission tests, not to disable exact identity or ratio safeguards.
